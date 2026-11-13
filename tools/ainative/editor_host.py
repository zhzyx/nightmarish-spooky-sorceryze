"""File based subprocess transport. Factory is trusted local CLI config, never graph data."""

import argparse
import base64
import hashlib
import importlib
import json
import math
import os
import struct
import sys
import uuid
from pathlib import Path

from executor import Executor, snapshot_file
from extensions import NodeRegistry, canonical, publish_new
from generation_service import (
    ServiceError,
    adapt_image_providers,
    check_inputs,
    check_service,
    failure,
    image_batch_settings,
    load_settings,
    prepare_provider,
    reject_retired_modeling_nodes,
    restore_provider,
    retired_modeling_provider,
    run_service,
    save_run_service,
)

SECRET_KEYS = {"token", "api_key", "apikey", "password", "secret", "authorization", "credentials", "factory", "python"}


def safe(value):
    if isinstance(value, dict):
        if any(k.lower() in SECRET_KEYS for k in value):
            raise ValueError("credential/config field forbidden")
        for child in value.values():
            safe(child)
    elif isinstance(value, list):
        for child in value:
            safe(child)


def target_graph(model, target):
    """Select the target's dependency closure before reading files or node schemas.

    Graph identity/edge structure is checked globally so ambiguous IDs cannot
    change what is executed. Unrelated node configuration is not evaluated.
    """
    if (
        not isinstance(model, dict)
        or not isinstance(model.get("nodes"), list)
        or not isinstance(model.get("edges"), list)
    ):
        raise ValueError("invalid model")
    nodes = {}
    for node in model["nodes"]:
        if not isinstance(node, dict) or not isinstance(node.get("id"), str) or not node["id"] or node["id"] in nodes:
            raise ValueError("invalid or duplicate node id")
        nodes[node["id"]] = node
    if not isinstance(target, str) or target not in nodes:
        raise ValueError("unknown target node")
    incoming = {key: [] for key in nodes}
    for edge in model["edges"]:
        if not isinstance(edge, dict) or not isinstance(edge.get("from"), str) or not isinstance(edge.get("to"), str):
            raise ValueError("invalid edge")
        if edge["to"] in incoming:
            incoming[edge["to"]].append(edge["from"])
    required, pending = set(), [target]
    while pending:
        key = pending.pop()
        if key in required:
            continue
        if key not in nodes:
            raise ValueError("missing dependency")
        required.add(key)
        pending.extend(incoming[key])
    return {
        **model,
        "nodes": [node for node in model["nodes"] if node["id"] in required],
        "edges": [edge for edge in model["edges"] if edge["to"] in required],
    }


