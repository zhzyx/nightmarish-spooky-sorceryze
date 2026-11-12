"""Provider-neutral ordered image inputs and independently durable image outputs.

Version 1 providers retain their original single-image contract. This adapter owns
version 2 image nodes: each output has its own child intent and idempotency key.
Single-reference backends receive one deterministic labeled board; native
multi-reference backends receive every ordered source, never a silently dropped tail.
"""

import base64
import copy
import hashlib
import re
import subprocess
from pathlib import Path

from codex_provider import CodexProvider, _creationflags, validate_png
from comfy_provider import digest
from extensions import NodeRegistry, canonical, require, validate_invocation, validate_outputs

VERSION = "2"
IMAGE_KINDS = ("text_to_image", "image_to_image")
MAX_IMAGES = 8
MESSAGES = {
    "invalid_image_batch": "图像输入或输出列表无效。每次支持 1～8 张输入和 1～8 张独立输出，标签不能为空或重复。",
    "reference_board_missing": "此生成方式一次只接收一张图片。请在本机环境设置中选择 Godot 和内置参考板构造器，以保留全部多源输入。",
    "reference_board_failed": "多源参考板构造失败，未提交图像生成，也未丢弃其他输入。",
    "image_batch_failed": "至少一个图像子任务失败。已完成的子任务回执仍保留，不会自动重新生成。",
    "image_batch_cancelled": "图像批次已取消；各子任务的已有回执仍保留。",
    "image_batch_result_invalid": "图像集合的数量、顺序或成员身份不一致，未发布该结果。",
}


def register_images(registry):
    """Add a new version; never mutate the version 1 definitions used by old runs."""
    from comfy_provider import register

    register(registry)
    for kind in IMAGE_KINDS:
        definition = registry.get(kind, "1")
        definition["version"] = VERSION
        definition["inputs"] = {"source": {"types": ["image", "image_set"], "required": kind == "image_to_image"}}
        definition["context_types"] = ["text", "image", "image_set"]
        definition["outputs"]["image_set"] = {"types": ["image_set"], "required": True}
        properties = definition["parameters"]["properties"]
        properties["output_count"] = {"type": "integer"}
        properties["output_labels"] = {"type": "array"}
        registry.register(definition)


def _ref(asset):
    return {key: asset[key] for key in ("id", "revision")}


def _sources(request, manifest):
    index = {asset["id"]: asset for asset in manifest["artifacts"]}
    ordered = list(request["inputs"].values()) + [
        context["artifact"] for context in request["context"] if "artifact" in context
    ]
    result = []

    def append(reference, label):
        require(isinstance(reference, dict) and set(reference) == {"id", "revision"}, "invalid_image_batch")
        asset = index.get(reference["id"])
        require(asset is not None and asset["revision"] == reference["revision"], "invalid_image_batch")
        if asset["type"] == "image_set":
            payload = asset["payload"]
            require(
                payload.get("schema_version") == 1 and isinstance(payload.get("items"), list), "invalid_image_batch"
            )
            for item in payload["items"]:
                append(item["artifact"], label + " / " + item["label"])
        else:
            require(asset["type"] == "image", "invalid_image_batch")
            result.append(dict(asset=asset, label=label))

    for position, reference in enumerate(ordered):
        append(reference, "source" if position == 0 else "reference " + str(position + 1))
    require(len(result) <= MAX_IMAGES, "invalid_image_batch")
    return result


def output_specifications(parameters):
    labels = parameters.get("output_labels", [])
    require(isinstance(labels, list), "invalid_image_batch")
    require(
        all(isinstance(label, str) and 0 < len(label.strip()) <= 80 and label.strip() == label for label in labels),
        "invalid_image_batch",
    )
    count = parameters.get("output_count", len(labels) if labels else 1)
    require(type(count) is int and 1 <= count <= MAX_IMAGES, "invalid_image_batch")
    if labels:
        require(len(labels) == count and len(set(labels)) == len(labels), "invalid_image_batch")
    else:
        labels = ["main"] if count == 1 else ["variant " + str(index + 1) for index in range(count)]
    return [dict(index=index, label=label) for index, label in enumerate(labels)]


