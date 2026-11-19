import hashlib
import io
import json
import tempfile
import unittest
from email.message import Message
from pathlib import Path
from unittest.mock import patch

from attachments import capture, checked_url


class UploadCapture(unittest.TestCase):
    def test_binary_content_and_resume_without_network(self):
        payload = bytes(range(256))
        response = io.BytesIO(payload)
        response.headers = Message()
        response.headers["Content-Type"] = "application/octet-stream"
        response.headers["Content-Length"] = str(len(payload))
        with tempfile.TemporaryDirectory() as tmp, patch("attachments.build_opener") as opener:
            root = Path(tmp)
            manifest = root / "records.jsonl"
            manifest.write_text(
                json.dumps({
                    "kind": "attachment",
                    "source_id": "sample",
                    "content": {"url": "https://github.com/user-attachments/assets/test"},
                })
            )
            opener.return_value.open.return_value = response
            dest = root / "captures"
            first = capture(manifest, dest)
            sha = hashlib.sha256(payload).hexdigest()
            self.assertEqual((dest / sha).read_bytes(), payload)
            self.assertEqual(first, capture(manifest, dest))
            opener.return_value.open.assert_called_once()

    def test_foreign_redirect(self):
        with self.assertRaises(ValueError):
            checked_url("https://example.org/upload")
