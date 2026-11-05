from copy import deepcopy
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"customizations/components/godot-host/daqian"))
import plan_store as store


class Answers(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        with patch.object(store.subprocess,"check_output",return_value=str(Path(tmp.name)/".git")):
            self.db=self.enterContext(store.connect(Path(tmp.name)))
        projection=store.source_plan({"html_url":"https://github.com/fixture/repo/issues/2","title":"流程",
            "body":"## 待确认\n- 【图片】请提供截图\n- 【选择】强调色 | 青色 | 紫色"},"request")
        self.source={"issue":"fixture#2","actor":"operator","source_revision":"v1","base":projection["plan"],
            "sources":projection["sources"],"questions":projection["questions"],"can_edit":False,"can_answer":True}
        self.photo,self.choice=projection["questions"]
        self.base=store.snapshot(self.db,self.source)
    def test_decision_can_be_supplied_before_execution_intake(self):
        req={"revision":self.base["revision"],"node":self.choice,"value":"青色"}
        first=store.answer(self.db,self.source,req)
        self.assertEqual(first["context"]["states"][self.choice],"answered")
        self.assertEqual(first["event"],"decision.recorded")
        self.assertEqual(store.answer(self.db,self.source,req)["context"],first["context"])
        with self.assertRaisesRegex(ValueError,"其他操作"):
            store.answer(self.db,self.source,dict(req,value="紫色"))
        self.assertNotIn(self.photo,first["context"]["answers"])
    def test_wrong_type_and_stale_q_leave_draft_independent(self):
        for key,value in [(self.photo,"abc"),(self.choice,"其它")]:
            with self.assertRaises(ValueError):
                store.answer(self.db,self.source,{"revision":self.base["revision"],"node":key,"value":value})
        with self.assertRaises(ValueError):
            store.answer(self.db,self.source,{"revision":"older","node":self.choice,"value":"青色"})
        self.assertEqual(store.snapshot(self.db,self.source)["context"]["answers"],{})
    def test_explicit_tag_is_the_source_of_the_image_placeholder(self):
        self.assertEqual(self.base["plan"]["nodes"][self.photo]["kind"],"image")
        self.assertEqual(self.base["context"]["questions"][self.photo]["kind"],"image")


if __name__=="__main__":
    unittest.main()
