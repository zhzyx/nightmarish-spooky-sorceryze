from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from integration_plan import classify_boundary, compose, inventory, overlap, plan


class IntegrationPlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.repo = Path(self.directory.name)
        self.git("init", "-q")
        self.git("config", "user.name", "Synthetic test")
        self.git("config", "user.email", "synthetic@example.invalid")
        self.git("config", "commit.gpgsign", "false")
        self.base = self.change({"shared": "base", "file with spaces": "base"})

    def git(self, *args: str) -> str:
        return subprocess.check_output(["git", "-C", str(self.repo), *args], stderr=subprocess.PIPE).decode().strip()

    def change(self, files: dict[str, str | bytes], base: str | None = None) -> str:
        if base:
            self.git("checkout", "--detach", "-q", base)
        for name, value in files.items():
            path = self.repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(value, bytes):
                path.write_bytes(value)
            else:
                path.write_text(value, encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "-qm", "synthetic fixture")
        return self.git("rev-parse", "HEAD")

    def test_independent_changes_and_read_dependency(self) -> None:
        a = self.change({"a": "a"}, self.base)
        b = self.change({"b": "b"}, self.base)
        inputs: list[dict[str, object]] = [
            {"id": "a", "tip": a, "reads": []},
            {"id": "b", "tip": b, "reads": []},
        ]
        self.assertEqual(plan(self.repo, self.base, inputs)["preparation_waves"], [["a", "b"]])
        inputs[1]["reads"] = ["a"]
        self.assertEqual(plan(self.repo, self.base, inputs)["preparation_waves"], [["a"], ["b"]])
        inputs[1].pop("reads")
        self.assertTrue(plan(self.repo, self.base, inputs)["conflicts"][0]["unknown_dependencies"])

    def test_overlap_target_drift_and_inclusion(self) -> None:
        a = self.change({"shared": "left"}, self.base)
        b = self.change({"shared": "right"}, self.base)
        result = plan(self.repo, a, [{"id": "a", "tip": a}, {"id": "b", "tip": b}])
        self.assertTrue(result["contributions"][0]["already_included"])
        self.assertEqual(result["contributions"][1]["target_overlap"], ["shared"])
        self.assertEqual(result["preparation_waves"], [["b"]])

    def test_dependencies_and_cycle(self) -> None:
        a = self.change({"a": "a"}, self.base)
        b = self.change({"b": "b"}, self.base)
        inputs: list[dict[str, object]] = [
            {"id": "b", "tip": b, "reads": [], "depends_on": ["a"]},
            {"id": "a", "tip": a, "reads": []},
        ]
        self.assertEqual(plan(self.repo, self.base, inputs)["preparation_waves"], [["a"], ["b"]])
        inputs[1]["depends_on"] = ["b"]
        with self.assertRaisesRegex(ValueError, "cycle"):
            plan(self.repo, self.base, inputs)
        inputs[1]["depends_on"] = ["missing"]
        with self.assertRaisesRegex(ValueError, "Unknown"):
            plan(self.repo, self.base, inputs)

    def test_rename_source_and_directory_overlap(self) -> None:
        self.git("mv", "shared", "renamed")
        self.git("commit", "-qm", "rename")
        a = self.git("rev-parse", "HEAD")
        b = self.change({"shared": "edit"}, self.base)
        result = plan(self.repo, self.base, [{"id": "a", "tip": a, "reads": []}, {"id": "b", "tip": b, "reads": []}])
        self.assertEqual(result["contributions"][0]["writes"], ["renamed", "shared"])
        self.assertEqual(result["conflicts"][0]["paths"], ["shared"])
        self.assertEqual(overlap(["a"], ["a/b"]), ["a"])

    def test_inventory_is_commit_bound_read_only_and_classifies_binaries_and_boundaries(self) -> None:
        rev = self.change(
            {
                "core/object/object.cpp": "int x = 1;\n",
                "thirdparty/lib/vendor.c": "int y = 2;\n",
                "framework/FOUNDATION.md": "# frozen\n",
                "customizations/components/tianxuan/api.py": "pass\n",
                "gonggong-diting-data/dataset.json": "{}\n",
                "design-docs/spec.md": "# doc\n",
                "platform/icon.bin": b"\x00\x89PNG\r\n\x1a\n\x00",
            },
            self.base,
        )
        self.git("checkout", "--detach", "-q", self.base)
        before = self.git("status", "--porcelain=v1")
        result = inventory(self.repo, rev)
        (self.repo / "shared").write_text("dirty")
        self.assertEqual(result, inventory(self.repo, rev))
        self.assertEqual(result["files"], 9)
        self.assertEqual(result["binary_files"], 1)
        self.assertEqual(result["text_files"], 8)
        self.assertIn("file with spaces", [e["path"] for e in result["entries"]])
        self.assertEqual(classify_boundary("core/object/object.cpp"), "engine_native")
        self.assertEqual(classify_boundary("thirdparty/lib/vendor.c"), "thirdparty")
        self.assertEqual(classify_boundary("framework/FOUNDATION.md"), "framework_governance")
        self.assertEqual(classify_boundary("customizations/components/tianxuan/api.py"), "host_adapters_and_apps")
        self.assertEqual(classify_boundary("gonggong-diting-data/dataset.json"), "telemetry_and_evidence")
        self.assertEqual(classify_boundary("design-docs/spec.md"), "documentation_and_specs")
        self.assertEqual(before, "")
        self.assertEqual(self.git("diff", "--cached"), "")
        self.assertEqual(json.loads(json.dumps(result)), result)

    def test_compose_folds_multi_base_disjoint_waves_and_isolates_conflicts_without_repo_mutation(self) -> None:
        # Advance target along main while contributors branched from different historical bases.
        c_early = self.change({"modules/alpha/a.cpp": "alpha v1\n"}, self.base)
        target_mid = self.change({"apps/web/page.tsx": "web v1\n"}, self.base)
        c_mid = self.change({"modules/beta/b.cpp": "beta v1\n"}, target_mid)
        c_conflict = self.change({"modules/alpha/a.cpp": "conflicting alpha\n"}, self.base)
        c_dep_on_conflict = self.change({"modules/gamma/g.cpp": "gamma\n"}, target_mid)
        target_latest = self.change({"design-docs/plan.md": "# plan\n"}, target_mid)

        objects_dir = Path(self.git("rev-parse", "--git-path", "objects"))
        if not objects_dir.is_absolute():
            objects_dir = (self.repo / objects_dir).resolve()
        before_objects = sorted(p.relative_to(objects_dir).as_posix() for p in objects_dir.rglob("*") if p.is_file())

        items: list[dict[str, object]] = [
            {"id": "early", "tip": c_early, "reads": []},
            {"id": "mid", "tip": c_mid, "reads": []},
            {"id": "conflict", "tip": c_conflict, "reads": []},
            {"id": "dependent", "tip": c_dep_on_conflict, "reads": [], "depends_on": ["conflict"]},
        ]
        dry_run = compose(self.repo, target_latest, items, write_objects=False)
        after_objects = sorted(p.relative_to(objects_dir).as_posix() for p in objects_dir.rglob("*") if p.is_file())
        self.assertEqual(before_objects, after_objects, "quarantine compose must not write loose objects")
        self.assertIsNone(dry_run["composed_tree"])
        self.assertEqual([x["id"] for x in dry_run["integrated"]], ["early", "mid"])
        self.assertEqual(
            [(x["id"], x["reason"]) for x in dry_run["isolated"]],
            [("conflict", "path_or_read_overlap"), ("dependent", "dependency_isolated")],
        )

        persisted = compose(self.repo, target_latest, items, write_objects=True)
        composed_tree = persisted["composed_tree"]
        self.assertEqual(composed_tree, dry_run["ephemeral_composed_tree"])
        self.assertEqual(self.git("show", f"{composed_tree}:modules/alpha/a.cpp"), "alpha v1")
        self.assertEqual(self.git("show", f"{composed_tree}:modules/beta/b.cpp"), "beta v1")
        self.assertEqual(self.git("show", f"{composed_tree}:apps/web/page.tsx"), "web v1")
        self.assertEqual(self.git("show", f"{composed_tree}:design-docs/plan.md"), "# plan")


if __name__ == "__main__":
    unittest.main()
