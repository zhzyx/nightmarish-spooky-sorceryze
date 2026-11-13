"""Tests for the independent runtime build and clean-source export helpers."""

import json
import shutil
import sys
import unittest
from pathlib import Path

import BuildRuntime
import ExportCleanSource


class BuildRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.repo = Path(__file__).resolve().parents[2]
        self.temporary = self.repo / "build/engine_next/TestBuildRuntime"
        shutil.rmtree(self.temporary, ignore_errors=True)
        self.temporary.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.temporary, ignore_errors=True)

    def test_response_quoting_preserves_paths(self):
        text = BuildRuntime.BuildSupport.quoted_response(["a path/object.o", "plain"], windows=False)
        self.assertIn("a path/object.o", text)
        self.assertTrue(text.endswith("\n"))

    def test_runtime_inputs_stay_outside_godot(self):
        for source in [
            *BuildRuntime.LIBRARY_SOURCES,
            *BuildRuntime.TEST_SOURCES,
            *BuildRuntime.APP_SOURCES["next_server"],
            *BuildRuntime.APP_SOURCES["next_client"],
        ]:
            self.assertTrue(source.startswith("engine_next/"), source)
            self.assertFalse((self.repo / source).is_symlink(), source)

    def test_clean_export_contains_only_declared_inputs(self):
        output = self.temporary / "CleanSource"
        result = ExportCleanSource.export_clean_source(self.repo, output)
        self.assertGreater(result["file_count"], 20)
        self.assertTrue((output / "engine_next/Runtime/RuntimeHost.cpp").is_file())
        self.assertTrue((output / "engine_next/Tools/BuildGameplay.py").is_file())
        self.assertFalse((output / "core").exists())
        self.assertFalse((output / "modules").exists())
        self.assertFalse((output / "SConstruct").exists())
        manifest = json.loads(result["manifest"].read_text(encoding="utf-8"))
        self.assertEqual(manifest["file_count"], result["file_count"])
        self.assertEqual(manifest["godot_roots_present"], [])
        self.assertTrue(all(item["path"].startswith(("engine_next/", "tools/")) for item in manifest["files"]))

    def test_clean_export_refuses_nonempty_output(self):
        output = self.temporary / "Occupied"
        output.mkdir()
        (output / "keep.txt").write_text("keep", encoding="utf-8")
        with self.assertRaises(ValueError):
            ExportCleanSource.export_clean_source(self.repo, output)


if __name__ == "__main__":
    unittest.main()
