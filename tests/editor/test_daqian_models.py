import json
import os
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from threading import Event
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "customizations/components/godot-host/daqian"))

# isort: split
import model_catalog as catalog  # noqa: E402
from model_api import result_data  # noqa: E402


class Models(unittest.TestCase):
    def test_saving_credentials_revokes_live_evidence_but_keeps_synthetic_results(self):
        with tempfile.TemporaryDirectory() as directory, closing(catalog.database(directory)) as db:
            profile = {
                "name": "fixture",
                "protocol": "responses",
                "model": "synthetic",
                "endpoint": "https://example.test/v1/responses",
            }
            vault = {}
            profile_id = catalog.add(db, profile, "old-synthetic-key", vault.__setitem__)
            for scope in ("live", "synthetic"):
                catalog.record_evaluation(
                    db,
                    profile_id,
                    "text",
                    scope,
                    True,
                    [True],
                    scope + "-evidence",
                    expected_revision=catalog.credential_revision(db, profile_id),
                )
            catalog.add(db, profile, "replacement-synthetic-key", vault.__setitem__)
            self.assertEqual(vault[profile_id], "replacement-synthetic-key")
            self.assertEqual(catalog.sinan_catalog(db, ["text"]), [])
            self.assertEqual(catalog.sinan_catalog(db, ["text"], "synthetic")[0]["id"], profile_id)
            self.assertEqual(catalog.profiles(db)[profile_id], profile)
            self.assertNotIn(b"replacement-synthetic-key", (Path(directory) / "models.sqlite").read_bytes())

    def test_credential_store_failure_cannot_leave_old_live_evidence(self):
        with tempfile.TemporaryDirectory() as directory, closing(catalog.database(directory)) as db:
            profile = {
                "name": "fixture",
                "protocol": "responses",
                "model": "synthetic",
                "endpoint": "https://example.test/v1/responses",
            }
            profile_id = catalog.add(db, profile, "old-synthetic-key", lambda *_: None)
            catalog.record_evaluation(
                db,
                profile_id,
                "text",
                "live",
                True,
                [True],
                "old-evidence",
                expected_revision=catalog.credential_revision(db, profile_id),
            )

            def fail_write(*_):
                # A second reader observes the revocation before the external
                # store is changed, even if that store fails after a partial write.
                with closing(catalog.database(directory)) as observer:
                    self.assertEqual(catalog.sinan_catalog(observer, ["text"]), [])
                raise OSError("synthetic credential store failure")

            with self.assertRaises(OSError):
                catalog.add(db, profile, "replacement-synthetic-key", fail_write)
            self.assertEqual(catalog.profiles(db)[profile_id], profile)
            self.assertEqual(catalog.sinan_catalog(db, ["text"]), [])

    def test_late_verification_cannot_qualify_replacement_credential(self):
        with tempfile.TemporaryDirectory() as directory, closing(catalog.database(directory)) as db:
            profile = {
                "name": "AI Chat",
                "protocol": "responses",
                "model": "synthetic",
                "endpoint": "https://example.test/v1/responses",
            }
            vault = {}
            profile_id = catalog.add(db, profile, "old-synthetic-key", vault.__setitem__)
            settings = {"backend": "3", "model": profile["model"], "endpoint": profile["endpoint"]}

            def late_response(_profile, prompt, _messages):
                with closing(catalog.database(directory)) as writer:
                    catalog.add(writer, profile, "replacement-synthetic-key", vault.__setitem__)
                return {"text": prompt.split()[-1]}

            with (
                patch.dict(os.environ, {}, clear=True),
                patch.object(catalog, "discover_cli", return_value=[]),
                patch.object(catalog, "invoke", side_effect=late_response),
            ):
                rows = catalog.connect_and_verify(db, settings)
            self.assertIn("旧验证结果已失效", rows[0]["note"])
            self.assertEqual(catalog.sinan_catalog(db, ["text"]), [])
            self.assertEqual(vault[profile_id], "replacement-synthetic-key")

    def test_pending_save_rejects_probe_and_explicit_retry_recovers(self):
        with tempfile.TemporaryDirectory() as directory, closing(catalog.database(directory)) as db:
            profile = {
                "name": "fixture",
                "protocol": "responses",
                "model": "synthetic",
                "endpoint": "https://example.test/v1/responses",
            }
            profile_id = catalog.add(db, profile, "old", lambda *_: None)
            previous = catalog.credential_revision(db, profile_id)

            def failed_write(*_):
                with closing(catalog.database(directory)) as reader:
                    with self.assertRaisesRegex(ValueError, "凭据正在保存"):
                        catalog.credential_revision(reader, profile_id)
                raise OSError("fixture failure")

            with self.assertRaises(OSError):
                catalog.add(db, profile, "new", failed_write)
            with self.assertRaisesRegex(ValueError, "凭据正在保存"):
                catalog.record_evaluation(
                    db, profile_id, "text", "live", True, [True], "late", expected_revision=previous
                )
            catalog.add(db, profile, "retry", lambda *_: None)
            current = catalog.credential_revision(db, profile_id)
            self.assertNotEqual(previous, current)
            with self.assertRaisesRegex(ValueError, "旧验证结果已失效"):
                catalog.record_evaluation(
                    db, profile_id, "text", "live", True, [True], "late", expected_revision=previous
                )
            catalog.record_evaluation(db, profile_id, "text", "live", True, [True], "new", expected_revision=current)
            self.assertEqual(len(catalog.sinan_catalog(db, ["text"])), 1)

    def test_concurrent_first_import_preserves_first_credential(self):
        with tempfile.TemporaryDirectory() as directory, ThreadPoolExecutor(max_workers=2) as pool:
            with closing(catalog.database(directory)):
                pass
            saving, second_started, release = Event(), Event(), Event()
            writes = []
            settings = {
                "backend": "3",
                "model": "synthetic",
                "endpoint": "https://example.test/v1/responses",
                "editor_key": "first",
            }

            def vault(_profile_id, key):
                writes.append(key)
                saving.set()
                if not release.wait(5):
                    raise RuntimeError("fixture release timeout")

            def import_profile(second=False):
                with closing(catalog.database(directory)) as db:
                    if second:
                        second_started.set()
                    return catalog.connect_local(db, dict(settings, editor_key="second" if second else "first"), vault)

            with patch.dict(os.environ, {}, clear=True), patch.object(catalog, "discover_cli", return_value=[]):
                first = pool.submit(import_profile)
                try:
                    self.assertTrue(saving.wait(5))
                    second = pool.submit(import_profile, True)
                    self.assertTrue(second_started.wait(5))
                finally:
                    release.set()
                a, b = first.result(timeout=5), second.result(timeout=5)
            self.assertEqual(writes, ["first"])
            self.assertEqual(a[0]["added"], 1)
            self.assertEqual(b[0]["existing"], 1)

    def test_catalog_separates_gates_scores_and_secrets(self):
        with tempfile.TemporaryDirectory() as directory, closing(catalog.database(directory)) as db:
            profile = {
                "name": "私有配置",
                "protocol": "responses",
                "model": "profile-a",
                "endpoint": "https://example.test/v1/responses",
            }
            secrets = {}
            a = catalog.add(db, profile, "private-unit-value", secrets.__setitem__)
            b = catalog.add(db, dict(profile, model="profile-b"), "other-unit-value", secrets.__setitem__)
            self.assertNotIn("private-unit-value", json.dumps(catalog.profiles(db)))
            self.assertEqual(catalog.sinan_catalog(db, ["image"]), [])
            catalog.record_evaluation(db, a, "image", "synthetic", True, [True, False], "fixture-a")
            catalog.record_evaluation(db, b, "image", "synthetic", True, [True, True], "fixture-b")
            ranked = catalog.sinan_catalog(db, ["image"], "synthetic", preferred=a)
            self.assertEqual([c["id"] for c in ranked], [b, a])
            self.assertEqual(catalog.sinan_catalog(db, ["image"], "live"), [])
            catalog.record_evaluation(db, b, "image", "synthetic", False, [True, True], "failed")
            self.assertEqual([c["id"] for c in catalog.sinan_catalog(db, ["image"], "synthetic")], [a])
            self.assertEqual(catalog.sinan_catalog(db, ["text", "image"], "synthetic"), [])
            self.assertNotIn(b"private-unit-value", (Path(directory) / "models.sqlite").read_bytes())

    def test_incomplete_responses(self):
        for protocol, raw in [
            ("responses", {"status": "incomplete", "output": []}),
            (
                "gemini-generate-content",
                {"candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": [{"text": "part"}]}}]},
            ),
            ("anthropic-messages", {"stop_reason": "max_tokens", "content": [{"type": "text", "text": "part"}]}),
            ("chat-completions", {"choices": [{"finish_reason": "length", "message": {"content": "part"}}]}),
        ]:
            with self.subTest(protocol=protocol), self.assertRaisesRegex(ValueError, "完整"):
                result_data(protocol, raw)


if __name__ == "__main__":
    unittest.main()
