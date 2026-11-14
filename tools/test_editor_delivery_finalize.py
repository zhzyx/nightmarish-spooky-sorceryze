import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "delivery_finalize", Path(__file__).with_name("editor_delivery_finalize.py")
)
assert spec is not None and spec.loader is not None
delivery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(delivery)


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.git("init", "-b", "candidate")
        self.git("config", "user.name", "fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("remote", "add", "origin", "https://github.com/org/repo.git")
        (self.root / "tools").mkdir()
        (self.root / ".github").mkdir()
        (self.root / "SConstruct").write_text("fixture")
        (self.root / "tools/editor_self_build.py").write_text("fixture")
        (self.root / "work-items.json").write_text(json.dumps({"repository": "org/repo", "tenant_id": "fixture"}))
        (self.root / ".github/labels.json").write_text(json.dumps([{"name": "type:bug"}]))
        self.git("add", ".")
        self.git("commit", "-m", "fixture")
        self.base = self.git("rev-parse", "HEAD")
        self.git("commit", "--allow-empty", "-m", "candidate")
        self.candidate = self.git("rev-parse", "HEAD")
        self.common = self.root / ".git"
        self.binding = {
            "version": 1,
            "state": "prepared",
            "owner": "parent-owner",
            "issue": 9,
            "request_id": "flow-test",
            "common_dir": str(self.common),
            "repository": "org/repo",
            "origin": "https://github.com/org/repo.git",
            "source_root": str(self.root),
            "branch": "candidate",
            "base_sha": self.base,
        }
        digest = delivery._candidate.candidate_digest(self.common, "org/repo", 9, "flow-test", "parent-owner")
        path = self.common / "gonggong-engine-candidates" / (digest + ".json")
        path.parent.mkdir()
        path.write_text(json.dumps(self.binding))
        self.binding["binding_path"] = str(path)
        self.request = {
            "schema_version": 1,
            "owner": "parent-owner",
            "snapshot_id": "snapshot",
            "generation": 4,
            "nonce": "fresh-nonce",
            "source_root": str(self.root),
            "binding": self.binding,
            "pr": 7,
            "expected_candidate": self.candidate,
            "expected_signed_commit": "b" * 40,
            "acceptance_items": [
                {
                    "id": "A1",
                    "module": "feature",
                    "acceptance": "Actual behavior",
                    "state": "done",
                    "evidence": "real fixture receipt digest",
                }
            ],
        }
        self.issue = {
            "number": 9,
            "url": "https://github.com/org/repo/issues/9",
            "body": "<!-- gonggong-request:flow-test -->",
            "state": "OPEN",
            "stateReason": None,
            "labels": [{"name": x} for x in ["type:bug", "workspace:gonggong", "status:in-progress", "business:keep"]],
        }
        self.writes = []
        self.comments = []
        self.check_state = "SUCCESS"
        self.activation = {"state": "activated"}
        self.failure = None
        self.changed_report = {}
        self.inspect_patch = patch.object(delivery.submission, "inspect_pr", side_effect=self.inspect)
        self.gh_patch = patch.object(delivery.submission.work_items, "gh", side_effect=self.gh)
        self.actor_patch = patch.object(
            delivery.submission, "writer", return_value={"login": "fixture", "databaseId": 1}
        )
        self.activation_patch = patch.object(
            delivery._activation, "after_delivery", side_effect=lambda *args: copy.deepcopy(self.activation)
        )
        for mocked in (self.inspect_patch, self.gh_patch, self.actor_patch, self.activation_patch):
            mocked.start()
            self.addCleanup(mocked.stop)

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args], stderr=subprocess.DEVNULL).decode().strip()

    def inspect(self, root, repository, pr):
        self.assertEqual((root, repository, pr), (self.root, "org/repo", 7))
        result = {
            "repository": repository,
            "issue": 9,
            "request_id": "flow-test",
            "candidate": self.candidate,
            "signed_commit": "b" * 40,
            "tree": self.git("rev-parse", "HEAD^{tree}"),
            "current_main": self.candidate,
            "merge_commit": self.candidate,
            "pull_request": "https://github.com/org/repo/pull/7",
            "pr_state": "MERGED",
            "delivered_paths_differ": [],
            "issue_receipt": {
                "state": self.issue["state"],
                "reason": self.issue["stateReason"],
                "labels": [v["name"] for v in self.issue["labels"]],
            },
        }
        result.update(self.changed_report)
        return result

    def gh(self, *args):
        if args[:2] == ("pr", "view"):
            return json.dumps({
                "headRefOid": "b" * 40,
                "statusCheckRollup": [{"name": "actual CI", "status": "COMPLETED", "conclusion": self.check_state}],
            })
        if args[:2] == ("issue", "view"):
            return json.dumps(self.issue)
        if args[0] == "api":
            return json.dumps([self.comments])
        self.writes.append(args)
        if args[:2] == ("issue", "comment"):
            self.comments.append({"body": Path(args[-1]).read_text()})
        elif "--add-label" in args:
            self.issue["labels"].append({"name": args[-1]})
            if self.failure == "concurrent_status":
                self.issue["labels"].append({"name": "status:blocked"})
        elif "--remove-label" in args:
            if self.failure == "remove_once":
                self.failure = None
                raise ValueError("interrupted before label removal")
            self.issue["labels"] = [value for value in self.issue["labels"] if value["name"] != args[-1]]
        elif args[:2] == ("issue", "close"):
            self.issue.update(state="CLOSED", stateReason="COMPLETED")
            if self.failure == "unknown_close":
                self.failure = None
                raise subprocess.TimeoutExpired("gh", 120)
        else:
            self.fail(args)
        return ""

    def complete(self, request=None):
        return delivery.complete(self.root, request or self.request)

    def test_real_git_owner_binding_then_done_close_readback_and_idempotent_retry(self):
        result = self.complete()
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["completion_verified"])
        self.assertEqual(result["acceptance_declaration"]["source"], "authorized_worker_declaration")
        self.assertEqual(result["host_facts"]["candidate"], self.candidate)
        self.assertIn({"name": "business:keep"}, self.issue["labels"])
        self.assertEqual(len(self.comments), 1)
        count = len(self.writes)
        self.assertTrue(self.complete()["ok"])
        self.assertEqual(len(self.writes), count, "Closed retry must not repeat Issue mutations")

    def test_foreign_pr_candidate_signature_or_delivery_never_mutates(self):
        for change in (
            {"issue": 10},
            {"request_id": "foreign"},
            {"candidate": "c" * 40},
            {"signed_commit": "c" * 40},
            {"pr_state": "OPEN"},
            {"delivered_paths_differ": ["file"]},
        ):
            with self.subTest(change=change):
                self.changed_report = change
                result = self.complete()
                self.assertFalse(result["completion_verified"])
                self.assertFalse(result["mutations_may_have_started"])
                self.assertEqual(self.writes, [])

    def test_missing_or_failed_ci_and_unknown_acceptance_keep_issue_open(self):
        for state in ("FAILURE", "PENDING", "CANCELLED", "NEUTRAL"):
            self.check_state = state
            self.assertFalse(self.complete()["completion_verified"])
        self.check_state = "SUCCESS"
        for state in ("remaining", "unknown"):
            self.request["acceptance_items"][0]["state"] = state
            self.assertFalse(self.complete()["completion_verified"])
        self.assertEqual(self.writes, [])

    def test_host_owner_and_current_source_are_revalidated(self):
        request = copy.deepcopy(self.request)
        request["owner"] = "foreign"
        self.assertFalse(self.complete(request)["completion_verified"])
        (self.root / "SConstruct").write_text("changed")
        self.assertFalse(self.complete()["completion_verified"])
        self.assertEqual(self.writes, [])

    def test_partial_label_transition_reconciles_only_own_prior_status(self):
        self.failure = "remove_once"
        first = self.complete()
        self.assertFalse(first["completion_verified"])
        self.assertTrue(first["mutations_may_have_started"])
        self.assertEqual(self.issue["state"], "OPEN")
        self.assertTrue(self.complete()["completion_verified"])
        self.assertEqual(len(self.comments), 1)
        self.assertEqual(sum("--add-label" in item for item in self.writes), 1)

    def test_concurrent_status_stops_without_closing(self):
        self.failure = "concurrent_status"
        self.assertFalse(self.complete()["completion_verified"])
        self.assertEqual(self.issue["state"], "OPEN")
        self.assertFalse(self.complete()["completion_verified"])
        self.assertFalse(any(item[:2] == ("issue", "close") for item in self.writes))

    def test_lost_close_receipt_is_unknown_then_read_back_without_repeating_write(self):
        self.failure = "unknown_close"
        result = self.complete()
        self.assertFalse(result["completion_verified"])
        self.assertTrue(result["mutations_may_have_started"])
        self.assertEqual(self.issue["state"], "CLOSED")
        count = len(self.writes)
        self.assertTrue(self.complete()["completion_verified"])
        self.assertEqual(len(self.writes), count)

    def test_changed_active_status_after_partial_failure_is_read_only(self):
        self.failure = "remove_once"
        self.assertFalse(self.complete()["completion_verified"])
        self.issue["labels"] = [item for item in self.issue["labels"] if not item["name"].startswith("status:")]
        self.issue["labels"].append({"name": "status:in-review"})
        count = len(self.writes)
        self.assertFalse(self.complete()["completion_verified"])
        self.assertEqual(len(self.writes), count)
        self.assertEqual(self.issue["state"], "OPEN")

    def test_activation_pending_preserves_completed_issue_without_claiming_activation(self):
        self.activation = {"state": "pending", "error": "actual_failure"}
        result = self.complete()
        self.assertTrue(result["completion_verified"])
        self.assertFalse(result["ok"])
        self.assertEqual(result["stage"], "activation_pending")
        count = len(self.writes)
        self.activation = {"state": "activated"}
        self.assertTrue(self.complete()["ok"])
        self.assertEqual(len(self.writes), count)

    def test_cancelled_or_ambiguous_issue_is_not_completed(self):
        self.issue.update(state="CLOSED", stateReason="NOT_PLANNED")
        self.assertFalse(self.complete()["completion_verified"])
        self.issue.update(state="OPEN", stateReason=None)
        self.issue["body"] += "\n<!-- gonggong-request:other -->"
        self.assertFalse(self.complete()["completion_verified"])
        self.assertEqual(self.writes, [])

    def test_no_write_authority_is_not_replaced_by_old_host_binding(self):
        with patch.object(
            delivery.submission, "writer", side_effect=ValueError("Repository write permission required")
        ):
            self.assertFalse(self.complete()["completion_verified"])
        self.assertEqual(self.writes, [])

    def test_untracked_source_design_or_business_data_is_not_treated_as_delivered(self):
        for name in ("new-source.cpp", "design-docs/new.md", "data-collection/new.json"):
            with self.subTest(name=name):
                path = self.root / name
                path.parent.mkdir(exist_ok=True)
                path.write_text("uncommitted")
                self.assertFalse(self.complete()["completion_verified"])
                path.unlink()
        self.assertEqual(self.writes, [])

    def test_only_checksummed_exact_request_late_telemetry_is_preserved_as_uncommitted(self):
        event = delivery._storage.event({
            "schema_version": 1,
            "event_id": "native-late-event",
            "tenant_id": "fixture",
            "request_id": "flow-test",
            "kind": "request",
            "occurred_at": "2026-11-07T00:00:00Z",
            "source_ref": "https://github.com/org/repo/issues/9",
            "agent": {"id": "fixture", "version": "1", "definition_sha256": "0" * 64, "origin": "offline-fixture"},
            "payload": {},
            "evidence_refs": [],
        })
        path = self.root / "gonggong-diting-data/events/fixture/flow-test/native-late-event.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(event))
        result = self.complete()
        self.assertTrue(result["completion_verified"], result)
        self.assertEqual(result["late_telemetry_at_start"]["count"], 1)
        self.assertFalse(result["late_telemetry_at_start"]["git_committed"])
        self.assertTrue(path.exists())
        event["sha256"] = "f" * 64
        path.write_text(json.dumps(event))
        self.assertFalse(self.complete()["completion_verified"])

    def test_recorded_base_cannot_drift_to_another_valid_ancestor(self):
        path = Path(self.binding["binding_path"])
        recorded = json.loads(path.read_text())
        recorded["base_sha"] = self.candidate
        path.write_text(json.dumps(recorded))
        result = self.complete()
        self.assertFalse(result["completion_verified"])
        self.assertEqual(self.writes, [])

    def test_real_isolated_python_entry_bootstraps_its_trusted_dependencies(self):
        worker = Path(delivery.__file__).resolve()
        result = subprocess.run([sys.executable, "-I", str(worker), "--help"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        request, output = self.root / "invalid-request.json", self.root / "invalid-result.json"
        request.write_text('{"schema_version":0}')
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                str(worker),
                "--source-root",
                str(self.root),
                "--request",
                str(request),
                "--out",
                str(output),
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 1, result.stderr)
        receipt = json.loads(output.read_text())
        self.assertFalse(receipt["completion_verified"])
        self.assertFalse(receipt["mutations_may_have_started"])
        self.assertIn("Unsupported delivery request", receipt["error"])

    def test_slice_delivery_mode_keeps_issue_open_and_deduplicates_reruns(self):
        slice_request = copy.deepcopy(self.request)
        slice_request["delivery_mode"] = "slice"
        slice_request["acceptance_items"] = [
            {
                "id": "A1",
                "module": "slice-a",
                "acceptance": "Slice A verified",
                "state": "done",
                "evidence": "slice-a-proof",
            },
            {
                "id": "A2",
                "module": "slice-b",
                "acceptance": "Slice B handled by collaborator B",
                "state": "remaining",
                "evidence": "assigned-to-collaborator-b",
            },
        ]

        def gh_with_rerun(*args):
            if args[:2] == ("pr", "view"):
                return json.dumps({
                    "headRefOid": "b" * 40,
                    "statusCheckRollup": [
                        {
                            "name": "actual CI",
                            "workflowName": "GHA",
                            "status": "COMPLETED",
                            "conclusion": "FAILURE",
                            "completedAt": "2026-11-14T00:01:00Z",
                        },
                        {
                            "name": "actual CI",
                            "workflowName": "GHA",
                            "status": "COMPLETED",
                            "conclusion": "SUCCESS",
                            "completedAt": "2026-11-14T00:05:00Z",
                        },
                    ],
                })
            return self.gh(*args)

        with patch.object(delivery.submission.work_items, "gh", side_effect=gh_with_rerun):
            result = self.complete(slice_request)
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["completion_verified"])
        self.assertEqual(result["delivery_mode"], "slice")
        self.assertEqual(self.issue["state"], "OPEN")
        self.assertIn({"name": "status:in-progress"}, self.issue["labels"])
        self.assertFalse(any(item[:2] == ("issue", "close") for item in self.writes))
        self.assertEqual(len(self.comments), 1)


if __name__ == "__main__":
    unittest.main()
