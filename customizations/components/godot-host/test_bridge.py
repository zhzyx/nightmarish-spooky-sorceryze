import importlib.util
import json
import tempfile
import time
import types
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("bridge", Path(__file__).with_name("bridge.py"))
assert spec is not None and spec.loader is not None
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


def batch_receipt(kwargs):
    import hashlib

    receipts = []
    for path in json.loads(kwargs["input"]):
        envelope = json.loads(Path(path).read_text(encoding="utf-8"))
        body = {key: value for key, value in envelope.items() if key != "sha256"}
        digest = hashlib.sha256(
            json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        receipts.append(
            dict(state="recorded_file", tenant_id=envelope["tenant_id"], event_id=envelope["event_id"], sha256=digest)
        )
    return json.dumps(dict(ok=True, receipts=receipts))


class IssueIntakeRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.request = {"issue_number": 165, "request_id": "fixture-request"}
        self.env = patch.object(bridge, "host_environment", return_value={"PATH": "fixture"})
        self.env.start()
        self.addCleanup(self.env.stop)

    def result(self, stderr="", ok=False):
        return types.SimpleNamespace(
            returncode=0 if ok else 1,
            stderr=stderr,
            stdout='{"number":165,"url":"https://github.com/test/repo/issues/165"}' if ok else "",
        )

    def receipts(self):
        return [
            json.loads(path.read_text()) for path in (self.root / ".gonggong-outbox/intake-failures").glob("*.json")
        ]

    def test_success_reads_once_and_never_records_a_failure(self):
        with patch.object(bridge.subprocess, "run", return_value=self.result(ok=True)) as run:
            self.assertEqual(bridge.issue_binding(self.root, self.request, "tenant")["number"], 165)
        self.assertEqual(run.call_count, 1)
        self.assertIn("--intake-only", run.call_args.args[0])
        self.assertEqual(self.receipts(), [])

    def test_recognised_transient_failure_rechecks_read_once(self):
        for code in ["GITHUB_NETWORK", "GITHUB_HTTP_429", "GITHUB_HTTP_500", "GITHUB_HTTP_503"]:
            with (
                self.subTest(code=code),
                patch.object(bridge.time, "monotonic", side_effect=(10.0 + i / 10 for i in range(100))),
                patch.object(
                    bridge.subprocess,
                    "run",
                    side_effect=[
                        self.result(code + ": fixture transient error"),
                        self.result(ok=True),
                    ],
                ) as run,
            ):
                self.assertEqual(bridge.issue_binding(self.root, self.request, "tenant")["number"], 165)
                self.assertEqual(run.call_count, 2)
                self.assertEqual(run.call_args_list[0].args, run.call_args_list[1].args)
                self.assertGreater(run.call_args_list[0].kwargs["timeout"], run.call_args_list[1].kwargs["timeout"])

    def test_permission_binding_and_unknown_errors_never_retry(self):
        for error in [
            "GITHUB_HTTP_401",
            "GITHUB_HTTP_403",
            "GITHUB_HTTP_404",
            "GITHUB_COMMAND",
            "Issue is not open",
            "Host tenant must match work-items.json",
            "fixture unexpected failure",
        ]:
            with (
                self.subTest(error=error),
                patch.object(bridge.subprocess, "run", return_value=self.result(error)) as run,
            ):
                with self.assertRaisesRegex(ValueError, "Issue intake rejected:"):
                    bridge.issue_binding(self.root, self.request, "tenant")
                self.assertEqual(run.call_count, 1)

    def test_repeated_transient_failure_is_bounded_at_two_reads(self):
        with patch.object(bridge.subprocess, "run", return_value=self.result("GITHUB_NETWORK: unavailable")) as run:
            with self.assertRaisesRegex(ValueError, "GITHUB_NETWORK; read attempts=2"):
                bridge.issue_binding(self.root, self.request, "tenant")
        self.assertEqual(run.call_count, 2)
        self.assertEqual({r["read_attempt"] for r in self.receipts()}, {1, 2})

    def test_no_retry_after_total_budget_is_exhausted(self):
        with (
            patch.object(bridge.time, "monotonic", side_effect=[0, 0, 121]),
            patch.object(bridge.subprocess, "run", return_value=self.result("GITHUB_NETWORK: unavailable")) as run,
        ):
            with self.assertRaisesRegex(ValueError, "read attempts=1"):
                bridge.issue_binding(self.root, self.request, "tenant")
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.kwargs["timeout"], 120)

    def test_timeout_is_recorded_without_an_unbounded_read(self):
        with (
            patch.object(bridge.time, "monotonic", side_effect=[0, 0, 121]),
            patch.object(bridge.subprocess, "run", side_effect=bridge.subprocess.TimeoutExpired("fixture", 120)) as run,
        ):
            with self.assertRaisesRegex(ValueError, "GITHUB_TIMEOUT; read attempts=1"):
                bridge.issue_binding(self.root, self.request, "tenant")
        self.assertEqual(run.call_count, 1)
        self.assertEqual(self.receipts()[0]["code"], "GITHUB_TIMEOUT")

    def test_second_read_rejection_never_reuses_prior_permission(self):
        with patch.object(
            bridge.subprocess,
            "run",
            side_effect=[
                self.result("GITHUB_NETWORK: unavailable"),
                self.result("Issue is not open"),
            ],
        ) as run:
            with self.assertRaisesRegex(ValueError, "Issue is not open; read attempts=2"):
                bridge.issue_binding(self.root, self.request, "tenant")
        self.assertEqual(run.call_count, 2)

    def test_arbitrary_stderr_is_private_bounded_and_not_reflected_in_the_ui(self):
        stderr = "fixture-private-secret " + "x" * 10000
        with patch.object(bridge.subprocess, "run", return_value=self.result(stderr)):
            with self.assertRaises(ValueError) as caught:
                bridge.issue_binding(self.root, self.request, "tenant")
        self.assertIn("INTAKE_LOCAL_FAILURE", str(caught.exception))
        self.assertNotIn("fixture-private-secret", str(caught.exception))
        receipt = self.receipts()[0]
        self.assertEqual(len(receipt["stderr"]), 8192)
        if bridge.os.name != "nt":
            path = next((self.root / ".gonggong-outbox/intake-failures").glob("*.json"))
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)


