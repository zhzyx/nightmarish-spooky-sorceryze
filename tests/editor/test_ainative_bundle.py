"""The compiled workbench must resolve its complete dependency closure off-project."""

import hashlib
import json
import re
import sys
import unittest
from pathlib import Path

from editor.ainative.builders import bundle_files

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


class AINativeBundleTests(unittest.TestCase):
    def test_shared_sources_are_closed_and_manifest_binds_installed_bytes(self):
        sources = [
            p for p in (ROOT / "samples/ainative-workbench/addons/ainative").glob("*.gd") if p.name != "plugin.gd"
        ]
        sources += [p for p in (ROOT / "tools/ainative").glob("*.py") if not p.name.startswith("test_")]
        files = bundle_files(sources)
        manifest = json.loads(files["manifest.json"])
        self.assertIn("tools/editor_host.py", files)
        self.assertIn("tools/portable_scene.py", files)
        self.assertNotIn("scripts/plugin.gd", files)
        for name, text in files.items():
            if not name.startswith("scripts/"):
                continue
            self.assertNotIn("res://addons/ainative/", text, name)
            self.assertEqual(
                hashlib.sha256(text.encode("utf-8")).hexdigest(), manifest["runtime_files"][Path(name).name]
            )
            for dependency in re.findall(r"preload\(['\"]([^'\"]+)['\"]\)|extends ['\"]([^'\"]+)['\"]", text):
                self.assertIn("scripts/" + next(item for item in dependency if item), files, name)
        self.assertIn("get_script().resource_path.get_base_dir()", files["scripts/hair_runtime.gd"])


if __name__ == "__main__":
    unittest.main()
