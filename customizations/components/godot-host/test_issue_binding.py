import importlib.util
import json
import types
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("intake_bridge", Path(__file__).with_name("bridge.py"))
assert spec is not None and spec.loader is not None
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


class BindingTests(unittest.TestCase):
    def test_missing_binding_never_launches(self):
        for value in (
            {},
            {"request_id": "req-6"},
            {"request_id": "req-6", "issue_number": True},
            {"request_id": "../escape", "issue_number": 6},
        ):
            with patch.object(bridge.subprocess, "run") as run:
                with self.assertRaises(ValueError):
                    bridge.issue_binding(Path("."), value, "test")
                run.assert_not_called()

    def test_rejection_and_success_use_real_intake_command(self):
        for code in (0, 1):
            with patch.object(
                bridge.subprocess,
                "run",
                return_value=types.SimpleNamespace(returncode=code, stdout=json.dumps({"number": 6})),
            ) as run:
                if code:
                    with self.assertRaises(ValueError):
                        bridge.issue_binding(Path("."), {"request_id": "req-6", "issue_number": 6}, "test")
                else:
                    self.assertEqual(
                        bridge.issue_binding(Path("."), {"request_id": "req-6", "issue_number": 6}, "test")["number"], 6
                    )
                self.assertIn("--intake-only", run.call_args.args[0])
