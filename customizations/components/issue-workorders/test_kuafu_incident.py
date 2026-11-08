"""Checks for identity, retry and recovery of local Kuafu handoffs."""

import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
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


class ContextHandoffTests(unittest.TestCase):
    """Private context receipts; remote identity checks are outside these unit fixtures."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.framework = self.root / "framework"
        (self.framework / "tools").mkdir(parents=True)
        (self.framework / "tools/agent-context.mjs").write_text("// synthetic subprocess fixture\n")
        profile = self.framework / "agents/kuafu/reporting.json"
        profile.parent.mkdir(parents=True)
        profile.write_text(json.dumps({"component": {"entry_sha256": "a" * 64, "version": "fixture"}}))
        self.folder = self.root / "incident"
        self.folder.mkdir()
        self.record = {"request_id": "private-context-fixture"}
        self.args = SimpleNamespace(authority="fixture-only", worker="fixture-worker")
        self.identity = ("fixture-operator", "fixture-source", "fixture-bug")

    def bind(self, framework=None):
        return host.bind_context(framework or self.framework, self.folder, self.record, self.args, self.identity)

    def linked(self, target, name):
        alias = self.root / name
        try:
            alias.symlink_to(target, target_is_directory=True)
        except OSError:
            self.skipTest("Directory links are unavailable to this test process")
        return alias

    def test_blank_context_never_creates_success_receipt(self):
        for context in (b"", b" \t\r\n", "\u00a0\u2003\n".encode()):
            with self.subTest(context=context), patch.object(host.subprocess, "check_output", return_value=context):
                with self.assertRaisesRegex(ValueError, "empty"):
                    self.bind()
                self.assertFalse((self.folder / "received.json").exists())

    def test_blank_context_does_not_rewrite_existing_receipt(self):
        with patch.object(host.subprocess, "check_output", return_value=b"synthetic context"):
            self.bind()
        received = self.folder / "received.json"
        before = received.read_bytes()
        with patch.object(host.subprocess, "check_output", return_value=b" \n"):
            with self.assertRaisesRegex(ValueError, "empty"):
                self.bind()
        self.assertEqual(received.read_bytes(), before)

    def test_context_process_failure_keeps_no_success_receipt(self):
        with patch.object(host.subprocess, "check_output", side_effect=subprocess.CalledProcessError(7, ["node"])):
            with self.assertRaises(subprocess.CalledProcessError):
                self.bind()
        self.assertFalse((self.folder / "received.json").exists())

    def test_nonempty_context_is_idempotent_and_changed_context_is_rejected(self):
        with patch.object(host.subprocess, "check_output", return_value=b"synthetic context"):
            first = self.bind()
            received = self.folder / "received.json"
            before = received.read_bytes()
            self.assertEqual(first, self.bind())
            self.assertEqual(received.read_bytes(), before)
        with patch.object(host.subprocess, "check_output", return_value=b"different synthetic context"):
            with self.assertRaisesRegex(ValueError, "context changed"):
                self.bind()
        self.assertEqual(received.read_bytes(), before)

    def test_context_script_uses_canonical_entry(self):
        alias = self.linked(self.framework, "framework-link")
        with patch.object(host.subprocess, "check_output", return_value=b"synthetic context") as execute:
            self.bind(alias)
        self.assertEqual(Path(execute.call_args.args[0][1]), self.framework / "tools/agent-context.mjs")

    def test_trusted_snapshot_returns_canonical_directory(self):
        unpacked = self.root / "unpacked"
        unpacked.mkdir()
        alias = self.linked(unpacked, "unpacked-link")
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as snapshot:
            snapshot.writestr("framework/tools/agent-context.mjs", "// private snapshot\n")
        with (
            patch.object(host.work_items, "gh", return_value="a" * 40),
            patch.object(host.subprocess, "run", return_value=subprocess.CompletedProcess(["git"], 0)),
            patch.object(host, "git", return_value=archive.getvalue()),
            patch.object(host.tempfile, "TemporaryDirectory", return_value=nullcontext(str(alias))),
        ):
            with host.trusted_framework(self.root, "fixture/repository") as framework:
                self.assertEqual(framework, unpacked / "framework")
                self.assertTrue((framework / "tools/agent-context.mjs").is_file())

    @unittest.skipUnless(shutil.which("node"), "Normal context CLI requires a Node runtime")
    def test_real_context_cli_reaches_mandate_through_directory_aliases(self):
        shutil.rmtree(self.framework)
        source = Path(__file__).resolve().parents[3] / "framework"
        shutil.copytree(source, self.framework, symlinks=True)
        canonical, binding = self.bind()
        self.assertIn("# 夸父".encode(), canonical)
        self.assertIn(b"Host mandate", canonical)
        self.assertIn(self.record["request_id"].encode(), canonical)
        self.assertEqual(binding["context_sha256"], host.sha(canonical))
        before = (self.folder / "received.json").read_bytes()
        aliases = [self.linked(self.framework, "real-framework-link")]
        if sys.platform == "darwin" and str(self.framework).startswith("/private/"):
            aliases.append(Path(str(self.framework).removeprefix("/private")))
        for alias in aliases:
            with self.subTest(alias=alias):
                self.assertNotEqual(alias, alias.resolve())
                self.assertEqual(self.bind(alias), (canonical, binding))
                self.assertEqual((self.folder / "received.json").read_bytes(), before)
