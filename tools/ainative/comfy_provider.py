"""Trusted local configuration, durable ComfyUI HTTP adapter (stdlib only).

ComfyUI has no global idempotency guarantee. Our SQLite intent prevents a second
POST from this storage; unknown receipts are reconciled from queue/history only.
"""

import base64
import hashlib
import ipaddress
import json
import os
import re
import sqlite3
import struct
import urllib.error
import urllib.parse
import urllib.request
import uuid
from contextlib import contextmanager
from pathlib import Path

from extensions import canonical, require, validate_invocation

KINDS = ("text_to_image", "image_to_image", "image_to_mesh", "text_to_mesh")
VERSION = "1"
DEFAULTS = dict(
    prompt="",
    seed=0,
    width=512,
    height=512,
    steps=1,
    denoise=0.65,
    mesh_steps=20,
    mesh_resolution=512,
    octree_resolution=128,
    mesh_algorithm="surface net",
    mesh_threshold=0.6,
)


def register(registry):
    props = {
        k: {"type": "string" if isinstance(v, str) else "integer" if type(v) is int else "number"}
        for k, v in DEFAULTS.items()
    }
    for kind in KINDS:
        registry.register(
            dict(
                id=kind,
                version=VERSION,
                inputs={"source": {"types": ["image"], "required": True}} if kind.startswith("image_") else {},
                outputs={"result": {"types": ["mesh" if kind.endswith("mesh") else "image"], "required": True}},
                context_types=["text", "image"],
                parameters={"properties": props},
                capabilities=[kind],
            )
        )


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def filename(value):
    require(
        isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.-]+", value) and value not in (".", ".."),
        "unsafe filename",
    )
    return value


def checkpoint_name(value):
    require(
        isinstance(value, str)
        and value
        and not value.startswith(("/", "\\"))
        and ".." not in value.replace("\\", "/").split("/")
        and not any(ord(c) < 32 for c in value),
        "invalid checkpoint name",
    )
    return value


def validate_embedded_glb(data):
    require(
        len(data) >= 20 and data[:4] == b"glTF" and struct.unpack_from("<II", data, 4) == (2, len(data)),
        "invalid GLB header",
    )
    size, kind = struct.unpack_from("<II", data, 12)
    require(kind == 0x4E4F534A and 20 + size <= len(data), "invalid GLB JSON chunk")
    document = json.loads(data[20 : 20 + size])

    def visit(value):
        if isinstance(value, dict):
            if "uri" in value:
                require(
                    isinstance(value["uri"], str) and value["uri"].startswith("data:"),
                    "external GLB dependency refused",
                )
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(document)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError("backend redirect refused")


