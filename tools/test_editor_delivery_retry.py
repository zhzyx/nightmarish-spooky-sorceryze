import copy
import importlib.util
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_editor_delivery_finalize as existing

spec = importlib.util.spec_from_file_location("delivery_retry", Path(__file__).with_name("editor_delivery_retry.py"))
assert spec and spec.loader
retry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(retry)


class RetryTests(unittest.TestCase):
    def setUp(self):
        self.fixture = existing.DeliveryTests(
            "test_activation_pending_preserves_completed_issue_without_claiming_activation"
        )
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.previous_delivery = retry.delivery
        retry.delivery = existing.delivery
        self.addCleanup(setattr, retry, "delivery", self.previous_delivery)
        self.fixture.activation = {"state": "pending", "error": "fixture strict-copy failure"}
        first = self.fixture.complete()
        self.assertEqual(first["stage"], "activation_pending", first)
        self.journal = next((self.fixture.common / "gonggong-delivery-finalization").glob("*.json"))
        self.original = self.journal.read_bytes()
        self.request = copy.deepcopy(self.fixture.request)
        self.request.pop("acceptance_items")
        self.request.update(
            kind="native_delivery_retry",
            host_action_request_id="desktop-action-1",
            original_journal_sha256=retry.sha(self.original),
            generation=0,
            nonce="new-live-host-nonce",
            engine_pid=os.getpid(),
            host_instance_id="d" * 32,
        )
        self.fixture.activation = {"state": "activated"}
        self.write_count = len(self.fixture.writes)
        self.activation_count = 0
        self.fixture.activation_patch.stop()
        self.activation_patch = patch.object(retry.delivery._activation, "after_delivery", side_effect=self.activate)
        self.activation_patch.start()
        self.addCleanup(self.activation_patch.stop)

    def activate(self, *args):
        self.activation_count += 1
        return copy.deepcopy(self.fixture.activation)

    def run_retry(self, request=None):
        return retry.retry(self.fixture.root, request or self.request)

    def assert_no_issue_writes(self):
        self.assertEqual(len(self.fixture.writes), self.write_count)
        self.assertEqual(self.journal.read_bytes(), self.original)

    def test_private_transaction_survives_restart_with_separate_fresh_generation(self):
        result = self.run_retry()
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["generation"], 0)
        self.assertEqual(result["original_transaction"]["generation"], 4)
        self.assertNotEqual(result["nonce"], result["original_transaction"]["nonce"])
        self.assertEqual(result["host_facts"]["candidate"], self.fixture.candidate)
        self.assertEqual(result["actor"]["login"], "fixture")
        self.assertTrue(Path(result["host_action_receipt"]).is_file())
        self.assert_no_issue_writes()

    def test_same_host_request_is_idempotent_and_preserves_original_pending(self):
        first = self.run_retry()
        self.assertEqual(self.run_retry(), first)
        self.assertEqual(self.activation_count, 1)
        self.assert_no_issue_writes()

    def test_caller_cannot_add_business_declaration_or_path(self):
        for key, value in (
            ("acceptance_items", self.fixture.request["acceptance_items"]),
            ("journal_path", str(self.journal)),
            ("entry_type", "arbitrary"),
        ):
            request = dict(self.request, **{key: value})
            self.assertFalse(self.run_retry(request)["completion_verified"])
        self.assertEqual(self.activation_count, 0)
        self.assert_no_issue_writes()

    def test_wrong_owner_snapshot_candidate_signed_pr_or_journal_hash_is_rejected(self):
        for key, value in (
            ("owner", "foreign"),
            ("snapshot_id", "foreign"),
            ("expected_candidate", "a" * 40),
            ("expected_signed_commit", "c" * 40),
            ("pr", 99),
            ("original_journal_sha256", "f" * 64),
            ("generation", True),
            ("engine_pid", 0),
            ("engine_pid", True),
            ("host_instance_id", ""),
        ):
            with self.subTest(key=key):
                self.assertFalse(self.run_retry(dict(self.request, **{key: value}))["ok"])
        self.assertEqual(self.activation_count, 0)
        self.assert_no_issue_writes()

    def test_missing_or_unknown_original_result_is_not_replayed(self):
        original = json.loads(self.original)
        for value in (
            None,
            {},
            dict(original["last_receipt"], completion_verified=False),
            dict(original["last_receipt"], stage="validation"),
        ):
            changed = dict(original, last_receipt=value)
            self.journal.write_text(json.dumps(changed))
            request = dict(self.request, original_journal_sha256=retry.sha(self.journal.read_bytes()))
            self.assertFalse(self.run_retry(request)["ok"])
        self.assertEqual(self.activation_count, 0)
        self.journal.write_bytes(self.original)
        self.assert_no_issue_writes()

    def test_ambiguous_pending_journal_is_not_selected_by_caller(self):
        duplicate = self.journal.with_name("f" * 64 + ".json")
        duplicate.write_bytes(self.original)
        self.assertFalse(self.run_retry()["ok"])
        self.assertEqual(self.activation_count, 0)
        self.assert_no_issue_writes()

    def test_original_acceptance_hash_and_closed_issue_are_revalidated(self):
        changed = json.loads(self.original)
        changed["last_receipt"]["acceptance_declaration"]["items"][0]["evidence"] = "changed"
        self.journal.write_text(json.dumps(changed))
        self.assertFalse(
            self.run_retry(dict(self.request, original_journal_sha256=retry.sha(self.journal.read_bytes())))["ok"]
        )
        self.journal.write_bytes(self.original)
        self.fixture.issue.update(state="OPEN", stateReason=None)
        self.assertFalse(self.run_retry()["ok"])
        self.assertEqual(self.activation_count, 0)
        self.assert_no_issue_writes()

    def test_failed_ci_or_revoked_current_writer_never_activates(self):
        self.fixture.check_state = "FAILURE"
        self.assertFalse(self.run_retry()["ok"])
        self.fixture.check_state = "SUCCESS"
        with patch.object(retry.delivery.submission, "writer", side_effect=ValueError("revoked")):
            self.assertFalse(self.run_retry()["ok"])
        self.assertEqual(self.activation_count, 0)
        self.assert_no_issue_writes()

    def test_unknown_started_retry_is_read_only_and_never_blindly_replayed(self):
        result = self.run_retry()
        path = Path(result["host_action_receipt"])
        saved = json.loads(path.read_text())
        saved["state"] = "started"
        saved.pop("result")
        path.write_text(json.dumps(saved))
        result = self.run_retry()
        self.assertFalse(result["ok"])
        self.assertIn("unknown", result["error"])
        self.assertEqual(self.activation_count, 1)
        changed_id = self.run_retry(dict(self.request, host_action_request_id="another-action"))
        self.assertFalse(changed_id["ok"])
        self.assertIn("unknown", changed_id["error"])
        self.assertEqual(self.activation_count, 1)
        self.assert_no_issue_writes()

    def test_new_generation_cannot_reuse_the_same_host_action_id(self):
        self.assertTrue(self.run_retry()["ok"])
        result = self.run_retry(dict(self.request, generation=1, nonce="different"))
        self.assertFalse(result["ok"])
        self.assertIn("conflicts", result["error"])
        self.assertEqual(self.activation_count, 1)
        self.assert_no_issue_writes()

    def test_activation_failure_stays_pending_in_new_receipt_without_issue_writes(self):
        self.fixture.activation = {"state": "pending", "error": "fixture repeat failure"}
        result = self.run_retry()
        self.assertTrue(result["completion_verified"], result)
        self.assertFalse(result["ok"])
        self.assertEqual(result["stage"], "activation_pending")
        self.assert_no_issue_writes()

    def test_removed_activation_binding_cannot_become_not_applicable_success(self):
        self.fixture.activation = {"state": "not_applicable"}
        result = self.run_retry()
        self.assertFalse(result["ok"])
        self.assertEqual(result["stage"], "activation_pending")
        self.assert_no_issue_writes()

    def test_acceptance_error_locates_item_without_passed_mapping(self):
        items = copy.deepcopy(self.fixture.request["acceptance_items"])
        items[0]["state"] = "passed"
        with self.assertRaisesRegex(ValueError, r"item 1 .*done, remaining or unknown"):
            retry.delivery.acceptance_declaration(items)
        items[0]["state"] = "remaining"
        with self.assertRaisesRegex(ValueError, r"item 1 .*only done"):
            retry.delivery.acceptance_declaration(items)


if __name__ == "__main__":
    unittest.main()
