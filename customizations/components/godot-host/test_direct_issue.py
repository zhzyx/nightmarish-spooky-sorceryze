"""Exercise the actual GitHub work-item adapter, stubbing only its remote transport."""

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import bridge
import direct_issue
import issue_route

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
        self.request = {
            "draft_id": "draft_0123456789abcdef0123",
            "expected_user": "7",
            "title": "原始标题",
            "category": "development",
            "outcome": "原始输入\n\n  保留空格  ",
        }
        self.patch(bridge, "work_items_module", return_value=self.work)
        self.patch(bridge, "gh_state", return_value=("gh", None))
        self.patch(direct_issue, "collaborator", return_value={"user_id": "7", "repo": "test/repo", "login": "alice"})
        self.patch(self.work, "gh", side_effect=self.gh)
        self.enqueue = self.patch(bridge, "enqueue")
        self.flush = self.patch(bridge, "flush")
        self.refresh = self.patch(
            direct_issue, "refresh", return_value={"execution": "not_dispatched", "sourcesRead": 0}
        )

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
        row = {
            "number": 19,
            "html_url": URL,
            "state": "open",
            "user": {"id": 7},
            "body": Path(args[args.index("--body-file") + 1]).read_text(),
            "title": args[args.index("--title") + 1],
            "updated_at": "2026-11-06T00:00:00Z",
            "created_at": "2026-11-06T00:00:00Z",
            "labels": [{"name": v} for i, v in enumerate(args) if args[i - 1] == "--label"],
        }
        row["assignees"] = []
        self.rows.append(row)
        if self.lose_receipt:
            raise self.work.GitHubCommandError(reason="timeout")
        return URL

    def submit(self, **overrides):
        return bridge.GUIDE_ACTIONS["issue-direct"](self.root, {**self.request, **overrides})

    def routing(self, created=None):
        created = created or self.submit()
        self.assertTrue(created["ok"], created)
        return {
            "issue_number": created["number"],
            "request_id": created["request_id"],
            "expected_user": "7",
            "expected_revision": created["revision"],
            "backend": "http",
            "model": "fixture-model",
            "endpoint": "https://example.invalid",
            "_private_api_key": "private-fixture-token",
        }

    def fixture_model(self, *results):
        def context(root, bridge_api, agent_id, binding, request):
            return (
                "REGISTERED " + agent_id,
                "fixture-" + agent_id,
                {"id": agent_id, "version": "1", "origin": "gonggong-framework", "definition_sha256": "a" * 64},
                {},
            )

        self.patch(issue_route, "context", side_effect=context)
        self.patch(
            issue_route,
            "registered_candidates",
            side_effect=lambda root, route: {agent: "fixture-" + agent for agent in {"sinan", route}},
        )
        model = self.patch(issue_route.requirements_agent, "complete")
        model.side_effect = [
            r
            if isinstance(r, Exception)
            else {"text": json.dumps(r), "finish_reason": "stop", "usage": {"input_tokens": 18}}
            for r in results
        ]
        return model

    @staticmethod
    def judgment(route="sinan", questions=None):
        return {
            "route": route,
            "reason": "依据原文核实范围",
            "scope": ["导出原文"],
            "acceptance": ["可以回读"],
            "questions": questions or [],
        }

    def test_create_and_reread_without_model_or_worker(self):
        first = self.submit()
        self.assertTrue(first["ok"], first)
        self.assertEqual(
            (19, "daqian-direct-0123456789abcdef0123", URL, "planned", self.rows[0]["updated_at"]),
            tuple(first[key] for key in ("number", "request_id", "url", "status", "revision")),
        )
        self.assertNotIn("执行授权来源", self.rows[0]["body"])
        self.assertIn(self.request["outcome"], self.rows[0]["body"])
        self.assertIn("<!-- gonggong-intake:daqian-direct -->", self.rows[0]["body"])
        self.assertEqual(self.enqueue.call_args.args[1]["source_ref"], URL)
        self.assertEqual(self.enqueue.call_args.args[1]["payload"]["event"], "request.created")
        self.rows[0]["labels"][1]["name"] = "status:blocked"
        self.rows[0]["updated_at"] = "2026-11-06T00:00:01Z"
        repeated = self.submit()
        self.assertEqual(
            (repeated["status"], repeated["revision"], self.writes), ("blocked", self.rows[0]["updated_at"], 1)
        )
        self.refresh.assert_called_once()

    def test_only_start_can_activate_exact_planned_issue(self):
        bound = self.submit()
        self.assertTrue(bound["ok"], bound)
        start = {
            "issue_number": bound["number"],
            "request_id": bound["request_id"],
            "expected_user": "7",
            "expected_revision": bound["revision"],
        }
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
        self.assertTrue(bridge.issue_start(self.root, start)["refresh_routing"])
        inputs = self.routing(bound)
        model = self.fixture_model(self.judgment())
        result = bridge.issue_route(self.root, inputs)
        self.assertTrue(result["ready"], result)
        self.assertEqual(result["route"], "sinan")
        self.assertEqual(bridge.issue_route(self.root, inputs), result)
        model.assert_called_once()
        messages = model.call_args.args[3]
        self.assertIn("REGISTERED sinan", messages[0]["content"])
        self.assertEqual(json.loads(messages[1]["content"])["issue"]["body"], self.rows[0]["body"])
        self.assertEqual(self.writes, 1)
        self.assertEqual(bridge.issue_start(self.root, start)["state"], "started")
        self.assertEqual(bridge.issue_start(self.root, start)["state"], "already_active")
        self.rows[0]["updated_at"] = "2026-11-06T00:00:01Z"
        _, api = bridge.direct_adapter()
        context = issue_route.chat_context(self.root, start, api)
        self.assertEqual(context["original"], self.request["outcome"])
        self.assertEqual(context["decision"]["scope"], result["scope"])
        self.assertEqual(context["planned_revision"], bound["revision"])
        folder = direct_issue.receipt_folder(self.root, bound["request_id"])
        self.assertNotIn(inputs["_private_api_key"], "".join(p.read_text() for p in folder.glob("*.json")))

    def test_active_label_without_local_start_receipt_cannot_execute(self):
        inputs = self.routing()
        self.rows[0]["labels"][1]["name"] = "status:in-progress"
        _, api = bridge.direct_adapter()
        with self.assertRaisesRegex(ValueError, "回执"):
            bridge.issue_start(self.root, inputs)
        with self.assertRaisesRegex(ValueError, "回执"):
            issue_route.chat_context(self.root, inputs, api)

    def test_delegation_requires_yanshi_and_answers_same_issue(self):
        inputs = self.routing()
        model = self.fixture_model(
            self.judgment("yanshi"), self.judgment("yanshi", ["输出格式？"]), self.judgment("yanshi")
        )
        first = bridge.issue_route(self.root, inputs)
        self.assertEqual((first["route"], first["ready"], first["questions"]), ("yanshi", False, ["输出格式？"]))
        self.assertTrue(bridge.issue_start(self.root, inputs)["refresh_routing"])
        self.assertEqual(bridge.issue_route(self.root, inputs), first)
        answered = {**inputs, "answer": "CSV", "expected_questions": first["questions"]}
        last = bridge.issue_route(self.root, answered)
        self.assertEqual((last["ready"], last["number"], last["url"]), (True, 19, URL))
        self.assertEqual(bridge.issue_route(self.root, answered), last)
        self.assertEqual(bridge.issue_route(self.root, inputs), last)
        self.assertEqual([call.kwargs["agent_id"] for call in model.call_args_list], ["sinan", "yanshi", "yanshi"])
        data = json.loads(model.call_args.args[3][1]["content"])
        self.assertEqual(data["clarifications"], [{"questions": ["输出格式？"], "answer": "CSV"}])
        self.assertEqual(self.writes, 1)

    def test_concurrent_editors_answer_only_the_bound_questions(self):
        inputs = self.routing()
        model = self.fixture_model(
            self.judgment("yanshi"),
            self.judgment("yanshi", ["语言？"]),
            self.judgment("yanshi", ["界面语言？"]),
            self.judgment("yanshi"),
        )
        self.assertFalse(bridge.issue_route(self.root, inputs)["ready"])
        first = {**inputs, "expected_questions": ["语言？"], "answer": "中文"}
        self.assertEqual(bridge.issue_route(self.root, first)["questions"], ["界面语言？"])
        self.assertEqual(bridge.issue_route(self.root, first)["questions"], ["界面语言？"])
        stale = bridge.issue_route(self.root, dict(first, answer="英文"))
        self.assertFalse(stale["ok"])
        self.assertTrue(stale["refresh_routing"])
        self.assertEqual(bridge.issue_route(self.root, inputs)["questions"], ["界面语言？"])
        second = {**first, "expected_questions": ["界面语言？"]}
        self.assertTrue(bridge.issue_route(self.root, second)["ready"])
        self.assertTrue(bridge.issue_route(self.root, first)["ready"])
        self.assertEqual(model.call_count, 4)

    def test_source_revision_and_account_change_invalidate_readiness(self):
        inputs = self.routing()
        self.fixture_model(self.judgment(), self.judgment())
        bridge.issue_route(self.root, inputs)
        self.account = "8"
        with self.assertRaises(ValueError):
            bridge.issue_start(self.root, inputs)
        self.account = "7"
        self.rows[0]["body"] = self.rows[0]["body"].replace("原始输入", "改后的需求")
        self.assertTrue(bridge.issue_start(self.root, inputs)["refresh_routing"])
        self.rows[0]["updated_at"] = "2026-11-06T00:00:01Z"
        with self.assertRaisesRegex(ValueError, "版本"):
            bridge.issue_route(self.root, inputs)
        fresh = dict(inputs, expected_revision=self.rows[0]["updated_at"])
        self.assertEqual(bridge.issue_route(self.root, fresh)["revision"], fresh["expected_revision"])

    def test_model_failure_and_missing_model_leave_verified_issue_recoverable(self):
        inputs = self.routing()
        model = self.fixture_model(RuntimeError(inputs["_private_api_key"]), self.judgment())
        with self.assertRaisesRegex(ValueError, "配置"):
            bridge.issue_route(self.root, dict(inputs, model=""))
        model.assert_not_called()
        with self.assertRaisesRegex(ValueError, "显式重试"):
            bridge.issue_route(self.root, inputs)
        with self.assertRaisesRegex(ValueError, "显式重试"):
            bridge.issue_route(self.root, inputs)
        model.assert_called_once()
        self.assertTrue(bridge.issue_start(self.root, inputs)["refresh_routing"])
        self.assertTrue(bridge.issue_route(self.root, dict(inputs, retry_authorized=True))["ready"])
        self.assertEqual(model.call_count, 2)
        self.assertEqual(self.writes, 1)
        self.assertEqual(self.rows[0]["labels"][1]["name"], "status:planned")

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
            row.update(
                number=n,
                html_url=f"https://github.com/test/repo/issues/{n}",
                issue_dependencies_summary={"total_blocked_by": 0},
            )
        actor = {"login": "alice", "user_id": "7", "repo": "test/repo", "repo_id": "1"}
        with patch.object(board.work_items, "gh", return_value=json.dumps([cases])):
            items = board.read_board(self.root, [], actor)["issues"]
        self.assertEqual([item["analyzed"] for item in items], [False, True, False])
        self.assertEqual(
            items[0]["plan"]["nodes"], {"requirement": {"kind": "text", "title": "需求", "value": outcome}}
        )
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
        for change in [
            {"title": "sk-" + "x" * 32},
            {"outcome": "/Users/me/private"},
            {"draft_id": "../oops"},
            {"outcome": "<!-- gonggong-depends-on:#42 -->"},
            {"expected_user": "8"},
            {"category": "other"},
        ]:
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
        for change in [
            {"state": "closed"},
            {"user": {"id": 8}},
            {"title": "different"},
            {"body": row["body"] + "different"},
            {"updated_at": ""},
            {"pull_request": {}},
        ]:
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
        for relative in [
            "customizations/platforms/data-collection/git-files/storage/diting_files.py",
            "framework/tools/git_batch.py",
            "gonggong-diting-data/dataset.json",
        ]:
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
        self.assertEqual(
            (receipt["sourceSnapshot"]["source"], receipt["revision"], receipt["sourcesRead"]),
            ("github:test/repo#19", result["revision"], 1),
        )
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

    def test_actual_admitted_contexts_http_adapter_and_model_receipts(self):
        node = os.environ.get("GONGGONG_NODE") or shutil.which("node")
        if not node:
            self.skipTest("Node.js required for actual registered agent contexts")
        storage = "customizations/platforms/data-collection/git-files/storage"
        shutil.copytree(HOST.parents[2] / storage, self.root / storage)
        shutil.copytree(HOST.parents[2] / "framework", self.root / "framework")
        shutil.copy(HOST.parents[2] / "CURRENT_FRAMEWORK.json", self.root)
        (self.root / "gonggong-diting-data").mkdir()
        shutil.copy(HOST.parents[2] / "gonggong-diting-data/dataset.json", self.root / "gonggong-diting-data")
        self.refresh.side_effect = REAL_REFRESH
        self.flush.side_effect = REAL_FLUSH
        self.enqueue.side_effect = REAL_ENQUEUE
        inputs = self.routing(self.submit(node_runtime=node))
        requests = []

        def response(request, timeout):
            payload = json.loads(request.data)
            requests.append(payload)
            self.assertNotIn("tools", payload)
            self.assertEqual(request.get_header("Authorization"), "Bearer " + inputs["_private_api_key"])
            self.assertNotIn(inputs["_private_api_key"], str(payload))
            value = {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": json.dumps(self.judgment("yanshi", [] if len(requests) == 1 else ["由谁验收？"]))
                        },
                    }
                ],
                "usage": {"prompt_tokens": 21, "completion_tokens": 9},
            }
            return io.BytesIO(json.dumps(value).encode())

        with patch("urllib.request.build_opener") as opener:
            opener.return_value.open.side_effect = response
            result = bridge.issue_route(self.root, dict(inputs, cli_node=node))
            repeated = bridge.issue_route(self.root, dict(inputs, cli_node=node))
        self.assertEqual(result, repeated)
        self.assertEqual(len(requests), 2)
        self.assertEqual(result["questions"], ["由谁验收？"])
        self.assertIn("司南：通用任务协调 Agent", requests[0]["messages"][0]["content"])
        self.assertIn("ClarifyFeature", requests[1]["messages"][0]["content"])
        for payload in requests:
            self.assertEqual(json.loads(payload["messages"][1]["content"])["issue"]["body"], self.rows[0]["body"])
        records = [json.loads(path.read_text()) for path in (self.root / "gonggong-diting-data/events").rglob("*.json")]
        self.assertEqual(len(records), 3)
        steps = [event for event in records if event["kind"] == "step"]
        self.assertEqual({step["agent"]["id"] for step in steps}, {"sinan", "yanshi"})
        self.assertTrue(all(event["source_ref"] == URL for event in records))
        self.assertTrue(all(step["payload"]["usage"]["input_tokens"] == 21 for step in steps))
        self.assertNotIn(inputs["_private_api_key"], str(records))

    def test_incomplete_coordination_can_resume_without_recreating(self):
        self.refresh.side_effect = ValueError("refresh unavailable")
        bound = self.submit()
        self.assertTrue(bound["ok"] and bound["coordination_pending"])
        inputs = self.routing(bound)
        model = self.fixture_model(self.judgment())
        with self.assertRaisesRegex(ValueError, "refresh unavailable"):
            bridge.issue_route(self.root, inputs)
        model.assert_not_called()
        self.refresh.side_effect = None
        self.assertTrue(bridge.issue_route(self.root, inputs)["ready"])
        self.assertEqual(self.writes, 1)


if __name__ == "__main__":
    unittest.main()
