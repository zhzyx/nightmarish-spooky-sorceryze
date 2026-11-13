"""Local HTTP infrastructure checks, not real-model inference acceptance."""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from comfy_provider import ComfyProvider, factory
from editor_host import dispatch
from executor import snapshot_file
from generation_service import (
    IMAGE_NODES,
    KINDS,
    MESH_NODES,
    ServiceError,
    check_service,
    failure,
    load_settings,
    run_service,
    settings,
)


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.requests = []
        self.info = {key: {} for key in IMAGE_NODES | MESH_NODES | {"ImageScale", "VAEEncode"}}
        self.info["CheckpointLoaderSimple"] = {"input": {"required": {"ckpt_name": [["images/model.safetensors"]]}}}
        self.info["ImageOnlyCheckpointLoader"] = {"input": {"required": {"ckpt_name": [["mesh.safetensors"]]}}}
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def send(self, value, status=200):
                self.send_response(status)
                self.end_headers()
                self.wfile.write(json.dumps(value).encode())

            def do_GET(self):
                owner.requests.append(("GET", self.path))
                if self.path == "/object_info":
                    self.send(owner.info)
                elif self.path == "/system_stats":
                    self.send({"system": {"comfyui_version": "test-infrastructure"}})
                elif self.path.startswith("/history"):
                    self.send({})
                elif self.path == "/queue":
                    self.send({"queue_pending": [], "queue_running": []})
                else:
                    self.send({}, 404)

            def do_POST(self):
                owner.requests.append(("POST", self.path))
                self.rfile.read(int(self.headers.get("Content-Length", 0)))
                self.send({"prompt_id": "infrastructure-only"})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.config = dict(
            schema_version=1,
            mode="comfy",
            endpoint="http://127.0.0.1:" + str(self.server.server_port),
            image_model="images/model.safetensors",
            mesh_model="mesh.safetensors",
        )
        self.file = self.root / "service.json"
        self.file.write_text(json.dumps(self.config))
        self.args = argparse.Namespace(
            db=str(self.root / "runs.sqlite"),
            factory="editor_demo:factory",
            command="create",
            service_config=str(self.file),
        )

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.tmp.cleanup()

    def model(self, kind="text_to_image"):
        return dict(nodes=[dict(id="gen", type=kind, provider="comfy", parameters={"prompt": "a stone owl"})], edges=[])

    def test_detection_get_only_discovery_no_model_autoselection(self):
        report = check_service(self.config)
        self.assertTrue(report["connected"])
        self.assertEqual(report["models"]["image"], ["images/model.safetensors"])
        self.assertTrue(all(state["ready"] for state in report["capabilities"].values()))
        report = check_service({**self.config, "image_model": "", "mesh_model": ""})
        self.assertTrue(report["connected"])
        self.assertTrue(all(state["ready"] for state in report["capabilities"].values()))
        self.assertEqual(report["models"]["mesh"], ["mesh.safetensors"])
        self.assertTrue(all(method == "GET" for method, _ in self.requests))
        self.assertFalse(any(route in ("/prompt", "/upload/image") for _, route in self.requests))

    def test_direct_codex_mesh_runs_without_cli(self):
        config = {**self.config, "mode": "codex", "image_model": "", "cli_path": str(self.root / "no-cli")}
        report = check_service(config)
        self.assertTrue(report["connected"])
        self.assertTrue(report["capabilities"]["image_to_mesh"]["ready"])
        self.assertFalse(report["capabilities"]["text_to_mesh"]["ready"])

        self.file.write_text(json.dumps(config))
        source = self.root / "mesh-input.png"
        source.write_bytes(b"\x89PNG\r\n\x1a\nfixture")
        model = self.model("image_to_mesh")
        model["nodes"][0].update(source=str(source), parameters={})
        with patch("codex_provider.check_cli", side_effect=AssertionError("Direct mesh contacted the CLI")):
            run = dispatch(self.args, {"model": model})["run_id"]
        self.assertEqual(run_service(self.args.db, run)["mode"], "codex")

    def test_mesh_only_needs_no_image_model(self):
        self.info = {key: value for key, value in self.info.items() if key in MESH_NODES}
        report = check_service({**self.config, "image_model": ""})
        self.assertTrue(report["capabilities"]["image_to_mesh"]["ready"])
        self.assertFalse(report["capabilities"]["text_to_mesh"]["ready"])
        source = self.root / "image.png"
        source.write_bytes(b"\x89PNG\r\n\x1a\nfixture")
        self.file.write_text(json.dumps({**self.config, "image_model": ""}))
        model = self.model("image_to_mesh")
        model["nodes"][0].update(source=str(source), parameters={})
        run = dispatch(self.args, {"model": model})["run_id"]
        snapshot = run_service(self.args.db, run)
        self.assertEqual(snapshot["provider"]["checkpoints"]["image"], {"name": "", "sha256": None})
        # Adding text requests an image edit before mesh generation.
        model["nodes"][0]["text"] = "make it red"
        with self.assertRaises(ServiceError):
            dispatch(self.args, {"model": model})

    def test_exact_capability_missing_nodes_and_models(self):
        self.info.pop("SaveGLB")
        report = check_service(self.config)
        self.assertEqual(report["capabilities"]["image_to_mesh"]["code"], "service_nodes_missing")
        self.assertIn("SaveGLB", report["capabilities"]["image_to_mesh"]["missing_nodes"])
        self.assertTrue(report["capabilities"]["text_to_image"]["ready"])
        self.info["SaveGLB"] = {}
        self.info["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"] = [[]]
        report = check_service({**self.config, "image_model": "removed.safetensors", "mesh_model": "removed.safetensors"})
        self.assertEqual(report["models"], {"image": [], "mesh": ["mesh.safetensors"]})
        self.assertTrue(report["capabilities"]["text_to_image"]["ready"])
        self.assertTrue(report["capabilities"]["text_to_mesh"]["ready"])
        self.assertTrue(report["capabilities"]["image_to_mesh"]["ready"])

    def test_frozen_settings_run_identity_and_no_fake_hashes(self):
        first = dispatch(self.args, {"model": self.model()})["run_id"]
        second = dispatch(self.args, {"model": self.model()})["run_id"]
        snapshot = run_service(self.args.db, first)
        self.assertIsNone(snapshot["provider"]["checkpoints"]["image"]["sha256"])
        self.assertNotEqual(
            snapshot["provider"]["backend_revision"], run_service(self.args.db, second)["provider"]["backend_revision"]
        )
        self.file.write_text(json.dumps({"mode": "offline"}))
        self.args.command = "step"
        state = dispatch(self.args, {"run": first})
        self.assertEqual(state["nodes"]["gen"]["state"], "queued")
        self.assertEqual([route for method, route in self.requests if method == "POST"], ["/prompt"])
        state = dispatch(self.args, {"run": first})
        self.assertEqual(state["nodes"]["gen"]["state"], "running")
        self.assertEqual([route for method, route in self.requests if method == "POST"], ["/prompt"])

    def test_reloaded_config_without_environment_and_offline_copy(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(load_settings(self.file), self.config)
            run = dispatch(self.args, {"model": self.model()})["run_id"]
            self.assertTrue(run)
        self.file.write_text(json.dumps({"mode": "offline"}))
        with self.assertRaisesRegex(ServiceError, "真实生成服务"):
            dispatch(self.args, {"model": self.model()})
        image = self.root / "copy.png"
        image.write_bytes(b"\x89PNG\r\n\x1a\nfixture")
        model = dict(nodes=[dict(id="copy", type="copy", source=str(image), parameters={"delay": 0})], edges=[])
        run = dispatch(self.args, {"model": model})["run_id"]
        self.args.command = "step"
        self.assertEqual(dispatch(self.args, {"run": run})["state"], "succeeded")

    def test_missing_inputs_checked_before_any_connection(self):
        model = self.model("image_to_mesh")
        with self.assertRaises(ServiceError) as context:
            dispatch(self.args, {"model": model})
        self.assertEqual(context.exception.code, "source_missing")
        self.assertEqual(self.requests, [])
        model = self.model()
        model["nodes"][0]["parameters"] = {}
        with self.assertRaises(ServiceError) as context:
            dispatch(self.args, {"model": model})
        self.assertEqual(context.exception.code, "prompt_missing")
        self.assertEqual(self.requests, [])
        # Target pruning remains ahead of input checks.
        model = self.model()
        model["nodes"].append(dict(id="unused", type="image_to_mesh", parameters={}))
        self.assertTrue(dispatch(self.args, {"model": model, "target": "gen"})["run_id"])

    def test_wrong_address_offline_protocol_and_redacted_errors(self):
        for endpoint in ("file:///secret", "http://user:secret@localhost:1", "http://localhost:1/path?secret=value"):
            report = check_service({**self.config, "endpoint": endpoint})
            self.assertEqual(report["code"], "service_address_invalid")
            self.assertNotIn("secret", json.dumps(report))
        self.info = {"unrelated": {}}
        self.assertEqual(check_service(self.config)["code"], "service_protocol_invalid")
        report = check_service({**self.config, "endpoint": "http://127.0.0.1:1"})
        self.assertEqual(report["code"], "service_unreachable")
        error = failure(ValueError("secret-token-and-private-path"))
        self.assertNotIn("secret-token", json.dumps(error))
        self.assertTrue(all(not state["ready"] for state in report["capabilities"].values()))
        self.assertEqual(set(report["capabilities"]), set(KINDS))
        with self.assertRaises(ServiceError):
            settings({"mode": "comfy", "api_key": "secret"})

    def test_real_cli_check_and_structured_create_error(self):
        spec = self.root / "spec.json"
        result = self.root / "result.json"
        spec.write_text(json.dumps({"service": self.config}))
        cli = [sys.executable, str(Path(__file__).with_name("editor_host.py"))]
        arguments = ["--db", self.args.db, "--spec", str(spec), "--result", str(result)]
        subprocess.run([*cli, "service-check", *arguments], check=True)
        self.assertTrue(json.loads(result.read_text())["result"]["connected"])
        self.assertTrue(all(method == "GET" for method, _ in self.requests))
        spec.write_text(json.dumps({"model": self.model()}))
        completed = subprocess.run([*cli, "create", *arguments], check=False)
        self.assertNotEqual(completed.returncode, 0)
        error = json.loads(result.read_text())
        self.assertEqual(error["error"], "service_not_configured")
        self.assertIn("本机设置", error["message"])

    def test_legacy_hashes_and_environment_factory_remain_supported(self):
        legacy = dict(
            endpoint=self.config["endpoint"],
            storage="legacy-state",
            backend_revision="known-deployment",
            checkpoints={role: dict(name=role + ".safetensors", sha256="a" * 64) for role in ("image", "mesh")},
        )
        file = self.root / "legacy.json"
        file.write_text(json.dumps(legacy))
        with patch.dict(os.environ, {"AINATIVE_COMFY_CONFIG": str(file)}):
            registry, providers = factory()
            self.assertEqual(providers["comfy"].config["checkpoints"], legacy["checkpoints"])
            self.assertEqual(providers["comfy"].describe(), factory()[1]["comfy"].describe())
            self.assertTrue(registry.get("image_to_mesh", "1"))
        with patch.dict(os.environ, {}, clear=True):
            self.assertTrue(factory(file)[0].get("text_to_image", "1"))
            with self.assertRaises(ServiceError) as context:
                factory()
            self.assertEqual(context.exception.code, "service_not_configured")
        unknown = {
            **legacy,
            "storage": str(self.root / "unknown"),
            "checkpoints": {role: dict(name=role + ".safetensors", sha256=None) for role in ("image", "mesh")},
        }
        with self.assertRaisesRegex(ValueError, "run-scoped identity"):
            ComfyProvider(unknown)

    def test_reference_conditioning_requires_exact_image_nodes_before_submission(self):
        source = self.root / "reference.png"
        source.write_bytes(b"\x89PNG\r\n\x1a\nfixture")
        snapshot = {**snapshot_file(source), "extension": ".png"}
        original = dict(self.info)
        for kind in ("text_to_image", "text_to_mesh"):
            for field, value in (("image_context", str(source)), ("image_context_snapshot", snapshot)):
                for missing in ("LoadImage", "ImageScale", "VAEEncode"):
                    with self.subTest(kind=kind, field=field, missing=missing):
                        self.info = {key: val for key, val in original.items() if key != missing}
                        model = self.model(kind)
                        model["nodes"][0][field] = value
                        # Baseline non-reference discovery remains available;
                        # the actual requested image-conditioning mode is not.
                        self.assertTrue(check_service(self.config)["capabilities"][kind]["ready"])
                        with self.assertRaises(ServiceError) as context:
                            dispatch(self.args, {"model": model})
                        self.assertEqual(context.exception.code, "service_nodes_missing")
                        self.assertIn(missing, failure(context.exception)["message"])
        self.assertFalse(any(method == "POST" for method, _ in self.requests))
        # Reference-conditioned generation never uses EmptyLatentImage.
        self.info = {key: val for key, val in original.items() if key != "EmptyLatentImage"}
        self.assertTrue(check_service(self.config)["capabilities"]["image_to_image"]["ready"])
        for kind in ("text_to_image", "text_to_mesh"):
            model = self.model(kind)
            model["nodes"][0]["image_context_snapshot"] = snapshot
            self.assertTrue(dispatch(self.args, {"model": model})["run_id"])

    def test_nested_checkpoint_selection_and_output_filename_protections(self):
        run = dispatch(self.args, {"model": self.model()})["run_id"]
        provider = ComfyProvider(run_service(self.args.db, run)["provider"])
        request = dict(node="text_to_image", version="1", inputs={}, parameters={"prompt": "a stone owl"}, context=[])
        graph, _ = provider.build(request, {"schema_version": 1, "artifacts": []}, "a" * 64)
        self.assertEqual(graph["image_model"]["inputs"]["ckpt_name"], "images/model.safetensors")
        from comfy_provider import checkpoint_name, filename

        self.assertEqual(checkpoint_name("folder/model.safetensors"), "folder/model.safetensors")
        for name in ("../model.safetensors", "/models/model.safetensors", "folder/../model.safetensors"):
            with self.assertRaises(ValueError):
                checkpoint_name(name)
        # Generated outputs retain the original stricter same-folder rule.
        with self.assertRaises(ValueError):
            filename("folder/result.png")


if __name__ == "__main__":
    unittest.main()
