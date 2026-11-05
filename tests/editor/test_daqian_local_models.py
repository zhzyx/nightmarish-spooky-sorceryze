import json
import os
from contextlib import closing, ExitStack
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "customizations/components/godot-host/daqian"))
from model_api import invoke
import local_models
import model_catalog as catalog


class LocalModels(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        folder = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.stack.enter_context(patch.object(catalog, "config_dir", return_value=folder))
        self.db = self.stack.enter_context(closing(catalog.database(folder)))
        self.stack.enter_context(patch.dict(os.environ, {"CODEX_HOME": str(folder)}, clear=True))
        self.cache = folder / "models_cache.json"
        self.stack.enter_context(patch.object(local_models, "installations", return_value=(
            "/node", {"codex": "/codex", "codebuddy": "/codebuddy"})))

    def test_connect_retries_preserve_profiles_evidence_and_secrets(self):
        self.cache.write_text(json.dumps({"models": [{"slug": "local-a"}, {"slug": "hidden", "visibility": "hide"}]}))
        os.environ.update(DEEPSEEK_MODEL="test-api", DEEPSEEK_API_KEY="private-test")
        secrets = {}
        with patch.object(local_models, "run_json", return_value={"models": [{"id": "local-b"}, {"id": "local-b"}]}):
            first = catalog.connect_local(self.db, {"codex_model": "local-a"}, secrets.__setitem__)
            self.assertEqual([row["added"] for row in first], [1, 1, 1])
            self.assertEqual(len(secrets), 1)
            self.assertFalse(catalog.sinan_catalog(self.db, ["text"]))
            profile_id = next(iter(catalog.profiles(self.db)))
            catalog.record_evaluation(self.db, profile_id, "text", "live", True, [True], "test-evidence")
            second = catalog.connect_local(self.db, {}, lambda *_: self.fail("overwrote existing credential"))
            self.assertEqual([row["existing"] for row in second], [1, 1, 1])
            self.assertEqual(catalog.sinan_catalog(self.db, ["text"])[0]["id"], profile_id)
        self.assertNotIn("private-test", json.dumps([first, second, catalog.profiles(self.db)]))

    def test_windows_npm_shim_and_custom_provider(self):
        shim = self.cache.parent / "codex.cmd"
        shim.touch()
        self.assertIsNone(local_models.codex_entry([shim]))
        js = shim.parent / "node_modules/@openai/codex/bin/codex.js"
        js.parent.mkdir(parents=True)
        js.touch()
        self.assertEqual(local_models.codex_entry([shim]), str(js.resolve()))
        (shim.parent / "config.toml").write_text('model_provider = "private"')
        with patch.object(local_models, "run_json", return_value={"models": []}):
            rows = catalog.connect_local(self.db, {"codex_model": "wrong-route"})
        self.assertIn("自定义" if sys.version_info >= (3, 11) else "3.11", rows[0]["note"])
        self.assertFalse(catalog.profiles(self.db))

    def test_source_failures_are_independent(self):
        self.cache.write_text("{")
        os.environ.update(OPENAI_MODEL="example", OPENAI_API_KEY="private-test", OPENAI_BASE_URL="https://other.test")
        with patch.object(local_models, "run_json", side_effect=[ValueError("离线"), {"models": [{"id": "ok"}]}]):
            results = catalog.connect_local(self.db, {})
        self.assertEqual([row["added"] for row in results], [0, 1, 0])
        self.assertTrue(all(row["note"] for row in (results[0], results[2])))

    def test_registered_cli_uses_matching_bridge_without_tools_or_key(self):
        def bridge(args, timeout):
            if args[2] == "models":
                return {"models": [{"id": "buddy"}]}
            self.assertEqual(list(args[1:4]), [local_models.BRIDGES["codebuddy"], "chat", "/codebuddy"])
            payload = json.loads(args[4].read_text())
            self.assertEqual(payload, {"model": "buddy", "messages": [{"role": "user", "content": "ping"}],
                                       "available_tools": []})
            return {"choices": [{"message": {"content": "pong"}, "finish_reason": "stop"}]}

        self.cache.write_text('{"models":[{"slug":"codex"}]}')
        with patch.object(local_models, "run_json", side_effect=bridge):
            catalog.connect_local(self.db, {})
            pid = next(k for k, v in catalog.profiles(self.db).items() if v["model"] == "buddy")
            profile = catalog.profiles(self.db)[pid]
            self.assertEqual(invoke(profile, "ping", [])["text"], "pong")
            with self.assertRaisesRegex(ValueError, "上限"):
                invoke(profile, "ping", [], limit=1)
            with self.assertRaisesRegex(ValueError, "未登记"):
                invoke(dict(profile, entry="/other"), "ping", [])
            with self.assertRaisesRegex(ValueError, "图像"):
                invoke(profile, "ping", [{}])


if __name__ == "__main__":
    unittest.main()
