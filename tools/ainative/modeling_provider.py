"""An explicit API planner returns bounded data for a fixed Godot mesh builder.

No generated program is executed. Durable intents are never automatically replayed
following an unknown worker result. API and Godot cancellation use owned process handles.
"""

import base64
import hashlib
import json
import math
import os
import re
import struct
import subprocess
import sys
import time
from pathlib import Path

from comfy_provider import digest, register, validate_embedded_glb
from extensions import NodeRegistry, canonical, require, validate_invocation
from owned_process import implementation_fingerprint, run_owned
from provider_common import DurableProvider, _creationflags, _environment, validate_png

VERSION = "1"
MAX_PLAN_BYTES = 256 * 1024
MAX_LOG_BYTES = 16 * 1024 * 1024
MAX_GLB_BYTES = 64 * 1024 * 1024
BUILDER_TIMEOUT = 90
PRIMITIVES = ("box", "sphere", "cylinder", "capsule", "torus")
MESSAGES = {
    "cli_result_unknown": "建模任务回执不明；已保留原任务，不会自动重复请求。",
    "gpt_modeling_retired": "GPT 单独生成网格已下线，请选择其他建模后端。",
    "plan_invalid": "建模指令超出支持范围或格式无效，未执行生成代码。",
    "builder_missing": "未找到 Godot 或内置建模工具，请检查引擎安装。",
    "builder_failed": "Godot 构造网格失败；建模指令和私有诊断已保留。",
    "builder_timeout": "Godot 构造网格超时，已停止本任务进程。",
    "mesh_invalid": "构造器未返回有效的非空网格，未发布结果。",
    "unsupported_context_semantics": "当前建模支持节点级文字说明和一张参考图。",
    "unsupported_multiple_image_constraints": "当前建模只支持一张输入或参考图。",
    "prompt_required": "请填写要构造的物体描述，或提供参考图。",
    "invalid_input": "输入图像内容或摘要无效。",
    "worker_failed": "建模工作进程失败；私有回执已保留，未自动重试。",
}
MESSAGES.update({
    name: message
    for name, message in (
        ("api_config_invalid", "API 地址、模型或凭据环境变量配置无效。"),
        ("api_key_missing", "未检测到指定的 API 凭据环境变量。"),
        ("api_output_invalid", "API 返回的规划不符合协议，未执行生成代码。"),
        ("api_execution_failed", "API 请求失败或回执未知，未自动重试。"),
        ("api_timeout", "API 请求超时，已停止本任务进程，未自动重试。"),
    )
})
_WORKERS: list[subprocess.Popen[bytes]] = []


def _name(value):
    return (
        isinstance(value, str)
        and 1 <= len(value) <= 80
        and value == value.strip()
        and not any(ord(char) < 32 or ord(char) == 127 or char in '/\\.:@%"' for char in value)
    )


def validate_plan(value):
    """Only a small declarative primitive dialect can reach the Godot builder."""
    require(isinstance(value, dict) and set(value) == {"version", "name", "parts"}, "plan_invalid")
    require(type(value["version"]) is int and value["version"] == 1 and _name(value["name"]), "plan_invalid")
    parts = value["parts"]
    require(isinstance(parts, list) and 1 <= len(parts) <= 64, "plan_invalid")
    names = set()
    for part in parts:
        require(
            isinstance(part, dict)
            and set(part) == {"name", "primitive", "position", "rotation_degrees", "size", "color"},
            "plan_invalid",
        )
        require(_name(part["name"]) and part["name"] not in names, "plan_invalid")
        names.add(part["name"])
        require(part["primitive"] in PRIMITIVES, "plan_invalid")
        for field, length, minimum, maximum in (
            ("position", 3, -100, 100),
            ("rotation_degrees", 3, -3600, 3600),
            ("size", 3, 0.001, 100),
            ("color", 4, 0, 1),
        ):
            vector = part[field]
            require(isinstance(vector, list) and len(vector) == length, "plan_invalid")
            require(
                all(
                    type(number) in (int, float) and math.isfinite(number) and minimum <= number <= maximum
                    for number in vector
                ),
                "plan_invalid",
            )
    return json.loads(canonical(value))


