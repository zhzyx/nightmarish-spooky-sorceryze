import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "gonggong_runtime_config", Path(__file__).with_name("gonggong_runtime_config.py")
)
assert spec is not None and spec.loader is not None
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


class RuntimeConfigReaderTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="gonggong-config-reader-")
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "config.json"
        self.environment = {"PATH": "", "GONGGONG_RUNTIME_CONFIG": str(self.path)}

    def write(self, values, version=1):
        self.path.write_text(json.dumps({"schema_version": version, "runtimes": values}))

    def test_reader_uses_four_independent_fields_without_bootstrap(self):
        self.write({"node": os.sys.executable})
        snapshot = runtime.read_effective(env=self.environment)
        self.assertEqual(set(snapshot["paths"]), {"node", "workflow_python", "build_python", "codex"})
        self.assertEqual(runtime.runtime_path(snapshot, "node"), os.sys.executable)
        self.assertEqual(runtime.runtime_path(snapshot, "build_python"), "")

    def test_external_override_does_not_change_durable_document(self):
        self.write({"node": "durable path"})
        before = self.path.read_bytes()
        snapshot = runtime.read_effective(env={**self.environment, "GONGGONG_NODE": os.sys.executable})
        self.assertEqual(snapshot["sources"]["node"], "environment")
        self.assertEqual(snapshot["configured"]["node"], "durable path")
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(runtime.read_effective(env=self.environment)["paths"]["node"], "durable path")

    def test_derived_export_does_not_hide_later_field_edit(self):
        self.write({"node": os.sys.executable})
        first = runtime.read_effective(env=self.environment)
        child = runtime.child_environment(first, self.environment)
        self.write({"node": "new configured path"})
        second = runtime.read_effective(env=child)
        self.assertEqual(second["paths"]["node"], "new configured path")
        self.assertEqual(second["sources"]["node"], "configuration")

    def test_invalid_external_override_stays_unavailable_in_child_reader(self):
        self.write({"node": os.sys.executable})
        environment = dict(self.environment, GONGGONG_NODE=str(self.path.parent / "missing-node"))
        snapshot = runtime.read_effective(env=environment)
        child = runtime.child_environment(snapshot, environment)
        child_snapshot = runtime.read_effective(env=child)
        self.assertEqual(child_snapshot["sources"]["node"], "environment")
        self.assertEqual(child_snapshot["paths"]["node"], environment["GONGGONG_NODE"])
        self.assertEqual(child_snapshot["executables"]["node"], "")

    def test_invalid_fields_are_unavailable_without_overwriting_drafts(self):
        values = {"node": "relative/draft", "codex": "https://not-an-executable"}
        self.write(values)
        snapshot = runtime.read_effective(env=self.environment)
        self.assertEqual(snapshot["configured"], values)
        self.assertEqual(runtime.runtime_path(snapshot, "node"), "")
        self.assertEqual(runtime.runtime_path(snapshot, "codex"), "")

    def test_json_numeric_version_matches_native_and_boolean_is_rejected(self):
        self.write({}, version=1.0)
        self.assertTrue(runtime.read_effective(env=self.environment)["ok"])
        for version in (True, 2, "1"):
            self.write({}, version=version)
            before = self.path.read_bytes()
            with self.assertRaises(ValueError):
                runtime.read_effective(env=self.environment)
            self.assertEqual(self.path.read_bytes(), before)

    def test_invalid_or_oversized_document_is_preserved(self):
        for value in (
            "{broken",
            '{"schema_version":1,"runtimes":{"credential":"not a runtime"}}',
            " " * (64 * 1024 + 1),
        ):
            self.path.write_text(value)
            with self.assertRaises(ValueError):
                runtime.read_effective(env=self.environment)
            self.assertEqual(self.path.read_text(), value)

    def test_relative_explicit_scope_is_rejected(self):
        with self.assertRaises(ValueError):
            runtime.read_effective("relative.json", env=self.environment)

    def test_bridge_respects_explicit_unavailable_node_over_legacy_deployment(self):
        source = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location(
            "runtime_bridge_fixture", source / "customizations/components/godot-host/bridge.py"
        )
        bridge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bridge)
        bundled = Path(self.temporary.name) / "project/runtime/node/node.exe"
        bundled.parent.mkdir(parents=True)
        bundled.touch()
        bundled.chmod(0o700)
        self.write({"node": ""})
        before = self.path.read_bytes()
        with (
            patch.dict(os.environ, self.environment, clear=True),
            patch.object(bridge, "find_gh", return_value=None),
            patch.object(
                bridge._igniter, "apply_state", side_effect=lambda root, env: dict(env, GONGGONG_NODE=str(bundled))
            ),
        ):
            environment = bridge.host_environment(Path(self.temporary.name))
        self.assertNotIn("GONGGONG_NODE", environment)
        self.assertEqual(environment["GONGGONG_RUNTIME_CONFIG"], str(self.path))
        self.assertEqual(self.path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
