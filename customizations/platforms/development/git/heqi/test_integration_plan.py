import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from integration_plan import inventory, plan


class IntegrationPlanTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.repo = Path(self.directory.name)
        self.git("init", "-q")
        self.git("config", "user.name", "Synthetic test")
        self.git("config", "user.email", "synthetic@example.invalid")
        self.base = self.change({"shared": "base", "file with spaces": "base"})

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.repo), *args], stderr=subprocess.PIPE).decode().strip()

    def change(self, files, base=None):
        if base:
            self.git("checkout", "--detach", "-q", base)
        for name, value in files.items():
            path = self.repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(value, encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "-qm", "synthetic fixture")
        return self.git("rev-parse", "HEAD")

    def test_independent_changes_and_read_dependency(self):
        a = self.change({"a": "a"}, self.base)
        b = self.change({"b": "b"}, self.base)
        inputs = [{"id": "a", "tip": a, "reads": []}, {"id": "b", "tip": b, "reads": []}]
        self.assertEqual(plan(self.repo, self.base, inputs)["preparation_waves"], [["a", "b"]])
        inputs[1]["reads"] = ["a"]
        self.assertEqual(plan(self.repo, self.base, inputs)["preparation_waves"], [["a"], ["b"]])
        inputs[1].pop("reads")
        self.assertTrue(plan(self.repo, self.base, inputs)["conflicts"][0]["unknown_dependencies"])

    def test_overlap_target_drift_and_inclusion(self):
        a = self.change({"shared": "left"}, self.base)
        b = self.change({"shared": "right"}, self.base)
        result = plan(self.repo, a, [{"id": "a", "tip": a}, {"id": "b", "tip": b}])
        self.assertTrue(result["contributions"][0]["already_included"])
        self.assertEqual(result["contributions"][1]["target_overlap"], ["shared"])
        self.assertEqual(result["preparation_waves"], [["b"]])

    def test_dependencies_and_cycle(self):
        a = self.change({"a": "a"}, self.base)
        b = self.change({"b": "b"}, self.base)
        inputs = [{"id": "b", "tip": b, "reads": [], "depends_on": ["a"]}, {"id": "a", "tip": a, "reads": []}]
        self.assertEqual(plan(self.repo, self.base, inputs)["preparation_waves"], [["a"], ["b"]])
        inputs[1]["depends_on"] = ["b"]
        with self.assertRaisesRegex(ValueError, "cycle"):
            plan(self.repo, self.base, inputs)
        inputs[1]["depends_on"] = ["missing"]
        with self.assertRaisesRegex(ValueError, "Unknown"):
            plan(self.repo, self.base, inputs)

    def test_rename_source_and_directory_overlap(self):
        self.git("mv", "shared", "renamed")
        self.git("commit", "-qm", "rename")
        a = self.git("rev-parse", "HEAD")
        b = self.change({"shared": "edit"}, self.base)
        result = plan(self.repo, self.base, [{"id": "a", "tip": a, "reads": []}, {"id": "b", "tip": b, "reads": []}])
        self.assertEqual(result["contributions"][0]["writes"], ["renamed", "shared"])
        self.assertEqual(result["conflicts"][0]["paths"], ["shared"])
        from integration_plan import overlap

        self.assertEqual(overlap(["a"], ["a/b"]), ["a"])

    def test_inventory_is_commit_bound_and_read_only(self):
        before = self.git("status", "--porcelain=v1")
        result = inventory(self.repo, self.base)
        (self.repo / "shared").write_text("dirty")
        self.assertEqual(result, inventory(self.repo, self.base))
        self.assertEqual(result["files"], 2)
        self.assertIn("file with spaces", [e["path"] for e in result["entries"]])
        self.assertEqual(before, "")
        self.assertEqual(self.git("diff", "--cached"), "")
        self.assertEqual(json.loads(json.dumps(result)), result)


if __name__ == "__main__":
    unittest.main()
