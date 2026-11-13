"""Synthetic plans and fake transport only; these tests never call AI inference."""

import base64
import copy
import hashlib
import json
import os
import shutil
import struct
import subprocess
import tempfile
import threading
import time
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

from comfy_provider import register
from editor_host import compile_graph
from executor import Executor, snapshot_file
from extensions import NodeRegistry, canonical
from kimi_provider import (
    DEFAULT_ENDPOINT,
    DEFAULT_MODEL,
    KimiNativeProvider,
    factory,
    perform_api,
    probe,
    request_body,
    validate_endpoint,
)
from modeling_provider import validate_mesh, validate_plan

KEY = "b" * 64
SECRET = "synthetic-kimi-secret-not-a-real-credential"
PLAN = {
    "version": 1,
    "name": "SyntheticTable",
    "parts": [
        {
            "name": "Top",
            "primitive": "box",
            "position": [0, 1, 0],
            "rotation_degrees": [0, 0, 0],
            "size": [2, 0.1, 1],
            "color": [0.4, 0.2, 0.1, 1],
        }
    ],
}


def response_bytes(plan=None, **changes):
    choice = {
        "finish_reason": "stop",
        "message": {
            "role": "assistant",
            "content": canonical(plan or PLAN),
            "reasoning_content": "not the structured result",
        },
    }
    choice.update(changes.pop("choice", {}))
    value = {
        "id": "chatcmpl-synthetic-fixture",
        "model": DEFAULT_MODEL,
        "choices": [choice],
        "usage": {
            "prompt_tokens": 11,
            "completion_tokens": 7,
            "total_tokens": 18,
            "completion_tokens_details": {"reasoning_tokens": 3},
        },
    }
    value.update(changes)
    return json.dumps(value).encode()


class FakeResponse:
    def __init__(self, data):
        self.data = data
        self.status = 200

    def read(self, _limit=-1):
        return self.data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeOpener:
    def __init__(self, data):
        self.data = data
        self.calls = []

    def open(self, request, timeout):
        self.calls.append((request, timeout))
        return FakeResponse(self.data)


def png_bytes():
    def chunk(kind, body):
        checksum = zlib.crc32(kind + body) & 0xFFFFFFFF
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", checksum)

    header = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00\xff"))
        + chunk(b"IEND", b"")
    )


