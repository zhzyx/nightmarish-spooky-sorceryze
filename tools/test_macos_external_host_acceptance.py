"""Receipt/fuse gate regressions only: these do not claim macOS OS identity evidence."""

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from run_macos_external_host_acceptance import (
    SENTINEL,
    cleanup_owned_resources,
    finish_report,
    fuse_states,
    parse_powershell_version,
    same_product_upgrade,
    validate_reply,
)


class AcceptanceGateTests(unittest.TestCase):
    def test_actual_product_receipt_must_match_pinned_package(self):
        self.assertEqual(parse_powershell_version("PowerShell 7.6.9\n", "7.6.9"), "7.6.9")
        for output, expected in (
            ("OtherMicrosoftProduct 7.7.0", None),
            ("7.7.0", None),
            ("PowerShell 7.7.0\nunknown extra output", None),
            ("PowerShell 7.7.0", "7.6.9"),
        ):
            with self.subTest(output=output), self.assertRaises(RuntimeError):
                parse_powershell_version(output, expected)

    def test_product_upgrade_allows_new_identifier_but_requires_real_version_change(self):
        identity = ("host", "UBF8T346G9", "pwsh-original-uuid", "a" * 40)
        candidate = ("host", "UBF8T346G9", "pwsh-new-uuid", "b" * 40)
        original = {"product": "PowerShell", "version": "7.6.9"}
        upgraded = {"product": "PowerShell", "version": "7.7.0"}
        self.assertTrue(same_product_upgrade(identity, original, candidate, upgraded))
        for changed_identity, changed_product in (
            (candidate, original),
            (candidate, {"product": "OtherMicrosoftProduct", "version": "7.7.0"}),
            (("host", "OTHERTEAM00", candidate[2], candidate[3]), upgraded),
            ((*candidate[:3], identity[3]), upgraded),
        ):
            with self.subTest(identity=changed_identity, product=changed_product):
                self.assertFalse(same_product_upgrade(identity, original, changed_identity, changed_product))

    def test_policy_cleanup_failure_still_stops_real_child_and_saves_logs(self):
        class BrokenPolicy:
            def registry(self):
                raise OSError("policy restore failed")

        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            owned = folder / "owned"
            owned.mkdir()
            (owned / "editor.log").write_text("preserved diagnostic")
            (owned / "discovery.json").write_text("private bearer must not be copied")
            path = folder / "report.json"
            report = {"ok": True, "error": "original native failure"}
            child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
            try:
                cleanup_owned_resources(BrokenPolicy(), child, owned, path, report)
                self.assertIsNotNone(child.poll())
                self.assertEqual((folder / "report-logs/editor.log").read_text(), "preserved diagnostic")
                self.assertFalse((folder / "report-logs/discovery.json").exists())
                self.assertEqual(report["error"], "original native failure")
                self.assertEqual(
                    report["cleanup_errors"], [{"stage": "restore_policy", "error": "policy restore failed"}]
                )
                self.assertFalse(report["ok"])
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(finish_report(report, path), 1)
                self.assertFalse(json.loads(path.read_text())["ok"])
            finally:
                if child.poll() is None:
                    child.kill()
                    child.wait(timeout=10)

    def test_terminal_failure_overrides_stale_success_flag(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "report.json"
            for failure in (
                {"error": "late failure"},
                {"cleanup_errors": [{"stage": "stop_editor", "error": "timeout"}]},
            ):
                report = {"ok": True, **failure}
                with self.subTest(failure=failure), contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(finish_report(report, path), 1)
                self.assertIs(json.loads(path.read_text())["ok"], False)

    def test_actual_peer_and_host_pids_required(self):
        value = {
            "client_pid": 101,
            "parent_pid": 100,
            "reply": {"ok": True, "authenticated_desktop_peer": True, "peer_pid": 101, "trusted_desktop_pid": 100},
        }
        validate_reply(value, True)
        for field, wrong in (("peer_pid", 102), ("trusted_desktop_pid", 99), ("authenticated_desktop_peer", False)):
            changed = dict(value, reply=dict(value["reply"], **{field: wrong}))
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                validate_reply(changed, True)

    def test_transport_and_unrelated_errors_are_not_identity_denial(self):
        for value in (
            {"probe_error": "timeout"},
            {"reply": {"ok": False, "error": "instruction_handler_unavailable"}},
            {"reply": {"ok": False, "error": "ancestor_uid_mismatch"}},
            {"reply": {"ok": False, "error": "ancestor_identity_unavailable"}},
            {"reply": {"ok": True, "error": "unrecognized_ancestor_code"}},
        ):
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                validate_reply(value, False)
        validate_reply({"reply": {"ok": False, "error": "unrecognized_ancestor_code"}}, False)
        validate_reply({"reply": {"ok": False, "error": "trusted_desktop_missing"}}, False)

    def test_every_electron_slice_is_checked_without_changing_fuses(self):
        enabled = SENTINEL + bytes([1, 2, 0x31, 0x30])
        disabled = SENTINEL + bytes([1, 1, 0x30])
        self.assertEqual(fuse_states(enabled), [0x31])
        self.assertEqual(fuse_states(enabled + b"padding" + disabled), [0x31, 0x30])
        self.assertFalse(all(state == 0x31 for state in fuse_states(enabled + disabled)))

    def test_unknown_or_truncated_fuses_cannot_enable_app_launch(self):
        for data in (
            b"no fuse",
            SENTINEL,
            SENTINEL + bytes([1, 2, 0x31]),
            SENTINEL + bytes([2, 1, 0x31]),
            (SENTINEL + bytes([1, 1, 0x31])) * 3,
        ):
            with self.subTest(data=data), self.assertRaises(RuntimeError):
                fuse_states(data)


if __name__ == "__main__":
    unittest.main()
