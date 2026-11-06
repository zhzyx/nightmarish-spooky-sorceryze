import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

@unittest.skipUnless(importlib.util.find_spec('PIL'),'image preparation requires Pillow')
class PreparationTests(unittest.TestCase):
    def run_prepare(self,source,output):
        return subprocess.run([sys.executable,str(Path(__file__).with_name('garment_prepare.py')),str(source),str(output),'--mode','blue'],capture_output=True)

    def test_source_alias_and_existing_sidecars_unchanged(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); source=root/'source.mask.png'; output=root/'source.png'
            Image.new('RGB',(16,16),(20,70,150)).save(source)
            before=source.read_bytes()
            self.assertNotEqual(self.run_prepare(source,output).returncode,0)
            self.assertEqual(source.read_bytes(),before); self.assertFalse(output.exists())
            source=root/'input.png'; source.write_bytes(before)
            for suffix in ('.mask.png','.prepare.json'):
                output=root/('new'+suffix.replace('.','_')+'.png')
                sidecar=output.with_suffix(suffix); sidecar.write_bytes(b'preserve-existing')
                self.assertNotEqual(self.run_prepare(source,output).returncode,0)
                self.assertEqual(sidecar.read_bytes(),b'preserve-existing')
                self.assertEqual(source.read_bytes(),before); self.assertFalse(output.exists())

    def test_real_derivative_provenance_and_no_overwrite(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); source=root/'input.png'; output=root/'output.png'
            Image.new('RGB',(16,16),(20,70,150)).save(source)
            before=source.read_bytes(); result=self.run_prepare(source,output)
            self.assertEqual(result.returncode,0,result.stderr.decode())
            record=json.loads(output.with_suffix('.prepare.json').read_text())
            self.assertEqual(record['source_sha256'],hashlib.sha256(before).hexdigest())
            self.assertEqual(source.read_bytes(),before)
            snapshots={p:p.read_bytes() for p in root.iterdir()}
            self.assertNotEqual(self.run_prepare(source,output).returncode,0)
            for path,data in snapshots.items(): self.assertEqual(path.read_bytes(),data)

if __name__=='__main__': unittest.main()