def triangle_glb(indices=(0, 1, 2), positions=((0, 0, 0), (1, 0, 0), (0, 1, 1)), node=None):
    binary = b"".join(struct.pack("<fff", *point) for point in positions)
    position_view = {"buffer": 0, "byteOffset": 0, "byteLength": len(binary)}
    views = [position_view]
    accessors = [{"bufferView": 0, "componentType": 5126, "count": len(positions), "type": "VEC3"}]
    primitive = {"attributes": {"POSITION": 0}, "mode": 4}
    if indices is not None:
        offset = len(binary)
        binary += b"".join(struct.pack("<H", index) for index in indices)
        views.append({"buffer": 0, "byteOffset": offset, "byteLength": len(indices) * 2})
        accessors.append({"bufferView": 1, "componentType": 5123, "count": len(indices), "type": "SCALAR"})
        primitive["indices"] = 1
    document = {
        "asset": {"version": "2.0"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [dict(mesh=0, **(node or {}))],
        "meshes": [{"primitives": [primitive]}],
        "buffers": [{"byteLength": len(binary)}],
        "bufferViews": views,
        "accessors": accessors,
    }
    encoded = json.dumps(document, separators=(",", ":")).encode()
    encoded += b" " * ((-len(encoded)) % 4)
    binary += b"\x00" * ((-len(binary)) % 4)
    length = 12 + 8 + len(encoded) + 8 + len(binary)
    return (
        b"glTF"
        + struct.pack("<II", 2, length)
        + struct.pack("<II", len(encoded), 0x4E4F534A)
        + encoded
        + struct.pack("<II", len(binary), 0x004E4942)
        + binary
    )


class RequestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="kimi-api-fixture-")
        self.directory = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def plan(self, source=None):
        return dict(prompt="a simple four leg wooden table", source=source, context=[], model=DEFAULT_MODEL)

    def api(self, data, body=None):
        directory = self.directory / str(len(list(self.directory.iterdir())))
        directory.mkdir()
        body = body or request_body(self.plan())
        (directory / "api-request.json").write_text(canonical(body), encoding="utf-8")
        opener = FakeOpener(data)
        with patch.dict(os.environ, {"KIMI_API_KEY": SECRET}), patch("kimi_provider._opener", return_value=opener):
            code = perform_api({"endpoint": DEFAULT_ENDPOINT, "model": DEFAULT_MODEL}, directory)
        return code, directory, opener

    def test_model_catalog_does_not_require_a_legacy_selection(self):
        opener = FakeOpener(json.dumps({"data": [{"id": DEFAULT_MODEL}]}).encode())
        with patch.dict(os.environ, {"KIMI_API_KEY": SECRET}), patch("kimi_provider._opener", return_value=opener):
            report = probe({"endpoint": DEFAULT_ENDPOINT, "model": ""})
        self.assertTrue(report["connected"])
        self.assertEqual(report["requested_model"], "")
        self.assertEqual(report["available_models"], [DEFAULT_MODEL])
        self.assertEqual(len(opener.calls), 1)

    def test_strict_text_request_and_response_receipt(self):
        body = request_body(self.plan())
        self.assertEqual(body["model"], DEFAULT_MODEL)
        self.assertEqual(body["reasoning_effort"], "low")
        self.assertFalse(body["stream"])
        self.assertTrue(body["response_format"]["json_schema"]["strict"])
        self.assertEqual(body["response_format"]["type"], "json_schema")
        self.assertNotIn("temperature", body)
        self.assertNotIn("top_p", body)
        self.assertNotIn("tools", body)
        self.assertIsInstance(body["messages"][0]["content"], list)
        code, directory, opener = self.api(response_bytes(), body=body)
        self.assertEqual(code, 0)
        self.assertEqual(len(opener.calls), 1)
        request, _ = opener.calls[0]
        self.assertEqual(request.full_url, DEFAULT_ENDPOINT + "/chat/completions")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("Authorization"), "Bearer " + SECRET)
        receipt = json.loads((directory / "api-receipt.json").read_text())
        self.assertEqual(receipt["response_id"], "chatcmpl-synthetic-fixture")
        self.assertEqual(receipt["model"], DEFAULT_MODEL)
        self.assertEqual(receipt["usage"]["reasoning_tokens"], 3)
        self.assertEqual(validate_plan(json.loads((directory / "api-plan.json").read_text())), PLAN)
        for path in directory.iterdir():
            self.assertNotIn(SECRET, path.read_bytes().decode("utf-8", "replace"))

    def test_image_request_uses_base64_data_url(self):
        data = png_bytes()
        source = {
            "payload": {
                "content_base64": base64.b64encode(data).decode(),
                "content_sha256": hashlib.sha256(data).hexdigest(),
                "extension": ".png",
            }
        }
        body = request_body(self.plan(source))
        content = body["messages"][0]["content"]
        self.assertEqual(content[1]["type"], "image_url")
        self.assertEqual(content[1]["image_url"]["url"], "data:image/png;base64," + base64.b64encode(data).decode())
        self.assertNotIn("image_base64", content[1])

    def test_content_not_reasoning_is_the_only_plan_source(self):
        other = copy.deepcopy(PLAN)
        other["name"] = "WrongReasoningPlan"
        response = response_bytes()
        document = json.loads(response)
        document["choices"][0]["message"]["reasoning_content"] = canonical(other)
        code, directory, _ = self.api(json.dumps(document).encode())
        self.assertEqual(code, 0)
        self.assertEqual(json.loads((directory / "api-plan.json").read_text())["name"], "SyntheticTable")

    def test_truncated_tool_empty_and_semantically_invalid_outputs_fail_closed(self):
        cases = [
            response_bytes(choice={"finish_reason": "length"}),
            response_bytes(
                choice={
                    "message": {
                        "role": "assistant",
                        "content": canonical(PLAN),
                        "tool_calls": [{"id": "x"}],
                    }
                }
            ),
            response_bytes(choice={"message": {"role": "assistant", "content": ""}}),
            response_bytes(choice={"message": {"role": "assistant", "content": "not-json"}}),
            response_bytes(plan=dict(PLAN, generated_code="print('forbidden')")),
            b'{"id":"truncated"',
        ]
        for data in cases:
            with self.subTest(data=data[:80]):
                code, directory, opener = self.api(data)
                self.assertEqual(code, 1)
                self.assertEqual(len(opener.calls), 1)
                self.assertFalse((directory / "api-plan.json").exists())
                self.assertFalse(json.loads((directory / "api-receipt.json").read_text())["ok"])

    def test_official_endpoint_allowlist_refuses_credential_or_redirect_targets(self):
        for endpoint in (
            "http://api.kimi.com/coding/v1",
            "https://user:secret@api.kimi.com/coding/v1",
            "https://api.kimi.com/coding/v1/chat/completions",
            "https://api.kimi.com/coding/v1?token=secret",
            "https://agent-gw.kimi.com/coding",
            "https://example.com/coding/v1",
        ):
            with self.subTest(endpoint=endpoint), self.assertRaisesRegex(ValueError, "kimi_endpoint_invalid"):
                validate_endpoint(endpoint)
        self.assertEqual(validate_endpoint(DEFAULT_ENDPOINT + "/"), DEFAULT_ENDPOINT)