class IntakeClassificationTests(unittest.TestCase):
    def envelope(self):
        return {
            "incident": "a" * 64,
            "state": "pending_kuafu_intake",
            "issue": 387,
            "action": "intake",
            "next_action": "The active host must invoke Kuafu now: receive, investigate, then assess with the actual worker and bug.",
            "dispatch": {"state": "dispatch_requested"},
        }

    def test_known_incident_envelope_preserves_fixed_binding_reason(self):
        prefix = json.dumps(self.envelope())
        error = "Issue requires exactly one active status label"
        self.assertEqual(bridge.intake_failure_reason(prefix + "\n" + error + "\n"), ("ISSUE_BINDING", False, error))
        self.assertEqual(
            bridge.intake_failure_reason(prefix + "\nGITHUB_NETWORK: failed"),
            ("GITHUB_NETWORK", True, "GITHUB_NETWORK"),
        )

    def test_arbitrary_prefix_and_substrings_are_not_unwrapped(self):
        error = "Issue requires exactly one active status label"
        for prefix in (
            "private output",
            json.dumps({"incident": "a" * 64}),
            json.dumps(dict(self.envelope(), action="delivery")),
            json.dumps(dict(self.envelope(), incident="bad")),
            json.dumps(dict(self.envelope(), issue=True)),
        ):
            with self.subTest(prefix=prefix):
                self.assertEqual(bridge.intake_failure_reason(prefix + "\n" + error)[0], "INTAKE_LOCAL_FAILURE")
        self.assertEqual(
            bridge.intake_failure_reason(json.dumps(self.envelope()) + "\nprivate\n" + error)[0], "INTAKE_LOCAL_FAILURE"
        )


class ChatGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / "CURRENT_FRAMEWORK.json").write_text(
            json.dumps({"path_base": "this_file_directory", "root": "framework", "manifest": "framework-manifest.json"})
        )
        (self.root / "framework").mkdir()
        (self.root / "framework/framework-manifest.json").write_text(
            json.dumps({
                "version": "test",
                "agents": [{"id": "yanshi", "version": "test", "entry": "entry.md", "candidate_digest": "test"}],
            })
        )
        (self.root / "framework/entry.md").write_text("Fixture only")
        self.request = {
            "request_id": "fixture",
            "outcome": "private fixture prompt",
            "authority_ref": "isolated-test",
            "project": "fixture",
            "tools_enabled": False,
            "file_changes_require_approval": True,
            "execution_requires_approval": True,
        }
        self.issue_patch = patch.object(
            bridge, "issue_binding", return_value={"url": "https://github.com/test/repo/issues/6"}
        )
        self.issue_patch.start()
        self.addCleanup(self.issue_patch.stop)

    def process(self, ok, receipt_ok=True):
        def run(command, **kwargs):
            if command[1].endswith("agent-context.mjs"):
                mandate = json.loads(Path(command[-1]).read_text())
                self.assertFalse(mandate["tool_permission"]["tools_enabled"])
                self.assertEqual(mandate["issue"]["url"], "https://github.com/test/repo/issues/6")
                self.assertIn(
                    "data-collection sources, evidence and receipts",
                    mandate["delivery_requirements"]["required_git_deliverables"],
                )
                self.assertEqual(kwargs["env"]["GONGGONG_PYTHON"], bridge.sys.executable)
                return types.SimpleNamespace(
                    returncode=0 if ok else 1, stdout="FRAMEWORK" if ok else "", stderr="admission blocked"
                )
            event = json.loads(Path(json.loads(kwargs["input"])[0]).read_text())
            self.assertNotIn(self.request["outcome"], json.dumps(event))
            self.assertEqual(event["payload"]["context_accepted"], ok)
            return types.SimpleNamespace(
                returncode=0 if receipt_ok else 1, stdout=batch_receipt(kwargs), stderr="receipt unavailable"
            )

        return run

    def test_context_is_actual_loader_output(self):
        with patch.object(bridge.subprocess, "run", side_effect=self.process(True)) as run:
            result = bridge.chat(self.root, self.request, "test")
        self.assertTrue(result["ok"])
        self.assertEqual(result["context"], "FRAMEWORK")
        self.assertEqual(run.call_count, 2)

    def test_admission_failure_cannot_send_context(self):
        with patch.object(bridge.subprocess, "run", side_effect=self.process(False)):
            result = bridge.chat(self.root, self.request, "test")
        self.assertFalse(result["ok"])
        self.assertEqual(result["context"], "")

    def test_receipt_failure_blocks_even_accepted_context(self):
        with patch.object(bridge.subprocess, "run", side_effect=self.process(True, False)):
            result = bridge.chat(self.root, self.request, "test")
        self.assertFalse(result["ok"])
        self.assertNotIn("context", result)

    def test_missing_host_permission_fails_before_launch(self):
        del self.request["tools_enabled"]
        with patch.object(bridge.subprocess, "run") as run:
            with self.assertRaises(ValueError):
                bridge.chat(self.root, self.request, "test")
        run.assert_not_called()

    def test_multiple_host_kinds_use_same_loader_and_real_agent_binding(self):
        for kind in ("engine", "ide", "cli", "production-tool"):
            request = dict(
                self.request, protocol_version=1, host={"id": "sample-" + kind, "kind": kind}, agent_id="yanshi"
            )
            with patch.object(bridge.subprocess, "run", side_effect=self.process(True)) as run:
                result = bridge.chat(self.root, request, "test")
            self.assertTrue(result["context_ready"])
            self.assertFalse(result["model_execution_started"])
            self.assertEqual(result["reporting"]["source_ref"], "https://github.com/test/repo/issues/6")
            self.assertEqual(run.call_args_list[0].args[0][-2], "yanshi")

    def test_registered_alternate_agent_is_not_rewritten_to_yanshi(self):
        manifest = self.root / "framework/framework-manifest.json"
        data = json.loads(manifest.read_text())
        data["agents"][0]["id"] = "kuafu"
        manifest.write_text(json.dumps(data))
        request = dict(self.request, protocol_version=1, host={"id": "example-cli", "kind": "cli"}, agent_id="kuafu")
        with patch.object(bridge.subprocess, "run", side_effect=self.process(True)) as run:
            result = bridge.chat(self.root, request, "test")
        self.assertEqual(run.call_args_list[0].args[0][-2], "kuafu")
        self.assertEqual(result["reporting"]["agent"]["id"], "kuafu")

    def test_invalid_identity_never_launches_loader(self):
        for changes in (
            {"protocol_version": 2},
            {"protocol_version": 1},
            {"protocol_version": 1, "host": {"id": "../escape", "kind": "ide"}, "agent_id": "yanshi"},
            {"protocol_version": 1, "host": {"id": "ide", "kind": "ide"}, "agent_id": "unknown"},
        ):
            with patch.object(bridge.subprocess, "run") as run:
                with self.assertRaises(ValueError):
                    bridge.chat(self.root, dict(self.request, **changes), "test")
            run.assert_not_called()

    def test_other_host_cannot_bypass_admission(self):
        request = dict(self.request, protocol_version=1, host={"id": "different-ide", "kind": "ide"}, agent_id="yanshi")
        with patch.object(bridge.subprocess, "run", side_effect=self.process(False)):
            result = bridge.chat(self.root, request, "test")
        self.assertFalse(result["ok"])
        self.assertEqual(result["context"], "")

    def test_local_upstream_locator_does_not_grant_admission(self):
        (self.root / ".gonggong-local.json").write_text(
            json.dumps({"GONGGONG_FRAMEWORK_SOURCE": "fixture-source", "force_approved": True})
        )
        env = bridge.host_environment(self.root)
        self.assertFalse("GONGGONG_FRAMEWORK_SOURCE" in env)
        self.assertNotIn("force_approved", env)

    def test_inherited_external_source_binding_is_removed(self):
        with patch.dict(bridge.os.environ, {"GONGGONG_FRAMEWORK_SOURCE": "Z:/missing-retired-source"}):
            env = bridge.host_environment(self.root)
        self.assertFalse("GONGGONG_FRAMEWORK_SOURCE" in env)

    def test_configured_node_is_available_to_framework_subprocesses(self):
        node = self.root / "node.exe"
        node.touch()
        with patch.dict(bridge.os.environ, {"GONGGONG_NODE": str(node), "PATH": ""}):
            env = bridge.host_environment(self.root)
        self.assertEqual(env["PATH"].split(bridge.os.pathsep)[0], str(self.root.resolve()))

    def test_workspace_runtime_does_not_require_ide_environment(self):
        node = self.root / "project/runtime/node/node.exe"
        node.parent.mkdir(parents=True)
        node.touch()
        with patch.dict(bridge.os.environ, {"PATH": ""}, clear=True):
            env = bridge.host_environment(self.root)
        self.assertEqual(env["GONGGONG_NODE"], str(node))
        self.assertEqual(env["PATH"].split(bridge.os.pathsep)[0], str(node.parent))

    def test_workspace_git_is_available_without_ide_path(self):
        git = self.root / "project/runtime/git/cmd/git.exe"
        git.parent.mkdir(parents=True)
        git.touch()
        with patch.dict(bridge.os.environ, {"PATH": ""}, clear=True):
            env = bridge.host_environment(self.root)
        self.assertEqual(env["PATH"].split(bridge.os.pathsep)[0], str(git.parent))

    def test_doctor_reports_admission_failure_without_enabling_execution(self):
        def check(command, _root):
            failed = command[-1].endswith("verify_framework.py") or command[-1] == "yanshi"
            return {"ok": not failed, "exit_code": 1 if failed else 0, "stderr": "admission blocked" if failed else ""}

        with patch.object(bridge, "run", side_effect=check), patch.object(bridge.shutil, "which", return_value="node"):
            result = bridge.diagnose(self.root)
        self.assertFalse(result["ok"])
        self.assertEqual(result["blocking_checks"], ["formal_framework_admission", "local_admission:yanshi"])
        self.assertFalse(result["model_execution_started"])
        self.assertFalse(result["host_authority_authenticated"])

    def test_broken_permit_does_not_prevent_diagnostics_or_data_validation(self):
        path = self.root / "framework/framework-manifest.json"
        manifest = json.loads(path.read_text())
        manifest["agents"][0].update(state="candidate", admission_pass="broken.json")
        path.write_text(json.dumps(manifest))
        for raw, expected in ((None, "missing"), ("{", "invalid_or_unavailable")):
            if raw is not None:
                (self.root / "framework/broken.json").write_text(raw)
            with patch.object(
                bridge, "diagnose", return_value={"ok": False, "blocking_checks": ["local_admission:yanshi"]}
            ) as diagnose:
                result = bridge.execute(self.root, "doctor", "test")
            diagnose.assert_called_once()
            self.assertFalse(result["ok"])
            self.assertEqual(result["agents"][0]["admission_record_status"], expected)
            with patch.object(bridge, "run", return_value={"ok": True}) as run:
                self.assertTrue(bridge.execute(self.root, "validate", "test")["ok"])
            run.assert_called_once()

    def test_failed_receipt_is_retried_without_duplicate_identity(self):
        with patch.object(bridge.subprocess, "run", side_effect=self.process(True, False)):
            self.assertFalse(bridge.chat(self.root, self.request, "test")["ok"])
        pending = list((self.root / ".gonggong-outbox/chat").glob("*.json"))
        self.assertEqual(len(pending), 1)
        original = pending[0].read_bytes()
        with patch.object(bridge.subprocess, "run", side_effect=self.process(True)):
            self.assertTrue(bridge.flush(self.root)["ok"])
        self.assertFalse(pending[0].exists())
        self.assertIn(b"event_id", original)

    def test_concurrent_flush_is_serialized(self):
        with patch.object(bridge.subprocess, "run", side_effect=self.process(True, False)):
            self.assertFalse(bridge.chat(self.root, self.request, "test")["ok"])

        def deliver(*args, **kwargs):
            time.sleep(0.15)
            return types.SimpleNamespace(returncode=0, stdout=batch_receipt(kwargs), stderr="")

        with (
            patch.object(bridge.subprocess, "run", side_effect=deliver) as run,
            ThreadPoolExecutor(max_workers=2) as pool,
        ):
            results = list(pool.map(lambda _: bridge.flush(self.root), range(2)))
        self.assertTrue(all(result["ok"] for result in results))
        self.assertEqual(run.call_count, 1)


