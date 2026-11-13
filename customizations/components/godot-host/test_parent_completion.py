"""Bound parent adapter tests with real Git candidate capture, controlled authority.

The native fixture separately exercises the actual installed intake and live
reviewer ownership. These tests do not authenticate a reviewer by JSON.
"""

import copy
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("parent_completion", Path(__file__).with_name("parent_completion.py"))
parent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parent)


class ParentCompletionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="parent-contract-")
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name).resolve()
        self.root = self.folder / "candidate"
        self.root.mkdir()
        self.node = shutil.which("node")
        self.assertIsNotNone(self.node, "Node is required for the actual candidate verifier")
        for args in [
            ("init", "-b", "main"),
            ("config", "user.name", "Fixture"),
            ("config", "user.email", "fixture@invalid"),
        ]:
            self.git(*args)
        (self.root / "design-docs").mkdir()
        (self.root / "design-docs/task.md").write_text("approved original design\n", encoding="utf8")
        (self.root / "output.txt").write_text("actual candidate bytes\n", encoding="utf8")
        self.git("add", ".")
        self.git("commit", "-m", "fixture")
        self.contract = {
            "version": 1,
            "scope": "complete-original-task",
            "request_id": "task",
            "issue_number": 42,
            "design_sha256": parent.hashlib.sha256((self.root / "design-docs/task.md").read_bytes()).hexdigest(),
            "criteria": [
                {
                    "id": "original-A",
                    "order": 1,
                    "criterion": "A",
                    "requirement": "execute actual test",
                    "kind": "acceptance",
                },
                {
                    "id": "original-B",
                    "order": 2,
                    "criterion": "B",
                    "requirement": "deliver actual output",
                    "kind": "delivery",
                },
            ],
        }
        self.verified = {
            "actor": {"login": "original-operator", "user_id": "1", "repo_id": "2", "repo": "example/project"},
            "row": {
                "number": 42,
                "html_url": "https://github.com/example/project/issues/42",
                "state": "open",
                "title": "Original task",
                "body": "",
            },
        }
        self.set_contract(self.contract)
        self.live = self.folder / "live.json"
        self.live.write_text(json.dumps({"active": True, "request_nonce": "live-nonce"}))
        self.request = {
            "operation": "bind",
            "issue_number": 42,
            "request_id": "task",
            "request_nonce": "live-nonce",
            "host_liveness_path": str(self.live),
            "owner": {
                "conversation": "original-parent",
                "token": "live-registration",
                "operator": "original-operator",
                "authority_ref": "native-confirmation",
            },
            "design": {
                "sha256": self.contract["design_sha256"],
                "workspace": str(self.root),
                "issue_number": "42",
                "request_id": "task",
            },
            "orders": [
                {
                    "number": i,
                    "acceptance_criteria_valid": True,
                    "acceptance_criteria": [{"id": c["criterion"], "requirement": c["requirement"]}],
                }
                for i, c in enumerate(self.contract["criteria"], 1)
            ],
            "observations": [
                {"number": 1, "state": "waiting", "ready": True, "accepted": False},
                {"number": 2, "state": "waiting", "ready": False, "accepted": False},
            ],
            "confirmation_source": parent.authority_snapshot(self.verified),
        }
        self.bridge = SimpleNamespace(host_environment=lambda root: dict(os.environ, GONGGONG_NODE=self.node))
        self.source_reads = 0

        def authority(*args):
            self.source_reads += 1
            return copy.deepcopy(self.verified)

        self.source = patch.object(parent, "source", side_effect=authority)
        self.source.start()
        self.addCleanup(self.source.stop)

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args], stderr=subprocess.STDOUT)

    def set_contract(self, contract):
        self.verified["row"]["body"] = (
            "Original full requirement\n```gonggong-parent-contract\n" + json.dumps(contract) + "\n```\n"
        )

    def execute(self, **changes):
        return parent.execute(self.bridge, self.root, dict(self.request, **changes))

    def bind(self):
        bound = self.execute()
        self.request.update(operation="check", binding=bound["binding"])
        return bound

    def authorize(self, check):
        return self.execute(
            operation="authorize",
            checked_candidate=check["candidate"],
            checked_facts=check["facts_sha256"],
            checked_action=check["action"],
        )

    def test_real_candidate_next_action_and_current_authority_rechecked(self):
        bound = self.bind()
        self.assertEqual(bound["candidate"]["head"], self.git("rev-parse", "HEAD").decode().strip())
        check = self.execute()
        self.assertEqual(check["action"], "dispatch_registered")
        self.assertEqual(self.authorize(check)["action"], "dispatch_registered")
        self.assertEqual(self.source_reads, 3)

    def test_complete_requires_all_mapped_live_decisions_including_delivery(self):
        self.bind()
        observations = self.request["observations"]
        observations[0].update(accepted=True, decision_sha256="a" * 64)
        self.assertNotEqual(self.execute()["action"], "complete")
        observations[1].update(accepted=True, decision_sha256="b" * 64)
        self.assertEqual(self.execute()["action"], "complete")

    def test_disk_done_and_closed_not_planned_do_not_accept(self):
        self.bind()
        (self.root / "done.json").write_text('{"done":true,"accepted":true}')
        self.assertEqual(self.execute()["action"], "dispatch_registered")
        self.verified["row"].update(state="closed", state_reason="not_planned")
        with self.assertRaisesRegex(ValueError, "current and open"):
            self.execute()

    def test_missing_original_contract_is_explicitly_unmapped(self):
        self.verified["row"]["body"] = "An arbitrary complete-looking checklist"
        self.assertEqual(self.execute()["state"], "unmapped")

    def test_partial_duplicate_wrong_issue_and_undeclared_delivery_rejected(self):
        for change in [
            lambda c: c["criteria"].pop(),
            lambda c: c["criteria"][1].update(id="original-A"),
            lambda c: c.update(issue_number=43),
            lambda c: c["criteria"][1].update(kind="acceptance"),
            lambda c: c["criteria"][1].update(order=3),
        ]:
            with self.subTest(change=change):
                value = copy.deepcopy(self.contract)
                change(value)
                self.set_contract(value)
                with self.assertRaises(ValueError):
                    self.execute()

    def test_actor_before_binding_and_after_binding_invalidates(self):
        self.request["owner"]["operator"] = "other-operator"
        with self.assertRaisesRegex(ValueError, "confirmation authority"):
            self.execute()
        self.request["owner"]["operator"] = "original-operator"
        self.bind()
        self.verified["actor"]["login"] = "other-operator"
        with self.assertRaisesRegex(ValueError, "confirmation authority"):
            self.execute()

    def test_source_definition_and_confirmed_design_change_rejected(self):
        self.bind()
        self.verified["row"]["title"] = "Different original task"
        with self.assertRaisesRegex(ValueError, "confirmation authority"):
            self.execute()
        self.verified["row"]["title"] = "Original task"
        (self.root / "design-docs/task.md").write_text("different design")
        with self.assertRaisesRegex(ValueError, "design changed"):
            self.execute()

    def test_incidental_remote_timestamps_are_not_source_changes(self):
        self.bind()
        self.verified["row"].update(updated_at="later-comment-time", comments=17)
        self.assertEqual(self.execute()["action"], "dispatch_registered")

    def test_check_start_race_rejects_actual_candidate_change(self):
        self.bind()
        check = self.execute()
        (self.root / "output.txt").write_text("changed after preflight")
        with self.assertRaisesRegex(ValueError, "changed before action"):
            self.authorize(check)

    def test_execution_map_change_after_check_rejected(self):
        self.bind()
        check = self.execute()
        self.request["observations"][0]["state"] = "running"
        with self.assertRaisesRegex(ValueError, "changed before action"):
            self.authorize(check)

    def test_cancellation_before_check_and_during_capture(self):
        self.bind()
        self.live.unlink()
        with self.assertRaises(FileNotFoundError):
            self.execute()
        self.live.write_text(json.dumps({"active": True, "request_nonce": "live-nonce"}))
        original = parent.candidate

        def capture(*args):
            value = original(*args)
            self.live.write_text(json.dumps({"active": False, "request_nonce": "live-nonce"}))
            return value

        with patch.object(parent, "candidate", side_effect=capture), self.assertRaisesRegex(ValueError, "cancelled"):
            self.execute()

    def test_unknown_side_effect_and_reserved_decision_never_dispatch(self):
        self.bind()
        self.assertEqual(self.execute(unknown_effect=True)["action"], "readback_required")
        self.assertEqual(self.execute(reserved_decision=True)["action"], "decision_required")

    def test_waiting_real_execution_requires_event_not_retry(self):
        self.bind()
        self.request["observations"][0].update(state="running", ready=False)
        check = self.execute()
        self.assertEqual(check["action"], "wait_event")
        self.assertEqual(self.authorize(check)["action"], "wait_event")

    def test_no_progress_is_bounded_and_transcript_is_not_progress(self):
        self.bind()
        first = self.execute()
        second = self.execute(transcript="different model words")
        self.assertEqual(first["facts_sha256"], second["facts_sha256"])
        self.assertEqual(self.execute(no_progress=2)["action"], "kuafu_required")

    def test_no_progress_invokes_existing_local_kuafu_and_preserves_deduplicated_receipt(self):
        (self.root / "work-items.json").write_text(json.dumps({"repository": "example/project"}))
        (self.root / ".github").mkdir()
        (self.root / ".github/labels.json").write_text(json.dumps([{"name": "type:bug"}]))
        self.bind()
        # Execute the installed incident implementation in its existing local
        # mode; no GitHub receiver or remote mutation is simulated as success.
        with patch.dict(os.environ, GONGGONG_KUAFU_LOCAL_ONLY="1"):
            first = self.execute(operation="blocker", no_progress=2)
            second = self.execute(operation="blocker", no_progress=2)
        one = json.loads(first["blocker_receipt"]["output"])
        two = json.loads(second["blocker_receipt"]["output"])
        self.assertEqual(one["incident"], two["incident"])
        self.assertEqual(one["dispatch"], "local_only")
        self.assertEqual(one["state"], "pending_kuafu_intake")
        self.assertEqual(one["issue"], 42)
        detected = list((self.root / ".git").rglob("detected.json"))
        self.assertEqual(len(detected), 1)
        self.assertEqual(json.loads(detected[0].read_text())["action"], "dispatch")

    def test_cold_binding_without_live_owner_is_not_restored(self):
        self.bind()
        self.live.write_text(json.dumps({"active": True, "request_nonce": "different-owner"}))
        with self.assertRaisesRegex(ValueError, "cancelled"):
            self.execute()

    def test_authority_reader_checks_actual_identity_and_write_each_time(self):
        self.source.stop()
        bridge = SimpleNamespace(host_environment=lambda root: {}, find_gh=lambda *args: "controlled-gh")
        with patch.object(
            parent,
            "run_command",
            side_effect=[
                json.dumps({"verified_issue_source": self.verified}),
                json.dumps({"login": "original-operator"}),
                json.dumps({"permission": "write"}),
            ],
        ) as calls:
            self.assertEqual(parent.source(bridge, self.root, self.request), self.verified)
            self.assertEqual(calls.call_count, 3)
        with (
            patch.object(
                parent,
                "run_command",
                side_effect=[
                    json.dumps({"verified_issue_source": self.verified}),
                    json.dumps({"login": "original-operator"}),
                    json.dumps({"permission": "read"}),
                ],
            ),
            self.assertRaisesRegex(ValueError, "write authority"),
        ):
            parent.source(bridge, self.root, self.request)
        with (
            patch.object(
                parent,
                "run_command",
                side_effect=[
                    json.dumps({"verified_issue_source": self.verified}),
                    json.dumps({"login": "other-operator"}),
                ],
            ),
            self.assertRaisesRegex(ValueError, "Operator changed"),
        ):
            parent.source(bridge, self.root, self.request)

    def test_owned_process_cancellation_prevents_late_descendant_write(self):
        target = self.folder / "late-write"
        child = "import time;from pathlib import Path;time.sleep(1);Path(" + repr(str(target)) + ").write_text('late')"
        script = "import subprocess,sys,time;subprocess.Popen([sys.executable,'-c'," + repr(child) + "]);time.sleep(5)"
        timer = threading.Timer(0.2, self.live.unlink)
        timer.start()
        self.addCleanup(timer.join)
        with self.assertRaises((OSError, ValueError)):
            parent.run_command(self.bridge, self.root, self.request, [sys.executable, "-c", script])
        time.sleep(1.1)
        self.assertFalse(target.exists(), "Cancelled owned descendant wrote late")


