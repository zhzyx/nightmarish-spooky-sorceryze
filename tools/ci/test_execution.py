from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from run_module import run_module
from summarize import validate_results


def registry(test_command):
    return {
        "schema_version": 1,
        "common_checks": [{"name": "static", "commands": ["true"]}],
        "modules": [
            {
                "name": "sample",
                "paths": ["sample/"],
                "runner": "ubuntu-latest",
                "handler": "generic",
                "setup_commands": [],
                "build_commands": ["true"],
                "test_commands": [test_command],
                "status_checks": ["Module / sample"],
                "dependencies": [],
            }
        ],
    }


class ExecutionTests(unittest.TestCase):
    def write_registry(self, directory, test_command):
        path = Path(directory) / "modules.json"
        path.write_text(json.dumps(registry(test_command)), encoding="utf-8")
        return path

    def test_real_command_success_is_required(self):
        with tempfile.TemporaryDirectory() as directory:
            registry_path = self.write_registry(directory, "printf tested > actual-result")
            self.assertEqual(run_module(Path(directory), registry_path, "sample"), 0)
            self.assertEqual((Path(directory) / "actual-result").read_text(), "tested")

    def test_command_failure_is_not_hidden(self):
        with tempfile.TemporaryDirectory() as directory:
            registry_path = self.write_registry(directory, "exit 23")
            self.assertEqual(run_module(Path(directory), registry_path, "sample"), 23)

    def test_non_generic_module_cannot_skip_its_specialized_tests(self):
        with tempfile.TemporaryDirectory() as directory:
            document = registry("true")
            document["modules"][0]["handler"] = "engine-next"
            path = Path(directory) / "modules.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "not the generic runner"):
                run_module(Path(directory), path, "sample")


class SummaryTests(unittest.TestCase):
    def test_unselected_special_jobs_may_be_skipped(self):
        selection = {"mode": "changed", "modules": ["docs"], "generic_matrix": []}
        needs = {
            "select": {"result": "success"},
            "module-tests": {"result": "skipped"},
            "engine-next": {"result": "skipped"},
        }
        self.assertEqual(validate_results(selection, needs), [])

    def test_selected_special_job_cannot_be_skipped(self):
        selection = {"mode": "changed", "modules": ["engine-next"], "generic_matrix": []}
        needs = {
            "select": {"result": "success"},
            "module-tests": {"result": "skipped"},
            "engine-next": {"result": "skipped"},
        }
        self.assertIn(
            "selected module engine-next required successful job engine-next", validate_results(selection, needs)
        )

    def test_generic_failure_is_not_success(self):
        selection = {"mode": "changed", "modules": ["ci"], "generic_matrix": [{"module": "ci"}]}
        needs = {"select": {"result": "success"}, "module-tests": {"result": "failure"}}
        self.assertTrue(validate_results(selection, needs))

    def test_full_regression_requires_static_and_all_special_jobs(self):
        selection = {"mode": "full", "modules": ["editor", "maliang"], "generic_matrix": []}
        needs = {
            "select": {"result": "success"},
            "static-checks": {"result": "skipped"},
            "module-tests": {"result": "skipped"},
            "editor-native": {"result": "success"},
            "maliang-offline": {"result": "success"},
            "blender-geometry": {"result": "success"},
        }
        self.assertIn("full regression requires successful static checks", validate_results(selection, needs))


if __name__ == "__main__":
    unittest.main()
