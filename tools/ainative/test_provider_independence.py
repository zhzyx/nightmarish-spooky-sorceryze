"""Local protocol fixtures only; never measures production model quality."""

import copy
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from extensions import canonical
from generation_service import capability, restore_provider, settings
from modeling_provider import ModelingProvider
from test_modeling_provider import BUILDER, GODOT, PLAN


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.responses = copy.deepcopy(PLAN)
        self.calls = []
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                owner.calls.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
                body = json.dumps(
                    dict(
                        model="fixture-model",
                        choices=[dict(finish_reason="stop", message=dict(content=json.dumps(owner.responses)))],
                    )
                ).encode()
                self.send_response(200)
                self.end_headers()
                self.wfile.write(body)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.env = patch.dict(os.environ, AINATIVE_FIXTURE_KEY="fixture-only", PATH="")
        self.env.start()
        self.config = dict(
            planner=dict(
                endpoint="http://127.0.0.1:" + str(self.server.server_port),
                model="explicit-fixture",
                key_env="AINATIVE_FIXTURE_KEY",
            ),
            storage=str(self.root / "state"),
            godot_path=str(GODOT if GODOT.is_file() else Path(sys.executable)),
            builder_path=str(BUILDER),
        )
        self.provider = ModelingProvider(self.config)
        self.request = dict(node="text_to_mesh", version="1", inputs={}, parameters=dict(prompt="table"), context=[])
        self.manifest = dict(schema_version=1, artifacts=[])
        self.key = "a" * 64

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.env.stop()
        self.tmp.cleanup()

    def seed(self):
        plan = self.provider.plan(self.request, self.manifest)
        with self.provider.db() as db:
            db.execute(
                "INSERT INTO jobs VALUES (?,?)", (self.key, canonical(dict(heartbeat=time.time(), stage="queued")))
            )
        directory = self.root / "job"
        directory.mkdir()
        return plan, directory

    def test_no_codex_import_or_executable_dependency(self):
        code = "import sys; sys.modules['codex_provider']=None; import kimi_provider, modeling_provider, sculpt_provider, api_planner; print('ok')"
        run = subprocess.run([sys.executable, "-c", code], cwd=Path(__file__).parent, capture_output=True)
        self.assertEqual(run.returncode, 0, run.stderr)

    def test_protocol_success_without_cli(self):
        plan, directory = self.seed()
        result, receipt = self.provider._instructions(self.key, plan, directory)
        self.assertEqual(result, PLAN)
        self.assertEqual(receipt["observed_model"], "fixture-model")
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.calls[0]["model"], "explicit-fixture")
        self.assertNotIn("fixture-only", "".join(p.read_text() for p in directory.glob("*.json")))
        self.assertEqual(self.provider.describe()["id"], "api-modeling")

    def test_explicit_gpt_api_is_rejected_before_auth_or_request(self):
        from api_planner import validate_config

        for endpoint, model in (
            ("https://api.openai.com/v1", "custom-deployment"),
            ("https://eu.api.openai.com/v1", "custom-deployment"),
            ("https://tenant.openai.azure.com/v1", "custom-deployment"),
            ("https://other.example/v1", "openai/gpt-5.1"),
            ("https://other.example/v1", "GPT-5.1-codex"),
            ("https://other.example/v1", "chatgpt-4o-latest"),
            ("https://other.example/v1", "ft:gpt-4.1-mini:account:model:id"),
        ):
            planner = dict(self.config["planner"], endpoint=endpoint, model=model)
            with self.subTest(model=model, endpoint=endpoint):
                with self.assertRaisesRegex(ValueError, "gpt_modeling_retired"):
                    validate_config(planner)
                with self.assertRaisesRegex(ValueError, "gpt_modeling_retired"):
                    ModelingProvider(dict(self.config, planner=planner))
        self.assertEqual(self.calls, [])
        for model in ("deepseek-v3", "kimi-k2", "domain-gpt-tool", "gpt-neox-20b"):
            validate_config(dict(self.config["planner"], model=model))

    def test_invalid_semantics_fails_after_one_request(self):
        self.responses = {"execute": "arbitrary code"}
        plan, directory = self.seed()
        with self.assertRaises(ValueError):
            self.provider._instructions(self.key, plan, directory)
        self.assertEqual(len(self.calls), 1)

    def test_cancel_is_immutable_and_does_not_submit(self):
        plan, directory = self.seed()
        self.provider.cancel(self.key)
        self.assertIsNone(self.provider._instructions(self.key, plan, directory))
        self.assertEqual(self.calls, [])
        self.provider.finish(self.key, "failed", "api_execution_failed")
        self.assertEqual(self.provider.poll(self.key)["state"], "cancelled")

    def test_sculpt_protocol_preserves_calibration_and_policy(self):
        from sculpt_provider import SculptProvider
        from test_sculpt_provider import BUILDER as SCULPT_BUILDER
        from test_sculpt_provider import PLAN as SCULPT_PLAN

        self.responses = copy.deepcopy(SCULPT_PLAN)
        config = dict(
            planner=self.config["planner"],
            storage=str(self.root / "sculpt-state"),
            blender_path=sys.executable,
            builder_path=str(SCULPT_BUILDER),
        )
        self.provider = SculptProvider(config)
        plan, directory = self.seed()
        with self.provider.db() as db:
            db.execute("INSERT INTO leases VALUES(?,?,0)", (self.key, time.time()))
        validated, receipt = self.provider._instructions(self.key, plan, directory)
        self.assertEqual(validated, SCULPT_PLAN)
        self.assertEqual(receipt["scope"], "validated_api_modeling_instructions")
        self.assertEqual(receipt["operator_calibration"]["attachment_index"], 1)
        self.assertEqual(self.calls[0]["messages"][0]["content"][1]["type"], "image_url")
        self.assertEqual(self.provider.describe()["id"], "api-sculpt")

    def test_sculpt_image_evidence_identifies_api_source(self):
        from sculpt_provider import SculptProvider
        from test_sculpt_provider import BUILDER as SCULPT_BUILDER
        from test_sculpt_provider import PLAN as SCULPT_PLAN
        from test_sculpt_provider import image_artifact

        self.responses = dict(
            copy.deepcopy(SCULPT_PLAN),
            reference_panels=[dict(view="front", box=[0, 0, 1, 1])],
            sheet_construction="model_plan",
        )
        config = dict(
            planner=self.config["planner"],
            storage=str(self.root / "sculpt-image-state"),
            blender_path=sys.executable,
            builder_path=str(SCULPT_BUILDER),
        )
        self.provider = SculptProvider(config)
        artifact = image_artifact("user-reference", b"\x11\x33\x55")
        self.request["node"] = "image_to_mesh"
        self.request["inputs"] = {"source": {name: artifact[name] for name in ("id", "revision")}}
        self.manifest["artifacts"] = [artifact]
        plan, directory = self.seed()
        with self.provider.db() as db:
            db.execute("INSERT INTO leases VALUES(?,?,0)", (self.key, time.time()))
        _, receipt = self.provider._instructions(self.key, plan, directory)
        self.assertEqual(receipt["sheet_view_evidence"]["source"], "api_observed_panels")
        self.assertEqual(receipt["scope"], "validated_api_modeling_instructions")
        self.assertNotIn("thread_id", receipt)
        self.assertNotIn("cli_turn_usage", receipt)
        self.assertEqual(receipt["requested_model"], "explicit-fixture")
        self.assertEqual(receipt["observed_model"], "fixture-model")

    def test_codex_fingerprint_tracks_shared_implementation(self):
        from codex_provider import CodexProvider

        config = dict(cli_path="not-installed", storage=str(self.root / "codex-state"), mesh_config=None)
        original = CodexProvider(config).fingerprint
        read_bytes = Path.read_bytes

        def changed(path):
            data = read_bytes(path)
            return data + b"\n# simulated shared implementation revision" if path.name == "provider_common.py" else data

        with patch.object(Path, "read_bytes", changed):
            self.assertNotEqual(CodexProvider(config).fingerprint, original)
        self.assertEqual(CodexProvider(config).fingerprint, original)

    def test_snapshot_restore_and_settings(self):
        value = settings(
            dict(
                mode="api_modeling",
                endpoint=self.config["planner"]["endpoint"],
                api_model="explicit-fixture",
                api_key_env="AINATIVE_FIXTURE_KEY",
                godot_path=str(GODOT if GODOT.is_file() else Path(sys.executable)),
                builder_path=str(BUILDER),
            )
        )
        self.assertNotIn("cli_path", value)
        _, providers = restore_provider(dict(mode="api_modeling", provider=self.config))
        self.assertEqual(providers["api-modeling"].fingerprint, self.provider.fingerprint)
        local = settings(dict(mode="local_mesh"))
        self.assertFalse(capability("text_to_mesh", local, {}, {})["ready"])
        self.assertFalse(capability("image_to_mesh", local, {}, {}, extra_image=True)["ready"])

    @unittest.skipUnless(os.environ.get("AINATIVE_GUI_TEST_GODOT"), "candidate Godot UI unavailable")
    def test_ui_mode_save_restore(self):
        script = self.root / "provider-ui.gd"
        script.write_text(
            r"""extends SceneTree
var panel
var failures = 0
func check(value, label):
    print(("PASS " if value else "FAIL ") + label)
    if not value: failures += 1
func _initialize():
    run.call_deferred()
func run():
    panel = load("res://addons/ainative/workbench.gd").new()
    panel.state_dir = OS.get_environment("AINATIVE_UI_STATE")
    panel.set_meta("ainative_builtin", true)
    root.add_child(panel)
    for i in 4: await process_frame
    for mode in ["api_modeling", "api_sculpt", "local_mesh"]:
        for i in panel.service_choice.item_count:
            if panel.service_choice.get_item_metadata(i) == mode:
                panel.service_choice.select(i)
                panel.service_choice.item_selected.emit(i)
        panel.endpoint_edit.text = "http://127.0.0.1:8188" if mode == "local_mesh" else "https://example.test/v1"
        panel.kimi_model_edit.text = "explicit-test-model"
        panel.blender_path_edit.text = "fixture-blender"
        panel.save_service_settings()
        var saved = panel.service_saved.duplicate(true)
        var original_file = FileAccess.get_file_as_string(panel.service_config_path)
        if mode.begins_with("api_"):
            for invalid_address in ["https://user:secret@example.test/v1", "https://example.test/v1?key=secret", "https://example.test:99999/v1"]:
                panel.endpoint_edit.text = invalid_address
                panel.save_service_settings()
                check(FileAccess.get_file_as_string(panel.service_config_path) == original_file, "invalid API address preserves saved configuration")
            panel.endpoint_edit.text = saved.endpoint
            panel.kimi_model_edit.text = ""
            panel.save_service_settings()
            check(FileAccess.get_file_as_string(panel.service_config_path) == original_file, "empty model preserves saved configuration")
        else:
            panel.endpoint_edit.text = "http://external.example:8188"
            panel.save_service_settings()
            check(FileAccess.get_file_as_string(panel.service_config_path) == original_file, "nonlocal mesh address preserves saved configuration")
        check(saved.mode == mode and not saved.has("cli_path"), mode + " saved without CLI")
        panel._restore_service_settings(ConfigFile.new())
        panel._update_service_summary()
        check(panel.service_draft() == saved, mode + " restores exact configuration")
        if mode.begins_with("api_"):
            check(panel.kimi_model_label.text == "API 模型 ID", "generic model label")
            check(not "Kimi" in panel.service_status.text and not "GPT" in panel.service_status.text, "accurate API status")
            check(("Blender" if mode == "api_sculpt" else "Godot") in panel.service_status.text, "accurate builder status")
    panel.queue_free()
    await process_frame
    quit(1 if failures else 0)
""",
            encoding="utf-8",
        )
        env = dict(os.environ, AINATIVE_UI_STATE=str(self.root / "ui-state"))
        Path(env["AINATIVE_UI_STATE"]).mkdir()
        result = subprocess.run(
            [
                env["AINATIVE_GUI_TEST_GODOT"],
                "--headless",
                "--path",
                str(Path(__file__).resolve().parents[2] / "samples/ainative-workbench"),
                "--script",
                str(script),
            ],
            env=env,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("SCRIPT ERROR", result.stderr)

    @unittest.skipUnless(GODOT.is_file(), "candidate Godot unavailable")
    def test_api_to_real_godot_builder(self):
        self.provider.submit(self.request, self.manifest, self.key)
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            result = self.provider.poll(self.key)
            if result["state"] in ("failed", "succeeded"):
                break
            time.sleep(0.1)
        self.assertEqual(result["state"], "succeeded", result)
        artifact = self.provider.result_manifest(self.key)["artifacts"][0]
        self.assertEqual(artifact["payload"]["provenance"]["provider"], "api-modeling")
        self.assertEqual(len(self.calls), 1)


if __name__ == "__main__":
    unittest.main()
