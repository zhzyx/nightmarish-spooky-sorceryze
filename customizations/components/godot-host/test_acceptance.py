"""Controlled authority fixtures; these do not attest a live reviewer or GitHub login."""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("acceptance", Path(__file__).with_name("acceptance.py"))
acceptance = importlib.util.module_from_spec(spec)
spec.loader.exec_module(acceptance)


class AcceptanceAuthorityTests(unittest.TestCase):
    def test_actual_wrapper_never_loads_candidate_verifier(self):
        installation = Path(__file__).resolve().parents[3]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake = root / "customizations/components/godot-host/bridge.py"
            fake.parent.mkdir(parents=True)
            marker = root / "candidate-executed"
            fake.write_text("from pathlib import Path\nPath(" + repr(str(marker)) + ").write_text('unsafe')\n")
            request = root / "request.json"
            request.write_text("{}")
            for action in ("acceptance-capture", "acceptance-verify", "acceptance-current"):
                output = root / (action + ".json")
                result = subprocess.run(
                    [
                        sys.executable,
                        str(installation / "tools/gonggong_bridge.py"),
                        action,
                        "--workspace",
                        str(root),
                        "--request",
                        str(request),
                        "--out",
                        str(output),
                    ],
                    capture_output=True,
                    timeout=30,
                )
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertFalse(marker.exists())
                response = json.loads(output.read_text(encoding="utf-8"))
                self.assertFalse(response["ok"])
                self.assertIn("Missing host request correlation", response["error"])

    def test_current_actual_cli_checks_unicode_inventory_without_granting_acceptance(self):
        installation = Path(__file__).resolve().parents[3]
        node = acceptance.shutil.which("node")
        self.assertIsNotNone(node)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "candidate"
            root.mkdir()

            def git(*args):
                return subprocess.check_output(["git", "-C", str(root), *args], stderr=subprocess.STDOUT)

            git("init", "-b", "main")
            git("config", "user.name", "Fixture")
            git("config", "user.email", "fixture@invalid")
            asset = root / "中文 空格.txt"
            asset.write_bytes(b"reviewed output")
            git("add", ".")
            git("commit", "-m", "fixture")
            capture = subprocess.check_output(
                [
                    node,
                    str(installation / "customizations/components/repository-dispatch/acceptance.mjs"),
                    "capture",
                    str(root),
                ],
                input=b"",
                timeout=30,
            )
            candidate = json.loads(capture)["candidate"]
            request = Path(directory) / "request.json"
            output = Path(directory) / "result.json"
            request.write_text(json.dumps({"request_nonce": "current-only", "candidate": candidate}), encoding="utf-8")

            def check_current(expected):
                result = subprocess.run(
                    [
                        sys.executable,
                        str(installation / "tools/gonggong_bridge.py"),
                        "acceptance-current",
                        "--workspace",
                        str(root),
                        "--request",
                        str(request),
                        "--out",
                        str(output),
                    ],
                    env=dict(os.environ, GONGGONG_NODE=node),
                    capture_output=True,
                    timeout=30,
                )
                self.assertEqual(result.returncode, 0 if expected else 1, result.stderr)
                value = json.loads(output.read_text(encoding="utf-8"))
                self.assertEqual(value["ok"], expected)
                self.assertNotIn("operator", value)
                self.assertNotIn("projection", value)
                if expected:
                    self.assertEqual(value["request_nonce"], "current-only")
                    self.assertEqual(value["candidate_sha256"], candidate["files_sha256"])

            check_current(True)
            added = root / "new-source.txt"
            added.write_bytes(b"unreviewed")
            check_current(False)
            added.unlink()
            asset.write_bytes(b"changed")
            check_current(False)
            asset.unlink()
            check_current(False)
            asset.write_bytes(b"reviewed output")
            moved = root.with_name("replacement")
            root.rename(moved)
            subprocess.run(
                [
                    node,
                    "-e",
                    "require('fs').symlinkSync(process.argv[1],process.argv[2],'junction')",
                    str(moved),
                    str(root),
                ],
                check=True,
            )
            try:
                check_current(False)
            finally:
                if os.name == "nt":
                    os.rmdir(root)
                else:
                    root.unlink()
                moved.rename(root)
            git("commit", "--allow-empty", "-m", "changed head")
            check_current(False)

    def run_fixture(self, permission="write", intake=True, capture=True):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "work-items.json").write_text(json.dumps({"repository": "fixture/repo"}))
            calls = []

            def run(command, **kwargs):
                calls.append(command)
                value = {"login": "fixture"} if command[-1] == "user" else {"permission": permission}
                if command[0] == "node":
                    value = {"ok": True, "candidate": {"fixture": True}}
                return SimpleNamespace(returncode=0, stdout=json.dumps(value))

            def bind(*args):
                if not intake:
                    raise ValueError("current intake refused")
                self.assertTrue(args[1]["daqian_bound"])

            bridge = SimpleNamespace(host_environment=lambda r: {}, find_gh=lambda e, r: "gh", issue_binding=bind)
            with (
                patch.object(acceptance.subprocess, "run", side_effect=run),
                patch.object(acceptance.shutil, "which", return_value="node"),
            ):
                result = acceptance.execute(
                    bridge,
                    root,
                    {"request_nonce": "host-generation", "issue_number": 776, "request_id": "fixture"},
                    capture,
                )
            return result, calls

    def test_current_write_and_intake_before_capture(self):
        result, calls = self.run_fixture()
        self.assertTrue(result["ok"])
        self.assertEqual(result["operator"], "fixture")
        self.assertEqual(result["request_nonce"], "host-generation")
        self.assertEqual(calls[-1][0], "node")

    def test_revoked_permission_stops_capture(self):
        with self.assertRaisesRegex(ValueError, "write permission"):
            self.run_fixture(permission="read")

    def test_failed_intake_stops_capture(self):
        with self.assertRaisesRegex(ValueError, "intake refused"):
            self.run_fixture(intake=False)

    def test_no_decision_is_not_a_verdict(self):
        with self.assertRaisesRegex(ValueError, "bounded host decision"):
            self.run_fixture(capture=False)

    def test_cancelled_generation_stops_before_authority_or_projection(self):
        with tempfile.TemporaryDirectory() as directory:
            live = Path(directory) / "request.live"
            live.write_text(json.dumps({"request_nonce": "old", "active": True}))
            with self.assertRaisesRegex(ValueError, "cancelled or unknown"):
                acceptance.execute(
                    None,
                    Path(directory),
                    {"request_nonce": "new", "decision_json": "{}", "host_liveness_path": str(live)},
                )

    def test_missing_generation_cannot_start_projection(self):
        with self.assertRaisesRegex(ValueError, "liveness path"):
            acceptance.execute(None, Path.cwd(), {"request_nonce": "new", "decision_json": "{}"})


if __name__ == "__main__":
    unittest.main()
