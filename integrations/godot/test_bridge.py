import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("bridge", Path(__file__).with_name("olympus_bridge.py"))
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "Olympus").mkdir()
        (self.root / "Olympus/framework-manifest.json").write_text(json.dumps({
            "version": "test", "status": "pending", "agents": [{"id": "fixture", "state": "pending"}]}))

    def test_status_never_enables_agents(self):
        result = bridge.execute(self.root, "status", "tenant")
        self.assertTrue(result["ok"])
        self.assertFalse(result["agent_execution_enabled"])
        self.assertFalse(result["data_available"])

    def test_rejection_survives_adapter(self):
        with patch.object(bridge, "run", return_value={"ok": False, "exit_code": 1, "stderr": "drift"}):
            result = bridge.execute(self.root, "check", "tenant")
        self.assertFalse(result["ok"])
        self.assertFalse(result["agent_execution_enabled"])

    def test_tenant_is_single_argument(self):
        tenant = "tenant with spaces; shell text"
        with patch.object(bridge, "run", return_value={"ok": True}) as run:
            bridge.execute(self.root, "analyze", tenant)
        self.assertEqual(run.call_args.args[0][-2:], ["--tenant", tenant])

    def test_unknown_action_rejected(self):
        with self.assertRaises(ValueError):
            bridge.execute(self.root, "activate", "tenant")

    def test_missing_executable_reported(self):
        self.assertFalse(bridge.run([str(self.root / "missing.exe")], self.root)["ok"])


if __name__ == "__main__":
    unittest.main()