class ScopedOutboxTests(unittest.TestCase):
    def test_failed_other_request_is_retained_without_blocking_current(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            other = {
                "event_id": "z-other",
                "tenant_id": "tenant",
                "request_id": "other",
                "source_ref": "https://example/issues/1",
            }
            current = {
                "event_id": "a-current",
                "tenant_id": "tenant",
                "request_id": "current",
                "source_ref": "https://example/issues/2",
            }
            bridge.enqueue(root, other)
            bridge.enqueue(root, current)
            scope = {key: current[key] for key in ("tenant_id", "request_id", "source_ref")}
            with (
                patch.object(bridge, "storage_entry", return_value="storage.py"),
                patch.object(bridge, "host_environment", return_value={}),
                patch.object(
                    bridge.subprocess,
                    "run",
                    side_effect=lambda *args, **kwargs: types.SimpleNamespace(
                        returncode=0, stdout=batch_receipt(kwargs), stderr=""
                    ),
                ) as run,
            ):
                self.assertTrue(bridge.flush(root, scope)["ok"])
                self.assertEqual(run.call_count, 1)
                self.assertTrue((root / ".gonggong-outbox/chat/z-other.json").exists())
                self.assertFalse((root / ".gonggong-outbox/chat/a-current.json").exists())
                run.side_effect = None
                run.return_value = types.SimpleNamespace(returncode=1, stdout="", stderr="failed")
                with self.assertRaises(ValueError):
                    bridge.flush(root, {key: other[key] for key in scope})
                self.assertTrue((root / ".gonggong-outbox/chat/z-other.json").exists())

    def test_cross_scope_predecessor_failure_blocks_current_and_retains_both(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            other = {"event_id": "z-other", "tenant_id": "tenant", "request_id": "other", "source_ref": "issue-1"}
            current = {
                "event_id": "a-current",
                "tenant_id": "tenant",
                "request_id": "current",
                "source_ref": "issue-2",
                "evidence_refs": ["z-other"],
            }
            bridge.enqueue(root, other)
            bridge.enqueue(root, current)
            scope = {key: current[key] for key in ("tenant_id", "request_id", "source_ref")}
            with (
                patch.object(bridge, "storage_entry", return_value="storage.py"),
                patch.object(bridge, "host_environment", return_value={}),
                patch.object(
                    bridge.subprocess,
                    "run",
                    return_value=types.SimpleNamespace(returncode=1, stdout="", stderr="failed dependency"),
                ) as run,
            ):
                with self.assertRaises(ValueError):
                    bridge.flush(root, scope)
                self.assertEqual(run.call_count, 1)
                self.assertEqual(len(list((root / ".gonggong-outbox/chat").glob("*.json"))), 2)

    def test_same_scope_cycle_is_rejected_before_delivery(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            scope = {
                "tenant_id": "tenant",
                "request_id": "current",
                "source_ref": "issue-2",
            }
            for event_id, predecessor in (("a", "z"), ("z", "a")):
                bridge.enqueue(
                    root,
                    {
                        **scope,
                        "event_id": event_id,
                        "evidence_refs": [predecessor],
                    },
                )
            with patch.object(bridge.subprocess, "run") as run:
                with self.assertRaisesRegex(ValueError, "Cyclic"):
                    bridge.flush(root, scope)
                run.assert_not_called()
            self.assertEqual(len(list((root / ".gonggong-outbox/chat").glob("*.json"))), 2)

    def test_unrelated_duplicate_identity_does_not_block_selected_scope(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            other = dict(tenant_id="tenant", event_id="other", request_id="other", source_ref="issue-1")
            current = dict(tenant_id="tenant", event_id="current", request_id="current", source_ref="issue-2")
            bridge.enqueue(root, other)
            outbox = root / ".gonggong-outbox/chat"
            (outbox / "duplicate.json").write_text(json.dumps(other), encoding="utf-8")
            bridge.enqueue(root, current)
            scope = {key: current[key] for key in ("tenant_id", "request_id", "source_ref")}
            selected = bridge.scoped_pending(sorted(outbox.glob("*.json")), scope)
            self.assertEqual([path.name for path in selected], ["current.json"])
            self.assertEqual(len(list(outbox.glob("*.json"))), 3)

    def test_duplicate_explicit_predecessor_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            other = dict(tenant_id="tenant", event_id="other", request_id="other", source_ref="issue-1")
            current = dict(
                tenant_id="tenant",
                event_id="current",
                request_id="current",
                source_ref="issue-2",
                evidence_refs=["other"],
            )
            bridge.enqueue(root, other)
            outbox = root / ".gonggong-outbox/chat"
            (outbox / "duplicate.json").write_text(json.dumps(other), encoding="utf-8")
            bridge.enqueue(root, current)
            scope = {key: current[key] for key in ("tenant_id", "request_id", "source_ref")}
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                bridge.scoped_pending(sorted(outbox.glob("*.json")), scope)
            self.assertEqual(len(list(outbox.glob("*.json"))), 3)

    def test_unmatched_batch_receipts_retain_every_envelope(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for identity in ("a", "b"):
                bridge.enqueue(
                    root, dict(event_id=identity, tenant_id="tenant", request_id="request", source_ref="issue")
                )
            result = types.SimpleNamespace(
                returncode=0,
                stdout=json.dumps({"ok": True, "receipts": [{"state": "queued"}, {"state": "queued"}]}),
                stderr="",
            )
            with (
                patch.object(bridge, "storage_entry", return_value="storage.py"),
                patch.object(bridge, "host_environment", return_value={}),
                patch.object(bridge.subprocess, "run", return_value=result),
            ):
                with self.assertRaisesRegex(ValueError, "Unmatched"):
                    bridge.flush(root)
            self.assertEqual(len(list((root / ".gonggong-outbox/chat").glob("*.json"))), 2)


class ProcessOutboxLockTests(unittest.TestCase):
    def holder(self, root):
        import subprocess
        import sys

        script = """import runpy, time, pathlib, sys
b = runpy.run_path(sys.argv[1])
root = pathlib.Path(sys.argv[2])
with b['outbox_lock'](root, time.monotonic() + 3):
    print('locked', flush=True)
    while not (root / 'release').exists():
        time.sleep(.01)
"""
        script_path = root / "holder.py"
        script_path.write_text(script, encoding="utf-8")
        process = subprocess.Popen(
            [sys.executable, str(script_path), str(Path(bridge.__file__).resolve()), str(root)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.addCleanup(process.stdout.close)
        self.addCleanup(process.stderr.close)
        self.addCleanup(lambda: process.kill() if process.poll() is None else None)
        ready = process.stdout.readline().strip()
        self.assertEqual(ready, "locked", process.stderr.read() if not ready else "")
        return process

    def test_independent_process_waits_for_healthy_owner(self):
        import threading

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            owner = self.holder(root)
            release = threading.Timer(0.15, lambda: (root / "release").touch())
            release.start()
            try:
                with bridge.outbox_lock(root, time.monotonic() + 1):
                    self.assertTrue((root / "release").exists())
            finally:
                release.join()
            self.assertEqual(owner.wait(timeout=3), 0)

    def test_independent_process_stalled_owner_remains_bounded(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            owner = self.holder(root)
            try:
                with self.assertRaisesRegex(ValueError, "delivery busy"):
                    with bridge.outbox_lock(root, time.monotonic() + 0.1):
                        self.fail("Stalled owner must not be bypassed")
            finally:
                (root / "release").touch()
            self.assertEqual(owner.wait(timeout=3), 0)
        self.assertGreater(bridge.RECEIPT_LOCK_WAIT_SECONDS, bridge.RECEIPT_EXECUTION_SECONDS)


class StorageValidationCostTests(unittest.TestCase):
    def test_batch_interrupt_after_parent_allows_graph_and_retry(self):
        import runpy
        import copy

        storage = (
            Path(bridge.__file__).resolve().parents[3]
            / "customizations/platforms/data-collection/git-files/storage/diting_files.py"
        )
        module = runpy.run_path(str(storage))
        source = next((storage.parents[5] / "gonggong-diting-data/events").rglob("*.json"))
        template = json.loads(source.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            data = root / "data"
            data.mkdir()
            paths = []
            for identity, refs in (("child", ["parent"]), ("parent", [])):
                value = copy.deepcopy(template)
                value.pop("sha256", None)
                value.pop("supersedes", None)
                value.update(event_id=identity, evidence_refs=refs)
                path = root / (identity + ".json")
                path.write_text(json.dumps(value), encoding="utf-8")
                paths.append(path)

            def load(_):
                records = {}
                for path in data.rglob("*.json"):
                    value = module["event"](json.loads(path.read_text(encoding="utf-8")))
                    records[(value["tenant_id"], value["event_id"])] = value
                module["graph"](records)
                return root, data, {}, records, []

            atomic = module["atomic_new"]
            writes = []

            def interrupt(path, value):
                writes.append(value["event_id"])
                if len(writes) == 2:
                    raise OSError("simulated interruption")
                atomic(path, value)

            function = module["record_batch"]
            with patch.dict(
                function.__globals__,
                {"load": load, "merged_records": lambda _, records: dict(records), "atomic_new": interrupt},
            ):
                with self.assertRaises(OSError):
                    function(root, paths)
                self.assertEqual(writes, ["parent", "child"])
                load(root)  # Persisted prefix remains a valid graph.
            with patch.dict(function.__globals__, {"load": load, "merged_records": lambda _, records: dict(records)}):
                result = function(root, paths)
            self.assertEqual([item["event_id"] for item in result["receipts"]], ["child", "parent"])
            self.assertTrue(result["receipts"][1]["idempotent"])
            self.assertEqual(len(load(root)[3]), 2)

    def test_batch_replays_load_once_and_return_each_receipt(self):
        import runpy

        storage = (
            Path(bridge.__file__).resolve().parents[3]
            / "customizations/platforms/data-collection/git-files/storage/diting_files.py"
        )
        module = runpy.run_path(str(storage))
        root = storage.parents[5]
        inputs = list((root / "gonggong-diting-data/events").rglob("*.json"))[:2]
        function = module["record_batch"]
        with patch.dict(function.__globals__, {"load": unittest.mock.Mock(wraps=module["load"])}):
            result = function(root, inputs)
            self.assertEqual(function.__globals__["load"].call_count, 2)
            self.assertEqual(
                function.__globals__["load"].call_args_list,
                [unittest.mock.call(root), unittest.mock.call(root, historical=True)],
            )
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["receipts"]), 2)
        self.assertTrue(all(receipt["idempotent"] for receipt in result["receipts"]))

    def test_uncached_load_does_not_resolve_each_event(self):
        import runpy

        storage = (
            Path(bridge.__file__).resolve().parents[3]
            / "customizations/platforms/data-collection/git-files/storage/diting_files.py"
        )
        module = runpy.run_path(str(storage))
        root = storage.parents[5]
        original = Path.resolve
        event_resolutions = []

        def resolve(path, *args, **kwargs):
            if path.suffix == ".json" and "events" in path.parts:
                event_resolutions.append(path)
            return original(path, *args, **kwargs)

        with patch.object(Path, "resolve", resolve):
            _, _, _, records, _ = module["load"](root)
        self.assertTrue(records)
        self.assertEqual(event_resolutions, [])


if __name__ == "__main__":
    unittest.main()
