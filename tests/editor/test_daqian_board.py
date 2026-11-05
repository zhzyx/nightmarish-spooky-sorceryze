import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"customizations/components/godot-host/daqian"))
import board


class BoardProjection(unittest.TestCase):
    def test_follow_and_history_are_deduplicated(self):
        repo="zhzyx/nightmarish-spooky-sorceryze"
        def issue(number,state="open"):
            return {"number":number,"state":state,"title":str(number),"body":"","updated_at":"fixture",
                    "labels":[],"assignees":[],"html_url":f"https://github.com/{repo}/issues/{number}",
                    "repository_url":f"https://api.github.com/repos/{repo}"}
        a,b,old=issue(1),issue(2),issue(3,"closed")
        additional=issue(4)
        additional["issue_dependencies_summary"]={"total_blocked_by":0}
        rows={1:[old],2:[old],3:[additional]}
        def gh(command,path,*flags):
            self.assertEqual(command,"api")
            if "?assignee=" in path:
                self.assertIn("assignee=team-user",path)
                return json.dumps([[a]])
            if path.endswith("/2"):
                return json.dumps(b)
            n=int(path.split("/issues/")[1].split("/")[0])
            return json.dumps([rows[n]])
        with patch.object(board.work_items,"gh",side_effect=gh):
            projection=board.read_board(ROOT,[1,2,2],{"login":"team-user","user_id":"42","repo":repo,"repo_id":"7"})
        self.assertEqual([item["number"] for item in projection["issues"]],[1,2,3,4])
        self.assertTrue(projection["issues"][2]["closed"])
        self.assertEqual(projection["issues"][2]["dependencies"],[additional["html_url"]])


if __name__=="__main__":
    unittest.main()