def make_reference_board(sources, directory, config):
    """Use the trusted Godot decoder for PNG and JPEG; no new Python imaging dependency."""
    godot, builder = config.get("board_godot_path", ""), config.get("board_builder_path", "")
    require(
        isinstance(godot, str)
        and isinstance(builder, str)
        and Path(godot).is_absolute()
        and Path(builder).is_absolute()
        and Path(godot).is_file()
        and Path(builder).is_file()
        and Path(builder).name == "image_contact_sheet.gd",
        "reference_board_missing",
    )
    directory.mkdir(exist_ok=True)
    project = directory / "project"
    project.mkdir(exist_ok=True)
    (project / "project.godot").write_text('[application]\nconfig/name="Private reference board"\n', encoding="utf-8")
    inputs = []
    for index, source in enumerate(sources):
        asset = source["asset"]
        payload = asset["payload"]
        data = base64.b64decode(payload["content_base64"], validate=True)
        require(hashlib.sha256(data).hexdigest() == payload["content_sha256"], "reference_board_failed")
        path = directory / ("source-" + str(index) + payload["extension"].lower())
        path.write_bytes(data)
        inputs.append(dict(path=str(path), label=source["label"], content_sha256=payload["content_sha256"]))
    request = project / "request.json"
    output = directory / "reference-board.png"
    request.write_text(canonical(dict(inputs=inputs, output=str(output))), encoding="utf-8")
    try:
        process = subprocess.run(
            [
                str(Path(godot).resolve()),
                "--headless",
                "--path",
                str(project),
                "--script",
                str(Path(builder).resolve()),
                "--",
                str(request),
            ],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=120,
            creationflags=_creationflags(),
        )
    except (OSError, subprocess.TimeoutExpired):
        raise ValueError("reference_board_failed") from None
    require(process.returncode == 0 and len(process.stdout + process.stderr) <= 1024 * 1024, "reference_board_failed")
    lines = process.stdout.decode("utf-8", "replace").splitlines()
    matches = [line.removeprefix("REFERENCE_BOARD: ") for line in lines if line.startswith("REFERENCE_BOARD: ")]
    require(matches == [str(output)], "reference_board_failed")
    data = output.read_bytes()
    validate_png(data)
    sha = hashlib.sha256(data).hexdigest()
    return dict(
        id="reference-board-" + sha,
        revision=sha,
        type="image",
        payload=dict(
            content_base64=base64.b64encode(data).decode("ascii"),
            content_sha256=sha,
            extension=".png",
            bytes=len(data),
            provenance=dict(
                adaptation="labelled_multi_source_reference_board",
                sources=[dict(source_sha256=item["content_sha256"], label=item["label"]) for item in inputs],
                board_sha256=sha,
            ),
        ),
    )