def compile_graph(model):
    safe(model)
    assets = []
    graph = []
    for n in model["nodes"]:
        inputs = {}
        context = []
        kind = n.get("type", "copy")
        for field in ("source", "image_context"):
            plural = field + "_paths"
            snapshots = field + "_snapshots"
            paths = n.get(plural, [])
            embedded_snapshots = n.get(snapshots, [])
            if not isinstance(paths, list) or not isinstance(embedded_snapshots, list):
                raise ValueError("invalid input collection")
            multiple = bool(paths or embedded_snapshots)
            if multiple and not paths and embedded_snapshots:
                paths = [""] * len(embedded_snapshots)
            if not multiple:
                paths = [n.get(field, "")]
                embedded_snapshots = [n.get(field + "_snapshot")] if n.get(field + "_snapshot") else []
            require_count = len(paths) if multiple else 1
            if multiple and embedded_snapshots and len(embedded_snapshots) != len(paths):
                raise ValueError("input paths/snapshots length mismatch")
            if require_count > 8:
                raise ValueError("too many input images")
            if kind == "model_adjust" and field == "source" and len(paths) > 1:
                raise ValueError("one source model required")
            for index in range(require_count):
                selected_path = paths[index] if index < len(paths) else ""
                snapshot = embedded_snapshots[index] if index < len(embedded_snapshots) else None
                if not selected_path and not snapshot:
                    continue
                if not isinstance(selected_path, str):
                    raise ValueError("invalid input path")
                path = Path(selected_path) if selected_path else None
                ext = path.suffix.lower() if path else snapshot["extension"].lower()
                if ext not in (".png", ".jpg", ".jpeg", ".glb", ".gltf"):
                    raise ValueError("unsupported asset")
                payload = snapshot_file(path) if path else dict(snapshot)
                if not isinstance(payload, dict):
                    raise ValueError("invalid input snapshot")
                if ext in (".png", ".jpg", ".jpeg"):
                    signature = base64.b64decode(payload["content_base64"][:12], validate=True)
                    if signature.startswith(b"\x89PNG\r\n\x1a\n"):
                        ext = ".png"
                    elif signature.startswith(b"\xff\xd8\xff") and ext == ".png":
                        ext = ".jpg"
                payload["extension"] = ext
                image_field = kind != "model_adjust" or field != "source"
                if kind != "copy" and image_field and ext not in (".png", ".jpg", ".jpeg"):
                    raise ValueError("image context required")
                if kind == "model_adjust" and field == "source" and ext not in (".glb", ".gltf"):
                    raise ValueError("source model required")
                if ext in (".gltf", ".glb"):

                    def embedded(v):
                        if isinstance(v, dict):
                            if "uri" in v and not v["uri"].startswith("data:"):
                                raise ValueError("glTF must embed dependencies")
                            for x in v.values():
                                embedded(x)
                        elif isinstance(v, list):
                            for x in v:
                                embedded(x)

                    data = base64.b64decode(payload["content_base64"])
                    if ext == ".glb":
                        magic, version, length, chunk_length, chunk_type = struct.unpack_from("<5I", data)
                        if magic != 0x46546C67 or version != 2 or length != len(data) or chunk_type != 0x4E4F534A:
                            raise ValueError("invalid GLB")
                        data = data[20 : 20 + chunk_length]
                    embedded(json.loads(data))
                aid = n["id"] + "-" + field + ("-" + str(index) if multiple else "")
                assets.append(
                    dict(
                        id=aid,
                        revision=payload["content_sha256"],
                        type="image" if ext in (".png", ".jpg", ".jpeg") else "mesh",
                        payload=payload,
                    )
                )
                ref = {"id": aid, "revision": payload["content_sha256"]}
                if field == "source" and "source" not in inputs:
                    inputs["source"] = ref
                else:
                    context.append(dict(artifact=ref, role="reference", scope="node", strength="reference"))
        if n.get("text"):
            context.append(dict(text=n["text"], role="instruction", scope="node", strength="constraint"))
        links = {}
        for edge in model["edges"]:
            if edge["to"] == n["id"]:
                port = edge.get("input", "source")
                if port in links:
                    raise ValueError("duplicate linked port")
                links[port] = {"node": edge["from"], "port": edge.get("output", "result")}
                inputs.pop(port, None)
        graph.append(
            dict(
                id=n["id"],
                provider=n.get("provider", "local-copy"),
                request=dict(
                    node=kind,
                    version=n.get("version", "1"),
                    inputs=inputs,
                    parameters=n["parameters"],
                    context=context,
                ),
                links=links,
            )
        )
    return graph, dict(schema_version=1, artifacts=assets)


def normalize_editor_integers(graph, registry):
    """Godot JSON numbers arrive as floats; normalize only schema integer fields.

    This transport accepts integers exactly representable by JSON/IEEE doubles.
    Executor and direct CLI contracts retain their strict original type rules.
    """
    maximum = 2**53 - 1
    for node in graph:
        request = node["request"]
        schema = registry.get(request["node"], request["version"])["parameters"]
        params = request["parameters"]
        if not isinstance(params, dict):
            raise ValueError("parameters must be object")
        params = dict(params)
        for name, spec in schema.get("properties", {}).items():
            if spec["type"] != "integer" or name not in params:
                continue
            value = params[name]
            if type(value) is int:
                if abs(value) > maximum:
                    raise ValueError("editor integer exceeds JSON safe range: " + name)
            elif type(value) is float and math.isfinite(value) and value.is_integer() and abs(value) <= maximum:
                params[name] = int(value)
            else:
                raise ValueError("editor integer must be a finite JSON safe integer: " + name)
        request["parameters"] = params


