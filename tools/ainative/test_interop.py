import struct
import tempfile
import unittest
from pathlib import Path
from interop_publish import publish


class InteropPublicationTests(unittest.TestCase):
    def test_glb_integrity_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            source, target = Path(directory)/'staged.glb', Path(directory)/'new.glb'
            payload = b'{"asset":{"version":"2.0"},"scenes":[{}],"scene":0}'
            payload += b' ' * (-len(payload) % 4)
            valid = b'glTF' + struct.pack('<II', 2, 20+len(payload)) + struct.pack('<I4s', len(payload), b'JSON') + payload
            source.write_bytes(valid)
            publish(source, target)
            self.assertEqual(target.read_bytes(), valid)
            with self.assertRaises(FileExistsError):
                publish(source, target)
            self.assertEqual(source.read_bytes(), valid)
            source.write_bytes(valid + b'truncated-length')
            with self.assertRaises(ValueError):
                publish(source, Path(directory)/'invalid.glb')

    def test_invalid_profile_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)/'staged.json'
            target = Path(directory)/'new.json'
            source.write_text('{"schema_version":1,"bones":[]}', encoding='utf-8')
            with self.assertRaises(ValueError):
                publish(source, target)
            self.assertFalse(target.exists())

    def test_header_only_glb_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)/'header.glb'
            source.write_bytes(b'glTF' + struct.pack('<II', 2, 12))
            with self.assertRaises(ValueError):
                publish(source, Path(directory)/'new.glb')