class MultiImageProvider(CodexProvider):
    """Batch lifecycle wrapper around an existing provider, sharing no child job key."""

    def __init__(self, inner, storage, board_config=None):
        self.inner = inner
        self.storage = Path(storage).resolve()
        self.storage.mkdir(parents=True, exist_ok=True)
        self.database = self.storage / "multi-image-jobs.sqlite"
        self.board_config = dict(board_config or {})
        require(set(self.board_config) <= {"board_godot_path", "board_builder_path"}, "reference_board_missing")
        self.fingerprint = digest([
            inner.describe(),
            self.board_config,
            hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        ])
        with self.db() as db:
            db.execute("CREATE TABLE IF NOT EXISTS jobs(key TEXT PRIMARY KEY, body TEXT NOT NULL)")

    def describe(self):
        result = self.inner.describe()
        result["version"] = VERSION
        result["model"] += " + ordered multi-input/multi-output workflow adapter"
        result["model_version"] = self.fingerprint
        result["context_types"] = sorted(set(result["context_types"]) | {"image_set"})
        return result

    def _prepare(self, request, manifest, key):
        require(request["node"] in IMAGE_KINDS and request["version"] == VERSION, "invalid_image_batch")
        sources = _sources(request, manifest)
        require(bool(sources) or request["node"] == "text_to_image", "invalid_image_batch")
        specifications = output_specifications(request["parameters"])
        native = self.inner.describe()["id"] == "kimi_work_image"
        adaptation = "ordered_native_multi_reference" if native else "single_reference"
        child_manifest = copy.deepcopy(manifest)
        child_request = copy.deepcopy(request)
        child_request["version"] = "1"
        for field in ("output_count", "output_labels"):
            child_request["parameters"].pop(field, None)
        board_pending = len(sources) > 1 and not native
        if native:
            # The original source port is not registered on version 1 text_to_image;
            # represent every reference uniformly in its ordered image context.
            references = [_ref(source["asset"]) for source in sources]
            child_request["inputs"] = {"source": references[0]} if request["node"] == "image_to_image" else {}
            child_request["context"] = [context for context in child_request["context"] if "text" in context]
            child_request["context"] += [
                dict(artifact=reference, role="reference", scope="node", strength="reference")
                for reference in references[1 if request["node"] == "image_to_image" else 0 :]
            ]
        elif request["node"] == "text_to_image" and "source" in child_request["inputs"]:
            reference = child_request["inputs"].pop("source")
            child_request["context"].insert(
                0, dict(artifact=reference, role="reference", scope="node", strength="reference")
            )
        # Upstream image_set artifacts are retained for lineage; their members and/or
        # derived board are the actual model inputs, not an extra hidden source.
        return dict(
            sources=[dict(ref=_ref(source["asset"]), label=source["label"]) for source in sources],
            specifications=specifications,
            adaptation=adaptation,
            reference_board=None,
            board_pending=board_pending,
            child_request=child_request,
            child_manifest=None if board_pending else child_manifest,
            children=[
                dict(index=index, key=hashlib.sha256((key + ":image:" + str(index)).encode()).hexdigest(), receipt=None)
                for index in range(len(specifications))
            ],
        )

    def _prepare_board(self, key):
        record = self.read(key)
        if not record.get("board_pending"):
            return
        try:
            sources = _sources(record["request"], record["manifest"])
            board = make_reference_board(sources, self.storage / key / "board", self.board_config)
        except ValueError as error:
            if str(error) not in ("reference_board_missing", "reference_board_failed"):
                raise
            self.write(key, terminal=self.snapshot(key, "failed", error=MESSAGES[str(error)]))
            return
        child_manifest = copy.deepcopy(record["manifest"])
        child_manifest["artifacts"].append(board)
        child_request = copy.deepcopy(record["child_request"])
        child_request["inputs"] = {"source": _ref(board)} if record["request"]["node"] == "image_to_image" else {}
        child_request["context"] = [context for context in child_request["context"] if "text" in context]
        if record["request"]["node"] == "text_to_image":
            child_request["context"].insert(
                0, dict(artifact=_ref(board), role="reference", scope="node", strength="reference")
            )
        labels = ", ".join("REF " + str(index + 1) + "=" + source["label"] for index, source in enumerate(sources))
        child_request["parameters"]["prompt"] += (
            "\nUse every ordered labeled source in the attached reference board: " + labels + "."
        )
        # The durable parent and original request already exist before this local
        # board is built. No reference upload or remote generation has run yet.
        self.write(
            key,
            child_manifest=child_manifest,
            child_request=child_request,
            reference_board=board["payload"]["provenance"],
            adaptation="labelled_multi_source_reference_board",
            board_pending=False,
        )

    def _local(self, key):
        try:
            return self.read(key)
        except ValueError as error:
            require(str(error) == "unknown local job", str(error))
            return None

    def _validate(self, key):
        record = self.read(key)
        require(record["fingerprint"] == self.fingerprint, "idempotency conflict")
        registry = NodeRegistry()
        register_images(registry)
        validate_invocation(registry, record["request"], record["manifest"], self.describe())
        return record

    def _request(self, plan, index):
        request = copy.deepcopy(plan["child_request"])
        specification = plan["specifications"][index]
        if len(plan["specifications"]) > 1:
            prompt = str(request["parameters"].get("prompt", ""))
            request["parameters"]["prompt"] = (
                prompt
                + "\nGenerate exactly one independent image for the labeled view/variant: "
                + specification["label"]
                + ". Do not return a contact sheet, collage or multiple panels."
            )
        return request

    def _store_receipt(self, key, index, receipt):
        from extensions import validate_job

        record = self.read(key)
        previous = record["children"][index]["receipt"]
        if previous is not None:
            validate_job(receipt, previous)
        record["children"][index]["receipt"] = receipt
        self.write(key, children=record["children"])

    def submit(self, request, manifest, idempotency_key):
        if request["node"] not in IMAGE_KINDS or request.get("version", "1") != VERSION:
            return self.inner.submit(request, manifest, idempotency_key)
        require(isinstance(idempotency_key, str) and re.fullmatch(r"[a-f0-9]{64}", idempotency_key), "invalid job key")
        previous = self._local(idempotency_key)
        if previous is not None:
            require(previous["request"] == request and previous["manifest"] == manifest, "idempotency conflict")
            return self.poll(idempotency_key)
        plan = self._prepare(request, manifest, idempotency_key)
        record = dict(request=request, manifest=manifest, fingerprint=self.fingerprint, children=[])
        with self.db() as db:
            require(
                db.execute("INSERT OR IGNORE INTO jobs VALUES (?,?)", (idempotency_key, canonical(record))).rowcount
                == 1,
                "idempotency conflict",
            )
        # Durable parent intent precedes local board construction and all uploads.
        self.write(idempotency_key, **plan)
        self._prepare_board(idempotency_key)
        return self.poll(idempotency_key)

    def lookup(self, key):
        return self.inner.lookup(key) if self._local(key) is None else self.poll(key)

    def _result(self, key, record):
        artifacts, items, identities = [], [], set()
        for child in record["children"]:
            manifest = self.inner.result_manifest(child["key"])
            images = [asset for asset in manifest["artifacts"] if asset["type"] == "image"]
            require(len(images) == 1, "image_batch_result_invalid")
            image = copy.deepcopy(images[0])
            identity = canonical(_ref(image))
            require(identity not in identities, "image_batch_result_invalid")
            identities.add(identity)
            specification = record["specifications"][child["index"]]
            provenance = copy.deepcopy(image["payload"].get("provenance", {}))
            provenance["workflow_adaptation"] = record["adaptation"]
            provenance["ordered_sources"] = record["sources"]
            provenance["output_label"] = specification["label"]
            provenance["output_index"] = child["index"]
            image["payload"]["provenance"] = provenance
            image["dependencies"] = [source["ref"] for source in record["sources"]]
            artifacts.append(image)
            items.append(dict(artifact=_ref(image), label=specification["label"], index=child["index"]))
        require(len(items) == len(record["specifications"]), "image_batch_result_invalid")
        body = dict(schema_version=1, items=items, count=len(items))
        set_id = "image-set-" + key
        collection = dict(
            id=set_id,
            revision=digest(body),
            type="image_set",
            payload=dict(
                body,
                provenance=dict(
                    adapter="multi_image_provider",
                    adaptation=record["adaptation"],
                    ordered_sources=record["sources"],
                    reference_board=record["reference_board"],
                ),
            ),
            dependencies=[item["artifact"] for item in items],
        )
        result = dict(
            schema_version=1,
            artifacts=copy.deepcopy(record["manifest"]["artifacts"]) + artifacts + [collection],
        )
        registry = NodeRegistry()
        register_images(registry)
        outputs = {"result": items[0]["artifact"], "image_set": _ref(collection)}
        validate_outputs(registry, record["request"]["node"], VERSION, outputs, result)
        self.write(key, result=result, terminal=self.snapshot(key, "succeeded", outputs))

    def _failed(self, key):
        record = self.read(key)
        # Reconcile already-submitted siblings once, but never launch remaining
        # children after a confirmed failure. Their private receipts stay intact.
        for child in record["children"]:
            previous = child["receipt"]
            if previous is not None and previous["state"] not in ("succeeded", "failed", "cancelled"):
                receipt = self.inner.lookup(child["key"])
                if receipt is not None:
                    self._store_receipt(key, child["index"], receipt)
        self.write(key, terminal=self.snapshot(key, "failed", error=MESSAGES["image_batch_failed"]))
        return self.read(key)["terminal"]

    def poll(self, key):
        if self._local(key) is None:
            return self.inner.poll(key)
        record = self._validate(key)
        if "terminal" in record:
            return record["terminal"]
        if "specifications" not in record:
            # A crash before the plan commit cannot have launched a child: the
            # parent intent is written first and all children derive from its plan.
            self.write(key, **self._prepare(record["request"], record["manifest"], key))
        if record.get("board_pending"):
            self._prepare_board(key)
            record = self.read(key)
        if "terminal" in record:
            return record["terminal"]
        receipts = [child["receipt"] for child in record["children"]]
        if any(receipt is not None and receipt["state"] == "failed" for receipt in receipts):
            return self._failed(key)
        if any(receipt is not None and receipt["state"] == "cancelled" for receipt in receipts):
            self.write(key, terminal=self.snapshot(key, "cancelled"))
            return self.read(key)["terminal"]
        for child in record["children"]:
            receipt = child["receipt"]
            if receipt is not None and receipt["state"] in ("succeeded", "failed", "cancelled"):
                continue
            try:
                self.inner.read(child["key"])
            except ValueError as error:
                require(str(error) == "unknown local job", str(error))
                # Every bundled child persists its intent before any external I/O.
                # No child row therefore proves that no submission was attempted.
                receipt = self.inner.submit(
                    self._request(record, child["index"]), record["child_manifest"], child["key"]
                )
            else:
                # In particular ComfyUI lookup reconciles a missing prompt_id;
                # never call submit again after an unknown remote outcome.
                receipt = self.inner.lookup(child["key"])
                if receipt is None:
                    receipt = self.snapshot(child["key"], "queued")
            self._store_receipt(key, child["index"], receipt)
            if receipt["state"] in ("failed", "cancelled"):
                break
        record = self.read(key)
        receipts = [child["receipt"] for child in record["children"]]
        if any(receipt is not None and receipt["state"] == "failed" for receipt in receipts):
            return self._failed(key)
        if any(receipt is not None and receipt["state"] == "cancelled" for receipt in receipts):
            self.write(key, terminal=self.snapshot(key, "cancelled"))
        elif all(receipt is not None and receipt["state"] == "succeeded" for receipt in receipts):
            self._result(key, record)
        else:
            return self.snapshot(key, "running")
        return self.read(key)["terminal"]

    def result_manifest(self, key):
        record = self._local(key)
        if record is None:
            return self.inner.result_manifest(key)
        require(record.get("terminal", {}).get("state") == "succeeded", "image_batch_result_invalid")
        return record["result"]

    def cancel(self, key):
        record = self._local(key)
        if record is None:
            return self.inner.cancel(key)
        if "terminal" in record:
            return record["terminal"]
        for child in record["children"]:
            if child["receipt"] is not None and child["receipt"]["state"] in ("succeeded", "failed", "cancelled"):
                continue
            if self._inner_exists(child["key"]):
                receipt = self.inner.cancel(child["key"])
                self._store_receipt(key, child["index"], receipt)
        self.write(key, terminal=self.snapshot(key, "cancelled"))
        return self.read(key)["terminal"]

    def _inner_exists(self, key):
        try:
            self.inner.read(key)
        except ValueError as error:
            require(str(error) == "unknown local job", str(error))
            return False
        return True
