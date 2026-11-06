"""Exercise the actual GitHub work-item adapter, stubbing only its remote transport."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

import bridge
import direct_issue

HOST = Path(__file__).resolve().parent
REAL_REFRESH = direct_issue.refresh
REAL_ENQUEUE = bridge.enqueue
REAL_FLUSH = bridge.flush
URL = "https://github.com/test/repo/issues/19"


class DirectIssueTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        (self.root / ".github").mkdir()
        (self.root / ".github/labels.json").write_text('[{"name":"type:development"}]')
        (self.root / "work-items.json").write_text('{"repository":"test/repo","tenant_id":"test"}')
        folder = self.root / "customizations/components/issue-workorders"
        folder.mkdir(parents=True)
        shutil.copy(HOST.parent / "issue-workorders/work_items.py", folder)
        self.work = bridge.work_items_module(self.root)
        self.rows = []
        self.writes = 0
        self.next_error = None
        self.lose_receipt = False
        self.account = "7"
        self.request = {"draft_id": "draft_0123456789abcdef0123", "expected_user": "7", "title": "原始标题",
                        "category": "development", "outcome": "原始输入\n\n  保留空格  "}
        self.patch(bridge, "work_items_module", return_value=self.work)
        self.patch(bridge, "gh_state", return_value=("gh", None))
        self.patch(direct_issue, "collaborator", return_value={"user_id": "7", "repo": "test/repo", "login": "alice"})
        self.patch(self.work, "gh", side_effect=self.gh)
        self.enqueue = self.patch(bridge, "enqueue")
        self.flush = self.patch(bridge, "flush")
        self.refresh = self.patch(direct_issue, "refresh", return_value={"execution": "not_dispatched", "sourcesRead": 0})

    def patch(self, obj, attr, **kwargs):
        context = patch.object(obj, attr, **kwargs)
        self.addCleanup(context.stop)
        return context.start()

    def gh(self, *args):
        if args == ("api", "user"):
            return '{"login":"alice","id":7}'
        if args == ("api", "user", "--jq", ".id"):
            return self.account
        if args[:2] == ("api", "repos/test/repo/issues?state=all&per_page=100"):
            return json.dumps([[], self.rows])
        if args == ("api", "repos/test/repo/issues/19"):
            return json.dumps(self.rows[0])
        if args[:2] != ("issue", "create"):
            self.fail(f"Unexpected command {args[:2]}")
        self.writes += 1
        if self.next_error:
            raise self.next_error
        row = {"number": 19, "html_url": URL, "state": "open", "user": {"id": 7},
               "body": Path(args[args.index("--body-file") + 1]).read_text(),
               "title": args[args.index("--title") + 1],
               "updated_at": "2026-11-06T00:00:00Z", "created_at": "2026-11-06T00:00:00Z",
               "labels": [{"name": v} for i, v in enumerate(args) if args[i-1] == "--label"]}
        row["assignees"] = []
        self.rows.append(row)
        if self.lose_receipt:
            raise self.work.GitHubCommandError(reason="timeout")
        return URL

    def submit(self, **overrides):
        return bridge.GUIDE_ACTIONS["issue-direct"](self.root, {**self.request, **overrides})

    def test_create_and_reread_without_model_or_worker(self):
        first = self.submit()
        self.assertTrue(first["ok"], first)
        self.assertEqual((19, "daqian-direct-0123456789abcdef0123", URL, "planned", self.rows[0]["updated_at"]),
                         tuple(first[key] for key in ("number", "request_id", "url", "status", "revision")))
        self.assertNotIn("执行授权来源", self.rows[0]["body"])
        self.assertIn(self.request["outcome"], self.rows[0]["body"])
        self.assertIn("<!-- gonggong-intake:daqian-direct -->", self.rows[0]["body"])
        self.assertEqual(self.enqueue.call_args.args[1]["source_ref"], URL)
        self.assertEqual(self.enqueue.call_args.args[1]["payload"]["event"], "request.created")
        self.rows[0]["labels"][1]["name"] = "status:blocked"
        self.rows[0]["updated_at"] = "2026-11-06T00:00:01Z"
        repeated = self.submit()
        self.assertEqual((repeated["status"], repeated["revision"], self.writes),
                         ("blocked", self.rows[0]["updated_at"], 1))
        self.refresh.assert_called_once()

    def test_only_start_can_activate_exact_planned_issue(self):
        bound = self.submit()
        self.assertTrue(bound["ok"], bound)
        start = {"issue_number": bound["number"], "request_id": bound["request_id"], "expected_user": "7",
                 "expected_revision": bound["revision"]}
        for change in [{"expected_revision": "stale"}, {"expected_user": "8"}]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                bridge.issue_start(self.root, {**start, **change})
        self.rows[0]["state"] = "closed"
        with self.assertRaises(ValueError):
            bridge.issue_start(self.root, start)
        self.rows[0]["state"] = "open"
        original = self.gh

        def activate(*args):
            if args[:2] == ("issue", "edit"):
                self.assertEqual(args[-4:], ("--add-label", "status:in-progress", "--remove-label", "status:planned"))
                self.rows[0]["labels"][1]["name"] = "status:in-progress"
                return URL
            return original(*args)

        self.work.gh.side_effect = activate
        self.assertEqual(bridge.issue_start(self.root, start)["state"], "started")
        self.assertEqual(bridge.issue_start(self.root, start)["state"], "already_active")

    def test_reopened_board_distinguishes_originals_from_yanshi_design(self):
        with patch.object(sys, "path", [str(HOST / "daqian"), *sys.path]):
            import board

        outcome = "  原始文字\n## 待确认\n- 示例并非偃师的澄清问题  "
        self.assertTrue(self.submit(outcome=outcome)["ok"])
        direct = self.rows[0]
        digest = "a" * 64
        marker = f"需求整理：Yanshi / ClarifyFeature；原始输入摘要：`{digest}`。"
        analyzed = "<!-- gonggong-request:requirement-" + digest[:32] + " -->\n" + marker
        cases = [direct, {**direct, "body": analyzed}, {**direct, "body": "example text " + marker}]
        for n, row in enumerate(cases, 19):
            row.update(number=n, html_url=f"https://github.com/test/repo/issues/{n}",
                       issue_dependencies_summary={"total_blocked_by": 0})
        actor = {"login": "alice", "user_id": "7", "repo": "test/repo", "repo_id": "1"}
        with patch.object(board.work_items, "gh", return_value=json.dumps([cases])):
            items = board.read_board(self.root, [], actor)["issues"]
        self.assertEqual([item["analyzed"] for item in items], [False, True, False])
        self.assertEqual(items[0]["plan"]["nodes"], {"requirement": {"kind": "text", "title": "需求", "value": outcome}})
        self.assertEqual(items[0]["pending_count"], 0)

    def test_concurrent_draft_is_published_once(self):
        barrier = threading.Barrier(2)

        def submit():
            barrier.wait(2)
            return self.submit()

        with ThreadPoolExecutor(max_workers=2) as workers:
            results = [f.result() for f in [workers.submit(submit), workers.submit(submit)]]
        self.assertTrue(all(row["ok"] for row in results), results)
        self.assertEqual(self.writes, 1)

    def test_bad_inputs_and_account_switch_before_write(self):
        for change in [{"title": "sk-" + "x" * 32}, {"outcome": "/Users/me/private"}, {"draft_id": "../oops"},
                       {"outcome": "<!-- gonggong-depends-on:#42 -->"}, {"expected_user": "8"}, {"category": "other"}]:
            with self.subTest(change=change):
                result = self.submit(**change)
                self.assertFalse(result["ok"])
                self.assertFalse(result["reconcile_required"])
        self.account = "8"
        self.assertFalse(self.submit()["reconcile_required"])
        self.assertEqual(self.writes, 0)

    def test_uncertain_create_reconciles_only_once_original_issue_is_visible(self):
        self.lose_receipt = True
        result = self.submit()
        self.assertTrue(result["reconcile_required"], result)
        self.enqueue.assert_not_called()
        published = self.rows.pop()
        self.assertTrue(self.submit()["reconcile_required"])
        self.assertTrue(self.submit(outcome="changed")["reconcile_required"])
        self.rows.append(published)
        self.assertTrue(self.submit()["ok"])
        self.assertEqual(self.writes, 1)

    def test_definite_rejection_allows_repair_and_edit(self):
        self.next_error = self.work.GitHubCommandError(403)
        self.assertFalse(self.submit()["reconcile_required"])
        self.next_error = None
        self.assertTrue(self.submit(outcome="repaired draft")["ok"])
        self.assertEqual(self.writes, 2)
        self.assertIn("repaired draft", self.rows[0]["body"])

    def test_reconciles_conflicts_without_dispatch_or_republication(self):
        self.lose_receipt = True
        self.submit()
        row = self.rows[0]
        for change in [{"state": "closed"}, {"user": {"id": 8}}, {"title": "different"},
                       {"body": row["body"] + "different"}, {"updated_at": ""}, {"pull_request": {}}]:
            with self.subTest(change=change):
                self.rows[0] = {**row, **change}
                self.assertTrue(self.submit()["reconcile_required"])
        self.rows = [row, dict(row, number=20)]
        self.assertTrue(self.submit()["reconcile_required"])
        self.assertEqual(self.writes, 1)
        self.enqueue.assert_not_called()

    def test_actual_sinan_assessment_and_diting_receipt(self):
        node = os.environ.get("GONGGONG_NODE") or shutil.which("node")
        if not node:
            self.skipTest("Node.js required to exercise the Sinan entry")
        for relative in ["framework/extensions/diting-files/diting_files.py", "framework/tools/git_batch.py",
                         "gonggong-diting-data/dataset.json"]:
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(HOST.parents[2] / relative, target)
        self.patch(bridge._igniter, "discover_node", return_value=None)
        self.refresh.side_effect = REAL_REFRESH
        self.flush.side_effect = REAL_FLUSH
        self.enqueue.side_effect = REAL_ENQUEUE
        result = self.submit(node_runtime=node)
        self.assertTrue(result["ok"], result)
        receipt = result["coordination"]
        self.assertEqual((receipt["sourceSnapshot"]["source"], receipt["revision"], receipt["sourcesRead"]),
                         ("github:test/repo#19", result["revision"], 1))
        self.assertEqual(receipt["execution"], "not_dispatched")
        self.assertFalse(receipt["ready"])
        self.assertRegex(receipt["sourceSnapshot"]["sha256"], r"^[a-f0-9]{64}$")
        records = list((self.root / "gonggong-diting-data/events").rglob("*.json"))
        self.assertEqual(len(records), 1)
        self.assertEqual(json.loads(records[0].read_text())["source_ref"], URL)
        self.assertTrue(self.submit(node_runtime=node)["ok"])
        args = list(self.refresh.call_args.args)
        for changed in [{"body": "missing identity"}, {"updated_at": "different revision"}, {"state": "closed"}]:
            args[2] = {**self.rows[0], **changed}
            with self.subTest(changed=changed), self.assertRaisesRegex(ValueError, "未取得匹配"):
                REAL_REFRESH(*args)

    def test_incomplete_coordination_can_resume_without_recreating(self):
        self.refresh.side_effect = ValueError("refresh unavailable")
        self.assertTrue(self.submit()["reconcile_required"])
        self.refresh.side_effect = None
        self.assertTrue(self.submit()["ok"])
        self.assertEqual(self.writes, 1)


if __name__ == "__main__":
    unittest.main()