def modeling_schema():
    def vector(length, minimum, maximum):
        return dict(
            type="array", minItems=length, maxItems=length, items=dict(type="number", minimum=minimum, maximum=maximum)
        )

    name = dict(
        type="string",
        minLength=1,
        maxLength=80,
        pattern=r'^[^\s\x00-\x1f\x7f/\\.:@%"](?:[^\x00-\x1f\x7f/\\.:@%"]*[^\s\x00-\x1f\x7f/\\.:@%"])?$',
    )
    part = dict(
        type="object",
        properties=dict(
            name=name,
            primitive=dict(type="string", enum=list(PRIMITIVES)),
            position=vector(3, -100, 100),
            rotation_degrees=vector(3, -3600, 3600),
            size=vector(3, 0.001, 100),
            color=vector(4, 0, 1),
        ),
        required=["name", "primitive", "position", "rotation_degrees", "size", "color"],
        additionalProperties=False,
    )
    return dict(
        type="object",
        properties=dict(
            version=dict(type="integer", const=1),
            name=name,
            parts=dict(type="array", minItems=1, maxItems=64, items=part),
        ),
        required=["version", "name", "parts"],
        additionalProperties=False,
    )


def _matrix_multiply(left, right):
    return tuple(
        tuple(sum(left[row][index] * right[index][column] for index in range(4)) for column in range(4))
        for row in range(4)
    )


def _node_matrix(node):
    identity = ((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1))
    if "matrix" in node:
        values = node["matrix"]
        require(isinstance(values, list) and len(values) == 16, "mesh_invalid")
        require(all(type(value) in (int, float) and math.isfinite(value) for value in values), "mesh_invalid")
        return tuple(tuple(values[column * 4 + row] for column in range(4)) for row in range(4))
    translation = node.get("translation", [0, 0, 0])
    rotation = node.get("rotation", [0, 0, 0, 1])
    scale = node.get("scale", [1, 1, 1])
    require(
        all(
            isinstance(value, list) and len(value) == length
            for value, length in ((translation, 3), (rotation, 4), (scale, 3))
        ),
        "mesh_invalid",
    )
    require(
        all(type(number) in (int, float) and math.isfinite(number) for number in translation + rotation + scale),
        "mesh_invalid",
    )
    x, y, z, w = rotation
    length = math.sqrt(x * x + y * y + z * z + w * w)
    require(length > 0, "mesh_invalid")
    x, y, z, w = x / length, y / length, z / length, w / length
    rotated = (
        (1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w), 0),
        (2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w), 0),
        (2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y), 0),
        (0, 0, 0, 1),
    )
    scaled = tuple(
        tuple(rotated[row][column] * (scale[column] if column < 3 else 1) for column in range(4)) for row in range(4)
    )
    translated = [list(row) for row in identity]
    translated[0][3], translated[1][3], translated[2][3] = translation
    return _matrix_multiply(tuple(tuple(row) for row in translated), scaled)


