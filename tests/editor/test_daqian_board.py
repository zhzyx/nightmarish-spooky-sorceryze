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
