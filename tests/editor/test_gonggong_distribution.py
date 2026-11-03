"""Single-framework package tamper and relocation tests; isolated fixtures only."""

import os
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRAMEWORK = Path(os.environ.get("GONGGONG_TEST_FRAMEWORK", ROOT / "framework")).resolve()
api = runpy.run_path(str(FRAMEWORK / "tools/package_integrity.py"))


class DistributionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "relocated"
        shutil.copytree(FRAMEWORK, self.root, ignore=shutil.ignore_patterns("__pycache__"))

    def test_relocated_package_needs_no_external_source(self):
        self.assertTrue(api["check"](self.root)["local_integrity"])
        r = subprocess.run(
            [sys.executable, str(self.root / "tools/verify_framework.py"), "--candidate"],
            cwd=self.root.parent,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_added_non_candidate_file_is_rejected(self):
        (self.root / "unexpected.txt").write_text("synthetic test")
        with self.assertRaisesRegex(ValueError, "drift"):
            api["check"](self.root)

    def test_changed_or_missing_file_is_rejected(self):
        p = self.root / "README.md"
        p.write_text("synthetic tamper")
        with self.assertRaisesRegex(ValueError, "drift"):
            api["check"](self.root)
        p.unlink()
        with self.assertRaisesRegex(ValueError, "drift"):
            api["check"](self.root)

    def test_extension_is_pinned_and_sync_is_absent(self):
        self.assertFalse((self.root / "sync").exists())
        p = self.root / "extensions/diting-files/diting_files.py"
        p.write_text("# synthetic tamper")
        with self.assertRaisesRegex(ValueError, "drift"):
            api["check"](self.root)


if __name__ == "__main__":
    unittest.main()
