import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("igniter", Path(__file__).with_name("environment_igniter.py"))
assert spec is not None and spec.loader is not None
igniter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(igniter)


class EnvironmentIgniterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "project/runtime").mkdir(parents=True)

    def state_path(self):
        return self.root / "project/runtime/state/installed.json"

    def test_check_reports_missing_and_locations(self):
        with patch.object(igniter, "component_status", return_value={
            "python": {"available": True, "path": "/usr/bin/python3", "sha256": None},
            "node": {"available": False, "path": None, "sha256": None},
            "git": {"available": False, "path": None, "sha256": None},
        }):
            result = igniter.environment_check(self.root)
        self.assertFalse(result["ok"])
        self.assertEqual(result["environment_missing"], ["node", "git"])
        self.assertIn("project-local", result["locations"])
        self.assertFalse(result["model_execution_started"])

    def test_deploy_records_state_and_env_changes(self):
        node = self.root / "node"
        node.write_bytes(b"fake node")
        os.chmod(node, 0o755)
        selection = {"components": ["node"], "location": "project-local", "paths": {"node": str(node)}}
        result = igniter.environment_deploy(self.root, selection)
        self.assertTrue(result["ok"])
        self.assertEqual(result["env_changes"]["GONGGONG_NODE"], str(node.resolve()))
        state = igniter.read_state(self.root)
        self.assertEqual(state["schema_version"], 1)
        self.assertEqual(state["components"][0]["id"], "node")
        self.assertIn("GONGGONG_NODE", state["env_changes"])
        recovery = self.root / "project/runtime/state/recovery.md"
        self.assertTrue(recovery.is_file())
        self.assertIn("environment-rollback", recovery.read_text(encoding="utf-8"))

    def test_deploy_refuses_unknown_component(self):
        with self.assertRaises(ValueError):
            igniter.environment_deploy(self.root, {"components": ["rust"], "location": "project-local"})

    def test_deploy_refuses_missing_path_without_auto_install(self):
        with patch.object(igniter, "component_status", return_value={
            "python": {"available": True, "path": "/usr/bin/python3", "sha256": None},
            "node": {"available": False, "path": None, "sha256": None},
            "git": {"available": False, "path": None, "sha256": None},
        }):
            with self.assertRaises(ValueError):
                igniter.environment_deploy(self.root, {"components": ["node"], "location": "project-local"})
        self.assertFalse(self.state_path().exists())

    def test_rollback_clears_record_and_keeps_recovery(self):
        node = self.root / "node"
        node.write_bytes(b"fake node")
        os.chmod(node, 0o755)
        igniter.environment_deploy(self.root, {"components": ["node"], "location": "project-local", "paths": {"node": str(node)}})
        result = igniter.environment_rollback(self.root)
        self.assertTrue(result["ok"])
        self.assertEqual(result["rolled_back"], ["node"])
        self.assertFalse(self.state_path().exists())
        self.assertTrue((self.root / "project/runtime/state/recovery.md").is_file())
        self.assertTrue((self.root / "project/runtime/state/deploy.log").is_file())

    def test_rollback_without_deployment_fails_cleanly(self):
        result = igniter.environment_rollback(self.root)
        self.assertFalse(result["ok"])
        self.assertEqual(result["rolled_back"], [])

    def test_apply_state_injects_env_and_never_raises(self):
        node = self.root / "node"
        node.write_bytes(b"fake node")
        os.chmod(node, 0o755)
        igniter.environment_deploy(self.root, {"components": ["node"], "location": "project-local", "paths": {"node": str(node)}})
        env = {"PATH": "/usr/bin"}
        applied = igniter.apply_state(self.root, env)
        self.assertEqual(applied["GONGGONG_NODE"], str(node.resolve()))
        self.assertEqual(applied["PATH"].split(os.pathsep)[0], str(node.resolve().parent))
        # Missing state must not raise.
        empty_root = self.root / "empty"
        empty_root.mkdir()
        self.assertEqual(igniter.apply_state(empty_root, {"PATH": "/usr/bin"}), {"PATH": "/usr/bin"})

    def test_state_write_is_atomic_and_readable(self):
        node = self.root / "node"
        node.write_bytes(b"fake node")
        os.chmod(node, 0o755)
        igniter.environment_deploy(self.root, {"components": ["node"], "location": "project-local", "paths": {"node": str(node)}})
        self.assertFalse((self.root / "project/runtime/state/installed.json.tmp").exists())
        value = json.loads(self.state_path().read_text(encoding="utf-8"))
        self.assertEqual(value["schema_version"], 1)


if __name__ == "__main__":
    unittest.main()