def _mesh_world_transforms(document):
    """Resolve glTF's column-major TRS scene graph into row-major world transforms."""
    nodes = document.get("nodes")
    scenes = document.get("scenes")
    require(isinstance(nodes, list) and len(nodes) <= 4096, "mesh_invalid")
    require(isinstance(scenes, list) and scenes, "mesh_invalid")
    scene_index = document.get("scene", 0)
    require(type(scene_index) is int and 0 <= scene_index < len(scenes), "mesh_invalid")
    roots = scenes[scene_index].get("nodes", [])
    require(isinstance(roots, list), "mesh_invalid")
    transforms = {index: [] for index in range(len(document.get("meshes", [])))}
    identity = ((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1))
    visited = set()

    def visit(index, parent):
        require(type(index) is int and 0 <= index < len(nodes) and index not in visited, "mesh_invalid")
        visited.add(index)
        node = nodes[index]
        require(isinstance(node, dict), "mesh_invalid")
        world = _matrix_multiply(parent, _node_matrix(node))
        if "mesh" in node:
            mesh = node["mesh"]
            require(type(mesh) is int and mesh in transforms, "mesh_invalid")
            transforms[mesh].append(world)
        children = node.get("children", [])
        require(isinstance(children, list), "mesh_invalid")
        for child in children:
            visit(child, world)

    for root in roots:
        visit(root, identity)
    require(all(len(values) == 1 for values in transforms.values()), "mesh_invalid")
    return {index: values[0] for index, values in transforms.items()}


def validate_mesh(data):
    """Independently validate indexed triangles and transformed finite scene bounds."""
    require(20 <= len(data) <= MAX_GLB_BYTES, "mesh_invalid")
    validate_embedded_glb(data)
    size = struct.unpack_from("<I", data, 12)[0]
    document = json.loads(data[20 : 20 + size])
    offset = 20 + size
    require(offset + 8 <= len(data), "mesh_invalid")
    binary_size, kind = struct.unpack_from("<II", data, offset)
    require(kind == 0x004E4942 and offset + 8 + binary_size == len(data), "mesh_invalid")
    binary = data[offset + 8 :]
    transforms = _mesh_world_transforms(document)
    total_vertices = total_triangles = primitives = 0
    lower = upper = None

    def accessor_bounds(accessor, component_size):
        require(isinstance(accessor, dict) and not accessor.get("sparse"), "mesh_invalid")
        count = accessor.get("count")
        view_index = accessor.get("bufferView")
        require(type(count) is int and count > 0 and type(view_index) is int, "mesh_invalid")
        views = document.get("bufferViews", [])
        require(0 <= view_index < len(views), "mesh_invalid")
        view = views[view_index]
        view_offset = view.get("byteOffset", 0)
        item_offset = accessor.get("byteOffset", 0)
        require(
            view.get("buffer", 0) == 0
            and type(view_offset) is int
            and type(item_offset) is int
            and view_offset >= 0
            and item_offset >= 0,
            "mesh_invalid",
        )
        stride = view.get("byteStride", component_size)
        require(type(stride) is int and component_size <= stride <= 256, "mesh_invalid")
        begin = view_offset + item_offset
        end = begin + (count - 1) * stride + component_size
        view_end = view_offset + view.get("byteLength", -1)
        require(0 <= begin < end <= view_end <= len(binary), "mesh_invalid")
        return begin, stride

    for mesh_index, mesh in enumerate(document.get("meshes", [])):
        world = transforms[mesh_index]
        for primitive in mesh.get("primitives", []):
            require(primitive.get("mode", 4) == 4 and primitives < 4096, "mesh_invalid")
            attributes = primitive.get("attributes", {})
            position_index = attributes.get("POSITION")
            accessors = document.get("accessors", [])
            require(type(position_index) is int and 0 <= position_index < len(accessors), "mesh_invalid")
            accessor = accessors[position_index]
            require(accessor.get("componentType") == 5126 and accessor.get("type") == "VEC3", "mesh_invalid")
            count = accessor.get("count")
            require(type(count) is int and 3 <= count <= 1000000, "mesh_invalid")
            begin, stride = accessor_bounds(accessor, 12)
            positions = [struct.unpack_from("<fff", binary, begin + index * stride) for index in range(count)]
            require(
                all(math.isfinite(value) and abs(value) <= 1000 for point in positions for value in point),
                "mesh_invalid",
            )
            for point in positions:
                x, y, z = point
                transformed = tuple(
                    world[row][0] * x + world[row][1] * y + world[row][2] * z + world[row][3] for row in range(3)
                )
                require(all(math.isfinite(value) and abs(value) <= 1000 for value in transformed), "mesh_invalid")
                if lower is None:
                    lower, upper = list(transformed), list(transformed)
                else:
                    lower = [min(lower[index], transformed[index]) for index in range(3)]
                    upper = [max(upper[index], transformed[index]) for index in range(3)]
            if "indices" in primitive:
                index_index = primitive["indices"]
                require(type(index_index) is int and 0 <= index_index < len(accessors), "mesh_invalid")
                indices_accessor = accessors[index_index]
                component = indices_accessor.get("componentType")
                require(component in (5121, 5123, 5125) and indices_accessor.get("type") == "SCALAR", "mesh_invalid")
                index_count = indices_accessor.get("count")
                require(
                    type(index_count) is int and 3 <= index_count <= 6000000 and index_count % 3 == 0,
                    "mesh_invalid",
                )
                component_size, code = {5121: (1, "B"), 5123: (2, "H"), 5125: (4, "I")}[component]
                index_begin, index_stride = accessor_bounds(indices_accessor, component_size)
                require(index_stride == component_size, "mesh_invalid")
                indices = [
                    struct.unpack_from("<" + code, binary, index_begin + index * index_stride)[0]
                    for index in range(index_count)
                ]
            else:
                indices = list(range(count))
            for start in range(0, len(indices), 3):
                triangle = indices[start : start + 3]
                require(
                    all(0 <= index < count for index in triangle) and len(set(triangle)) == 3,
                    "mesh_invalid",
                )
            total_vertices += count
            total_triangles += len(indices) // 3
            require(total_vertices <= 1000000 and total_triangles <= 2000000, "mesh_invalid")
            primitives += 1
    require(
        primitives >= 1
        and 3 <= total_vertices <= 1000000
        and 1 <= total_triangles <= 2000000
        and lower is not None
        and all(upper[index] > lower[index] for index in range(3)),
        "mesh_invalid",
    )
    return dict(
        vertices=total_vertices,
        triangles=total_triangles,
        primitives=primitives,
        bytes=len(data),
        bounds=dict(min=lower, max=upper),
    )