class ParentDeliveryIntegrationTests(unittest.TestCase):
    """Actual verifier/finalizer/journal with controlled remote readbacks.

    Independent observer snapshots are the unit-test seam. Native acceptance
    fixtures establish those snapshots through actual independent child turns.
    """

    def setUp(self):
        installation = Path(__file__).resolve().parents[3]
        spec = importlib.util.spec_from_file_location(
            "parent_existing_delivery_tests", installation / "tools/test_editor_delivery_finalize.py"
        )
        existing = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(existing)
        self.delivery = existing.delivery
        self.fixture = existing.DeliveryTests(
            "test_real_git_owner_binding_then_done_close_readback_and_idempotent_retry"
        )
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        f = self.fixture
        self.root = f.root
        (self.root / "design-docs").mkdir()
        design_path = self.root / "design-docs/flow-test.md"
        design_path.write_text("Original full controlled finalization requirement\n")
        (self.root / "evidence.txt").write_text("Actual controlled acceptance evidence\n")
        f.git("add", ".")
        f.git("commit", "-m", "Original complete task and evidence")
        f.candidate = f.git("rev-parse", "HEAD")
        f.request["expected_candidate"] = f.candidate
        contract = {
            "version": 1,
            "scope": "complete-original-task",
            "request_id": "flow-test",
            "issue_number": 9,
            "design_sha256": parent.hashlib.sha256(design_path.read_bytes()).hexdigest(),
            "criteria": [
                {
                    "id": "A1",
                    "order": 1,
                    "criterion": "observed-A",
                    "requirement": "Actual behavior",
                    "kind": "delivery",
                }
            ],
        }
        f.issue["body"] += "\n```gonggong-parent-contract\n" + json.dumps(contract) + "\n```\n"
        verified = {
            "actor": {"login": "fixture", "user_id": "1", "repo": "org/repo", "repo_id": "2"},
            "row": {
                "number": 9,
                "html_url": f.issue["url"],
                "state": "open",
                "title": "Controlled original task",
                "body": f.issue["body"],
            },
        }
        self.bridge = SimpleNamespace(
            host_environment=lambda root: dict(os.environ, GONGGONG_NODE=shutil.which("node"))
        )
        self.source_patch = patch.object(parent, "source", return_value=verified)
        self.source_patch.start()
        self.addCleanup(self.source_patch.stop)
        self.live = self.root / ".git/parent-live.json"
        self.live.write_text(json.dumps({"active": True, "request_nonce": f.request["nonce"]}))
        self.guard = {
            "operation": "bind",
            "issue_number": 9,
            "request_id": "flow-test",
            "request_nonce": f.request["nonce"],
            "host_liveness_path": str(self.live),
            "owner": {
                "conversation": f.request["owner"],
                "token": "live-controlled-owner",
                "operator": "fixture",
                "authority_ref": "native-confirmation",
            },
            "design": {
                "workspace": str(self.root),
                "sha256": contract["design_sha256"],
                "issue_number": "9",
                "request_id": "flow-test",
            },
            "confirmation_source": parent.authority_snapshot(verified),
            "orders": [
                {
                    "number": 1,
                    "acceptance_criteria_valid": True,
                    "acceptance_criteria": [{"id": "observed-A", "requirement": "Actual behavior"}],
                }
            ],
        }
        bound = parent.execute(self.bridge, self.root, self.guard)
        candidate = bound["candidate"]
        identities = []
        for identity in ("producer", "reviewer"):
            receipt = self.root / ".git" / (identity + ".json")
            receipt.write_text(identity + " controlled native-observer seam")
            identities.append({
                "worker_id": identity,
                "conversation_id": identity + "-conversation",
                "receipt": {"path": str(receipt), "sha256": parent.hashlib.sha256(receipt.read_bytes()).hexdigest()},
            })
        decision = {
            "verdict": "pass",
            "reason": "Controlled independent observer seam",
            "design_sha256": contract["design_sha256"],
            "candidate": candidate,
            "producer": identities[0],
            "reviewer": identities[1],
            "criteria": [
                {
                    "id": "observed-A",
                    "evidence": [
                        {
                            "path": "evidence.txt",
                            "sha256": parent.hashlib.sha256((self.root / "evidence.txt").read_bytes()).hexdigest(),
                        }
                    ],
                }
            ],
        }
        raw = json.dumps(decision)
        sha = parent.hashlib.sha256(raw.encode()).hexdigest()
        self.guard.update(
            operation="check",
            binding=bound["binding"],
            observations=[{"number": 1, "state": "completed", "accepted": True, "decision_sha256": sha}],
        )
        checked = parent.execute(self.bridge, self.root, self.guard)
        self.guard.update(
            operation="authorize",
            checked_candidate=checked["candidate"],
            checked_facts=checked["facts_sha256"],
            checked_action=checked["action"],
            live_decisions=[{"number": 1, "decision_json": raw, "decision_sha256": sha}],
        )
        self.request = copy.deepcopy(f.request)
        self.request["parent_completion_guard"] = self.guard
        self.original_run = parent.run_command
        self.finalizer_calls = 0

        def route(bridge, root, guard, arguments, *args, **kwargs):
            if any(str(a).endswith("editor_delivery_finalize.py") for a in arguments):
                self.finalizer_calls += 1
                payload = json.loads(Path(arguments[arguments.index("--request") + 1]).read_text())
                result = f.complete(payload)  # Actual implementation, no synthetic success.
                Path(arguments[arguments.index("--out") + 1]).write_text(json.dumps(result))
                return ""
            return self.original_run(bridge, root, guard, arguments, *args, **kwargs)

        self.runner_patch = patch.object(parent, "run_command", side_effect=route)
        self.runner_patch.start()
        self.addCleanup(self.runner_patch.stop)
        self.reader_patch = patch.object(parent, "delivery_module", return_value=self.delivery)
        self.reader_patch.start()
        self.addCleanup(self.reader_patch.stop)
        self.reader_gh = patch.object(
            self.delivery.submission.work_items,
            "gh",
            side_effect=lambda *args: (
                json.dumps({"login": "fixture", "id": 1}) if args == ("api", "user") else f.gh(*args)
            ),
        )
        self.reader_gh.start()
        self.addCleanup(self.reader_gh.stop)

    def test_complete_live_proofs_enter_actual_finalizer_and_journal(self):
        result = parent.finalize(self.bridge, self.root, self.request)
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["completion_verified"])
        self.assertEqual(self.finalizer_calls, 1)
        self.assertEqual(self.fixture.issue["state"], "CLOSED")
        self.assertTrue(list((self.root / ".git/gonggong-delivery-finalization").glob("*.json")))

    def test_producer_checklist_cannot_enter_finalizer_before_acceptance(self):
        self.guard["observations"][0]["accepted"] = False
        with self.assertRaisesRegex(ValueError, "Independent complete acceptance"):
            parent.finalize(self.bridge, self.root, self.request)
        self.assertEqual(self.finalizer_calls, 0)
        self.assertEqual(self.fixture.writes, [])

    def test_approval_delay_rechecks_actual_candidate_and_decision_bytes(self):
        (self.root / "evidence.txt").write_text("changed during approval")
        with self.assertRaises(ValueError):
            parent.finalize(self.bridge, self.root, self.request)
        self.assertEqual(self.finalizer_calls, 0)
        self.assertEqual(self.fixture.writes, [])

    def test_lost_close_receipt_readback_is_exact_and_zero_mutation_even_after_revocation(self):
        self.fixture.failure = "unknown_close"
        result = parent.finalize(self.bridge, self.root, self.request)
        self.assertFalse(result["completion_verified"])
        self.assertEqual(self.fixture.issue["state"], "CLOSED")
        count = len(self.fixture.writes)
        self.live.unlink()  # A stopped/cold owner is not recreated by readback.
        with patch.object(self.delivery.submission, "writer", side_effect=ValueError("WRITE revoked")):
            readback = parent.readback_delivery(self.root, self.request)
        self.assertTrue(readback["completion_verified"])
        self.assertTrue(readback["read_only"])
        self.assertFalse(readback["business_acceptance_restored"])
        self.assertFalse(readback["mutations_replayed"])
        self.assertEqual(len(self.fixture.writes), count)
        wrong = copy.deepcopy(self.request)
        wrong["nonce"] = wrong["parent_completion_guard"]["request_nonce"] = "unrelated-attempt"
        with self.assertRaisesRegex(ValueError, "no observed attempt"):
            parent.readback_delivery(self.root, wrong)
        self.assertEqual(len(self.fixture.writes), count)
        # An otherwise matching owner/nonce cannot use another signed delivery
        # when that attempt carries explicit candidate facts.
        attempt_path = next((self.root / ".git/gonggong-delivery-finalization/attempts").glob("*.json"))
        attempt = json.loads(attempt_path.read_text())
        attempt["host_facts"] = {"candidate": "f" * 40}
        attempt_path.write_text(json.dumps(attempt))
        with self.assertRaisesRegex(ValueError, "no observed attempt"):
            parent.readback_delivery(self.root, self.request)
        self.assertEqual(len(self.fixture.writes), count)

    def test_activation_pending_uses_existing_native_retry_contract(self):
        self.fixture.activation = {"state": "pending", "error": "controlled activation wait"}
        result = parent.finalize(self.bridge, self.root, self.request)
        self.assertTrue(result["completion_verified"])
        self.assertFalse(result["ok"])
        journal = next((self.root / ".git/gonggong-delivery-finalization").glob("*.json"))
        original = journal.read_bytes()
        filename = Path(__file__).resolve().parents[3] / "tools/editor_delivery_retry.py"
        spec = importlib.util.spec_from_file_location("parent_actual_delivery_retry", filename)
        retry = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(retry)
        retry.delivery = self.delivery
        request = copy.deepcopy(self.fixture.request)
        request.pop("acceptance_items")
        request.update(
            kind="native_delivery_retry",
            host_action_request_id="parent-recovery-1",
            original_journal_sha256=retry.sha(original),
            generation=0,
            nonce="new-recovery-observation",
            engine_pid=os.getpid(),
            host_instance_id="d" * 32,
        )
        self.fixture.activation = {"state": "activated"}
        before = len(self.fixture.writes)
        recovered = retry.retry(self.root, request)
        self.assertTrue(recovered["ok"], recovered)
        self.assertTrue(recovered["completion_verified"])
        self.assertEqual(len(self.fixture.writes), before)
        self.assertEqual(journal.read_bytes(), original)


