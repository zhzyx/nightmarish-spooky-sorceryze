"""Checks for identity, retry and recovery of local Kuafu handoffs."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import kuafu_incident as host


class LocalHandoffTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for name, replacement in (
            ("git", lambda root, *args: b"a" * 40 if "HEAD" in args and "rev-parse" in args else b"index"),
            ("private_root", lambda root: self.root / "private"),
        ):
            fake = patch.object(host, name, replacement)
            fake.start()
            self.addCleanup(fake.stop)
        fake = patch.object(host.work_items, "config", return_value=({"repository": "foo/bar"}, []))
        fake.start()
        self.addCleanup(fake.stop)

    def detect(self):
        return host.capture(self.root, 123, "task", "validation", "DO_NOT_STORE_RAW_LOGS", "origin/main")

    def test_redaction_retry_and_bound_success(self):
        notice = self.detect()
        self.assertEqual(self.detect(), notice)
        folder = host.private_root(self.root) / notice["incident"]
        self.assertNotIn("DO_NOT_STORE_RAW_LOGS", (folder / "detected.json").read_text())
        host.observe_success(self.root, 123, "task", "validation", {}, "wrong-base")
        self.assertFalse(list(folder.glob("recheck-*.json")))
        host.observe_success(self.root, 123, "task", "validation", {"result": "passed"}, "origin/main")
        self.assertEqual(host.read(next(folder.glob("recheck-*.json")))["state"], "operation_reverified")
        self.assertFalse((folder / "received.json").exists())

    def test_candidate_recheck_keeps_original_pending_and_condition_is_independent(self):
        key = self.detect()["incident"]
        folder = host.private_root(self.root) / key
        record = host.read(folder / "detected.json")
        self.assertEqual(
            host.recovery_summary(folder, record),
            dict(first_failure_at=record["occurred_at"], condition_observed_at=None, reverified_at=None),
        )
        binding = dict(operator="alice", worker="release-worker")
        condition = host.record_condition(folder, record, binding, "verified prerequisite receipt")
        self.assertEqual(host.record_condition(folder, record, binding, "verified prerequisite receipt"), condition)
        with self.assertRaisesRegex(ValueError, "Reconcile"):
            host.record_condition(folder, record, binding, "different receipt")
        with patch.object(host, "git", side_effect=lambda root, *args: b"b" * 40 if "rev-parse" in args else b"index"):
            for _ in range(2):
                host.observe_success(self.root, 123, "task", "validation", {}, "origin/main")
        self.assertEqual(len(list(folder.glob("recheck-*.json"))), 1)
        pending = host.recovery_summary(folder, record)
        self.assertEqual(pending["condition_observed_at"], condition["observed_at"])
        self.assertIsNone(pending["reverified_at"])
        host.observe_success(self.root, 123, "task", "validation", {}, "origin/main")
        completed = host.recovery_summary(folder, record)
        self.assertGreaterEqual(completed["reverified_at"], completed["condition_observed_at"])
        self.assertEqual(len(list(folder.glob("recheck-*.json"))), 2)
        recurrence = self.detect()["incident"]
        self.assertNotEqual(recurrence, key)
        self.assertEqual(self.detect()["incident"], recurrence)
        latest = host.private_root(self.root) / recurrence
        self.assertIsNone(host.recovery_summary(latest, host.read(latest / "detected.json"))["reverified_at"])

    def test_condition_restores_only_the_bound_legacy_pending_pointer(self):
        key = self.detect()["incident"]
        folder = host.private_root(self.root) / key
        pending = host.operation_folder(self.root, 123, "task", "validation", "origin/main") / (key + ".pending")
        record = host.read(folder / "detected.json")
        record.pop("validation_base")
        (folder / "detected.json").write_text(json.dumps(record), encoding="utf8")
        # Pre-upgrade observe_success kept the successor receipt and removed this pointer.
        host.write_new(
            folder / "recheck-legacy.json", {"state": "recovery_candidate", "observed_at": "2026-01-01T01:00:00Z"}
        )
        pending.unlink()
        binding = {"operator": "alice", "worker": "worker"}
        host.record_condition(folder, record, binding, "dependency-readback")
        self.assertEqual(host.read(pending), {"incident": key})
        host.observe_success(self.root, 123, "task", "validation", {}, "origin/main")
        self.assertTrue(pending.exists())
        self.assertIsNone(host.recovery_summary(folder, record)["reverified_at"])

    def test_same_named_base_moving_does_not_verify_the_original(self):
        key = self.detect()["incident"]
        folder = host.private_root(self.root) / key
        with patch.object(host, "validation_base", return_value="f" * 40):
            host.observe_success(self.root, 123, "task", "validation", {}, "origin/main")
        self.assertEqual(host.read(next(folder.glob("recheck-*.json")))["state"], "recovery_candidate")
        self.assertIsNone(host.recovery_summary(folder, host.read(folder / "detected.json"))["reverified_at"])

    def test_unknown_workflow_dispatch_not_replayed(self):
        n = self.detect()
        with patch.object(host.issue_gate, "check_repository"), patch.object(host.work_items, "gh") as api:
            api.side_effect = [
                json.dumps({
                    "state": "open",
                    "body": "<!-- gonggong-request:task -->",
                    "labels": [{"name": "workspace:gonggong"}],
                }),
                "active",
                ValueError("lost reply"),
            ]
            self.assertEqual(host.send_to_kuafu(self.root, n)["dispatch"], "unconfirmed_reconcile_before_retry")
            api.side_effect = ["writer", '[{"workflow_runs":[]}]']
            self.assertEqual(host.send_to_kuafu(self.root, n)["dispatch"], "unconfirmed_reconcile_before_retry")
            api.side_effect = [
                "writer",
                json.dumps([
                    {"workflow_runs": [{"display_title": "kuafu-local-" + n["incident"], "html_url": "verified-run"}]}
                ]),
            ]
            self.assertEqual(host.send_to_kuafu(self.root, n)["dispatch"]["response"], "verified-run")
            self.assertEqual(sum(call.args[:2] == ("workflow", "run") for call in api.call_args_list), 1)

    def test_wrong_source_retained_without_dispatch(self):
        n = self.detect()
        with (
            patch.object(host.issue_gate, "check_repository"),
            patch.object(
                host.work_items,
                "gh",
                return_value=json.dumps({
                    "state": "open",
                    "body": "<!-- gonggong-request:other -->",
                    "labels": [{"name": "workspace:gonggong"}],
                }),
            ) as api,
        ):
            self.assertEqual(host.send_to_kuafu(self.root, n)["dispatch"], "source_binding_unconfirmed")
            self.assertEqual(api.call_count, 1)