class ModelingProvider(DurableProvider):
    CONFIG_KEYS = frozenset(("planner", "storage", "godot_path", "builder_path"))
    DATABASE_NAME = "modeling-jobs.sqlite"
    MESSAGES = MESSAGES

    def __init__(self, config):
        require(
            isinstance(config, dict) and set(config) == self.CONFIG_KEYS,
            "invalid modeling config",
        )
        require(
            all(isinstance(value, str) and value.strip() for key, value in config.items() if key != "planner"),
            "invalid modeling config",
        )
        if "planner" in self.CONFIG_KEYS:
            from api_planner import validate_config

            validate_config(config["planner"])
        self.config = json.loads(canonical(config))
        self.storage = Path(config["storage"]).expanduser().resolve()
        self.storage.mkdir(parents=True, exist_ok=True)
        self.database = self.storage / self.DATABASE_NAME
        with self.db() as db:
            db.execute("CREATE TABLE IF NOT EXISTS jobs(key TEXT PRIMARY KEY, body TEXT NOT NULL)")
        builder = Path(config["builder_path"])
        self.fingerprint = digest([
            self.config,
            implementation_fingerprint(),
            hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            hashlib.sha256(Path(__file__).with_name("provider_common.py").read_bytes()).hexdigest(),
            hashlib.sha256(Path(__file__).with_name("api_planner.py").read_bytes()).hexdigest()
            if "planner" in config
            else None,
            hashlib.sha256(builder.read_bytes()).hexdigest() if builder.is_file() else None,
        ])

    def describe(self):
        return dict(
            id="api-modeling",
            version=VERSION,
            model=self.config["planner"]["model"],
            model_version=self.fingerprint,
            capabilities=["text_to_mesh", "image_to_mesh"],
            context_types=["text", "image"],
            available=True,
        )

    def worker_path(self):
        return Path(__file__).resolve()

    def check_authentication(self):
        from api_planner import check_configuration

        return check_configuration(self.config["planner"])

    def finish(self, key, state, code=None, result=None):
        outputs = {"result": {k: result["artifacts"][-1][k] for k in ("id", "revision")}} if result else None
        values = dict(terminal=self.snapshot(key, state, outputs, self.MESSAGES[code] if code else None))
        if result:
            values["result"] = result
        return self.write(key, **values)["terminal"]

    def plan(self, request, manifest):
        require(request["node"] in ("text_to_mesh", "image_to_mesh"), "invalid_input")
        refs = list(request["inputs"].values()) + [
            context["artifact"] for context in request["context"] if "artifact" in context
        ]
        require(len(refs) <= 1, "unsupported_multiple_image_constraints")
        for context in request["context"]:
            reference = context["role"] in ("reference", "instruction") and context["strength"] == "reference"
            instruction = "text" in context and context["role"] == "instruction" and context["strength"] == "constraint"
            require(context["scope"] == "node" and (reference or instruction), "unsupported_context_semantics")
        prompt = "\n".join(
            [request["parameters"].get("prompt", "")]
            + [context["text"] for context in request["context"] if "text" in context]
        ).strip()
        require(prompt or refs, "prompt_required")
        require(len(prompt.encode("utf-8")) <= 32768, "invalid_input")
        source = next(
            (
                artifact
                for artifact in manifest["artifacts"]
                if refs and artifact["id"] == refs[0]["id"] and artifact["revision"] == refs[0]["revision"]
            ),
            None,
        )
        require(not refs or source is not None, "invalid_input")
        if source:
            payload = source["payload"]
            data = base64.b64decode(payload["content_base64"], validate=True)
            require(
                len(data) <= 32 * 1024 * 1024
                and hashlib.sha256(data).hexdigest() == payload["content_sha256"]
                and payload["extension"].lower() in (".png", ".jpg", ".jpeg"),
                "invalid_input",
            )
            if payload["extension"].lower() == ".png":
                validate_png(data)
            else:
                require(data.startswith(b"\xff\xd8") and data.endswith(b"\xff\xd9"), "invalid_input")
        require(
            Path(self.config["godot_path"]).is_file() and Path(self.config["builder_path"]).is_file(), "builder_missing"
        )
        return dict(prompt=prompt, source=source, context=json.loads(canonical(request["context"])))

    def submit(self, request, manifest, idempotency_key):
        registry = NodeRegistry()
        register(registry)
        validate_invocation(registry, request, manifest, self.describe())
        key = idempotency_key
        require(isinstance(key, str) and re.fullmatch(r"[a-f0-9]{64}", key), "invalid idempotency key")
        record = dict(
            request=request,
            manifest=manifest,
            fingerprint=self.fingerprint,
            created=time.time(),
            heartbeat=time.time(),
            stage="intent",
        )
        with self.db() as db:
            inserted = db.execute("INSERT OR IGNORE INTO jobs VALUES (?,?)", (key, canonical(record))).rowcount
        if not inserted:
            previous = self.read(key)
            require(
                previous["request"] == request
                and previous["manifest"] == manifest
                and previous["fingerprint"] == self.fingerprint,
                "idempotency conflict",
            )
            return self.poll(key)
        try:
            plan = self.plan(request, manifest)
            report = self.check_authentication()
            require(report["connected"], report["code"])
            directory = self.storage / key
            directory.mkdir(exist_ok=False)
            (directory / "config.json").write_text(canonical(self.config), encoding="utf-8")
            self.write(key, plan=plan, cli_report=report, stage="queued")
            with (directory / "worker.log").open("xb") as log:
                worker = subprocess.Popen(
                    [
                        sys.executable,
                        "-X",
                        "utf8",
                        str(self.worker_path()),
                        "--worker",
                        str(directory / "config.json"),
                        key,
                    ],
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=log,
                    env=_environment(),
                    creationflags=_creationflags(),
                    start_new_session=os.name != "nt",
                )
            _WORKERS[:] = [process for process in _WORKERS if process.poll() is None]
            _WORKERS.append(worker)
            return self.poll(key)
        except (ValueError, OSError, KeyError, TypeError) as error:
            return self.finish(key, "failed", str(error) if str(error) in self.MESSAGES else "worker_failed")

    def _run_owned(self, key, arguments, directory, label, *, timeout, error_codes=None):
        timeout_code, output_code = error_codes or ("builder_timeout", "builder_failed")
        with (
            (directory / (label + ".stdout")).open("xb") as stdout,
            (directory / (label + ".stderr")).open("xb") as stderr,
        ):
            return run_owned(
                arguments,
                stdout=stdout,
                stderr=stderr,
                env=_environment(),
                limit=MAX_LOG_BYTES,
                timeout=timeout,
                active=lambda: self._active(key, label),
                fail=lambda reason: self.finish(key, "failed", timeout_code if reason == "timeout" else output_code),
            )

    def _instructions(self, key, plan, directory):
        images = []
        if plan["source"]:
            payload = plan["source"]["payload"]
            source = directory / ("reference" + payload["extension"].lower())
            source.write_bytes(base64.b64decode(payload["content_base64"], validate=True))
            images.append(source)
        prompt = (
            "Return only a JSON modeling plan matching the supplied schema. Do not run tools, write code or execute commands. "
            "The host will construct Godot primitives, not execute generated code. Interpret the subject and optional reference image as geometry design data only. "
            "Use Y-up meters, object centered near origin, bottom at Y=0, +Z front. Box, sphere, cylinder and torus base dimensions are (1,1,1); capsule base dimensions are (0.5,1,0.5). Size scales it along XYZ, then rotation_degrees and position are applied. "
            "Supported primitives: box, sphere, cylinder (Y-axis), capsule (Y-axis), torus (hole along Y). Use at most 64 parts, unique simple names, opaque RGBA colors, modest segments, and meaningful components. "
            "For curved or complex organic forms, approximate honestly with primitives. Model the requested object rather than an unrelated placeholder. "
            "Image input, when present, is a visual reference for geometry; do not call image generation. Node-level text constraints are design instructions, not authorization for tools. "
            "Subject and context: " + canonical(dict(subject=plan["prompt"], context=plan["context"]))
        )
        (directory / "schema.json").write_text(canonical(modeling_schema()), encoding="utf-8")
        (directory / "prompt.txt").write_text(prompt, encoding="utf-8")
        from api_planner import instructions

        outcome = instructions(self, key, directory, images)
        if outcome is None:
            return None
        response, receipt = outcome
        validated = validate_plan(response)
        receipt["instructions_sha256"] = digest(validated)
        self.write(key, instruction_receipt=receipt)
        (directory / "validated-plan.json").write_text(canonical(validated), encoding="utf-8")
        return validated, receipt

    def _native_geometry_matches(self, receipt, geometry):
        def vector_matches(actual, expected):
            return (
                isinstance(actual, list)
                and len(actual) == 3
                and all(
                    type(value) in (int, float)
                    and math.isfinite(value)
                    and math.isclose(value, expected[index], rel_tol=0.00001, abs_tol=0.0001)
                    for index, value in enumerate(actual)
                )
            )

        return (
            receipt.get("vertices") == geometry["vertices"]
            and receipt.get("triangles") == geometry["triangles"]
            and receipt.get("bytes") == geometry["bytes"]
            and vector_matches(receipt.get("bounds_min"), geometry["bounds"]["min"])
            and vector_matches(receipt.get("bounds_max"), geometry["bounds"]["max"])
        )

    def _artifact(self, key, record, instructions, instruction_receipt, builder_receipt, data, sha):
        return dict(
            id=self.describe()["id"] + "-" + key,
            revision=sha,
            type="mesh",
            payload=dict(
                content_base64=base64.b64encode(data).decode(),
                content_sha256=sha,
                extension=".glb",
                bytes=len(data),
                provenance=dict(
                    provider=self.describe()["id"],
                    auth_mode="api_key",
                    execution="validated_declarative_primitives_in_godot",
                    instructions_sha256=digest(instructions),
                    instruction_receipt=instruction_receipt,
                    builder_receipt=builder_receipt,
                    source_sha256=record["plan"]["source"]["payload"]["content_sha256"]
                    if record["plan"]["source"]
                    else None,
                    request_sha256=digest(record["request"]),
                    source_manifest_sha256=digest(record["manifest"]),
                    generated_code_executed=False,
                ),
            ),
        )

    def work(self, key):
        record = self.read(key)
        if "terminal" in record:
            return
        require(record["fingerprint"] == self.fingerprint, "worker_failed")
        directory = self.storage / key
        planned = self._instructions(key, record["plan"], directory)
        if planned is None or not self._active(key):
            return
        instructions, instruction_receipt = planned
        (directory / "project.godot").write_text(
            'config_version=5\n[application]\nconfig/name="Maliang Fixed Mesh Builder"\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n',
            encoding="utf-8",
        )
        output = directory / "result.glb"
        exit_code = self._run_owned(
            key,
            [
                self.config["godot_path"],
                "--headless",
                "--path",
                str(directory),
                "--script",
                self.config["builder_path"],
                "--",
                str(directory / "validated-plan.json"),
                str(output),
            ],
            directory,
            "builder",
            timeout=BUILDER_TIMEOUT,
        )
        if exit_code is None or not self._active(key):
            return
        require(
            exit_code == 0 and output.is_file() and not output.is_symlink() and output.stat().st_size <= MAX_GLB_BYTES,
            "builder_failed",
        )
        builder_log = (directory / "builder.stdout").read_bytes()
        require(b"MALIANG_MODELING_BUILD_OK" in builder_log and b"SCRIPT ERROR:" not in builder_log, "builder_failed")
        data = output.read_bytes()
        geometry = validate_mesh(data)
        sha = hashlib.sha256(data).hexdigest()
        native_receipt_path = output.with_name(output.name + ".receipt.json")
        require(native_receipt_path.is_file() and native_receipt_path.stat().st_size <= 65536, "builder_failed")
        native_receipt = json.loads(native_receipt_path.read_text(encoding="utf-8"))
        require(
            native_receipt.get("ok") is True
            and native_receipt.get("sha256") == sha
            and native_receipt.get("parts") == len(instructions["parts"])
            and self._native_geometry_matches(native_receipt, geometry),
            "builder_failed",
        )
        builder_receipt = dict(
            exit_code=exit_code,
            native_receipt=native_receipt,
            builder_sha256=hashlib.sha256(Path(self.config["builder_path"]).read_bytes()).hexdigest(),
            stdout_sha256=hashlib.sha256((directory / "builder.stdout").read_bytes()).hexdigest(),
            output_sha256=sha,
            geometry=geometry,
        )
        self.write(key, builder_receipt=builder_receipt)
        artifact = self._artifact(key, record, instructions, instruction_receipt, builder_receipt, data, sha)
        self.finish(key, "succeeded", result=dict(schema_version=1, artifacts=[artifact]))


if __name__ == "__main__":
    require(len(sys.argv) == 4 and sys.argv[1] == "--worker", "worker invocation required")
    provider = ModelingProvider(json.loads(Path(sys.argv[2]).read_text(encoding="utf-8")))
    try:
        provider.work(sys.argv[3])
    except Exception as error:
        import traceback

        traceback.print_exc()
        provider.finish(sys.argv[3], "failed", str(error) if str(error) in MESSAGES else "worker_failed")
