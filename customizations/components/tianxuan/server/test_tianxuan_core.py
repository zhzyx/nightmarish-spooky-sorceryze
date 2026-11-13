import unittest

from tianxuan_core import (
    Tianxuan,
    TianxuanError,
    TransitionRejected,
    UnknownTool,
    VersionConflict,
    classify,
    machine_view,
)


class TianxuanCoreTests(unittest.TestCase):
    def setUp(self):
        self.tx = Tianxuan(":memory:")
        self.account = self.tx.register("天璇测试组织", "owner@example.com", "secret-pass", "Owner")
        self.actor = self.account["user_id"]

    def test_register_and_authenticate(self):
        user = self.tx.authenticate("owner@example.com", "secret-pass")
        self.assertEqual(user["user_id"], self.actor)
        self.assertIsNone(self.tx.authenticate("owner@example.com", "wrong"))
        with self.assertRaises(TianxuanError):
            self.tx.register("天璇测试组织", "owner@example.com", "another")

    def test_document_versioning_and_conflict(self):
        doc = self.tx.create_doc(self.actor, "上线检查", "# 上线检查\n\n登录与文档创建必须通过。\n")
        self.assertEqual(doc["version"], 1)
        updated = self.tx.update_doc(self.actor, doc["id"], doc["body_md"] + "\n补充：支持离线草稿。\n", 1)
        self.assertEqual(updated["version"], 2)
        with self.assertRaises(VersionConflict):
            self.tx.update_doc(self.actor, doc["id"], "stale", 1)
        self.assertEqual([v["version"] for v in self.tx.versions(doc["id"])], [1, 2])

    def test_ai_machine_view_exposes_headings_links_and_summary(self):
        body = "# 需求\n\n目标：把需求落库为 Markdown。\n\n## 关联\n\n- [[issue-1]]\n- [[issue-2]]\n"
        doc = self.tx.create_doc(self.actor, "需求", body, kind="requirement", request_id="req-1")
        view = self.tx.ai_view(doc["id"])
        self.assertEqual([h["text"] for h in view["machine"]["headings"]], ["需求", "关联"])
        self.assertEqual(view["machine"]["links"], ["issue-1", "issue-2"])
        self.assertIn("目标", view["machine"]["summary"])
        self.assertIn("requirement", view["tags"])

    def test_requirement_to_tickets_to_progress(self):
        requirement = self.tx.create_requirement(
            self.actor,
            "tianxuan-slice-1",
            "天璇首切片",
            "注册后能创建文档并建工单",
            "单组织首版",
            "文档可读、工单可推进、进度同步",
        )
        issues = self.tx.plan_tickets(
            self.actor,
            requirement["id"],
            [
                {"title": "注册登录", "acceptance": "邮箱注册与登录通过"},
                {"title": "文档创建", "acceptance": "Markdown 文档可创建与更新"},
            ],
        )
        self.assertEqual(len(issues), 3)
        self.assertEqual(len({i["number"] for i in issues}), 3)
        self.assertTrue(all(i["requirement_id"] == requirement["id"] for i in issues))

        child = next(i for i in issues if i["type"] == "task")
        for status in ("planned", "in-progress", "in-review", "done"):
            child = self.tx.transition_issue(self.actor, child["id"], status)
        self.assertEqual(child["status"], "done")
        progress = self.tx.sync_progress(requirement["id"])
        self.assertEqual(progress["total"], 3)
        self.assertEqual(progress["done"], 1)
        self.assertEqual(progress["percent"], 33)
        self.assertEqual(self.tx.get_doc(requirement["id"])["progress"]["done"], 1)

    def test_transition_rejects_illegal_edge(self):
        issue = self.tx.create_issue(self.actor, "非法迁移")
        with self.assertRaises(TransitionRejected):
            self.tx.transition_issue(self.actor, issue["id"], "done")

    def test_cancelled_transition_is_terminal(self):
        issue = self.tx.create_issue(self.actor, "取消迁移")
        self.tx.transition_issue(self.actor, issue["id"], "planned")
        cancelled = self.tx.transition_issue(self.actor, issue["id"], "cancelled")
        self.assertEqual(cancelled["status"], "cancelled")
        with self.assertRaises(TransitionRejected):
            self.tx.transition_issue(self.actor, issue["id"], "in-progress")

    def test_events_and_ai_tools(self):
        doc = self.tx.dispatch_tool(self.actor, "doc.create", {"title": "AI 工具文档", "body_md": "# 工具\n\n内容\n"})
        self.assertEqual(doc["title"], "AI 工具文档")
        listed = self.tx.dispatch_tool(self.actor, "doc.list", {})
        self.assertEqual([d["id"] for d in listed["docs"]], [doc["id"]])
        with self.assertRaises(UnknownTool):
            self.tx.dispatch_tool(self.actor, "doc.delete", {})
        types = [event["type"] for event in self.tx.events(self.actor)]
        self.assertIn("user.registered", types)
        self.assertIn("doc.created", types)

    def test_classify_and_machine_view_are_pure(self):
        self.assertIn("requirement", classify("需求与验收"))
        self.assertIn("design", classify("Design and architecture"))
        self.assertEqual(machine_view("plain paragraph")["headings"], [])


if __name__ == "__main__":
    unittest.main()
