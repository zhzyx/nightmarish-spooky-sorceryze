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
        self.root = Path(self.temp.name).resolve()
        (self.root / "project/runtime").mkdir(parents=True)

    def state_path(self):
        return self.root / "project/runtime/state/installed.json"

    def test_check_reports_missing_and_locations(self):
        with patch.object(
            igniter,
            "component_status",
            return_value={
                "python": {"available": True, "path": "/usr/bin/python3", "sha256": None},
                "node": {"available": False, "path": None, "sha256": None},
                "git": {"available": False, "path": None, "sha256": None},
            },
        ):
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

    def test_deploy_refuses_duplicate_or_malformed_components_before_writing(self):
        for components in (["python", "python"], [None], [["node"]]):
            with self.subTest(components=components), self.assertRaises(ValueError):
                igniter.environment_deploy(self.root, {"components": components})
            self.assertFalse(self.state_path().exists())

    def test_deploy_refuses_missing_path_without_auto_install(self):
        with patch.object(
            igniter,
            "component_status",
            return_value={
                "python": {"available": True, "path": "/usr/bin/python3", "sha256": None},
                "node": {"available": False, "path": None, "sha256": None},
                "git": {"available": False, "path": None, "sha256": None},
            },
        ):
            with self.assertRaises(ValueError):
                igniter.environment_deploy(self.root, {"components": ["node"], "location": "project-local"})
        self.assertFalse(self.state_path().exists())

    def test_rollback_clears_record_and_keeps_recovery(self):
        node = self.root / "node"
        node.write_bytes(b"fake node")
        os.chmod(node, 0o755)
        igniter.environment_deploy(
            self.root, {"components": ["node"], "location": "project-local", "paths": {"node": str(node)}}
        )
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
        igniter.environment_deploy(
            self.root, {"components": ["node"], "location": "project-local", "paths": {"node": str(node)}}
        )
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
        igniter.environment_deploy(
            self.root, {"components": ["node"], "location": "project-local", "paths": {"node": str(node)}}
        )
        self.assertFalse((self.root / "project/runtime/state/installed.json.tmp").exists())
        value = json.loads(self.state_path().read_text(encoding="utf-8"))
        self.assertEqual(value["schema_version"], 1)

    def deploy_pair(self):
        paths = {}
        for name in ("node", "git"):
            path = self.root / name / name
            path.parent.mkdir()
            path.write_bytes(name.encode())
            os.chmod(path, 0o755)
            paths[name] = str(path)
        igniter.environment_deploy(self.root, {"components": list(paths), "paths": paths})
        return paths

    def test_restart_restores_both_paths_from_disk_idempotently(self):
        paths = self.deploy_pair()
        # A separately loaded module models a fresh bridge process with no memory.
        restarted = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(restarted)
        with patch("os.getcwd", return_value=str(self.root.parent)):
            env = restarted.apply_state(self.root, {"PATH": "original"})
        self.assertEqual(env["GONGGONG_NODE"], paths["node"])
        self.assertEqual(env["GONGGONG_GIT"], paths["git"])
        self.assertEqual(env["PATH"].split(os.pathsep), [str(Path(p).parent) for p in paths.values()] + ["original"])
        self.assertEqual(restarted.apply_state(self.root, dict(env)), env)
        self.assertEqual(igniter.read_state(self.root)["path_base"], "workspace_root")

    def test_changed_component_rejects_entire_restore_and_keeps_evidence(self):
        paths = self.deploy_pair()
        Path(paths["node"]).write_bytes(b"changed")
        env = {"PATH": "original"}
        self.assertEqual(igniter.apply_state(self.root, dict(env)), env)
        recovery = igniter.recovery_status(self.root)
        self.assertFalse(recovery["ok"])
        self.assertIn("node", recovery["error"])
        self.assertTrue(self.state_path().exists())
        Path(paths["git"]).unlink()
        self.assertFalse(igniter.recovery_status(self.root)["ok"])

    def test_malformed_state_does_not_crash_or_inject_environment(self):
        self.state_path().parent.mkdir()
        for value in (
            "{",
            "[]",
            '{"schema_version":1,"env_changes":null}',
            '{"schema_version":1,"authorized":true,"components":[null]}',
        ):
            self.state_path().write_text(value, encoding="utf-8")
            with self.subTest(value=value):
                self.assertEqual(igniter.apply_state(self.root, {"PATH": "original"}), {"PATH": "original"})
                self.assertFalse(igniter.recovery_status(self.root)["ok"])

    def test_legacy_state_ignores_arbitrary_environment_keys(self):
        paths = self.deploy_pair()
        state = igniter.read_state(self.root)
        del state["path_base"]
        state["env_changes"] = {"UNRELATED_KEY": "injected", "PATH": "unverified"}
        igniter.write_state_atomic(self.root, state)
        env = igniter.apply_state(self.root, {})
        self.assertNotIn("UNRELATED_KEY", env)
        self.assertEqual(env["GONGGONG_GIT"], paths["git"])
        self.assertNotIn("unverified", env["PATH"])

    def test_rollback_prevents_restore_in_new_process(self):
        self.deploy_pair()
        igniter.environment_rollback(self.root)
        self.assertEqual(igniter.apply_state(self.root, {"PATH": "original"}), {"PATH": "original"})
        self.assertTrue(igniter.recovery_status(self.root)["ok"])
        self.assertFalse(igniter.recovery_status(self.root)["active"])

    def test_simulated_mac_and_windows_runtime_layouts(self):
        # Files model executable layout/permissions; no foreign binary is run.
        for suffix in ("", ".exe"):
            for location in ("project-local", "user-level"):
                with self.subTest(suffix=suffix, location=location):
                    workspace = self.root / (location + ("-windows" if suffix else "-mac"))
                    workspace.mkdir()
                    paths = {}
                    for component in ("node", "git"):
                        executable = workspace / (component + suffix)
                        executable.write_bytes(b"simulated executable")
                        executable.chmod(0o755)
                        paths[component] = str(executable)
                    igniter.environment_deploy(
                        workspace,
                        {
                            "components": list(paths),
                            "paths": paths,
                            "location": location,
                        },
                    )
                    restarted = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(restarted)
                    restored = restarted.apply_state(workspace, {"PATH": "original"})
                    self.assertEqual(restored["GONGGONG_NODE"], paths["node"])
                    self.assertEqual(restored["GONGGONG_GIT"], paths["git"])
                    self.assertEqual(restarted.read_state(workspace)["location"], location)
                    self.assertTrue(restarted.environment_rollback(workspace)["ok"])
                    self.assertEqual(restarted.apply_state(workspace, {"PATH": "original"}), {"PATH": "original"})


if __name__ == "__main__":
    unittest.main()
