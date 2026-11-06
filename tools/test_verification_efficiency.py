"""Real-Git negative cases for batch evidence and exact-byte reuse."""

import importlib.util
import json
import os
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
DITING = ROOT / "customizations/platforms/data-collection/git-files/storage/diting_files.py"
spec = importlib.util.spec_from_file_location("efficiency_diting", DITING)
assert spec is not None and spec.loader is not None
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)
batch = runpy.run_path(str(ROOT / "customizations/platforms/development/git/git_batch.py"))
sys.path.insert(0, str(ROOT / "customizations/components/issue-workorders"))
import issue_gate as gate  # noqa: E402


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.git("init", "-q")
        self.git("config", "user.name", "test")
        self.git("config", "user.email", "test@example.invalid")
        for name, origin in [("gonggong-diting-data", "gonggong"), ("olympus-hermes-data", "olympus")]:
            folder = self.root / name
            folder.mkdir()
            (folder / "dataset.json").write_text(
                json.dumps({
                    "schema_version": 1,
                    "name": name,
                    "origin_framework": origin,
                    "dataset_id": "d055bdfe-f4d0-451a-9874-173f0c3ce6f0",
                })
            )
        value = d.event({
            "schema_version": 1,
            "event_id": "event1",
            "tenant_id": "test",
            "request_id": "request1",
            "kind": "request",
            "occurred_at": "2026-11-05T00:00:00Z",
            "source_ref": "test:fixture",
            "agent": {"id": "test", "version": "1", "definition_sha256": "0" * 64, "origin": "fixture"},
            "payload": {},
            "evidence_refs": [],
        })
        self.event = self.root / "gonggong-diting-data/events/test/request1/event1.json"
        self.event.parent.mkdir(parents=True)
        self.event.write_text(json.dumps(value))
        self.git("add", ".")
        self.git("commit", "-qm", "fixture")

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args], stderr=subprocess.PIPE)

    def test_committed_and_index_raw_bytes(self):
        self.assertEqual(d.git_check(self.root, True)["git_state"], "committed")
        name = b"gonggong-diting-data/events/test/request1/event1.json"
        self.assertEqual(batch["objects"](self.root, ":", ["gonggong-diting-data"])[name], self.event.read_bytes())
        self.event.write_bytes(self.event.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "not committed"):
            d.git_check(self.root, True)

    def test_ignored_tracked_is_rejected(self):
        (self.root / ".gitignore").write_text("gonggong-diting-data/\n")
        with self.assertRaisesRegex(ValueError, "ignored:"):
            d.git_check(self.root)

    def test_untracked_and_deleted(self):
        self.git("rm", "--cached", str(self.event))
        with self.assertRaisesRegex(ValueError, "untracked:"):
            d.git_check(self.root)
        self.event.unlink()
        with self.assertRaisesRegex(ValueError, "deleted history"):
            d.git_check(self.root)

    def test_git_errors_fail_closed(self):
        with patch("subprocess.run", return_value=subprocess.CompletedProcess([], 128, b"", b"failure")):
            with self.assertRaises(ValueError):
                batch["ignored"](self.root, [b"x"])
            with self.assertRaises(ValueError):
                batch["objects"](self.root, "HEAD", ["x"])

    def test_spaces_unicode_and_binary_blobs(self):
        path = self.root / "space 汉字.txt"
        path.write_bytes(b"\0\n\xffraw\r\n")
        self.git("add", ".")
        self.assertEqual(batch["objects"](self.root, ":", [path.name])[os.fsencode(path.name)], path.read_bytes())

    def test_exact_bytes_reused_and_mutation_invalidates(self):
        cache = {}
        with patch.object(d, "event", wraps=d.event) as validate:
            d.git_check(self.root, cache=cache)
            first = validate.call_count
            (self.root / "unrelated.md").write_text("documentation")
            d.git_check(self.root, cache=cache)
            self.assertEqual(validate.call_count, first)
            value = json.loads(self.event.read_text())
            value["payload"] = {"changed": True}
            self.event.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, "checksum"):
                d.git_check(self.root, cache=cache)
            self.assertGreater(validate.call_count, first)

    def test_graph_is_not_cached(self):
        cache = {}
        d.git_check(self.root, cache=cache)
        value = json.loads(self.event.read_text())
        value.pop("sha256")
        value["evidence_refs"] = ["absent"]
        self.event.write_text(json.dumps(d.event(value)))
        with self.assertRaisesRegex(ValueError, "Missing evidence"):
            d.git_check(self.root, cache=cache)

    def test_history_loaded_once_and_bounded_git_calls(self):
        with patch.object(d, "load", wraps=d.load) as load, patch("subprocess.run", wraps=subprocess.run) as calls:
            d.git_check(self.root, True)
        self.assertEqual(load.call_count, 2)
        self.assertLessEqual(calls.call_count, 6)

    def test_session_tool_changes_and_failures_clear_evidence(self):
        for relative in [
            "customizations/platforms/data-collection/git-files/storage/diting_files.py",
            "customizations/platforms/development/git/git_batch.py",
        ]:
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)
        session = gate.VerificationSession()
        session.check_diting(self.root)
        self.assertTrue(session.events)
        old_module = session.module
        path = self.root / "customizations/platforms/development/git/git_batch.py"
        path.write_bytes(path.read_bytes() + b"\n")
        session.check_diting(self.root)
        self.assertIsNot(session.module, old_module)
        self.event.write_text("{broken json")
        with self.assertRaises(ValueError):
            session.check_diting(self.root)
        self.assertFalse(session.events)

    def test_session_requires_restart_after_gate_change(self):
        session = gate.VerificationSession()
        session.events["old"] = "old"
        with patch.object(gate, "GATE_SOURCE", b"old-version"):
            with self.assertRaisesRegex(ValueError, "restart"):
                session.check_runtime()
        self.assertFalse(session.events)

    def test_snapshot_binds_raw_content_and_index(self):
        with patch.object(gate.hashlib, "file_digest", side_effect=AssertionError("requires Python 3.11"), create=True):
            before = gate.snapshot(self.root)
        original = self.event.read_bytes()
        self.event.write_bytes(original + b" ")
        self.assertNotEqual(before, gate.snapshot(self.root))
        self.git("add", ".")
        self.event.write_bytes(original)
        self.assertNotEqual(before, gate.snapshot(self.root))


if __name__ == "__main__":
    unittest.main()
