import copy
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
