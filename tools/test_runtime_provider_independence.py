"""Actual Windows PowerShell setup regression, with isolated policy/doctor fixtures."""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("runtime_policy_fixture", ROOT / "tests/editor/runtime_policy_fixture.py")
assert spec and spec.loader
policy_fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy_fixture)


@unittest.skipUnless(os.name == "nt", "Windows PowerShell integration")
class ProviderIndependentSetup(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="gonggong-provider-free-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        policy_fixture.copy_runtime_policy(ROOT, self.root)
        for name in ("run_gonggong_config_agent.ps1", "configure_gonggong_runtime.ps1"):
            shutil.copyfile(ROOT / "tools" / name, self.root / "tools" / name)
        self.doctor = self.root / "tools/gonggong_bridge.py"
        self.doctor.write_text(
            'import os\nassert all(os.path.isfile(os.environ[k]) for k in ("GONGGONG_PYTHON","GONGGONG_NODE","GONGGONG_GIT"))\n'
        )
        (self.root / "tools/check_gonggong_github.ps1").write_text(
            'param($Workspace,$Gh,$Out)\n[IO.File]::WriteAllText($Out, \'{"ok":false,"error":"gh_unauthenticated"}\')\n'
        )
        (self.root / "tools/install_gonggong_github_cli.ps1").write_text("throw 'Unexpected installer invocation'\n")
        self.shell = str(Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe")
        self.env = {k: v for k, v in os.environ.items() if not k.startswith(("GONGGONG_", "CODEX_"))}
        self.env.update(
            PATH=str(Path(self.shell).parent),
            LOCALAPPDATA=str(self.root / "empty"),
            ProgramFiles=str(self.root / "empty"),
            USERPROFILE=str(self.root / "empty"),
        )
        # Python executes the real stdlib probe and doctor; the other components use
        # a working --version executable. This tests routing, not vendor packages.
        self.env.update({f"GONGGONG_{name}": sys.executable for name in ("PYTHON", "NODE", "GIT", "GH")})
        self.out = self.root / "result.json"
        self.pending = self.root / "pending-request.txt"
        self.pending.write_text("retained user request")

    def run_setup(self, success=True):
        proc = subprocess.run(
            [
                self.shell,
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(self.root / "tools/run_gonggong_config_agent.ps1"),
                "-Workspace",
                str(self.root),
                "-Out",
                str(self.out),
                "-Codex",
                str(self.root / "does-not-exist.exe"),
                "-Model",
                "unused",
            ],
            env=self.env,
            capture_output=True,
            timeout=90,
        )
        self.assertTrue(self.out.exists(), proc.stderr)
        value = json.loads(self.out.read_text(encoding="utf-8-sig"))
        self.assertEqual(proc.returncode == 0, success, (value, proc.stderr))
        self.assertEqual(value["ok"], success, value)
        self.assertEqual(self.pending.read_text(), "retained user request")
        return value

    def test_no_codex_or_account_configuration_and_rollback(self):
        value = self.run_setup()
        self.assertFalse(value["agent"]["provider_started"])
        self.assertIsNone(value["agent"]["observed_model"])
        self.assertEqual(value["github"]["error"], "gh_unauthenticated")
        self.assertEqual(value["python"], sys.executable)
        first_plan = json.loads(Path(value["agent"]["plan"]).read_text(encoding="utf-8-sig"))
        second = self.run_setup()
        self.assertEqual(first_plan, json.loads(Path(second["agent"]["plan"]).read_text(encoding="utf-8-sig")))
        proc = subprocess.run(
            [
                self.shell,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(self.root / "tools/configure_gonggong_runtime.ps1"),
                "-Workspace",
                str(self.root),
                "-Out",
                str(self.out),
                "-Rollback",
                value["receipt"],
            ],
            capture_output=True,
            timeout=60,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(self.out.read_text(encoding="utf-8-sig"))["state"], "rolled_back")
        self.assertTrue(Path(sys.executable).is_file())

    def test_github_checker_failures_preserve_configured_runtime(self):
        checker = self.root / "tools/check_gonggong_github.ps1"
        for body in (
            "throw 'fixture_checker_failure'",
            "return",
            "[IO.File]::WriteAllText($Out, '{invalid-json')",
            '[IO.File]::WriteAllText($Out, \'{"ok":"true"}\')',
        ):
            with self.subTest(checker=body):
                checker.write_text("param($Workspace,$Gh,$Out)\n" + body + "\n")
                value = self.run_setup()
                self.assertEqual(value["state"], "configured")
                self.assertFalse(value["github"]["ok"])
                self.assertTrue(value["github"]["action_required"])
                self.assertEqual(value["github"]["error"], "github_check_failed")
                self.assertTrue(value["github"]["detail"])
                self.assertEqual(value["python"], sys.executable)
                self.assertEqual(
                    json.loads(Path(value["receipt"]).read_text(encoding="utf-8-sig"))["state"], "configured"
                )
                for component in ("python", "node", "git", "gh"):
                    self.assertTrue(Path(value[component]).is_file())

    def test_failed_probe_is_not_selected(self):
        self.env["GONGGONG_NODE"] = str(self.root / "missing-node.exe")
        value = self.run_setup(False)
        self.assertIn("Missing validated runtime component: node", value["error"])
        self.assertFalse(value["agent"]["provider_started"])

    def test_policy_tamper_blocks_configuration(self):
        policy = self.root / "framework/FOUNDATION.md"
        policy.write_bytes(policy.read_bytes() + b"\ntampered")
        del self.env["GONGGONG_GH"]  # Policy rejection must precede any missing-gh install.
        value = self.run_setup(False)
        self.assertIn("Trusted host policy changed", value["error"])
        self.assertFalse(value["agent"]["policy_verified"])
        self.assertEqual(list(self.root.rglob("receipt.json")), [])

    def test_doctor_failure_preserves_deployment_failure_and_receipt(self):
        self.doctor.write_text("raise SystemExit(1)\n")
        value = self.run_setup(False)
        self.assertEqual(value["state"], "repair_environment")
        self.assertEqual(value["rollback"], "not_needed")
        self.assertTrue(Path(value["receipt"]).is_file())
        self.assertEqual(json.loads(Path(value["receipt"]).read_text(encoding="utf-8-sig"))["state"], "failed")


if __name__ == "__main__":
    unittest.main()
