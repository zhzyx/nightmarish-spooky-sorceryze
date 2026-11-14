from __future__ import annotations

import contextlib
import copy
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

import writer_submit as submission


class WriterTests(unittest.TestCase):
    def test_permission_is_per_repository_and_not_a_personal_whitelist(self) -> None:
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

    def test_retry_recovers_signed_commit_without_push_or_second_signature(self) -> None:
        receipt: dict[str, Any] = {
            "oid": "signed",
            "message": "bound",
            "tree": {"oid": "tree"},
            "parents": {"nodes": [{"oid": "candidate"}]},
            "author": {"user": {"login": "bob"}},
            "signature": {"isValid": True, "wasSignedByGitHub": True},
        }
        cases: list[dict[str, Any]] = [
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


class ActivationInvocationTests(unittest.TestCase):
    def test_fixed_installed_process_keeps_repository_and_report_as_data(self) -> None:
        repo = Path("quoted repo ' 空间; ignored")
        report = {"pr_state": "MERGED", "text": "quote '\"\n; arbitrary-looking data"}
        paths, modules = list(sys.path), dict(sys.modules)
        with patch.object(
            submission.subprocess,
            "run",
            return_value=subprocess.CompletedProcess([], 0, '{"state":"not_applicable"}', ""),
        ) as run:
            self.assertEqual(submission.engine_launch_activation(repo, report), {"state": "not_applicable"})
        arguments = run.call_args.args[0]
        self.assertEqual(arguments[:7], [sys.executable, "-E", "-s", "-B", "-X", "utf8", "-c"])
        self.assertEqual(arguments[-1], str(repo))
        self.assertNotIn(report["text"], arguments[-2])
        self.assertEqual(run.call_args.kwargs["cwd"], Path(submission.__file__).resolve().parents[3] / "tools")
        self.assertEqual(json.loads(run.call_args.kwargs["input"]), report)
        self.assertTrue(run.call_args.kwargs["check"])
        self.assertEqual(sys.path, paths)
        self.assertEqual(sys.modules, modules)

    def test_invalid_child_output_is_not_an_activation_receipt(self) -> None:
        for text in (
            "not json",
            "[]",
            "null",
            '{"state":"unknown"}',
            '{"state":"activated"}',
            '{"state":"activated","ok":false}',
            '{"state":"activated","ok":true} trailing',
        ):
            with (
                self.subTest(text=text),
                patch.object(submission.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, text, "")),
            ):
                with self.assertRaises(ValueError):
                    submission.engine_launch_activation(Path("."), {})

    def test_child_errors_preserve_confirmed_merge_and_sanitize_public_result(self) -> None:
        report = {"pr_state": "MERGED", "candidate": "a" * 40, "current_main": "b" * 40}
        for error in (
            subprocess.CalledProcessError(1, ["private command"], stderr="private stderr"),
            ValueError("private invalid child output"),
            UnicodeDecodeError("utf-8", b"\xff", 0, 1, "private decode failure"),
        ):
            output = io.StringIO()
            with (
                self.subTest(error=type(error).__name__),
                patch.object(sys, "argv", ["writer_submit.py", "--repo", ".", "--inspect-pr", "7"]),
                patch.object(submission.work_items, "config", return_value=({"repository": "fixture/repo"}, [])),
                patch.object(submission.issue_gate, "check_repository"),
                patch.object(submission, "inspect_pr", return_value=dict(report)),
                patch.object(submission, "engine_launch_activation", side_effect=error),
                contextlib.redirect_stdout(output),
            ):
                submission.main()
            result = json.loads(output.getvalue())
            for key, value in report.items():
                self.assertEqual(result[key], value)
            self.assertEqual(
                result["engine_launch_activation"], {"state": "pending", "error": "activation_adapter_failed"}
            )
            self.assertNotIn("private", output.getvalue())