class GeometryTests(unittest.TestCase):
    def test_indexed_triangle_statistics_and_transformed_bounds(self):
        data = triangle_glb(node={"translation": [10, 0, -1], "scale": [2, 3, 4]})
        result = validate_mesh(data)
        self.assertEqual(result["vertices"], 3)
        self.assertEqual(result["triangles"], 1)
        self.assertEqual(result["primitives"], 1)
        self.assertEqual(result["bounds"]["min"], [10, 0, -1])
        self.assertEqual(result["bounds"]["max"], [12, 3, 3])

    def test_nonindexed_triangle_is_supported(self):
        result = validate_mesh(triangle_glb(indices=None))
        self.assertEqual(result["triangles"], 1)

    def test_invalid_index_degenerate_and_incomplete_triangles_are_rejected(self):
        for indices, positions in (
            ((0, 1, 3), ((0, 0, 0), (1, 0, 0), (0, 1, 1))),
            ((0, 1, 1), ((0, 0, 0), (1, 0, 0), (0, 1, 1))),
            ((0, 1, 2, 0), ((0, 0, 0), (1, 0, 0), (0, 1, 1))),
            (None, ((0, 0, 0), (1, 0, 0), (0, 1, 1), (1, 1, 1))),
        ):
            with self.subTest(indices=indices, positions=positions), self.assertRaisesRegex(ValueError, "mesh_invalid"):
                validate_mesh(triangle_glb(indices=indices, positions=positions))


