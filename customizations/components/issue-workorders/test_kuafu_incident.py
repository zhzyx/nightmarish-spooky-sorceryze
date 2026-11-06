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
