import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import ExitStack, closing
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "customizations/components/godot-host/daqian"))

# isort: split
import local_models  # noqa: E402
import model_api  # noqa: E402
import model_catalog as catalog  # noqa: E402
from model_api import invoke  # noqa: E402


class LocalModels(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        folder = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.stack.enter_context(patch.object(catalog, "config_dir", return_value=folder))
        self.db = self.stack.enter_context(closing(catalog.database(folder)))
        self.stack.enter_context(patch.dict(os.environ, {"CODEX_HOME": str(folder)}, clear=True))
        self.cache = folder / "models_cache.json"
        self.entries = {}
        for name in ("node", "codex", "codebuddy"):
            path = folder / name
            path.touch()
            path.chmod(0o700)
            self.entries[name] = str(path)
        self.stack.enter_context(
            patch.object(
                local_models,
                "installations",
                return_value=(self.entries["node"], {name: self.entries[name] for name in ("codex", "codebuddy")}),
            )
        )

    def test_selected_api_key_is_bound_across_concurrent_replacement(self):
        settings = {
            "backend": "3",
            "model": "fixture",
            "endpoint": "https://example.test/v1/responses",
            "editor_key": "selected-A",
        }
        vault = {}
        real_connect = catalog.connect_local
        for boundary in ("before_capture", "after_capture", "none"):
            with self.subTest(boundary=boundary):
                observed = []
                selected = {}

                def replace():
                    with closing(catalog.database(self.cache.parent)) as other:
                        catalog.add(other, selected, "concurrent-B", vault.__setitem__)

                def connect(*args, **kwargs):
                    rows = real_connect(*args, **kwargs)
                    selected.update(catalog.profiles(self.db)[rows[0]["candidate"]])
                    if boundary == "before_capture":
                        replace()
                    return rows

                class Opener:
                    def open(self, request, timeout):
                        observed.append(request.headers.get("Authorization"))
                        if boundary == "after_capture":
                            replace()
                        body = json.loads(request.data)
                        challenge = body["input"][0]["content"][0]["text"].split()[-1]
                        return io.BytesIO(
                            json.dumps({
                                "status": "completed",
                                "output": [
                                    {"type": "message", "content": [{"type": "output_text", "text": challenge}]}
                                ],
                            }).encode()
                        )

                with (
                    patch.object(catalog, "discover_cli", return_value=[]),
                    patch.object(catalog, "connect_local", side_effect=connect),
                    patch.object(model_api.urllib.request, "build_opener", return_value=Opener()),
                ):
                    rows = catalog.connect_and_verify(self.db, settings, vault.__setitem__)
                self.assertEqual(observed, [] if boundary == "before_capture" else ["Bearer selected-A"])
                self.assertEqual(len(catalog.sinan_catalog(self.db, ["text"])), int(boundary == "none"))
                self.assertNotIn("selected-A", json.dumps(rows))
                self.assertNotIn("concurrent-B", json.dumps(rows))

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
        with patch.object(
            local_models,
            "run_json",
            side_effect=lambda args, *_: {"models": [{"id": "local-a" if "codex_cli" in str(args[1]) else "local-b"}]},
        ):
            first = catalog.connect_local(self.db, {"codex_model": "local-a"}, secrets.__setitem__)
            self.assertEqual([row["added"] for row in first], [1, 1, 1])
            self.assertEqual(len(secrets), 1)
            self.assertFalse(catalog.sinan_catalog(self.db, ["text"]))
            profile_id = next(iter(catalog.profiles(self.db)))
            catalog.record_evaluation(
                self.db,
                profile_id,
                "text",
                "live",
                True,
                [True],
                "test-evidence",
                expected_revision=catalog.verification_revision(self.db, profile_id),
            )
            second = catalog.connect_local(self.db, {}, lambda *_: self.fail("overwrote existing credential"))
            self.assertEqual([row["existing"] for row in second], [1, 1, 1])
            self.assertEqual(catalog.sinan_catalog(self.db, ["text"])[0]["id"], profile_id)
        self.assertNotIn("private-test", json.dumps([first, second, catalog.profiles(self.db)]))

    def test_removed_catalog_model_revokes_proof_and_late_probe(self):
        def respond(profile, prompt, images, **options):
            return {"text": prompt.split()[-1]}

        with (
            patch.object(local_models, "run_json", return_value={"models": [{"id": "removed"}]}),
            patch.object(catalog, "invoke", side_effect=respond),
        ):
            catalog.connect_and_verify(self.db, {"backend": "2"})
        candidate = catalog.sinan_catalog(self.db, ["text"])[0]
        profile_id = candidate["id"]
        revision = catalog.verification_revision(self.db, profile_id)
        with patch.object(local_models, "run_json", return_value={"models": []}):
            catalog.connect_local(self.db, {})
        self.assertEqual(catalog.sinan_catalog(self.db, ["text"]), [])
        self.assertIn(profile_id, catalog.profiles(self.db))
        with self.assertRaisesRegex(ValueError, "移除"):
            invoke(candidate["config"], "must not start removed model", [])
        with patch.object(local_models, "run_json", return_value={"models": [{"id": "removed"}]}):
            catalog.connect_local(self.db, {})
        self.assertNotEqual(catalog.verification_revision(self.db, profile_id), revision)
        with self.assertRaisesRegex(ValueError, "旧验证"):
            catalog.record_evaluation(
                self.db, profile_id, "text", "live", True, [True], "late", expected_revision=revision
            )
        self.assertEqual(catalog.sinan_catalog(self.db, ["text"]), [])

    def test_model_removed_while_invoking_cannot_return_current_result(self):
        with patch.object(local_models, "run_json", return_value={"models": [{"id": "removed-during-call"}]}):
            catalog.connect_local(self.db, {})
        profile = next(v for v in catalog.profiles(self.db).values() if v["protocol"] == "codex-cli")

        def retire(*args, **kwargs):
            with patch.object(local_models, "run_json", return_value={"models": []}):
                catalog.connect_local(self.db, {})
            return {"text": "stale"}

        with patch.object(local_models, "invoke_cli", side_effect=retire):
            with self.assertRaisesRegex(ValueError, "移除"):
                invoke(profile, "probe", [])

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

    def test_discovery_reads_config_from_captured_runtime_environment(self):
        captured_home = self.cache.parent / "captured"
        captured_home.mkdir()
        (captured_home / "config.toml").write_text('model_provider = "private"')
        environment = {"CODEX_HOME": str(captured_home)}
        runtime = SimpleNamespace(child_environment=lambda _: environment)
        with (
            patch.object(local_models, "runtime_configuration", return_value=(runtime, object())),
            patch.object(local_models, "run_json", return_value={"models": []}) as bridge,
        ):
            rows = list(local_models.discover_cli({"codex_model": "wrong-route"}))
        self.assertEqual(rows[0][1], [])
        self.assertIn("自定义", rows[0][2])
        self.assertEqual(bridge.call_count, 1)  # Only the independent CodeBuddy discovery.
        self.assertIn("codebuddy_cli", str(bridge.call_args.args[0][1]))
        self.assertEqual(bridge.call_args.args[2], environment)

    def test_one_click_always_proves_selected_current_source(self):
        self.cache.write_text('{"models":[{"slug":"chosen"}]}')
        calls = []

        def respond(profile, prompt, images, **options):
            calls.append(profile["model"])
            return {"text": prompt.split()[-1]}

        with (
            patch.object(local_models, "run_json", return_value={"models": [{"id": "chosen"}]}),
            patch.object(catalog, "invoke", side_effect=respond),
        ):
            for _ in range(2):
                catalog.connect_and_verify(self.db, {"backend": "2"})
        self.assertEqual(calls, ["chosen", "chosen"])
        self.assertEqual(catalog.sinan_catalog(self.db, ["text"])[0]["config"]["model"], "chosen")

    def test_wrong_challenge_keeps_discovered_model_unqualified(self):
        self.cache.write_text('{"models":[{"slug":"local"}]}')
        with (
            patch.object(local_models, "run_json", return_value={"models": [{"id": "local"}]}),
            patch.object(catalog, "invoke", return_value={"text": "other"}),
        ):
            rows = catalog.connect_and_verify(self.db, {"backend": "2"})
        self.assertIn("验证回复", rows[0]["note"])
        self.assertEqual(catalog.sinan_catalog(self.db, ["text"]), [])

    def test_selected_provider_failure_does_not_verify_another_provider(self):
        self.cache.write_text('{"models":[{"slug":"chosen"}]}')
        calls = []

        def fail_selected(profile, *_, **options):
            calls.append(profile["name"])
            raise ValueError("selected provider is offline")

        with (
            patch.object(local_models, "run_json", return_value={"models": [{"id": "other"}]}),
            patch.object(catalog, "invoke", side_effect=fail_selected),
        ):
            rows = catalog.connect_and_verify(self.db, {"backend": "2"})
        self.assertEqual(calls, ["Codex"])
        self.assertIn("offline", next(row for row in rows if row["name"] == "Codex")["note"])
        self.assertEqual(len(catalog.profiles(self.db)), 2)  # Discovery remains independent.
        self.assertEqual(catalog.sinan_catalog(self.db, ["text"]), [])

    def test_missing_selected_api_configuration_never_uses_discovered_cli(self):
        self.cache.write_text('{"models":[{"slug":"available-but-not-selected"}]}')
        with (
            patch.object(local_models, "run_json", return_value={"models": []}),
            patch.object(catalog, "invoke") as invoke,
        ):
            rows = catalog.connect_and_verify(self.db, {"backend": "3"})
        invoke.assert_not_called()
        selected = next(row for row in rows if row["name"] == "AI Chat")
        self.assertFalse(selected["candidate"])
        self.assertIn("配置", selected["note"])

    def test_unknown_explicit_backend_does_not_discover_or_invoke(self):
        with patch.object(catalog, "connect_local") as discover, patch.object(catalog, "invoke") as invoke:
            with self.assertRaisesRegex(ValueError, "连接方式"):
                catalog.connect_and_verify(self.db, {"backend": "unknown"})
        discover.assert_not_called()
        invoke.assert_not_called()

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
            self.assertEqual(list(args[1:4]), [local_models.BRIDGES["codebuddy"], "chat", self.entries["codebuddy"]])
            payload = json.loads(args[4].read_text())
            self.assertEqual(
                payload, {"model": "buddy", "messages": [{"role": "user", "content": "ping"}], "available_tools": []}
            )
            return {"choices": [{"message": {"content": "pong"}, "finish_reason": "stop"}]}

        self.cache.write_text('{"models":[{"slug":"codex"}]}')
        with patch.object(local_models, "run_json", side_effect=bridge):
            catalog.connect_local(self.db, {})
            pid = next(
                k
                for k, v in catalog.profiles(self.db).items()
                if v["model"] == "buddy" and v["protocol"] == "codebuddy-cli"
            )
            profile = catalog.profiles(self.db)[pid]
            self.assertEqual(invoke(profile, "ping", [])["text"], "pong")
            with self.assertRaisesRegex(ValueError, "上限"):
                invoke(profile, "ping", [], limit=1)
            with self.assertRaisesRegex(ValueError, "未登记"):
                invoke(dict(profile, entry="/other"), "ping", [])
            with self.assertRaisesRegex(ValueError, "图像"):
                invoke(profile, "ping", [{}])

    def test_stale_cache_never_suppresses_shared_bridge_discovery(self):
        self.cache.write_text('{"fetched_at":"2000-01-01","models":[{"slug":"retired"}]}')
        with patch.object(local_models, "run_json", return_value={"models": [{"id": "fresh"}]}) as run:
            ids = local_models.codex_ids(self.entries["node"], self.entries["codex"], self.cache.parent)
        self.assertEqual(ids, ["fresh"])
        self.assertEqual(run.call_args.args[0][1:3], [local_models.BRIDGES["codex"], "models"])

    def test_source_change_invalidates_proof_without_deleting_history(self):
        for change in ("home", "environment", "login_file", "uninstall"):
            with self.subTest(change=change), patch.dict(os.environ, os.environ.copy(), clear=True):
                Path(self.entries["codex"]).touch()
                with (
                    patch.object(local_models, "run_json", return_value={"models": [{"id": "chosen"}]}),
                    patch.object(
                        catalog, "invoke", side_effect=lambda _, text, _images, **options: {"text": text.split()[-1]}
                    ),
                ):
                    catalog.connect_and_verify(self.db, {"backend": "2"})
                available = catalog.sinan_catalog(self.db, ["text"])
                self.assertTrue(available)
                profile = available[0]["config"]
                if change == "home":
                    os.environ["CODEX_HOME"] += "/another-account"
                elif change == "environment":
                    os.environ["OPENAI_API_KEY"] = "private-account-switch-marker"
                elif change == "login_file":
                    (self.cache.parent / "auth.json").write_text("private-login-marker")
                else:
                    Path(self.entries["codex"]).unlink()
                self.assertEqual(catalog.sinan_catalog(self.db, ["text"]), [])
                self.assertIn(catalog.identity(profile), catalog.profiles(self.db))
                with self.assertRaises(ValueError):
                    local_models.invoke_cli(profile, "do not launch stale source", [])
                raw = (self.cache.parent / "models.sqlite").read_bytes()
                self.assertNotIn(b"private-account-switch-marker", raw)
                self.assertNotIn(b"private-login-marker", raw)

    def test_failed_retry_revokes_previous_text_proof(self):
        with (
            patch.object(local_models, "run_json", return_value={"models": [{"id": "chosen"}]}),
            patch.object(catalog, "invoke", side_effect=lambda _, text, _images, **options: {"text": text.split()[-1]}),
        ):
            catalog.connect_and_verify(self.db, {"backend": "2"})
            self.assertTrue(catalog.sinan_catalog(self.db, ["text"]))
            with patch.object(catalog, "invoke", side_effect=ValueError("connection unavailable")):
                rows = catalog.connect_and_verify(self.db, {"backend": "2"})
            self.assertIn("unavailable", rows[0]["note"])
            self.assertEqual(catalog.sinan_catalog(self.db, ["text"]), [])

    def test_source_switch_during_probe_cannot_publish_old_proof(self):
        def switched(_profile, text, _images, **options):
            os.environ["CODEX_HOME"] += "/new"
            return {"text": text.split()[-1]}

        with (
            patch.object(local_models, "run_json", return_value={"models": [{"id": "chosen"}]}),
            patch.object(catalog, "invoke", side_effect=switched),
        ):
            rows = catalog.connect_and_verify(self.db, {"backend": "2"})
        self.assertIn("旧验证结果已失效", rows[0]["note"])
        self.assertEqual(catalog.sinan_catalog(self.db, ["text"]), [])

    def test_current_editor_key_is_explicitly_saved_and_verified(self):
        settings = {
            "backend": "3",
            "model": "synthetic",
            "endpoint": "https://example.test/v1/responses",
            "editor_key": "first-key",
        }
        vault = {}
        calls = []

        def reply(profile, text, _images, **options):
            self.assertEqual(options["timeout"], 60)
            calls.append(vault[catalog.identity(profile)])
            return {"text": text.split()[-1]}

        with patch.object(catalog, "discover_cli", return_value=[]), patch.object(catalog, "invoke", side_effect=reply):
            first = catalog.connect_and_verify(self.db, settings, vault.__setitem__)
            second = catalog.connect_and_verify(self.db, dict(settings, editor_key="current-key"), vault.__setitem__)
            missing = catalog.connect_and_verify(self.db, dict(settings, editor_key=""), vault.__setitem__)
        self.assertEqual(calls, ["first-key", "current-key"])
        self.assertEqual(first[0]["added"], 1)
        self.assertEqual(second[0]["existing"], 1)
        self.assertNotIn("candidate", missing[0])
        self.assertIn("凭据", missing[0]["note"])
        self.assertNotIn("current-key", json.dumps(catalog.profiles(self.db)))


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
            self.assertEqual(calls[0][0][0], files["node-new"])
            self.assertEqual(calls[0][0][3], files["codex-new"])
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
                if arguments[2] == "models":
                    return {"models": [{"id": "runtime-model"}]}
                calls.append(arguments)
                self.assertEqual(arguments[2], "chat")
                self.assertEqual(environment["GONGGONG_RUNTIME_CONFIG"], str(configuration))
                payload = json.loads(arguments[4].read_text())
                challenge = payload["messages"][0]["content"].split()[-1]
                return {"choices": [{"message": {"content": challenge}, "finish_reason": "stop"}]}

            stack.enter_context(patch.object(local_models, "run_json", side_effect=bridge))
            catalog.connect_and_verify(database, {"backend": "2"})
            original_profiles = catalog.profiles(database)
            original_id = next(key for key, value in original_profiles.items() if value["protocol"] == "codex-cli")
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
            self.assertEqual(catalog.sinan_catalog(database, ["text"]), [])

            catalog.connect_and_verify(database, {"backend": "2"})
            current = catalog.profiles(database)
            new_id = next(
                key
                for key, value in current.items()
                if value["node"] == entries["node-new"] and value["protocol"] == "codex-cli"
            )
            self.assertNotEqual(new_id, original_id)
            self.assertEqual(current[original_id], original)
            self.assertTrue(any(row["id"] == new_id for row in catalog.sinan_catalog(database, ["text"])))
            self.assertEqual(calls[-1][0], entries["node-new"])
            self.assertEqual(str(calls[-1][3]), entries["codex-new"])


if __name__ == "__main__":
    unittest.main()
