import json
from pathlib import Path
import tempfile
import unittest
from garment_generate import finalize_output, argument_parser

class GarmentPublicationTests(unittest.TestCase):
    def test_thin_garment_preset_and_explicit_diagnostic_override(self):
        parser=argument_parser()
        defaults=parser.parse_args(['--output','new.glb'])
        self.assertEqual((defaults.mesh_resolution,defaults.mesh_threshold,defaults.octree_resolution),(512,0.5,256))
        override=parser.parse_args(['--output','new.glb','--mesh-threshold','0.6','--octree-resolution','128'])
        self.assertEqual((override.mesh_threshold,override.octree_resolution),(0.6,128))
    def test_resume_receipt_after_atomic_source_publication(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'source.glb'; path.write_bytes(b'actual-completed-output')
            finalize_output(path,b'actual-completed-output',{'run_id':'existing-run'},resume=True)
            self.assertEqual(json.loads(path.with_suffix('.receipt.json').read_text())['run_id'],'existing-run')
            self.assertEqual(path.read_bytes(),b'actual-completed-output')

    def test_conflicting_resume_never_changes_existing_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'source.glb'; path.write_bytes(b'preserve-existing')
            with self.assertRaises(FileExistsError): finalize_output(path,b'different-result',{},resume=True)
            self.assertEqual(path.read_bytes(),b'preserve-existing')
            self.assertFalse(path.with_suffix('.receipt.json').exists())

if __name__=='__main__': unittest.main()
