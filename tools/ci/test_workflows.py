from __future__ import annotations

import re
import unittest
from pathlib import Path

from select_modules import load_registry

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github/workflows"


class WorkflowContractTests(unittest.TestCase):
    def test_only_central_workflows_have_ordinary_triggers(self):
        for path in WORKFLOWS.glob("*.yml"):
            if path.name in {"modular-ci.yml", "runner.yml", "gonggong-issue-gate.yml", "kuafu-blockers.yml"}:
                continue
            text = path.read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"^  pull_request:", text, re.M), path.name)
            self.assertIsNone(re.search(r"^  push:", text, re.M), path.name)

    def test_engine_next_contains_no_maliang_or_gameplay_suite(self):
        text = (WORKFLOWS / "engine_next_contract.yml").read_text(encoding="utf-8")
        self.assertNotIn("tools/ainative", text)
        self.assertNotIn("BuildGameplay.py", text)
        self.assertNotIn("test_unified_settings.py", text)
        self.assertIn("BuildRuntime.py", text)
        self.assertIn("--soak", text)

    def test_maliang_retains_workbench_acceptance(self):
        text = (WORKFLOWS / "maliang_hunyuan_windows.yml").read_text(encoding="utf-8")
        self.assertIn("test_unified_settings.py", text)
        self.assertIn("run_bundled_hunyuan_windows.ps1", text)

    def test_windows_build_only_cannot_run_business_tests(self):
        text = (WORKFLOWS / "windows_builds.yml").read_text(encoding="utf-8")
        self.assertIn("default: build-only", text)
        self.assertIn("default: full", text)
        for name in (
            "Editor build and staging contracts",
            "Validate native WebView2 in a hidden window",
            "Tianshu workbench UI smoke",
            "Native reasoning session isolation and Codex wire regression",
            "Runtime deployment interruption and original request recovery",
            "Parent binding survives interrupted editor shutdown",
            "Original design reconfirmation and independent continuation",
        ):
            block = text.split(f"- name: {name}", 1)[1].split("\n      - name:", 1)[0]
            self.assertIn("inputs.validation_profile == 'editor'", block, name)
            self.assertIn("inputs.validation_profile == 'full'", block, name)

    def test_every_special_handler_is_wired_to_the_central_workflow(self):
        registry = load_registry(ROOT / "tools/ci/modules.json")
        central = (WORKFLOWS / "modular-ci.yml").read_text(encoding="utf-8")
        expected = {
            "engine-next": "engine_next_contract.yml",
            "gameplay": "gameplay_tests.yml",
            "web": "web_builds.yml",
            "tianxuan": "tianxuan-tests.yml",
            "integration": "integration-plan.yml",
            "build": "engine_build_scope.yml",
        }
        for module in registry["modules"]:
            handler = module["handler"]
            if handler in expected:
                self.assertIn(f"uses: ./.github/workflows/{expected[handler]}", central)
                self.assertIn(f"'{module['name']}'", central)
        self.assertIn(
            "validation_profile: ${{ github.event_name == 'workflow_dispatch' && 'full' || 'editor' }}", central
        )
        self.assertIn("full_regression=true", central)

    def test_no_module_workflow_uses_path_filters(self):
        for name in (
            "engine_next_contract.yml",
            "maliang_hunyuan_windows.yml",
            "blender_geometry_windows.yml",
            "tianxuan-tests.yml",
            "tianxuan-deploy-build.yml",
            "integration-plan.yml",
            "native-cache.yml",
            "engine_build_scope.yml",
        ):
            self.assertNotIn("paths:", (WORKFLOWS / name).read_text(encoding="utf-8"), name)


if __name__ == "__main__":
    unittest.main()
