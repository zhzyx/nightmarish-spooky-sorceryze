from __future__ import annotations

import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from select_modules import changed_files, load_registry, owning_module, select_modules, selection_document

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "tools/ci/modules.json"


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.registry = load_registry(REGISTRY)

    def assertSelection(self, files, expected):
        self.assertEqual([module["name"] for module in select_modules(self.registry, files)], expected)

    def test_maliang_does_not_select_engine_next(self):
        self.assertSelection(["tools/ainative/test_executor.py"], ["maliang"])
        self.assertSelection(["editor/ainative/AIChat.gd"], ["maliang"])

    def test_engine_next_network_does_not_select_maliang_or_gameplay(self):
        self.assertSelection(["engine_next/Network/Session.cpp"], ["engine-next"])

    def test_gameplay_has_more_specific_ownership(self):
        self.assertSelection(["modules/gameplay/Session.cpp"], ["gameplay"])
        self.assertSelection(["engine_next/Gameplay/World.cpp"], ["gameplay"])

    def test_editor_and_web_are_independent(self):
        self.assertSelection(["editor/editor_node.cpp"], ["editor"])
        self.assertSelection(["platform/web/js/engine/engine.js"], ["web"])

    def test_multiple_modules_do_not_become_full_regression(self):
        self.assertSelection(
            ["tools/ainative/executor.py", "engine_next/Runtime/Server.cpp"], ["maliang", "engine-next"]
        )

    def test_shared_build_file_selects_only_build(self):
        self.assertSelection(["SConstruct"], ["engine-core"])
        self.assertSelection(["tools/build_engine_modules.py"], ["build"])

    def test_docs_only_select_common_checks(self):
        modules = select_modules(self.registry, ["Markdown/testing/README.md"])
        self.assertEqual([module["name"] for module in modules], ["docs"])
        selection = selection_document(self.registry, modules, ["Markdown/testing/README.md"], "a", "b", False)
        self.assertEqual(selection["generic_matrix"], [])

    def test_empty_diff_selects_nothing(self):
        self.assertSelection([], [])

    def test_unregistered_path_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "Unregistered changed path"):
            select_modules(self.registry, ["new-unregistered-dir/file.txt"])

    def test_full_regression_is_explicit_and_complete(self):
        modules = select_modules(self.registry, [], full=True)
        self.assertEqual(len(modules), len(self.registry["modules"]))
        self.assertIn("maliang", [module["name"] for module in modules])
        self.assertIn("engine-next", [module["name"] for module in modules])

    def test_duplicate_mapping_is_invalid(self):
        candidate = copy.deepcopy(self.registry)
        candidate["modules"][1]["paths"].append("tools/ci/")
        with self.assertRaisesRegex(ValueError, "registered by both"):
            from select_modules import validate_registry

            validate_registry(candidate)

    def test_unknown_dependency_is_invalid(self):
        candidate = copy.deepcopy(self.registry)
        candidate["modules"][0]["dependencies"] = ["not-a-module"]
        with self.assertRaisesRegex(ValueError, "unknown dependencies"):
            from select_modules import validate_registry

            validate_registry(candidate)

    def test_generic_module_requires_real_test(self):
        candidate = copy.deepcopy(self.registry)
        candidate["modules"][0]["test_commands"] = []
        with self.assertRaisesRegex(ValueError, "at least one test"):
            from select_modules import validate_registry

            validate_registry(candidate)

    def test_unsafe_or_unnormalized_paths_are_invalid(self):
        from select_modules import validate_registry

        for unsafe in ("/absolute", "../escape", "tools/./ci", "tools//ci", "tools\\ci"):
            candidate = copy.deepcopy(self.registry)
            candidate["modules"][0]["paths"] = [unsafe]
            with self.subTest(unsafe=unsafe), self.assertRaises(ValueError):
                validate_registry(candidate)

    def test_all_current_tracked_paths_are_registered(self):
        files = subprocess.check_output(
            ["git", "-c", "core.quotePath=false", "ls-files"], cwd=ROOT, text=True
        ).splitlines()
        unregistered = []
        for path in files:
            try:
                owning_module(self.registry, path)
            except ValueError:
                unregistered.append(path)
        self.assertEqual(unregistered, [])

    def test_real_git_diff_covers_rename_old_and_new_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.email", "ci@example.invalid"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "CI Test"], cwd=repo, check=True)
            (repo / "Markdown/testing").mkdir(parents=True)
            (repo / "Markdown/testing/old.md").write_text("before", encoding="utf-8")
            subprocess.run(["git", "add", "Markdown/testing/old.md"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "base"], cwd=repo, check=True)
            base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
            (repo / "Markdown/testing/old.md").rename(repo / "Markdown/testing/new.md")
            subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "rename"], cwd=repo, check=True)
            head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
            _, files = changed_files(repo, base, head)
            self.assertEqual(files, ["Markdown/testing/new.md", "Markdown/testing/old.md"])
            from select_modules import main

            output = repo / "selection.json"
            self.assertEqual(
                main([
                    "--repo",
                    str(repo),
                    "--registry",
                    str(REGISTRY),
                    "--base",
                    base,
                    "--head",
                    head,
                    "--output",
                    str(output),
                ]),
                0,
            )
            selection = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(selection["base"], base)
            self.assertEqual(selection["head"], head)
            self.assertEqual(selection["modules"], ["docs"])

    def test_cli_emits_machine_readable_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "github-output"
            from select_modules import main

            result = main([
                "--registry",
                str(REGISTRY),
                "--file",
                "tools/ainative/executor.py",
                "--github-output",
                str(output),
            ])
            self.assertEqual(result, 0)
            content = output.read_text(encoding="utf-8")
            self.assertIn('modules=["maliang"]', content)
            self.assertIn('generic_matrix={"include":[{"module":"maliang","runs_on":"ubuntu-latest"}]}', content)
            selection = json.loads(
                next(line.split("=", 1)[1] for line in content.splitlines() if line.startswith("selection="))
            )
            self.assertEqual(selection["path_ownership"], {"tools/ainative/executor.py": "maliang"})


if __name__ == "__main__":
    unittest.main()
