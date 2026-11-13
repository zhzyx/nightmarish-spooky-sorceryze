import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from receipt_diagnostics import MAX_FILES, collect_receipt_diagnostics, file_metadata


class ReceiptDiagnosticsTests(unittest.TestCase):
    def test_failure_metadata_survives_cleanup_without_private_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            cache = root / "installation/editor_data/cache"
            cache.mkdir(parents=True)
            (cache / "gonggong-receipt-1-2.json").write_text('{"private-token": "RAW-USER-SECRET"')
            (cache / "gonggong-receipt-1-2.tmp").write_text('{"ok": true, "secret": "RAW-USER-SECRET"}')
            (cache / "gonggong-receipt-1-2.json.diagnostic.json").write_text(
                json.dumps({
                    "status": "parse_failed",
                    "exit_code": 2,
                    "read_attempts": 6,
                    "io_error": 0,
                    "parse_line": 1,
                    "temporary_present": True,
                    "stderr": "RAW-USER-SECRET",
                })
            )
            outbox = root / ".gonggong-outbox/chat"
            outbox.mkdir(parents=True)
            (outbox / "RAW-USER-SECRET.json").write_text(
                json.dumps({
                    "event_id": "RAW-USER-SECRET",
                    "request_id": "request",
                    "payload": "RAW-USER-SECRET",
                })
            )
            metadata = collect_receipt_diagnostics(root, root / "installation")
        encoded = json.dumps(metadata)
        self.assertNotIn("RAW-USER-SECRET", encoded)
        self.assertNotIn(folder, encoded)
        self.assertEqual(len(metadata["receipts"]), 3)
        self.assertEqual(len({item["identity_sha256"] for item in metadata["receipts"]}), 1)
        diagnostic = next(item for item in metadata["receipts"] if item["kind"] == "diagnostic")
        self.assertEqual(diagnostic["native_status"], "parse_failed")
        self.assertEqual(diagnostic["exit_code"], 2)
        self.assertEqual(diagnostic["read_attempts"], 6)
        self.assertTrue(diagnostic["temporary_present"])
        self.assertEqual(metadata["outbox"][0]["state"], "json_object")

    def test_file_and_byte_limits_and_unreadable_file_are_explicit(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            outbox = root / ".gonggong-outbox/chat"
            outbox.mkdir(parents=True)
            for index in range(MAX_FILES + 1):
                (outbox / f"{index}.json").write_text("{}")
            metadata = collect_receipt_diagnostics(root, root)
            self.assertEqual(len(metadata["outbox"]), MAX_FILES)
            self.assertTrue(metadata["outbox_truncated"])
            with patch("receipt_diagnostics.MAX_BYTES", 1):
                self.assertEqual(file_metadata(outbox / "0.json")["state"], "oversized")
            with patch.object(Path, "open", side_effect=PermissionError(13, "PRIVATE-PATH")):
                value = file_metadata(outbox / "0.json")
            self.assertEqual(value["state"], "read_failed")
            self.assertEqual(value["errno"], 13)
            self.assertNotIn("PRIVATE-PATH", json.dumps(value))

    def test_unpaired_surrogate_identities_preserve_bounded_diagnostics(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            outbox = root / ".gonggong-outbox/chat"
            outbox.mkdir(parents=True)
            identity = chr(0xD800)
            (outbox / "one.json").write_text(json.dumps({"event_id": identity, "request_id": "safe"}))
            metadata = collect_receipt_diagnostics(root, root)
            item = metadata["outbox"][0]
            self.assertEqual(item["state"], "json_object")
            self.assertEqual(len(item["identity_sha256"]["event_id"]), 64)
            self.assertNotIn(identity, json.dumps(metadata, ensure_ascii=False))

    def test_malformed_diagnostic_values_cannot_export_raw_data(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "file.json"
            path.write_text('{"status": "PRIVATE", "exit_code": "SECRET", "ok": "USER-TEXT"}')
            self.assertNotIn("PRIVATE", json.dumps(file_metadata(path)))
            self.assertNotIn("SECRET", json.dumps(file_metadata(path)))
            self.assertNotIn("USER-TEXT", json.dumps(file_metadata(path)))
            path.write_text('{"status": {"secret": "PRIVATE"}}')
            self.assertNotIn("PRIVATE", json.dumps(file_metadata(path)))


if __name__ == "__main__":
    unittest.main()
