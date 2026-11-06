import tempfile
import unittest
from pathlib import Path
from rigging_publish import publish

class RiggingPublicationTests(unittest.TestCase):
    def test_no_clobber_and_source_preservation(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)/'staged.tscn'
            source.write_bytes(b'[gd_scene format=3]\n[node name="Character" type="Node3D"]\n')
            original = source.read_bytes()
            target = Path(directory)/'character.tscn'
            receipt = publish(source, target)
            self.assertEqual(target.read_bytes(), original)
            self.assertEqual(receipt['bytes'],len(original))
            with self.assertRaises(FileExistsError): publish(source,target)
            with self.assertRaises(FileExistsError): publish(source,source)
            self.assertEqual(source.read_bytes(),original)

    def test_invalid_encoding_is_not_published(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)/'source'
            source.write_bytes(b'not a scene')
            target = Path(directory)/'character.tscn'
            with self.assertRaises(ValueError): publish(source,target)
            self.assertFalse(target.exists())