@unittest.skipIf(os.name == "nt", "POSIX nested groups; Windows descendants use the enclosing Job")
class ParentDeliveryOwnershipTests(unittest.TestCase):
    def setUp(self):
        tools = Path(__file__).resolve().parents[3] / "tools"
        sys.path.insert(0, str(tools))
        self.addCleanup(sys.path.remove, str(tools))
        import test_editor_provenance_guard as provenance

        self.provenance = provenance
        self.fixture = provenance.ProvenanceGuardTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def check_outer_termination(self, *, timeout):
        fixture = self.fixture
        cancel = fixture.folder / "outer.cancel"
        live = fixture.folder / "delivery.request.json"
        ready = fixture.folder / "child-ready"
        effect = fixture.folder / "late-effect"
        live.write_text(json.dumps({"active": True, "request_nonce": "owned-delivery"}))
        child = (
            "import time;from pathlib import Path;Path(" + repr(str(ready)) + ").write_text('started');"
            "time.sleep(3.5);Path(" + repr(str(effect)) + ").write_text('late mutation')"
        )
        adapter = Path(__file__).with_name("parent_completion.py")
        driver = (
            "import importlib.util,os,sys;from pathlib import Path;from types import SimpleNamespace;"
            "spec=importlib.util.spec_from_file_location('parent_adapter'," + repr(str(adapter)) + ");"
            "module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);"
            "module.run_command(SimpleNamespace(host_environment=lambda _:dict(os.environ)),"
            "Path("
            + repr(str(fixture.root))
            + "),"
            + repr({"host_liveness_path": str(live), "request_nonce": "owned-delivery"})
            + ",[sys.executable,'-c',"
            + repr(child)
            + "],timeout=10)"
        )

        def cancel_after_start():
            deadline = time.monotonic() + 10
            while not ready.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            if ready.exists():
                cancel.write_text("cancel\n")

        watcher = None
        if not timeout:
            watcher = threading.Thread(target=cancel_after_start)
            watcher.start()
        try:
            code = self.provenance.guard.run_guard(
                fixture.binding,
                [sys.executable, "-B", "-c", driver],
                cwd=fixture.root,
                cancel_file=cancel,
                timeout=2 if timeout else 15,
            )
        finally:
            if watcher is not None:
                watcher.join()
        # Keep the inner live marker active: this exercises termination of the
        # outer owner itself, including the race before native live revocation.
        self.assertTrue(json.loads(live.read_text())["active"])
        self.assertTrue(ready.exists(), "The nested command must actually have started")
        self.assertNotEqual(code, 0)
        deadline = time.monotonic() + 3.75
        while not effect.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertFalse(effect.exists(), "Nested command escaped the cancelled provenance owner")

    def test_provenance_cancel_closes_nested_command_with_live_request(self):
        self.check_outer_termination(timeout=False)

    def test_provenance_timeout_closes_nested_command_with_live_request(self):
        self.check_outer_termination(timeout=True)


if __name__ == "__main__":
    unittest.main()
