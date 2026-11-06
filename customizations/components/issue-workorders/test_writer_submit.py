import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import writer_submit as submission


class WriterTests(unittest.TestCase):
    def test_permission_is_per_repository_and_not_a_personal_whitelist(self):
        for login, permission in [
            ("alice", "WRITE"),
            ("bob", "MAINTAIN"),
            ("carol", "ADMIN"),
            ("owner", "READ"),
            ("writer-elsewhere", "TRIAGE"),
            ("former", None),
        ]:
            data = {
                "viewer": {"login": login, "databaseId": 123},
                "repository": {"nameWithOwner": "team/game", "viewerPermission": permission},
            }
            with self.subTest(login=login), patch.object(submission, "graphql", return_value=data):
                if permission in {"WRITE", "MAINTAIN", "ADMIN"}:
                    self.assertEqual(submission.writer("team/game"), data["viewer"])
                else:
                    with self.assertRaises(ValueError):
                        submission.writer("team/game")
                with self.assertRaises(ValueError):
                    submission.writer("team/other")

    def test_retry_recovers_signed_commit_without_push_or_second_signature(self):
        receipt = {
            "oid": "signed",
            "message": "bound",
            "tree": {"oid": "tree"},
            "parents": {"nodes": [{"oid": "candidate"}]},
            "author": {"user": {"login": "bob"}},
            "signature": {"isValid": True, "wasSignedByGitHub": True},
        }
        cases = [
            {},
            {"author": None},
            {"parents": {"nodes": []}},
            {"tree": {"oid": "different"}},
            {"message": "different"},
            {"signature": {"isValid": True, "wasSignedByGitHub": False}},
        ]
        for change in cases:
            tip = copy.deepcopy(receipt)
            tip.update(change)
            with (
                self.subTest(change=change),
                patch.object(submission, "remote_tip", return_value=tip),
                patch.object(submission, "git") as git,
                patch.object(submission, "graphql") as mutate,
            ):
                args = (Path("."), "team/game", "bob", "branch", "candidate", "tree", "bound")
                if change:
                    with self.assertRaises(ValueError):
                        submission.issue_receipt(*args)
                else:
                    self.assertEqual(submission.issue_receipt(*args), "signed")
                git.assert_not_called()
                mutate.assert_not_called()


class HandoffTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.repo = Path(folder.name)
        self.git("init", "-b", "main")
        self.git("config", "user.name", "test")
        self.git("config", "user.email", "test@example.invalid")
        (self.repo / "seed").write_text("seed")
        self.commit("base")
        self.base = self.git("rev-parse", "HEAD")
        self.git("switch", "-c", "feature")
        (self.repo / "ship.txt").write_text("item")
        self.commit("feature")
        self.candidate = self.git("rev-parse", "HEAD")
        self.tree = self.git("rev-parse", "HEAD^{tree}")
        self.message = (
            "Sign delivery for #9\n\nGongGong-Issue: #9\nGongGong-Request: flow-test\nRepository: org/repo\n"
            f"Candidate: {self.candidate}\nTree: {self.tree}\nBase: {self.base}\nTarget: main\nWriter: alice"
        )
        self.git("commit", "--allow-empty", "-m", self.message)
        self.signed = self.git("rev-parse", "HEAD")
        self.git("update-ref", "refs/pull/7/head", self.signed)
        self.git("switch", "main")
        (self.repo / "other.txt").write_text("independent")
        self.commit("other work")
        self.pr_base = self.git("rev-parse", "HEAD")
        self.pr = {
            "url": "https://github.com/org/repo/pull/7",
            "headRefName": "codex/submit/alice/9/" + self.candidate,
            "headRefOid": self.signed,
            "baseRefName": "main",
            "isCrossRepository": False,
            "state": "OPEN",
            "mergeCommit": None,
        }
        self.tip = {
            "message": self.message,
            "oid": self.signed,
            "tree": {"oid": self.tree},
            "parents": {"nodes": [{"oid": self.candidate}]},
            "author": {"user": {"login": "alice"}},
            "signature": {"isValid": True, "wasSignedByGitHub": True},
        }

    def git(self, *args):
        return submission.git(self.repo, *args)

    def commit(self, message):
        self.git("add", "--all")
        self.git("commit", "-m", message)

    def inspect(self):
        def fetch(repo, operation, url, ref):
            self.assertEqual((operation, url), ("fetch", "https://github.com/org/repo.git"))
            return submission.git(repo, "fetch", str(self.repo), ref)

        with (
            patch.object(submission.work_items, "gh", return_value=json.dumps(self.pr)),
            patch.object(submission, "graphql", return_value={"repository": {"object": self.tip}}),
            patch.object(submission, "authenticated_git", side_effect=fetch),
        ):
            return submission.inspect_pr(self.repo, "org/repo", 7)

    def test_concurrent_main_and_old_pr_without_new_metadata(self):
        result = self.inspect()
        self.assertEqual(result["write_paths"], ["ship.txt"])
        self.assertTrue(result["base_advanced"])
        self.assertEqual(result["overlapping_write_paths"], [])
        self.assertIsNone(result["substantive_rework"])
        self.assertEqual(result["signed_commit"], self.signed)
        self.tip["signature"]["isValid"] = False
        with self.assertRaisesRegex(ValueError, "signed receipt"):
            self.inspect()

    def test_merged_receipt_checks_target_parent_and_landed_content(self):
        self.git("merge", "--no-ff", "feature", "-m", "merge")
        self.pr.update(state="MERGED", mergeCommit={"oid": self.git("rev-parse", "HEAD")})
        (self.repo / "ship.txt").write_text("separate later change")
        self.commit("later")
        result = self.inspect()
        self.assertEqual(result["main_observed"], self.pr_base)
        self.assertEqual(result["current_main"], self.git("rev-parse", "main"))
        self.assertEqual(result["delivered_paths_differ"], [])
        self.assertIn("已有 main 回执", result["next_action"])

    def test_shared_path_and_file_directory_write(self):
        path = self.repo / "ship.txt"
        path.mkdir()
        (path / "nested").write_text("other worker")
        self.commit("overlapping directory")
        result = self.inspect()
        self.assertEqual(result["overlapping_write_paths"], ["ship.txt"])
        self.assertIn("重叠路径", result["next_action"])

    def test_normal_submit_refuses_drift_before_gating_and_includes_overlap(self):
        (self.repo / "ship.txt").write_text("other worker")
        self.commit("overlap")
        self.git("switch", "-c", "work", self.candidate)
        with (
            patch.object(submission.work_items, "config", return_value=({"repository": "org/repo"}, [])),
            patch.object(submission.issue_gate, "check_repository"),
            patch.object(submission, "writer", return_value={"login": "alice", "databaseId": 1}),
            patch.object(submission, "matching_pr", return_value=None),
            patch.object(submission, "authenticated_git", side_effect=lambda *args: self.git("fetch", ".", "main")),
            patch.object(submission.issue_gate, "gate") as gate,
            self.assertRaisesRegex(ValueError, "Integrate current main") as error,
        ):
            submission.submit(self.repo, 9, "flow-test", "ship", "checked")
        gate.assert_not_called()
        details = json.loads(str(error.exception).split(": ", 1)[1])
        self.assertEqual(details["overlapping_write_paths"], ["ship.txt"])
        self.assertEqual(details["base"], self.base)
        self.assertEqual(details["tree"], self.tree)

    def test_normal_submission_includes_exact_handoff_and_reuses_existing_pr(self):
        self.git("switch", "-c", "ship", "main")
        (self.repo / "new.txt").write_text("new")
        self.git("add", "new.txt")
        checker = self.repo / "framework/extensions/diting-files/diting_files.py"
        checker.parent.mkdir(parents=True)
        checker.write_text("import sys\nassert '--require-committed' in sys.argv\n")
        bodies = []
        readback = dict(state="OPEN", baseRefOid=self.pr_base)

        def gh(*args):
            if args[:2] == ("pr", "list"):
                return json.dumps([self.pr] if bodies else [])
            if args[:2] == ("pr", "create"):
                bodies.append(Path(args[args.index("--body-file") + 1]).read_text(encoding="utf8"))
                return self.pr["url"]
            return json.dumps(dict(headRefOid=self.signed, baseRefName="main", isCrossRepository=False, **readback))

        with (
            patch.object(submission.work_items, "config", return_value=({"repository": "org/repo"}, [])),
            patch.object(submission.work_items, "gh", side_effect=gh),
            patch.object(submission.issue_gate, "check_repository"),
            patch.object(submission.issue_gate, "gate") as gate,
            patch.object(submission, "writer", return_value=dict(login="alice", databaseId=1)),
            patch.object(submission, "authenticated_git", side_effect=lambda *args: self.git("fetch", ".", "main")),
            patch.object(submission, "issue_receipt", return_value=self.signed),
        ):
            first = submission.submit(self.repo, 9, "flow-test", "ship", "验收证据")
            second = submission.submit(self.repo, 9, "flow-test", "ship", "验收证据")
            for state, main in [("CLOSED", self.pr_base), ("OPEN", "f" * 40)]:
                readback.update(state=state, baseRefOid=main)
                with patch.object(submission, "inspect_pr", return_value=dict(pr_state=state, current_main=main)):
                    with self.assertRaisesRegex(ValueError, "handoff requires reconciliation"):
                        submission.submit(self.repo, 9, "flow-test", "ship", "验收证据")
        self.assertEqual(first, second)
        self.assertEqual(gate.call_count, 4)
        self.assertEqual(len(bodies), 1)
        for text in (self.pr_base, self.signed, first["candidate"], first["tree"], "new.txt", "alice", "验收证据"):
            self.assertIn(text, bodies[0])
        self.assertEqual(first["handoff"]["write_paths"], ["new.txt"])
