"""Unit checks for the binding between an authenticated plan and the Issue assignment."""
from contextlib import closing
from copy import deepcopy
import hashlib
import json
import os
import sqlite3
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

import worker


class AssignmentTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.state = Path(temporary.name).resolve()
        self.assignment = {"ticket": "github:example/repo#1", "authorityRef": "host-mandate",
                           "reads": [worker.resource(worker.FRAMEWORK.parent)], "writes": [worker.resource(self.state)],
                           "model": {"id": "profile", "capabilities": ["draft"]}, "sourceSnapshot": {"sha256": "revision"}, "outcome": "draft"}
        self.task = {"authority_ref": "host-mandate", "tenant_id": "gonggong-workspace", "id": "test",
                     "steps": [{"kind": "draft"}], "outcome": "draft", "source_revision": "revision", "work_items": [{"id": self.assignment["ticket"]}]}
        self.grant = {"payload": {"state_dir": str(self.state), "authority_ref": "host-mandate",
                                  "task": self.task, "profiles": [{"id": "profile"}]}}

    def test_invalid_signature_checked_before_runtime(self):
        with patch.object(worker.runner, "verify_grant", side_effect=ValueError("signature")), patch.object(worker.runner, "run") as run:
            with self.assertRaisesRegex(ValueError, "signature"):
                worker.execute(self.grant, self.assignment)
            run.assert_not_called()

    def test_unreserved_writes_and_capabilities_block(self):
        for changes in ({"writes": []}, {"reads": []}, {"model": {"id":"profile","capabilities":[]}}):
            with patch.object(worker.runner, "verify_grant"), self.assertRaisesRegex(ValueError,"assignment"):
                worker.execute(self.grant, {**self.assignment, **changes}, "--check")

    def test_drift_blocks_production(self):
        for change in ({"tenant_id": "other"}, {"source_revision": "old"}, {"authority_ref": "different"},
                       {"outcome": "different"}, {"work_items": []}, {"validation_only": True}):
            with self.subTest(change=change), patch.object(worker.runner, "verify_grant"), patch.object(worker.runner, "run") as run:
                grant = deepcopy(self.grant)
                grant["payload"]["task"].update(change)
                with self.assertRaisesRegex(ValueError, "assignment"):
                    worker.execute(grant, self.assignment)
                run.assert_not_called()

    def run_signed_fixture(self):
        with patch.object(worker.runner, "validate_plan"):
            binding = worker.execute(self.grant, self.assignment, "--check")["binding"]
        return worker.execute(self.grant, self.assignment, "run", binding)

    def test_unknown_outcome_never_acknowledged(self):
        with patch.object(worker.runner, "verify_grant"), patch.object(worker.runner, "run", return_value={"status": "needs_reconciliation"}):
            self.assertEqual(self.run_signed_fixture()["status"], "needs_reconciliation")

    def test_recovery_reads_only_matching_terminal_ledger(self):
        runner = worker.runner
        self.grant["payload"].update(expires_at=1, framework_sha256=hashlib.sha256(
            (worker.FRAMEWORK / "framework-manifest.json").read_bytes()).hexdigest())
        with patch.dict(os.environ, GONGGONG_HOST_KEY="isolated-test-key-not-a-production-secret"):
            self.grant["signature"] = runner.signature(self.grant["payload"])
            with self.assertRaisesRegex(ValueError, "expired"):
                worker.execute(self.grant, self.assignment)
            # Binding was issued while the original grant was valid.
            binding = runner.digest({k:v for k,v in self.grant["payload"].items() if k != "expires_at"})
            original_signature = self.grant["signature"]
            self.grant["signature"] = "invalid"
            with self.assertRaisesRegex(ValueError, "signature"):
                worker.execute(self.grant,self.assignment,"--inspect",binding)
            self.grant["signature"] = original_signature
            with closing(sqlite3.connect(self.state / "runtime.sqlite")) as db, db:
                db.execute("CREATE TABLE jobs(id,task_hash,grant_hash,status,result)")
                db.execute("INSERT INTO jobs VALUES(?,?,?,?,?)", (runner.jid_for(self.task), runner.digest(self.task),
                           runner.digest(self.grant), "cancelled", None))
            with patch.object(runner, "run", side_effect=AssertionError("recovery launched production")):
                self.assertEqual(worker.execute(self.grant,self.assignment,"--inspect",binding)["status"], "cancelled")
                with self.assertRaisesRegex(ValueError, "changed"):
                    worker.execute(self.grant,self.assignment,"--inspect","wrong")
                with closing(sqlite3.connect(self.state / "runtime.sqlite")) as db, db:
                    db.execute("UPDATE jobs SET status='completed',result=?", (json.dumps({"diting_submission_id":"proof"}),))
                self.assertEqual(worker.execute(self.grant,self.assignment,"--inspect",binding)["submission"], "proof")

    def test_only_candidate_reference_returned(self):
        with patch.object(worker.runner, "verify_grant"), patch.object(worker.runner, "run", return_value={
            "status": "completed", "result": {"diting_submission_id": "submission", "outputs": "private"}}):
            self.assertEqual(self.run_signed_fixture(),
                             {"status": "completed", "submission": "submission", "job": worker.runner.jid_for(self.task)})


if __name__ == "__main__":
    unittest.main()
