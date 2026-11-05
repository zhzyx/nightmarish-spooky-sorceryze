import copy
import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "customizations/components/godot-host/daqian"))
store = importlib.import_module("plan_store")


class Plans(unittest.TestCase):
    def setUp(self):
        source = {"issue":"test/repo#42", "source_revision":"a", "base":{"nodes":{}, "edges":[]},
                  "sources":{}, "actor":"fixture", "can_edit":True}
        self.source = source
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        location = Path(self.temp.name)
        with patch.object(store.subprocess, "check_output", return_value=str(location / ".git")):
            self.db = self.enterContext(store.connect(location))
        self.before = store.snapshot(self.db, source)
        self.graph = {"nodes":{"a":{"kind":"text","title":"目标","value":"修复"},
                               "b":{"kind":"task","title":"实现","value":""}},
                      "edges":[{"from":"a","to":"b","kind":"data"}]}

    def put(self, plan, base=None, source=None):
        return store.apply(self.db, source or self.source, dict(self.before if base is None else base, plan=plan))

    def test_revision_and_state_conflict_leave_previous_graph(self):
        first = self.put(self.graph)
        with self.assertRaisesRegex(ValueError, "变化"):
            self.put(self.graph)
        self.db.execute("INSERT INTO node_runs VALUES(?,?,?,?,?)", ("test/repo#42","b","run1","running","fixture"))
        self.db.commit()
        changed = copy.deepcopy(self.graph)
        changed["nodes"]["b"]["value"] = "另一任务"
        with self.assertRaisesRegex(ValueError, "变化"):
            self.put(changed, first)
        with self.assertRaisesRegex(ValueError, "保护"):
            self.put(changed, store.snapshot(self.db,self.source))
        self.assertEqual(store.snapshot(self.db,self.source)["plan"], self.graph)
        self.assertEqual(self.db.execute("SELECT count(*) FROM plan_events").fetchone()[0],1)

    def test_mixed_cycle(self):
        self.graph["edges"].append({"from":"b","to":"a","kind":"after"})
        with self.assertRaisesRegex(ValueError,"循环"):
            self.put(self.graph)
        self.assertEqual(store.snapshot(self.db,self.source)["plan"],self.before["plan"])

    def test_permissions_and_protected_source(self):
        with self.assertRaisesRegex(ValueError,"权限"):
            self.put(self.graph,source=dict(self.source,can_edit=False))
        protected = dict(self.source,base=self.graph)
        with self.assertRaisesRegex(ValueError,"连线"):
            self.put(dict(self.graph,edges=[]),store.snapshot(self.db,protected),protected)

    def test_yanshi_projection_is_stable(self):
        issue = {"html_url":"https://github.com/test/repo/issues/42","title":"案例",
                 "body":"## 范围\n- 检查截图\n## 验收条件\n- 能打开\n## 待确认\n- 使用哪个入口？"}
        plan = store.source_plan(issue,"request")
        self.assertEqual(plan,store.source_plan(issue,"request"))
        self.assertEqual([n["kind"] for n in plan["plan"]["nodes"].values()],["text","task","join","question"])
        self.assertEqual(len(plan["sources"]),4)


if __name__ == "__main__":
    unittest.main()