class ProviderTests(unittest.TestCase):
    """Synthetic plan + synthetic GLB exercise durable Executor code, not model quality."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="kimi-provider-fixture-")
        self.root = Path(self.tmp.name)
        self.godot = self.root / "godot-fixture"
        self.builder = self.root / "builder-fixture.gd"
        self.godot.write_bytes(b"fixture")
        self.builder.write_text("# synthetic fixture; no Godot invoked in this unit test\n", encoding="utf-8")
        self.config = dict(
            endpoint=DEFAULT_ENDPOINT,
            model=DEFAULT_MODEL,
            storage=str(self.root / "state"),
            godot_path=str(self.godot),
            builder_path=str(self.builder),
        )
        self.provider = KimiNativeProvider(self.config)
        self.request = dict(
            node="text_to_mesh",
            version="1",
            inputs={},
            parameters={"prompt": "four leg table", "seed": 42, "steps": 20},
            context=[],
        )
        self.manifest = dict(schema_version=1, artifacts=[])

    def tearDown(self):
        with self.provider.db() as db:
            keys = [row[0] for row in db.execute("SELECT key FROM jobs")]
        for key in keys:
            self.provider.cancel(key)
        self.tmp.cleanup()

    def auth(self):
        return dict(connected=True, code="", version="", auth_mode="environment_api_key")

    def submit_without_worker(self, provider=None):
        provider = provider or self.provider
        with (
            patch("kimi_provider.check_kimi", return_value=self.auth()),
            patch("modeling_provider.subprocess.Popen") as popen,
        ):
            popen.return_value.poll.return_value = 0
            return provider.submit(self.request, self.manifest, KEY)

    def build_synthetic_result(self, key):
        data = triangle_glb()
        geometry = validate_mesh(data)
        sha = hashlib.sha256(data).hexdigest()
        receipt = dict(
            ok=True,
            parts=1,
            vertices=geometry["vertices"],
            triangles=geometry["triangles"],
            bytes=geometry["bytes"],
            bounds_min=geometry["bounds"]["min"],
            bounds_max=geometry["bounds"]["max"],
            sha256=sha,
        )

        def instructions(_key, _plan, _directory):
            return copy.deepcopy(PLAN), dict(
                response_id="chatcmpl-synthetic-fixture",
                model=DEFAULT_MODEL,
                request_sha256="a" * 64,
                response_sha256="b" * 64,
                instructions_sha256="c" * 64,
                usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            )

        def builder(_key, _arguments, directory, _label, **_kwargs):
            (directory / "result.glb").write_bytes(data)
            (directory / "result.glb.receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
            (directory / "builder.stdout").write_text("MALIANG_MODELING_BUILD_OK synthetic\n", encoding="utf-8")
            (directory / "builder.stderr").write_text("", encoding="utf-8")
            return 0

        with (
            patch.object(self.provider, "_instructions", side_effect=instructions),
            patch.object(self.provider, "_run_owned", side_effect=builder),
        ):
            self.provider.work(key)

    def test_executor_recovers_written_provider_result_without_resubmission(self):
        graph, manifest = compile_graph({
            "nodes": [
                dict(
                    id="generate",
                    type="text_to_mesh",
                    provider="kimi_native",
                    parameters=self.request["parameters"],
                )
            ],
            "edges": [],
        })
        registry = NodeRegistry()
        register(registry)
        host = Executor(self.root / "executor.sqlite", registry, {"kimi_native": self.provider})
        try:
            run = host.create(graph, manifest)
            with (
                patch("kimi_provider.check_kimi", return_value=self.auth()),
                patch("modeling_provider.subprocess.Popen") as popen,
            ):
                popen.return_value.poll.return_value = 0
                state = host.step(run)
            self.assertIn(state["state"], ("queued", "running"))
            key = state["nodes"]["generate"]["idempotency_key"]
            self.build_synthetic_result(key)
            # Provider terminal/result already exist, but Executor has not persisted its receipt yet.
            state = host.step(run)
            self.assertEqual(state["state"], "succeeded")
            exported = host.export(run)
            artifact = exported["manifest"]["artifacts"][-1]
            provenance = artifact["payload"]["provenance"]
            self.assertEqual(provenance["provider"], "kimi_native")
            self.assertEqual(provenance["model"], DEFAULT_MODEL)
            self.assertEqual(
                provenance["generation_stages"],
                ["kimi_strict_modeling_plan", "fixed_godot_primitive_construction"],
            )
            self.assertFalse(provenance["generated_code_executed"])
            self.assertFalse(provenance["fallback_used"])
            self.assertEqual(provenance["parameters_not_applied"], {"seed": "not_applied", "steps": "not_applied"})
            self.assertEqual(provenance["builder_receipt"]["geometry"]["triangles"], 1)
            with patch("kimi_provider.check_kimi", side_effect=AssertionError("idempotent submit probed again")):
                self.assertEqual(self.provider.submit(self.request, self.manifest, key)["state"], "succeeded")
            before = host.export(run)
            self.build_synthetic_result(key)
            self.assertEqual(host.export(run), before)
            self.assertEqual(self.provider.cancel(key)["state"], "succeeded")
        finally:
            host.close()

    def test_cancellation_terminates_only_owned_api_child_and_blocks_late_result(self):
        self.assertIn(self.submit_without_worker()["state"], ("queued", "running"))
        directory = self.root / "state" / KEY
        outcome = []

        def run():
            outcome.append(
                self.provider._run_owned(
                    KEY,
                    [os.environ.get("PYTHON", "python"), "-c", "import time; time.sleep(30)"],
                    directory,
                    "api",
                    timeout=30,
                    error_codes=("api_timeout", "api_output_invalid"),
                )
            )

        thread = threading.Thread(target=run)
        thread.start()
        deadline = time.monotonic() + 5
        while not (directory / "api.stdout").exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertEqual(self.provider.cancel(KEY)["state"], "cancelled")
        thread.join(10)
        self.assertFalse(thread.is_alive())
        self.assertEqual(outcome, [None])
        self.build_synthetic_result(KEY)
        self.assertEqual(self.provider.poll(KEY)["state"], "cancelled")

    def test_factory_and_saved_config_contain_no_secret_or_other_provider(self):
        config_path = self.root / "kimi.json"
        config_path.write_text(json.dumps(dict(self.config, storage="relative-state")), encoding="utf-8")
        with patch.dict(os.environ, {"AINATIVE_KIMI_CONFIG": str(config_path), "KIMI_API_KEY": SECRET}):
            registry, providers = factory()
        self.assertIn("kimi_native", providers)
        self.assertNotIn("comfy", providers)
        self.assertNotIn("codex", providers)
        self.assertIsNotNone(registry.get("text_to_mesh", "1"))
        persisted = self.root / "state" / KEY / "config.json"
        if persisted.exists():
            self.assertNotIn(SECRET, persisted.read_text())
        self.assertNotIn("api_key", config_path.read_text())
        self.assertNotIn("KIMI_API_KEY", json.dumps(self.provider.config))

    def test_strict_image_validation_and_multiple_image_rejection(self):
        source = self.root / "reference.png"
        source.write_bytes(png_bytes())
        snapshot = dict(snapshot_file(source), extension=".png")
        manifest = dict(
            schema_version=1,
            artifacts=[dict(id="reference", revision=snapshot["content_sha256"], type="image", payload=snapshot)],
        )
        request = copy.deepcopy(self.request)
        request.update(
            node="image_to_mesh",
            inputs={"source": {"id": "reference", "revision": snapshot["content_sha256"]}},
            parameters={"prompt": "make the pictured object"},
        )
        plan = self.provider.plan(request, manifest)
        self.assertEqual(plan["source"]["payload"]["content_sha256"], snapshot["content_sha256"])
        request["context"] = [
            dict(
                role="reference",
                scope="node",
                strength="reference",
                artifact={"id": "reference", "revision": snapshot["content_sha256"]},
            )
        ]
        with self.assertRaisesRegex(ValueError, "unsupported_multiple_image_constraints"):
            self.provider.plan(request, manifest)


class RealGodotBuilderTests(unittest.TestCase):
    """A synthetic plan through the real fixed builder; still no AI inference."""

    def test_real_builder_exports_gl_b_with_matching_independent_geometry(self):
        root = Path(__file__).resolve().parents[2]
        godot = Path(os.environ.get("AINATIVE_TEST_GODOT", root / "bin/godot.windows.editor.x86_64.exe"))
        builder = root / "samples/ainative-workbench/addons/ainative/modeling_builder.gd"
        if not godot.is_file() and shutil.which("godot"):
            godot = Path(shutil.which("godot"))
        if not godot.is_file() or not builder.is_file():
            self.skipTest("Real Godot and fixed builder required")
        with tempfile.TemporaryDirectory(prefix="kimi-real-builder-") as temporary:
            directory = Path(temporary)
            plan_path = directory / "plan.json"
            output = directory / "result.glb"
            plan_path.write_text(canonical(PLAN), encoding="utf-8")
            (directory / "project.godot").write_text(
                'config_version=5\n[application]\nconfig/name="Synthetic Kimi Builder Test"\n'
                '[rendering]\nrenderer/rendering_method="gl_compatibility"\n',
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    str(godot),
                    "--headless",
                    "--path",
                    str(directory),
                    "--script",
                    str(builder),
                    "--",
                    str(plan_path),
                    str(output),
                ],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                timeout=90,
            )
            self.assertEqual(completed.returncode, 0, (completed.stdout + completed.stderr).decode("utf-8", "replace"))
            self.assertIn(b"MALIANG_MODELING_BUILD_OK", completed.stdout)
            geometry = validate_mesh(output.read_bytes())
            receipt = json.loads((directory / "result.glb.receipt.json").read_text())
            self.assertGreater(geometry["triangles"], 0)
            self.assertEqual(receipt["vertices"], geometry["vertices"])
            self.assertEqual(receipt["triangles"], geometry["triangles"])
            self.assertEqual(receipt["sha256"], hashlib.sha256(output.read_bytes()).hexdigest())
            bounds = (
                (receipt["bounds_min"], geometry["bounds"]["min"]),
                (receipt["bounds_max"], geometry["bounds"]["max"]),
            )
            for native, independent in bounds:
                for actual, expected in zip(native, independent):
                    self.assertAlmostEqual(actual, expected, places=4)


if __name__ == "__main__":
    unittest.main()