def selected(host, request, preview=False):
    exported = host.export_node(request["run"], request["node"]) if preview else host.export(request["run"])
    outputs = exported["outputs"][request["node"]]
    ref = outputs["result"]
    chosen = request.get("artifact")
    if chosen is not None:
        require_ref = isinstance(chosen, dict) and set(chosen) == {"id", "revision"}
        if not require_ref:
            raise ValueError("invalid selected artifact")
        if "image_set" not in outputs:
            raise ValueError("selected artifact is not a set member")
        collection = next(
            (
                a
                for a in exported["manifest"]["artifacts"]
                if a["id"] == outputs["image_set"]["id"] and a["revision"] == outputs["image_set"]["revision"]
            ),
            None,
        )
        if collection is None or not any(item["artifact"] == chosen for item in collection["payload"]["items"]):
            raise ValueError("selected artifact is not a set member")
        ref = chosen
    asset = next(
        a for a in exported["manifest"]["artifacts"] if a["id"] == ref["id"] and a["revision"] == ref["revision"]
    )
    if asset["type"] not in ("image", "mesh"):
        raise ValueError("selected artifact is not previewable")
    token = hashlib.sha256(canonical([request["run"], ref, asset]).encode()).hexdigest()
    return exported, asset, token


def dispatch(args, request):
    if args.command == "managed-comfy":
        from managed_comfy import manage

        return manage(request)
    if args.command == "service-check":
        return check_service(request.get("service", {}))
    registry, providers = NodeRegistry(), {}
    model = None
    runtime_service = None
    run_id = None
    service_path = getattr(args, "service_config", None)
    if args.command == "create":
        model = target_graph(request["model"], request["target"]) if "target" in request else request["model"]
        safe(model)
        reject_retired_modeling_nodes(model["nodes"])
        check_inputs(model)
        if service_path:
            run_id = uuid.uuid4().hex
            config = load_settings(service_path)
            registry, providers, runtime_service = prepare_provider(config, model, args.db, run_id)
            runtime_service["image_batch"] = image_batch_settings(config)
            runtime_service["image_batch"]["database"] = str(Path(args.db).resolve())
            runtime_service["image_batch"]["enabled"] = runtime_service["image_batch"]["enabled"] and any(
                n.get("type", "copy") in ("text_to_image", "image_to_image") and n.get("version") == "2"
                for n in model["nodes"]
            )
            providers = adapt_image_providers(providers, args.db, runtime_service["image_batch"])
        elif args.factory == "editor_demo:factory" and any(n.get("type", "copy") != "copy" for n in model["nodes"]):
            raise ServiceError("service_not_configured")
    elif args.command == "step":
        runtime_service = run_service(args.db, request["run"])
        if runtime_service is not None:
            registry, providers = restore_provider(runtime_service)
    if args.command in ("create", "step"):
        if runtime_service is None:
            module, func = args.factory.split(":")
            registry, providers = getattr(importlib.import_module(module), func)()
    host = Executor(args.db, registry, providers)
    try:
        if args.command == "create":
            graph, manifest = compile_graph(model)
            normalize_editor_integers(graph, registry)
            if runtime_service is not None:
                # Persist before creating the run. A crash leaves only an unused
                # local settings row; a created run always has frozen identity.
                save_run_service(args.db, run_id, runtime_service)
            return {"run_id": host.create(graph, manifest, run_id=run_id)}
        if args.command in ("step", "retry"):
            run = host.status(request["run"])
            if args.command == "retry":
                nodes = [run["nodes"][request["node"]]]
            elif run["state"] == "cancelled":
                nodes = []
            else:
                nodes = [
                    node for node in run["nodes"].values() if node["state"] not in ("succeeded", "failed", "cancelled")
                ]
            if any(retired_modeling_provider(node.get("provider")) for node in nodes):
                raise ServiceError("gpt_modeling_retired")
        if args.command == "retry":
            host.retry(request["run"], request["node"])
            return host.status(request["run"])
        if args.command == "preview":
            exported, asset, token = selected(host, request, preview=True)

            def materialize(selected_asset, selected_token):
                data = base64.b64decode(selected_asset["payload"]["content_base64"], validate=True)
                if hashlib.sha256(data).hexdigest() != selected_asset["payload"]["content_sha256"]:
                    raise ValueError("digest")
                extension = selected_asset["payload"]["extension"]
                if extension not in (".png", ".jpg", ".jpeg", ".glb", ".gltf"):
                    raise ValueError("unsupported preview format")
                path = Path(args.db).parent / (selected_token + extension)
                try:
                    with path.open("xb") as stream:
                        stream.write(data)
                except FileExistsError:
                    if path.read_bytes() != data:
                        raise ValueError("preview collision")
                return dict(path=str(path), token=selected_token, type=selected_asset["type"])

            result = materialize(asset, token)
            result["artifact"] = {"id": asset["id"], "revision": asset["revision"]}
            outputs = exported["outputs"][request["node"]]
            if "image_set" in outputs:
                collection = next(a for a in exported["manifest"]["artifacts"] if a["id"] == outputs["image_set"]["id"])
                result["images"] = []
                for item in collection["payload"]["items"]:
                    _, member, member_token = selected(host, dict(request, artifact=item["artifact"]), preview=True)
                    entry = materialize(member, member_token)
                    entry.update(label=item["label"], artifact=item["artifact"])
                    result["images"].append(entry)
            return result
        if args.command == "publish":
            exported, asset, token = selected(host, request)
            if request["confirmation"] != token:
                raise ValueError("stale confirmation")
            target = Path(request["target"])
            if target.suffix.lower() not in (".tres", ".tscn"):
                raise ValueError("Godot target required")
            data = Path(request["staged"]).read_bytes()
            if hashlib.sha256(data).hexdigest() != request["staged_sha256"]:
                raise ValueError("staged bytes changed")
            expected = b"[gd_resource " if target.suffix.lower() == ".tres" else b"[gd_scene "
            if not data.startswith(expected):
                raise ValueError("encoded type mismatch")

            class Encoded:
                def encode(self, manifest):
                    return data

            return publish_new(Encoded(), exported["manifest"], target)
        return getattr(host, args.command)(request["run"])
    finally:
        host.close()


def main():
    # The editor starts the bundled interpreter with -E -s -B. Its supervisor
    # and generation workers start fresh interpreters, so pass that isolation
    # on to them as well. Bytecode under the signed app invalidates its seal.
    if sys.flags.ignore_environment and sys.flags.no_user_site and sys.dont_write_bytecode:
        for key in tuple(os.environ):
            if key.startswith("PYTHON"):
                del os.environ[key]
        os.environ.update(PYTHONNOUSERSITE="1", PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1")
    p = argparse.ArgumentParser()
    p.add_argument(
        "command",
        choices=["create", "step", "status", "cancel", "retry", "preview", "publish", "service-check", "managed-comfy"],
    )
    p.add_argument("--db", required=True)
    p.add_argument("--factory", default="editor_demo:factory")
    p.add_argument("--service-config")
    p.add_argument("--spec", required=True)
    p.add_argument("--result", required=True)
    args = p.parse_args()
    try:
        result = {"ok": True, "result": dispatch(args, json.loads(Path(args.spec).read_text(encoding="utf-8")))}
    except Exception as error:
        result = failure(error)
    path = Path(args.result)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(result), encoding="utf-8")
    os.replace(temp, path)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
