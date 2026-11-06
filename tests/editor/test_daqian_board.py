import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"customizations/components/godot-host/daqian"))
import board


class BoardProjection(unittest.TestCase):
    def test_bound_design_document_and_published_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs = root / "design-docs"
            docs.mkdir()
            doc = docs / "design.md"
            body = "<!-- gonggong-request:example -->\n\n需求文档：`design-docs/design.md`\n\n# Published\n\n<!-- gonggong-host-git:fixture -->\n"
            self.assertEqual(board.design_document(root, body)["markdown"], "# Published")
            doc.write_text("# In progress", encoding="utf-8")
            self.assertEqual(board.design_document(root, body)["markdown"], "# In progress")
            self.assertEqual(board.design_document(root, body.replace("design.md", "../outside.md")), {})
            self.assertEqual(board.design_document(root, body.replace("需求文档", "无关链接")), {})

    def test_combined_scope_is_visible_without_requesting_user_input(self):
        from plan_store import connect
        issue = {"html_url": "https://github.com/fixture/board/issues/83", "title": "验证只读权限"}
        lines = ["核对权限", "读取代码", "拒绝写入", "隔离咨询", "固定模式", "记录上游阻塞"]
        with tempfile.TemporaryDirectory() as tmp, patch("subprocess.check_output", return_value=str(Path(tmp)/".git")), connect(Path(tmp)) as db:
            for section in ("范围与验收", "范围和验收"):
                issue["body"] = "## " + section + "\n" + "\n".join("- " + line for line in lines)
                item = board.source_plan(issue, "request")
                item.update(url=issue["html_url"], closed=False, updated="rev", request="request", status="needs-decision")
                tasks = [node["value"] for node in item["plan"]["nodes"].values() if node["kind"] == "task"]
                self.assertEqual(tasks, lines)
                self.assertEqual(len(item["plan"]["edges"]), len(lines))
                db.execute("INSERT OR IGNORE INTO answers(issue,node,question_version,value_json,actor) VALUES(?,?,?,?,?)",
                           (item["url"], "decision", "old-version", '"确认"', "member"))
                summary = board.plan_summary(db, item)
                self.assertEqual((summary["decision"], summary["pending_count"], summary["answered_count"]), (False, 0, 0))

    def test_shared_progress_counts_only_admitted_answers_and_verifies_actor(self):
        import graph_host
        import plan_store
        actor = {"user_id": "42", "repo_id": "7"}
        url = "https://github.com/fixture/board/issues/83"
        source = board.source_plan({"html_url": url, "title": "需求", "body": "## 待确认\n- 支持哪个版本？"}, "request")
        item = dict(source, url=url, updated="revision", request="request", closed=False, status="needs-decision")
        envelope = dict(action="board-progress", repository="fixture/board", expected_user="42", repo_id="7", follow=[83])
        with tempfile.TemporaryDirectory() as tmp, patch("subprocess.check_output", return_value=str(Path(tmp)/".git")), patch.object(board.work_items, "config", return_value=({"repository":"fixture/board"}, [])), patch.object(graph_host, "read_board", return_value={"issues":[item]}) as read:
            root = Path(tmp)
            with self.assertRaisesRegex(ValueError, "身份"):
                graph_host.execute(root, dict(envelope, expected_user="other"), actor)
            read.assert_not_called()
            summary = lambda: graph_host.execute(root, envelope, actor)["summaries"][url]
            self.assertEqual(summary()["pending_count"], 1)
            item["status"] = "blocked"
            self.assertFalse(summary()["decision"])
            item["status"] = "needs-decision"
            with plan_store.connect(root) as db:
                question, = item["questions"]
                source = dict(issue=url, actor="member", source_revision="rev", base=item["plan"],
                              sources=item["sources"], questions=item["questions"], can_edit=False, can_answer=True)
                revision = plan_store.snapshot(db, source)["revision"]
                plan_store.answer(db, source, dict(node=question, value="版本 1", revision=revision))
            self.assertEqual((summary()["pending_count"], summary()["answered_count"]), (0, 1))

    def test_private_workers_match_current_source_until_terminal(self):
        repo = "fixture/board"
        row = dict(number=2, title="Review", state="open", updated_at="rev1",
                   labels=[], assignees=[], body="")
        item = dict(number=2, request="work-2", url="https://github.com/fixture/board/issues/2", closed=False)
        ticket = "github:fixture/board#2"
        key = "a" * 64
        snapshot = dict(requestId=item["request"], authority=item["url"], sha256=board.progress.dispatch_revision(row))
        assign = dict(ticket=ticket, key=key, sourceSnapshot=snapshot)
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            folder = base / "codex-dispatch/sources"
            folder.mkdir(parents=True)
            stem = board.progress.issue_route.digest(ticket) + "-" + key
            (folder / (stem + ".claim.json")).write_text(json.dumps(dict(assignment=assign)))
            packet = dict(key=key, receipt=dict(workerId="reviewer", setupPending=False))
            (folder / (stem + ".worker.json")).write_text(json.dumps(packet))
            project = lambda: board.progress.workers_for_row(base, repo, row, item)
            self.assertEqual(project(), ["reviewer"])
            row["updated_at"] = "rev2"
            self.assertEqual(project(), [])
            row["updated_at"] = "rev1"
            (folder / (stem + ".terminal.json")).write_text("{}")
            self.assertEqual(project(), [])

    def test_follow_and_history_are_deduplicated(self):
        repo="zhzyx/nightmarish-spooky-sorceryze"
        def issue(number,state="open"):
            return {"number":number,"state":state,"title":str(number),"body":"","updated_at":"fixture",
                    "labels":[],"assignees":[],"html_url":f"https://github.com/{repo}/issues/{number}",
                    "repository_url":f"https://api.github.com/repos/{repo}"}
        a,b,old=issue(1),issue(2),issue(3,"closed")
        mine = issue(5)
        mine["issue_dependencies_summary"] = {"total_blocked_by": 0}
        assigned_only = dict(issue(7), issue_dependencies_summary={"total_blocked_by": 0})
        pull = dict(issue(6), pull_request={"url":"fixture"})
        additional=issue(4)
        additional["issue_dependencies_summary"]={"total_blocked_by":0}
        rows={1:[old],2:[old],3:[additional]}
        def gh(command,path,*flags):
            self.assertEqual(command,"api")
            if "?assignee=" in path:
                self.assertEqual(path, f"repos/{repo}/issues?assignee=team-user&state=open&per_page=100")
                self.assertEqual(flags, ("--paginate", "--slurp"))
                return json.dumps([[a], [assigned_only]])
            if "?creator=" in path:
                self.assertEqual(path, f"repos/{repo}/issues?creator=team-user&state=open&per_page=100")
                self.assertEqual(flags, ("--paginate", "--slurp"))
                return json.dumps([[pull, a], [mine]])
            if path.endswith("/2"):
                return json.dumps(b)
            n=int(path.split("/issues/")[1].split("/")[0])
            return json.dumps([rows[n]])
        with patch.object(board.work_items,"gh",side_effect=gh):
            projection=board.read_board(ROOT,[1,2,2],{"login":"team-user","user_id":"42","repo":repo,"repo_id":"7"})
        self.assertEqual([item["number"] for item in projection["issues"]],[1,2,3,4,5,7])
        self.assertTrue(projection["issues"][2]["closed"])
        self.assertEqual(projection["issues"][2]["dependencies"],[additional["html_url"]])


if __name__=="__main__":
    unittest.main()