class ComfyProvider:
    def __init__(self, config):
        self.config = json.loads(canonical(config))
        require(set(config) == {"endpoint", "storage", "checkpoints", "backend_revision"}, "invalid local config")
        url = urllib.parse.urlsplit(config["endpoint"])
        require(
            url.scheme in ("http", "https")
            and url.hostname
            and not url.username
            and not url.password
            and not url.query
            and not url.fragment
            and url.path in ("", "/"),
            "invalid trusted endpoint",
        )
        self.endpoint = config["endpoint"].rstrip("/")
        require(set(config["checkpoints"]) == {"image", "mesh"}, "two checkpoints required")
        for model in config["checkpoints"].values():
            require(set(model) == {"name", "sha256"}, "checkpoint identity required")
            # GUI discovery cannot verify a remote file hash. Missing selections
            # and unknown hashes are explicit, never substituted with fake hashes.
            require(
                model["name"] == "" and model["sha256"] is None or checkpoint_name(model["name"]),
                "checkpoint name required",
            )
            require(
                model["sha256"] is None
                or isinstance(model["sha256"], str)
                and re.fullmatch("[a-f0-9]{64}", model["sha256"]),
                "checkpoint sha256 required",
            )
        require(bool(config["backend_revision"]), "backend revision required")
        if any(model["sha256"] is None for model in config["checkpoints"].values()):
            require(
                re.fullmatch(r".*\|unverified-weights;run=[a-f0-9]{32}", config["backend_revision"]),
                "unknown checkpoint hashes require run-scoped identity",
            )
        storage = Path(config["storage"]).expanduser().resolve()
        storage.mkdir(parents=True, exist_ok=True)
        self.database = storage / "comfy-jobs.sqlite"
        with self.db() as db:
            db.execute("CREATE TABLE IF NOT EXISTS jobs (key TEXT PRIMARY KEY, body TEXT NOT NULL)")
        self.fingerprint = digest([config, hashlib.sha256(Path(__file__).read_bytes()).hexdigest()])
        try:
            local = ipaddress.ip_address(url.hostname).is_loopback
        except ValueError:
            local = url.hostname == "localhost"
        handlers = [urllib.request.ProxyHandler({})] if local else []
        self.http = urllib.request.build_opener(*handlers, NoRedirect())

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.database, timeout=20)
        db.execute("PRAGMA synchronous=FULL")
        try:
            with db:
                yield db
        finally:
            db.close()

    def describe(self):
        return dict(
            id="comfy",
            version=VERSION,
            model="SD-Turbo + Hunyuan3D-2mini",
            model_version=self.fingerprint,
            capabilities=list(KINDS),
            context_types=["text", "image"],
            available=True,
        )

    def call(self, route, data=None, raw=False, content_type="application/json"):
        body = data if isinstance(data, bytes) else canonical(data).encode() if data is not None else None
        req = urllib.request.Request(self.endpoint + route, data=body, headers={"Content-Type": content_type})
        with self.http.open(req, timeout=60) as response:
            payload = response.read(128 * 1024 * 1024 + 1)
        require(len(payload) <= 128 * 1024 * 1024, "backend response too large")
        return payload if raw else json.loads(payload)

    def read(self, key):
        require(re.fullmatch("[a-f0-9]{64}", key), "invalid job key")
        with self.db() as db:
            row = db.execute("SELECT body FROM jobs WHERE key=?", (key,)).fetchone()
        require(row is not None, "unknown local job")
        return json.loads(row[0])

    def write(self, key, record):
        # Serialize updates after network I/O. A late worker cannot replace a
        # terminal receipt or erase a receipt learned by another worker.
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            current = json.loads(db.execute("SELECT body FROM jobs WHERE key=?", (key,)).fetchone()[0])
            if "terminal" in current:
                return current
            if current.get("remote"):
                require(record.get("remote") in (None, current["remote"]), "conflicting remote receipt")
                record = dict(record, remote=current["remote"])
            current.update(record)
            db.execute("UPDATE jobs SET body=? WHERE key=?", (canonical(current), key))
            return current

    def owns(self, prompt, key, record):
        return (
            isinstance(prompt, list)
            and len(prompt) > 3
            and prompt[1] == record["remote"]
            and isinstance(prompt[3], dict)
            and prompt[3].get("ainative_key") == key
            and canonical(prompt[2]) == canonical(record.get("graph"))
        )

    def snapshot(self, key, state, outputs=None, error=None):
        return dict(job_id=key, state=state, outputs=outputs or {}, error=error)

    def upload(self, asset):
        p = asset["payload"]
        data = base64.b64decode(p["content_base64"], validate=True)
        require(hashlib.sha256(data).hexdigest() == p["content_sha256"], "input digest")
        ext = p["extension"].lower()
        require(ext in (".png", ".jpg", ".jpeg"), "image required")
        name = "ainative-" + uuid.uuid4().hex + ext
        boundary = "ainative" + uuid.uuid4().hex
        body = (
            f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="{name}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode()
            + data
            + f"\r\n--{boundary}--\r\n".encode()
        )
        result = self.call("/upload/image", body, content_type="multipart/form-data; boundary=" + boundary)
        require(result.get("name") == name and not result.get("subfolder"), "unexpected upload location")
        return name

    def build(self, request, manifest, key):
        p = dict(DEFAULTS, **request["parameters"])
        kind = request["node"]
        require(
            0 <= p["seed"] < 2**64 and p["width"] in range(64, 1025, 8) and p["height"] in range(64, 1025, 8),
            "invalid dimensions/seed",
        )
        require(
            1 <= p["steps"] <= 8 and 1 <= p["mesh_steps"] <= 50 and 0 < p["denoise"] < 1, "invalid sampling parameters"
        )
        require(16 <= p["octree_resolution"] <= 256 and 1 <= p["mesh_resolution"] <= 4096, "invalid mesh resolution")
        require(
            p["mesh_algorithm"] in ("surface net", "basic") and -1 <= p["mesh_threshold"] <= 1,
            "invalid mesh extraction",
        )
        refs = list(request["inputs"].values()) + [c["artifact"] for c in request["context"] if "artifact" in c]
        require(len(refs) <= 1, "unsupported_multiple_image_constraints")
        for c in request["context"]:
            require(c["scope"] == "node" and c["role"] in ("reference", "instruction"), "unsupported_context_semantics")
        prompt = "\n".join([p["prompt"]] + [c["text"] for c in request["context"] if "text" in c]).strip()
        require(bool(prompt) or kind == "image_to_mesh", "prompt required")
        g = {}

        def add(name, cls, **inputs):
            g[name] = {"class_type": cls, "inputs": inputs}
            return [name, 0]

        image = None
        if refs:
            asset = next(
                a for a in manifest["artifacts"] if a["id"] == refs[0]["id"] and a["revision"] == refs[0]["revision"]
            )
            image = add("input", "LoadImage", image=self.upload(asset))
        edit = kind != "image_to_mesh" or bool(prompt)
        if edit:
            checkpoint_name(self.config["checkpoints"]["image"]["name"])
            ck = add("image_model", "CheckpointLoaderSimple", ckpt_name=self.config["checkpoints"]["image"]["name"])
            pos = add("positive", "CLIPTextEncode", text=prompt, clip=["image_model", 1])
            neg = add("negative", "CLIPTextEncode", text="", clip=["image_model", 1])
            if image:
                image = add(
                    "resize",
                    "ImageScale",
                    image=image,
                    upscale_method="lanczos",
                    width=p["width"],
                    height=p["height"],
                    crop="disabled",
                )
                latent = add("latent", "VAEEncode", pixels=image, vae=["image_model", 2])
            else:
                latent = add("latent", "EmptyLatentImage", width=p["width"], height=p["height"], batch_size=1)
            sample = add(
                "sample",
                "KSampler",
                model=ck,
                positive=pos,
                negative=neg,
                latent_image=latent,
                seed=p["seed"],
                steps=p["steps"],
                cfg=1.0,
                sampler_name="euler",
                scheduler="normal",
                denoise=p["denoise"] if refs else 1.0,
            )
            image = add("decode", "VAEDecode", samples=sample, vae=["image_model", 2])
        if kind.endswith("mesh"):
            checkpoint_name(self.config["checkpoints"]["mesh"]["name"])
            ck = add("mesh_model", "ImageOnlyCheckpointLoader", ckpt_name=self.config["checkpoints"]["mesh"]["name"])
            vision = add("vision", "CLIPVisionEncode", clip_vision=["mesh_model", 1], image=image, crop="none")
            cond = add("conditioning", "Hunyuan3Dv2Conditioning", clip_vision_output=vision)
            latent = add("mesh_latent", "EmptyLatentHunyuan3Dv2", resolution=p["mesh_resolution"], batch_size=1)
            sample = add(
                "mesh_sample",
                "KSampler",
                model=ck,
                positive=cond,
                negative=["conditioning", 1],
                latent_image=latent,
                seed=p["seed"],
                steps=p["mesh_steps"],
                cfg=5.0,
                sampler_name="euler",
                scheduler="simple",
                denoise=1.0,
            )
            voxel = add(
                "voxel",
                "VAEDecodeHunyuan3D",
                samples=sample,
                vae=["mesh_model", 2],
                num_chunks=8000,
                octree_resolution=p["octree_resolution"],
            )
            mesh = add("mesh", "VoxelToMesh", voxel=voxel, algorithm=p["mesh_algorithm"], threshold=p["mesh_threshold"])
            mesh = add("normals", "MeshSmoothNormals", mesh=mesh, crease_angle=180.0)
            add("output", "SaveGLB", mesh=mesh, filename_prefix="ainative/" + key)
        else:
            add("output", "SaveImage", images=image, filename_prefix="ainative/" + key)
        return g, dict(
            parameters=p,
            effective_prompt=prompt,
            image_usage="img2img_initial_latent" if refs and edit else "hunyuan_vision" if refs else "none",
            text_usage="image_diffusion" if edit else "none",
        )

    def submit(self, request, manifest, idempotency_key):
        from extensions import NodeRegistry

        registry = NodeRegistry()
        register(registry)
        validate_invocation(registry, request, manifest, self.describe())
        key = idempotency_key
        require(re.fullmatch("[a-f0-9]{64}", key), "invalid idempotency key")
        record = dict(request=request, manifest=manifest, fingerprint=self.fingerprint, remote=None)
        with self.db() as db:
            inserted = db.execute("INSERT OR IGNORE INTO jobs VALUES (?,?)", (key, canonical(record))).rowcount
        if not inserted:
            existing = self.read(key)
            require(
                canonical(existing["request"]) == canonical(request)
                and canonical(existing["manifest"]) == canonical(manifest)
                and existing["fingerprint"] == self.fingerprint,
                "idempotency conflict",
            )
            return self.lookup(key)
        try:
            graph, usage = self.build(request, manifest, key)
        except ValueError as exc:
            record["terminal"] = self.snapshot(key, "failed", error=str(exc))
            record = self.write(key, record)
            return record["terminal"]
        record.update(graph=graph, usage=usage)
        record = self.write(key, record)  # intent is durable BEFORE external POST
        if "terminal" in record:
            return record["terminal"]
        try:
            result = self.call("/prompt", dict(prompt=graph, client_id="ainative", extra_data={"ainative_key": key}))
        except urllib.error.HTTPError as exc:
            if exc.code != 400:
                raise
            record["terminal"] = self.snapshot(key, "failed", error="comfy_prompt_rejected")
            record = self.write(key, record)
            return record["terminal"]
        require(isinstance(result.get("prompt_id"), str), "missing receipt")
        record["remote"] = result["prompt_id"]
        record = self.write(key, record)
        return record.get("terminal") or self.snapshot(key, "queued")

    def lookup(self, key):
        record = self.read(key)
        if "terminal" in record:
            return record["terminal"]
        if record["remote"]:
            return self.poll(key)
        queue = self.call("/queue")
        history = self.call("/history")
        prompts = (
            list(queue.get("queue_running", []))
            + list(queue.get("queue_pending", []))
            + [h["prompt"] for h in history.values() if "prompt" in h]
        )
        matches = {
            p[1]
            for p in prompts
            if len(p) > 3 and p[3].get("ainative_key") == key and canonical(p[2]) == canonical(record.get("graph"))
        }
        require(len(matches) <= 1, "ambiguous remote submission")
        if not matches:
            return None
        record["remote"] = matches.pop()
        self.write(key, record)
        return self.poll(key)

    def poll(self, key):
        record = self.read(key)
        if "terminal" in record:
            return record["terminal"]
        remote = record["remote"]
        require(remote is not None, "unknown receipt")
        history = self.call("/history/" + urllib.parse.quote(remote, safe=""))
        if remote in history:
            h = history[remote]
            require(self.owns(h.get("prompt"), key, record), "foreign history receipt")
            status = h.get("status", {})
            if status.get("status_str") == "error":
                record["terminal"] = self.snapshot(key, "failed", error="comfy_execution_failed")
            elif status.get("completed"):
                output = h.get("outputs", {}).get("output", {})
                entries = [
                    v
                    for values in output.values()
                    if isinstance(values, list)
                    for v in values
                    if isinstance(v, dict) and "filename" in v
                ]
                require(len(entries) == 1, "expected one generated output")
                entry = entries[0]
                name = filename(entry["filename"])
                require(
                    entry.get("type") == "output"
                    and entry.get("subfolder") == "ainative"
                    and name.startswith(key + "_"),
                    "foreign output",
                )
                ext = ".glb" if record["request"]["node"].endswith("mesh") else ".png"
                require(name.endswith(ext), "unexpected output format")
                data = self.call(
                    "/view?" + urllib.parse.urlencode(dict(filename=name, subfolder="ainative", type="output")),
                    raw=True,
                )
                require(
                    data.startswith(b"\x89PNG\r\n\x1a\n")
                    if ext == ".png"
                    else len(data) >= 12
                    and data[:4] == b"glTF"
                    and struct.unpack_from("<II", data, 4) == (2, len(data)),
                    "invalid generated bytes",
                )
                if ext == ".glb":
                    validate_embedded_glb(data)
                sha = hashlib.sha256(data).hexdigest()
                aid = "comfy-" + key
                asset = dict(
                    id=aid,
                    revision=sha,
                    type="mesh" if ext == ".glb" else "image",
                    payload=dict(
                        content_base64=base64.b64encode(data).decode(),
                        content_sha256=sha,
                        extension=ext,
                        bytes=len(data),
                        provenance=dict(
                            provider=self.describe(),
                            checkpoints=self.config["checkpoints"],
                            backend_revision=self.config["backend_revision"],
                            workflow_sha256=digest(record["graph"]),
                            request=record["request"],
                            source_manifest_sha256=digest(record["manifest"]),
                            usage=record["usage"],
                        ),
                    ),
                )
                record["result"] = dict(schema_version=1, artifacts=[asset])
                record["terminal"] = self.snapshot(key, "succeeded", {"result": dict(id=aid, revision=sha)})
            else:
                return self.snapshot(key, "running")
            record = self.write(key, record)
            return record["terminal"]
        queue = self.call("/queue")
        if any(self.owns(p, key, record) for p in queue.get("queue_running", [])):
            return self.snapshot(key, "running")
        # A missing history entry is NOT proof of failure; retain known job identity.
        return self.snapshot(key, "running")

    def result_manifest(self, key):
        return self.read(key)["result"]

    def cancel(self, key):
        record = self.read(key)
        if "terminal" in record:
            return record["terminal"]
        remote = record["remote"]
        if remote:
            queue = self.call("/queue")
            if any(self.owns(p, key, record) for p in queue.get("queue_pending", [])):
                self.call("/queue", {"delete": [remote]})
        # Never /interrupt: running jobs may finish; results are locally discarded.
        record["terminal"] = self.snapshot(key, "cancelled")
        record = self.write(key, record)
        return record["terminal"]


class LocalMeshProvider(ComfyProvider):
    """Direct local image-to-mesh contract; cannot silently invoke image editing."""

    def describe(self):
        value = super().describe()
        value.update(capabilities=["image_to_mesh"], model="local image-to-mesh")
        return value

    def build(self, request, manifest, key):
        require(request["node"] == "image_to_mesh", "local_mesh_only")
        prompt = "\n".join(
            [request["parameters"].get("prompt", "")] + [c["text"] for c in request["context"] if "text" in c]
        ).strip()
        require(not prompt, "local_mesh_does_not_redraw")
        return super().build(request, manifest, key)


def factory(config_path=None):
    from editor_demo import factory as demo_factory
    from generation_service import ServiceError

    chosen_path = config_path or os.environ.get("AINATIVE_COMFY_CONFIG")
    if not chosen_path:
        raise ServiceError("service_not_configured")
    config_path = Path(chosen_path).resolve()
    try:
        config = json.loads(config_path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        raise ServiceError("service_config_invalid") from None
    storage = Path(config["storage"])
    if not storage.is_absolute():
        config["storage"] = str(config_path.parent / storage)
    registry, providers = demo_factory()
    register(registry)
    providers["comfy"] = ComfyProvider(config)
    return registry, providers
