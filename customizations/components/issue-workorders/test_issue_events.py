"""Isolated intake tests; all remote data and receipts below are synthetic."""

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import issue_events as events


class EventIntakeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "work-items.json").write_text(json.dumps({"repository": "test/repo", "tenant_id": "test-tenant"}))
        (self.root / "AGENTS.md").write_text("synthetic host definition")
        (self.root / ".github").mkdir()
        (self.root / ".github/labels.json").write_text(json.dumps([{"name": "type:development"}]))
        self.issue = {
            "number": 9,
            "html_url": "https://github.com/test/repo/issues/9",
            "state": "open",
            "body": "<!-- olympus-request:test-request -->\n<!-- olympus-depends-on:#6 --> see #7",
            "labels": [{"name": n} for n in ["type:development", "status:in-progress", "workspace:olympus"]],
            "assignees": [{"login": "test-owner"}],
            "updated_at": "2026-11-03T00:00:00Z",
        }
        self.event = {"id": 123, "event": "labeled", "created_at": "2026-11-03T00:00:00Z"}

    def tearDown(self):
        self.temporary.cleanup()

    def invoke(self):
        return events.intake(self.root, 9, 123, "test-host", "test-tenant", "test-request", Path("AGENTS.md"))

    def test_mapping_does_not_infer_prose_dependencies_or_dispatch(self):
        mapped = events.mapping(self.issue, "test-request", {"type:development"})
        self.assertEqual(mapped["dependencies"], [6])
        self.assertEqual(mapped["coordination"], "associate_only_no_dispatch")
        self.assertFalse(mapped["parent_auto_close"])

    def test_reject_other_workspace_and_ambiguous_status_or_request(self):
        for change in ("workspace", "status", "request"):
            with self.subTest(change=change):
                value = copy.deepcopy(self.issue)
                if change == "workspace":
                    value["labels"][-1]["name"] = "workspace:gonggong"
                elif change == "status":
                    value["labels"].append({"name": "status:done"})
                else:
                    value["body"] += "<!-- olympus-request:different -->"
                with self.assertRaises(ValueError):
                    events.mapping(value, "test-request", {"type:development"})

    def test_remote_event_must_belong_to_issue_and_not_pull_request(self):
        with patch.object(events, "gh", return_value=json.dumps([[self.event]])):
            with self.assertRaises(ValueError):
                events.remote_event("test/repo", 9, 456)
        issue = dict(self.issue, pull_request={})
        with patch.object(events, "gh", side_effect=[json.dumps([[self.event]]), json.dumps(issue)]):
            with self.assertRaises(ValueError):
                events.remote_event("test/repo", 9, 123)

    def test_receipt_replay_retains_original_envelope_and_refuses_reattribution(self):
        completed = subprocess.CompletedProcess([], 0, '{"state":"recorded_file","idempotent":true}', "")
        with (
            patch.object(events, "remote_event", return_value=(self.event, self.issue)) as remote,
            patch.object(events.subprocess, "run", return_value=completed),
        ):
            first = self.invoke()
            envelope = self.root / first["receipt"].replace("receipt.json", "envelope.json")
            original = envelope.read_bytes()
            second = self.invoke()
            self.assertEqual(first, second)
            self.assertEqual(remote.call_count, 1)
            self.assertEqual(original, envelope.read_bytes())
            (self.root / "AGENTS.md").write_text("different definition")
            with self.assertRaises(ValueError):
                self.invoke()

    def test_failed_record_retains_envelope_without_success_receipt_and_retry_uses_it(self):
        failed = subprocess.CompletedProcess([], 1, "", "synthetic failure")
        with (
            patch.object(events, "remote_event", return_value=(self.event, self.issue)),
            patch.object(events.subprocess, "run", return_value=failed),
        ):
            with self.assertRaises(ValueError):
                self.invoke()
        self.assertEqual(len(list(self.root.rglob("envelope.json"))), 1)
        self.assertEqual(len(list(self.root.rglob("receipt.json"))), 0)
        completed = subprocess.CompletedProcess([], 0, '{"state":"recorded_file"}', "")
        with (
            patch.object(events, "remote_event", side_effect=AssertionError("must reuse persisted envelope")),
            patch.object(events.subprocess, "run", return_value=completed),
        ):
            self.assertEqual(self.invoke()["state"], "recorded_file")

    def test_existing_lock_rejects_concurrent_invocation(self):
        identity = {"repository": "test/repo", "issue": 9, "event_id": 123}
        lock = self.root / ".olympus-outbox/issue-events" / (events.digest(identity) + ".lock")
        with events.event_lock(lock):
            with self.assertRaises(OSError):
                self.invoke()
        self.assertTrue(lock.exists())

    def test_top_level_binding_tampering_rejected_before_record(self):
        completed = subprocess.CompletedProcess([], 0, '{"state":"recorded_file"}', "")
        with (
            patch.object(events, "remote_event", return_value=(self.event, self.issue)),
            patch.object(events.subprocess, "run", return_value=completed),
        ):
            receipt = self.invoke()
        envelope = self.root / receipt["receipt"].replace("receipt.json", "envelope.json")
        original = events.read(envelope)
        mutations = [
            ("tenant_id", "other"),
            ("request_id", "other"),
            ("event_id", "other"),
            ("source_ref", "other"),
            ("agent.id", "other"),
            ("agent.definition_sha256", "0" * 64),
        ]
        for name, replacement in mutations:
            with self.subTest(field=name), patch.object(events.subprocess, "run") as record:
                value = copy.deepcopy(original)
                if name.startswith("agent."):
                    value["agent"][name.split(".")[1]] = replacement
                else:
                    value[name] = replacement
                envelope.write_text(json.dumps(value), encoding="utf-8")
                with self.assertRaises(ValueError):
                    self.invoke()
                record.assert_not_called()

    def test_existing_receipt_digest_mismatch_rejected_before_record(self):
        completed = subprocess.CompletedProcess([], 0, '{"state":"recorded_file"}', "")
        with (
            patch.object(events, "remote_event", return_value=(self.event, self.issue)),
            patch.object(events.subprocess, "run", return_value=completed),
        ):
            result = self.invoke()
        path = self.root / result["receipt"]
        value = events.read(path)
        value["envelope_sha256"] = "0" * 64
        path.write_text(json.dumps(value), encoding="utf-8")
        with patch.object(events.subprocess, "run") as record, self.assertRaises(ValueError):
            self.invoke()
        record.assert_not_called()

    def test_unknown_type_and_wrong_tenant_rejected(self):
        value = copy.deepcopy(self.issue)
        value["labels"][0]["name"] = "type:unknown"
        with self.assertRaises(ValueError):
            events.mapping(value, "test-request", {"type:development"})
        with patch.object(events, "remote_event") as remote, self.assertRaises(ValueError):
            events.intake(self.root, 9, 123, "test-host", "different-tenant", "test-request", Path("AGENTS.md"))
        remote.assert_not_called()

    def test_atomic_publication_failure_leaves_no_partial_target(self):
        target = self.root / "new.json"
        with (
            patch.object(events.os, "link", side_effect=OSError("synthetic publication failure")),
            self.assertRaises(OSError),
        ):
            events.write_new(target, {"complete": True})
        self.assertFalse(target.exists())
        self.assertEqual(list(self.root.glob(".issue-pending-*")), [])
        events.write_new(target, {"complete": True})
        with self.assertRaises(FileExistsError):
            events.write_new(target, {"complete": False})
        self.assertEqual(events.read(target), {"complete": True})

    def test_process_exit_releases_os_lock(self):
        lock = self.root / "crash.lock"
        program = (
            "import os; from pathlib import Path; from issue_events import event_lock\nwith event_lock(Path("
            + repr(str(lock))
            + ")):\n os._exit(0)\n"
        )
        subprocess.run([sys.executable, "-c", program], cwd=Path(events.__file__).parent, check=True, timeout=10)
        with events.event_lock(lock):
            self.assertTrue(lock.exists())


if __name__ == "__main__":
    unittest.main()
