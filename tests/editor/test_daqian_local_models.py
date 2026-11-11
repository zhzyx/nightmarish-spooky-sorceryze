import json
import os
import sys
import tempfile
import unittest
from contextlib import ExitStack, closing
from pathlib import Path
from unittest.mock import patch

import local_models
import model_catalog as catalog
from model_api import invoke

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "customizations/components/godot-host/daqian"))


class LocalModels(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        folder = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.stack.enter_context(patch.object(catalog, "config_dir", return_value=folder))
        self.db = self.stack.enter_context(closing(catalog.database(folder)))
        self.stack.enter_context(patch.dict(os.environ, {"CODEX_HOME": str(folder)}, clear=True))
        self.cache = folder / "models_cache.json"
        self.stack.enter_context(
            patch.object(
                local_models, "installations", return_value=("/node", {"codex": "/codex", "codebuddy": "/codebuddy"})
            )
        )

    def test_project_responses_connection_imports_matching_protocol_and_secret(self):
        vault = {}
        settings = {
            "backend": "3",
            "model": "project-responses-model",
            "endpoint": "https://example.test/v1/chat/completions",
            "editor_key": "synthetic-private-key",
        }
        with patch.object(local_models, "run_json", return_value={"models": []}):
            rows = catalog.connect_local(self.db, settings, vault.__setitem__)
        row = next(row for row in rows if row["name"] == "AI Chat")
        profile = catalog.profiles(self.db)[row["candidate"]]
        self.assertEqual(profile["protocol"], "responses")
        self.assertEqual(profile["endpoint"], "https://example.test/v1/responses")
        self.assertEqual(vault[row["candidate"]], "synthetic-private-key")
        self.assertNotIn("synthetic-private-key", json.dumps(profile))

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

    def test_one_click_proves_selected_source_and_reuses_evidence(self):
        self.cache.write_text('{"models":[{"slug":"chosen"}]}')
        calls = []

        def respond(profile, prompt, images):
            calls.append(profile["model"])
            return {"text": prompt.split()[-1]}

        with (
            patch.object(local_models, "run_json", return_value={"models": []}),
            patch.object(catalog, "invoke", side_effect=respond),
        ):
            for _ in range(2):
                catalog.connect_and_verify(self.db, {"backend": "2"})
        self.assertEqual(calls, ["chosen"])
        self.assertEqual(catalog.sinan_catalog(self.db, ["text"])[0]["config"]["model"], "chosen")

    def test_wrong_challenge_keeps_discovered_model_unqualified(self):
        self.cache.write_text('{"models":[{"slug":"local"}]}')
        with (
            patch.object(local_models, "run_json", return_value={"models": []}),
            patch.object(catalog, "invoke", return_value={"text": "other"}),
        ):
            rows = catalog.connect_and_verify(self.db, {"backend": "2"})
        self.assertIn("验证回复", rows[0]["note"])
        self.assertEqual(catalog.sinan_catalog(self.db, ["text"]), [])

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
            self.assertEqual(
                payload, {"model": "buddy", "messages": [{"role": "user", "content": "ping"}], "available_tools": []}
            )
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


class RuntimeProfileTransitions(unittest.TestCase):
    def test_discovery_uses_one_runtime_for_arguments_and_child_environment(self):
        with tempfile.TemporaryDirectory() as temporary, ExitStack() as stack:
            folder = Path(temporary).resolve()
            files = {}
            for name in ("node-new", "codex-new", "buddy.js", "node-old"):
                path = folder / name
                path.touch()
                path.chmod(0o700)
                files[name] = str(path)
            configuration = folder / "runtime.json"
            configuration.write_text(
                json.dumps({"schema_version": 1, "runtimes": {"node": files["node-new"], "codex": files["codex-new"]}})
            )
            stack.enter_context(
                patch.dict(
                    os.environ,
                    {
                        "CODEX_HOME": str(folder),
                        "GONGGONG_RUNTIME_CONFIG": str(configuration),
                        "GONGGONG_NODE": files["node-old"],
                        "GONGGONG_RUNTIME_DERIVED_ENV": json.dumps({"node": files["node-old"]}),
                    },
                    clear=True,
                )
            )
            read = stack.enter_context(
                patch.object(local_models, "runtime_configuration", wraps=local_models.runtime_configuration)
            )
            calls = []

            def reply(arguments, timeout, environment=None):
                calls.append((arguments, environment))
                self.assertEqual(environment["GONGGONG_NODE"], files["node-new"])
                self.assertEqual(environment["GONGGONG_CODEX"], files["codex-new"])
                return {"models": [{"slug": "current", "id": "current"}]}

            stack.enter_context(patch.object(local_models, "run_json", side_effect=reply))
            rows = list(local_models.discover_cli({"cli_entry": files["buddy.js"]}))
            self.assertEqual(read.call_count, 1)
            self.assertEqual(len(calls), 2)
            self.assertEqual(calls[0][0][0], files["codex-new"])
            self.assertEqual(calls[1][0][0], files["node-new"])
            self.assertTrue(all(row[1] for row in rows))

    def test_changed_runtime_requires_existing_connection_verification(self):
        self.check_transition(False)

    @unittest.skipIf(os.name == "nt", "This alias transition covers Unix executable symlinks")
    def test_alias_target_change_requires_new_registered_identity(self):
        self.check_transition(True)

    def check_transition(self, use_alias):
        with tempfile.TemporaryDirectory(prefix="runtime-model-profile-") as temporary, ExitStack() as stack:
            folder = Path(temporary).resolve()
            configuration = folder / "runtime.json"
            entries = {}
            for name in ("node-old", "node-new", "codex-old", "codex-new"):
                path = folder / name
                path.write_text("#!/bin/sh\nexit 99\n")
                path.chmod(0o755)
                entries[name] = str(path)

            def save(suffix):
                paths = {"node": entries["node-" + suffix], "codex": entries["codex-" + suffix]}
                if use_alias:
                    for field, target in list(paths.items()):
                        alias = folder / (field + "-alias")
                        alias.unlink(missing_ok=True)
                        alias.symlink_to(target)
                        paths[field] = str(alias)
                configuration.write_text(json.dumps({"schema_version": 1, "runtimes": paths}))

            save("old")
            (folder / "models_cache.json").write_text('{"models":[{"slug":"runtime-model"}]}')
            stack.enter_context(
                patch.dict(
                    os.environ, {"CODEX_HOME": str(folder), "GONGGONG_RUNTIME_CONFIG": str(configuration)}, clear=True
                )
            )
            stack.enter_context(patch.object(catalog, "config_dir", return_value=folder))
            database = stack.enter_context(closing(catalog.database(folder)))
            calls = []

            def bridge(arguments, timeout, environment=None):
                calls.append(arguments)
                self.assertEqual(arguments[2], "chat")
                self.assertEqual(environment["GONGGONG_RUNTIME_CONFIG"], str(configuration))
                payload = json.loads(arguments[4].read_text())
                challenge = payload["messages"][0]["content"].split()[-1]
                return {"choices": [{"message": {"content": challenge}, "finish_reason": "stop"}]}

            stack.enter_context(patch.object(local_models, "run_json", side_effect=bridge))
            catalog.connect_and_verify(database, {"backend": "2"})
            original_profiles = catalog.profiles(database)
            original_id = next(iter(original_profiles))
            original = dict(original_profiles[original_id])
            self.assertTrue(any(row["id"] == original_id for row in catalog.sinan_catalog(database, ["text"])))
            self.assertEqual(calls[-1][0], entries["node-old"])
            self.assertEqual(str(calls[-1][3]), entries["codex-old"])

            before = configuration.read_bytes()
            save("new")
            if use_alias:
                self.assertEqual(configuration.read_bytes(), before)
            calls.clear()
            with self.assertRaisesRegex(ValueError, "运行路径已更新"):
                invoke(original, "do not execute stale runtime", [])
            self.assertEqual(calls, [])
            self.assertEqual(catalog.profiles(database)[original_id], original)

            catalog.connect_and_verify(database, {"backend": "2"})
            current = catalog.profiles(database)
            new_id = next(key for key, value in current.items() if value["node"] == entries["node-new"])
            self.assertNotEqual(new_id, original_id)
            self.assertEqual(current[original_id], original)
            self.assertTrue(any(row["id"] == new_id for row in catalog.sinan_catalog(database, ["text"])))
            self.assertEqual(calls[-1][0], entries["node-new"])
            self.assertEqual(str(calls[-1][3]), entries["codex-new"])


if __name__ == "__main__":
    unittest.main()