class HandoffTests(unittest.TestCase):
    issue_receipt: dict[str, Any]

    def setUp(self) -> None:
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.repo = Path(folder.name)
        self.git("init", "-b", "main")
        self.git("config", "user.name", "test")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "commit.gpgsign", "false")
        self.git("config", "core.autocrlf", "false")
        dataset = self.repo / "gonggong-diting-data/dataset.json"
        dataset.parent.mkdir()
        dataset.write_bytes((submission.issue_gate.INSTALLATION / "gonggong-diting-data/dataset.json").read_bytes())
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
        self.pr: dict[str, Any] = {
            "url": "https://github.com/org/repo/pull/7",
            "headRefName": "codex/submit/alice/9/" + self.candidate,
            "headRefOid": self.signed,
            "baseRefName": "main",
            "isCrossRepository": False,
            "state": "OPEN",
            "mergeCommit": None,
        }
        self.tip: dict[str, Any] = {
            "message": self.message,
            "oid": self.signed,
            "tree": {"oid": self.tree},
            "parents": {"nodes": [{"oid": self.candidate}]},
            "author": {"user": {"login": "alice"}},
            "signature": {"isValid": True, "wasSignedByGitHub": True},
        }

    def git(self, *args: str) -> str:
        return submission.git(self.repo, *args)

    def commit(self, message: str) -> None:
        self.git("add", "--all")
        self.git("commit", "-m", message)

    def inspect(self) -> dict[str, Any]:
        def fetch(repo: Path, operation: str, url: str, ref: str) -> str:
            self.assertEqual((operation, url), ("fetch", "https://github.com/org/repo.git"))
            return submission.git(repo, "fetch", str(self.repo), ref)

        def read_source(command: str, *args: str) -> str:
            if command == "issue":
                return json.dumps(getattr(self, "issue_receipt", {"state": "OPEN", "stateReason": None, "labels": []}))
            return json.dumps(self.pr)

        with (
            patch.object(submission.work_items, "gh", side_effect=read_source),
            patch.object(submission, "graphql", return_value={"repository": {"object": self.tip}}),
            patch.object(submission, "authenticated_git", side_effect=fetch),
        ):
            return submission.inspect_pr(self.repo, "org/repo", 7)

    def test_concurrent_main_and_old_pr_without_new_metadata(self) -> None:
        result = self.inspect()
        self.assertEqual(result["write_paths"], ["ship.txt"])
        self.assertTrue(result["base_advanced"])
        self.assertEqual(result["overlapping_write_paths"], [])
        self.assertIsNone(result["substantive_rework"])
        self.assertEqual(result["signed_commit"], self.signed)
        self.tip["signature"]["isValid"] = False
        with self.assertRaisesRegex(ValueError, "signed receipt"):
            self.inspect()

    def test_merged_receipt_checks_target_parent_and_landed_content(self) -> None:
        self.git("merge", "--no-ff", "feature", "-m", "merge")
        self.pr.update(state="MERGED", mergeCommit={"oid": self.git("rev-parse", "HEAD")})
        (self.repo / "ship.txt").write_text("separate later change")
        self.commit("later")
        result = self.inspect()
        self.assertEqual(result["main_observed"], self.pr_base)
        self.assertEqual(result["current_main"], self.git("rev-parse", "main"))
        self.assertEqual(result["delivered_paths_differ"], [])
        self.assertIn("逐项执行", result["next_action"])
        for reason, labels, expected in [
            ("COMPLETED", [{"name": "status:done"}], "目标单已有完成回执"),
            ("NOT_PLANNED", [], "核对关闭原因"),
        ]:
            self.issue_receipt = {"state": "CLOSED", "stateReason": reason, "labels": labels}
            self.assertIn(expected, self.inspect()["next_action"])

    def test_shared_path_and_file_directory_write(self) -> None:
        path = self.repo / "ship.txt"
        path.mkdir()
        (path / "nested").write_text("other worker")
        self.commit("overlapping directory")
        result = self.inspect()
        self.assertEqual(result["overlapping_write_paths"], ["ship.txt"])
        self.assertIn("重叠路径", result["next_action"])

    def test_normal_submit_refuses_drift_before_gating_and_includes_overlap(self) -> None:
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

    def test_auto_integrate_submit_rebases_zero_overlap_and_refuses_read_overlap(self) -> None:
        # Branch from old self.base while main has advanced to self.pr_base (modified other.txt).
        self.git("switch", "-c", "drifted-work", self.base)
        (self.repo / "disjoint.txt").write_text("disjoint payload")
        self.git("add", "disjoint.txt")
        new_pr_url = "https://github.com/org/repo/pull/8"

        def gh(*args: str) -> str:
            if args[:2] == ("pr", "list"):
                return "[]"
            if args[:2] == ("pr", "create"):
                return new_pr_url
            return json.dumps({
                "headRefOid": self.signed,
                "baseRefName": "main",
                "isCrossRepository": False,
                "state": "OPEN",
                "baseRefOid": self.pr_base,
            })

        # Read dependency overlapping upstream other.txt must still refuse auto-integration.
        with (
            patch.object(submission.work_items, "config", return_value=({"repository": "org/repo"}, [])),
            patch.object(submission.issue_gate, "check_repository"),
            patch.object(submission, "writer", return_value={"login": "alice", "databaseId": 1}),
            patch.object(submission, "matching_pr", return_value=None),
            patch.object(submission, "authenticated_git", side_effect=lambda *args: self.git("fetch", ".", "main")),
            patch.object(submission.issue_gate, "gate") as gate,
            self.assertRaisesRegex(ValueError, "overlapping_read_paths"),
        ):
            submission.submit(self.repo, 9, "flow-test", "ship", "checked", auto_integrate=True, reads=["other.txt"])
        gate.assert_not_called()

        # Disjoint write and read paths auto-integrate cleanly onto current main before gating.
        with (
            patch.object(submission.work_items, "config", return_value=({"repository": "org/repo"}, [])),
            patch.object(submission.work_items, "gh", side_effect=gh),
            patch.object(submission.issue_gate, "check_repository"),
            patch.object(submission.issue_gate, "gate") as gate,
            patch.object(submission, "writer", return_value={"login": "alice", "databaseId": 1}),
            patch.object(submission, "authenticated_git", side_effect=lambda *args: self.git("fetch", ".", "main")),
            patch.object(submission, "issue_receipt", return_value=self.signed),
        ):
            result = submission.submit(
                self.repo, 9, "flow-test", "ship disjoint", "validation notes", auto_integrate=True, reads=["seed"]
            )
        self.assertEqual(gate.call_count, 1)
        self.assertEqual(result["handoff"]["base"], self.pr_base)
        self.assertEqual(result["handoff"]["write_paths"], ["disjoint.txt"])
        self.assertEqual((self.repo / "other.txt").read_text(), "independent")
        self.assertEqual((self.repo / "disjoint.txt").read_text(), "disjoint payload")

    def test_rebind_pr_preserves_worktree_validates_gates_and_closes_superseded(self) -> None:
        # Leave dirty local state on main to verify rebind_pr operates in an isolated worktree.
        (self.repo / "local-dirty.txt").write_text("keep untouched")
        created_bodies: list[str] = []
        closed_calls: list[tuple[str, ...]] = []
        new_pr_url = "https://github.com/org/repo/pull/12"
        original_body = (
            "GongGong-Issue: #9\nGongGong-Request: flow-test\n\n"
            f"交接 · 发布者 alice · 目标 main · 基线 `{self.base}`\n"
            f"源候选 `{self.candidate}` · 已签 head `{self.signed}` · 内容树 `{self.tree}`\n"
            '相对签发基线写入 1 个仓库路径（含删除）：\n\n    "ship.txt"\n\n'
            "Unit and integration checks passed."
        )
        self.assertEqual(submission.extract_pr_notes(original_body), "Unit and integration checks passed.")

        def fetch(repo: Path, operation: str, url: str, ref: str) -> str:
            return submission.git(repo, "fetch", str(self.repo), ref)

        def gh(*args: str) -> str:
            if args[:3] == ("pr", "view", "7") and "title,body" in args:
                return json.dumps({"title": "feat: ship item", "body": original_body})
            if args[:3] == ("pr", "view", "7"):
                return json.dumps(self.pr)
            if args[:2] == ("pr", "list"):
                return "[]"
            if args[:2] == ("pr", "create"):
                created_bodies.append(Path(args[args.index("--body-file") + 1]).read_text(encoding="utf-8"))
                return new_pr_url
            if args[:2] == ("pr", "close"):
                closed_calls.append(args)
                return ""
            return json.dumps({
                "headRefOid": "9" * 40,
                "baseRefName": "main",
                "isCrossRepository": False,
                "state": "OPEN",
                "baseRefOid": self.pr_base,
            })

        # Different writer cannot hijack or rebind alice's PR.
        with (
            patch.object(submission.work_items, "config", return_value=({"repository": "org/repo"}, [])),
            patch.object(submission.work_items, "gh", side_effect=gh),
            patch.object(submission.issue_gate, "check_repository"),
            patch.object(submission, "writer", return_value={"login": "bob", "databaseId": 2}),
            patch.object(submission, "graphql", return_value={"repository": {"object": self.tip}}),
            patch.object(submission, "authenticated_git", side_effect=fetch),
            self.assertRaisesRegex(ValueError, "original authenticated writer"),
        ):
            submission.rebind_pr(self.repo, 7)

        # Original writer rebinds zero-overlap PR onto self.pr_base and closes old PR #7.
        with (
            patch.object(submission.work_items, "config", return_value=({"repository": "org/repo"}, [])),
            patch.object(submission.work_items, "gh", side_effect=gh),
            patch.object(submission.issue_gate, "check_repository"),
            patch.object(submission.issue_gate, "gate") as gate,
            patch.object(submission, "writer", return_value={"login": "alice", "databaseId": 1}),
            patch.object(submission, "graphql", return_value={"repository": {"object": self.tip}}),
            patch.object(submission, "authenticated_git", side_effect=fetch),
            patch.object(submission, "issue_receipt", return_value="9" * 40),
        ):
            rebound = submission.rebind_pr(self.repo, 7, close_superseded=True, reads=["seed"])

        self.assertTrue(rebound["rebound"])
        self.assertTrue(rebound["superseded_closed"])
        self.assertEqual(rebound["superseded_pr"], self.pr["url"])
        self.assertEqual(rebound["pull_request"], new_pr_url)
        self.assertEqual(rebound["handoff"]["base"], self.pr_base)
        self.assertEqual(rebound["handoff"]["write_paths"], ["ship.txt"])
        self.assertEqual(gate.call_count, 1)
        self.assertEqual(len(closed_calls), 1)
        self.assertIn("Unit and integration checks passed.", created_bodies[0])
        self.assertIn("Rebound from #7", created_bodies[0])
        self.assertEqual((self.repo / "local-dirty.txt").read_text(), "keep untouched")
        self.assertEqual(self.git("symbolic-ref", "--short", "HEAD"), "main")

        # Overlapping upstream write must refuse auto-rebind.
        (self.repo / "ship.txt").write_text("upstream conflict")
        self.commit("upstream overlap")
        with (
            patch.object(submission.work_items, "config", return_value=({"repository": "org/repo"}, [])),
            patch.object(submission.work_items, "gh", side_effect=gh),
            patch.object(submission.issue_gate, "check_repository"),
            patch.object(submission, "writer", return_value={"login": "alice", "databaseId": 1}),
            patch.object(submission, "graphql", return_value={"repository": {"object": self.tip}}),
            patch.object(submission, "authenticated_git", side_effect=fetch),
            self.assertRaisesRegex(ValueError, "Cannot auto-rebind"),
        ):
            submission.rebind_pr(self.repo, 7)

    def test_normal_submission_includes_exact_handoff_and_reuses_existing_pr(self) -> None:
        self.git("switch", "-c", "ship", "main")
        (self.repo / "new.txt").write_text("new")
        self.git("add", "new.txt")
        bodies: list[str] = []
        readback: dict[str, Any] = dict(state="OPEN", baseRefOid=self.pr_base)

        def gh(*args: str) -> str:
            if args[:2] == ("pr", "list"):
                return json.dumps([self.pr] if bodies else [])
            if args[:2] == ("pr", "create"):
                bodies.append(Path(args[args.index("--body-file") + 1]).read_text(encoding="utf8"))
                return str(self.pr["url"])
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


if __name__ == "__main__":
    unittest.main()
