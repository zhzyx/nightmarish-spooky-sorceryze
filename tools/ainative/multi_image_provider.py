"""Provider-neutral ordered image inputs and independently durable image outputs.

Version 1 providers retain their original single-image contract. Versions 2 and 3
keep explicit labeled batches. Version 4 infers the requested views/details from the
prompt and derives every non-primary result from the successful primary image.
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

VERSION = "4"
BATCH_VERSIONS = ("2", "3", VERSION)
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
    """Add versions without mutating definitions already used by old runs."""
    from comfy_provider import register

    register(registry)
    for kind in IMAGE_KINDS:
        definition = registry.get(kind, "1")
        definition["version"] = "2"
        definition["inputs"] = {"source": {"types": ["image", "image_set"], "required": kind == "image_to_image"}}
        definition["context_types"] = ["text", "image", "image_set"]
        definition["outputs"]["image_set"] = {"types": ["image_set"], "required": True}
        properties = definition["parameters"]["properties"]
        properties["output_count"] = {"type": "integer"}
        properties["output_labels"] = {"type": "array"}
        registry.register(definition)
        definition["version"] = "3"
        definition["outputs"] = {"image_set": {"types": ["image_set"], "required": True}}
        registry.register(definition)
        definition["version"] = VERSION
        properties.pop("output_count", None)
        properties.pop("output_labels", None)
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


_AUTOMATIC_VIEWS = [
    ("三分之四侧面", "view", ["三分之四侧面", "四分之三侧面", "3/4侧面", "three-quarter view"]),
    ("正面", "view", ["正面", "前视图", "正面图", "front view"]),
    ("左侧面", "view", ["左侧面", "左侧视图", "左视图", "left view"]),
    ("右侧面", "view", ["右侧面", "右侧视图", "右视图", "right view"]),
    ("侧面", "view", ["侧面", "侧视图", "side view"]),
    ("背面", "view", ["背面", "后视图", "背面图", "back view", "rear view"]),
    ("俯视", "view", ["俯视", "俯视图", "顶视图", "top view"]),
    ("仰视", "view", ["仰视", "仰视图", "底视图", "bottom view"]),
    ("面部细节", "detail", ["面部细节", "脸部细节", "面部特写", "脸部特写", "face close-up"]),
    ("眼部细节", "detail", ["眼部细节", "眼睛特写", "眼部特写", "eye close-up"]),
    ("手部细节", "detail", ["手部细节", "手指细节", "手部特写", "hand close-up"]),
    ("服装细节", "detail", ["服装细节", "衣服细节", "服饰特写", "costume detail"]),
    ("武器细节", "detail", ["武器细节", "武器特写", "weapon detail"]),
    ("局部细节", "detail", ["局部细节", "细节图", "局部特写", "detail view", "detail shot", "close-up"]),
]
_DEFAULT_VIEWS = [
    ("正面", "view"),
    ("三分之四侧面", "view"),
    ("侧面", "view"),
    ("背面", "view"),
    ("左侧面", "view"),
    ("俯视", "view"),
    ("局部细节", "detail"),
    ("补充细节", "detail"),
]


def automatic_output_specifications(prompt):
    """Infer bounded output requirements from the request, never a manual count field."""
    require(isinstance(prompt, str), "invalid_image_batch")
    text = prompt.strip().casefold()
    count_match = re.search(
        r"([0-9]+|[一二两三四五六七八九])\s*(?:张(?:图|图片)?|幅(?:图)?|个(?:视角|视图)|视图)", text
    )
    count = None
    if count_match:
        token = count_match.group(1)
        count = (
            int(token)
            if token.isdigit()
            else {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}[token]
        )
        require(1 <= count <= MAX_IMAGES, "invalid_image_batch")
    found = []
    occupied = []
    for label, mode, terms in _AUTOMATIC_VIEWS:
        candidates = []
        for term in terms:
            start = text.find(term)
            while start >= 0:
                end = start + len(term)
                if not any(start >= left and end <= right for left, right in occupied):
                    candidates.append((start, end))
                start = text.find(term, start + 1)
        if candidates:
            start, end = min(candidates, key=lambda item: (item[0], -(item[1] - item[0])))
            occupied.append((start, end))
            found.append((start, label, mode))
    found.sort()
    labels = [(label, mode) for _, label, mode in found]
    if (
        not labels
        and not count
        and any(term in text for term in ["多视角", "多角度", "多视图", "multi-view", "multiview", "turnaround"])
    ):
        labels = [("正面", "view"), ("右侧面", "view"), ("背面", "view"), ("左侧面", "view")]
    if not labels and "三视图" in text:
        labels = [("正面", "view"), ("侧面", "view"), ("背面", "view")]
    elif not labels and "四视图" in text:
        labels = [("正面", "view"), ("右侧面", "view"), ("背面", "view"), ("左侧面", "view")]
    count = count if count is not None else len(labels)
    if count == 0:
        return [dict(index=0, label="main", mode="view")]
    for label, mode in _DEFAULT_VIEWS:
        if len(labels) >= count:
            break
        if label not in [item[0] for item in labels]:
            labels.append((label, mode))
    require(len(labels) <= MAX_IMAGES, "invalid_image_batch")
    return [dict(index=index, label=label, mode=mode) for index, (label, mode) in enumerate(labels)]


def _has_output_cue(text):
    lowered = text.casefold()
    return (
        any(term in lowered for _, _, terms in _AUTOMATIC_VIEWS for term in terms)
        or any(term in lowered for term in ["多视角", "多角度", "多视图", "multi-view", "multiview", "turnaround"])
        or re.search(r"([0-9]+|[一二两三四五六七八九])\s*(?:张|幅|个视角|个视图|视图)", lowered) is not None
    )


def primary_prompt(prompt):
    """Remove view enumeration from the primary request without losing its subject."""
    kept_sentences = []
    for sentence in re.split(r"[\n。！？!?;；.]+", prompt):
        clauses = []
        for clause in re.split(r"[，,]", sentence):
            if not _has_output_cue(clause):
                if clause.strip():
                    clauses.append(clause.strip())
                continue
            positions = [
                clause.casefold().find(term)
                for _, _, terms in _AUTOMATIC_VIEWS
                for term in terms
                if clause.casefold().find(term) >= 0
            ]
            if positions:
                prefix = clause[: min(positions)].strip()
                if "的" in prefix:
                    clauses.append(prefix + "单张主图")
        if clauses:
            kept_sentences.append("，".join(clauses))
    cleaned = "。".join(kept_sentences).strip()
    return cleaned if cleaned else "Create one primary image of the originally requested subject."


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
        require(request["node"] in IMAGE_KINDS and request["version"] in BATCH_VERSIONS, "invalid_image_batch")
        sources = _sources(request, manifest)
        require(bool(sources) or request["node"] == "text_to_image", "invalid_image_batch")
        automatic = request["version"] == VERSION
        specifications = (
            automatic_output_specifications(str(request["parameters"].get("prompt", "")))
            if automatic
            else output_specifications(request["parameters"])
        )
        derivation = (
            "primary_image_derived"
            if automatic and len(specifications) > 1
            else "automatic_single_image"
            if automatic
            else "independent_labeled_outputs"
        )
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
            derivation=derivation,
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

    def _primary_ref(self, plan):
        first = plan["children"][0]
        require(
            plan["request"]["version"] == VERSION
            and first["receipt"] is not None
            and first["receipt"]["state"] == "succeeded",
            "image_batch_result_invalid",
        )
        reference = first["receipt"]["outputs"]["result"]
        manifest = self.inner.result_manifest(first["key"])
        asset = next(
            (
                item
                for item in manifest["artifacts"]
                if item["id"] == reference["id"] and item["revision"] == reference["revision"]
            ),
            None,
        )
        require(asset is not None and asset["type"] == "image", "image_batch_result_invalid")
        return _ref(asset)

    def _child_manifest(self, plan, index):
        if plan["request"]["version"] != VERSION or index == 0:
            return plan["child_manifest"]
        return self.inner.result_manifest(plan["children"][0]["key"])

    def _request(self, plan, index):
        request = copy.deepcopy(plan["child_request"])
        specification = plan["specifications"][index]
        if plan["request"]["version"] != VERSION:
            if len(plan["specifications"]) > 1:
                prompt = str(request["parameters"].get("prompt", ""))
                request["parameters"]["prompt"] = (
                    prompt
                    + "\nGenerate exactly one independent image for the labeled view/variant: "
                    + specification["label"]
                    + ". Do not return a contact sheet, collage or multiple panels."
                )
            return request
        prompt = str(request["parameters"].get("prompt", ""))
        if index == 0:
            if len(plan["specifications"]) > 1:
                request["parameters"]["prompt"] = (
                    "Generate exactly one primary image containing exactly one single subject. "
                    + primary_prompt(prompt)
                    + "\nOnly one instance of the subject is allowed. Do not return multiple views, duplicates, a contact sheet, collage or multiple panels."
                )
            return request
        primary = self._primary_ref(plan)
        request["node"] = "image_to_image"
        request["version"] = "1"
        request["inputs"] = {"source": primary}
        action = (
            "Create a close-up detail of the same subject, focusing on: "
            if specification.get("mode") == "detail"
            else "Show the exact same subject from this camera/view direction: "
        )
        request["parameters"]["prompt"] = (
            "The attached primary image is the authoritative depiction of the same generated subject. "
            + action
            + specification["label"]
            + ". Preserve its identity, geometry, materials, colors, style and background. "
            + "Change only the camera/view or framing needed for this derived image; do not design a new subject. "
            + "The result must contain exactly one instance of the subject. "
            + "Do not return multiple views, duplicates, a contact sheet, collage or multiple panels."
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
        if request["node"] not in IMAGE_KINDS or request.get("version", "1") not in BATCH_VERSIONS:
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
            reference = child["receipt"]["outputs"]["result"]
            image = copy.deepcopy(
                next(
                    (
                        asset
                        for asset in manifest["artifacts"]
                        if asset["id"] == reference["id"] and asset["revision"] == reference["revision"]
                    ),
                    None,
                )
            )
            require(image is not None and image["type"] == "image", "image_batch_result_invalid")
            identity = canonical(_ref(image))
            require(identity not in identities, "image_batch_result_invalid")
            identities.add(identity)
            specification = record["specifications"][child["index"]]
            provenance = copy.deepcopy(image["payload"].get("provenance", {}))
            provenance["workflow_adaptation"] = record["adaptation"]
            provenance["ordered_sources"] = record["sources"]
            provenance["output_label"] = specification["label"]
            provenance["output_index"] = child["index"]
            image["dependencies"] = [source["ref"] for source in record["sources"]]
            if record["request"]["version"] == VERSION and child["index"] > 0:
                primary = self._primary_ref(record)
                provenance["derived_from"] = primary
                image["dependencies"] = [primary] + [
                    source["ref"] for source in record["sources"] if source["ref"] != primary
                ]
            image["payload"]["provenance"] = provenance
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
                    derivation=record.get("derivation", "independent_labeled_outputs"),
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
        outputs = {"image_set": _ref(collection)}
        if record["request"]["version"] == "2":
            outputs["result"] = items[0]["artifact"]
        validate_outputs(registry, record["request"]["node"], record["request"]["version"], outputs, result)
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
                    self._request(record, child["index"]), self._child_manifest(record, child["index"]), child["key"]
                )
            else:
                # In particular ComfyUI lookup reconciles a missing prompt_id;
                # never call submit again after an unknown remote outcome.
                receipt = self.inner.lookup(child["key"])
                if receipt is None:
                    receipt = self.snapshot(child["key"], "queued")
            self._store_receipt(key, child["index"], receipt)
            if record["request"]["version"] == VERSION and child["index"] == 0:
                # Derived children must wait for the durable primary result; never
                # launch them from the original prompt while the primary is pending.
                if receipt["state"] != "succeeded":
                    break
                record = self.read(key)
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
