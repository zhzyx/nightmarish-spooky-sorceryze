"""Isolation boundaries and optional real editor verification (ISOLATION_TEST_EDITOR)."""

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import editor_test_isolation as isolation


def digest_settings():
    # Read only filenames, sizes and hashes: never expose setting values or rewrite files.
    roots = [
        Path.home() / "Library/Application Support/Godot",
        Path.home() / ".config/godot",
        Path.home() / "AppData/Roaming/Godot",
    ]
    return {
        str(p): hashlib.sha256(p.read_bytes()).hexdigest()
        for root in roots
        if root.is_dir()
        for p in root.rglob("*")
        if p.is_file() and p.name.lower().startswith("editor_settings")
    }


class IsolationTests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, {"GONGGONG_WORKSPACE": ""})
        environment.start()
        self.addCleanup(environment.stop)
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.source = self.root / "editor"
        self.source.write_bytes(b"#!/bin/sh\nexit 0\n")
        self.source.chmod(0o755)

    def test_workspace_ancestor_rejected_before_copy_or_directory_creation(self):
        workspace = self.root / "workspace"
        private_parent = workspace / "data-collection/receipts"
        private_parent.mkdir(parents=True)
        marker = workspace / "gonggong-workspace.json"
        marker.write_text('{"fixture": true}')
        target = private_parent / "private-editor"
        with patch.object(isolation.subprocess, "run") as clone:
            with self.assertRaisesRegex(ValueError, "inherits a GongGong workspace"):
                isolation.copy_editor(self.source, target)
            clone.assert_not_called()
        self.assertFalse(target.exists())
        self.assertEqual(marker.read_text(), '{"fixture": true}')
        self.assertEqual(self.source.read_bytes(), b"#!/bin/sh\nexit 0\n")

    def test_inherited_workspace_environment_rejected_without_disclosure(self):
        target = self.root / "private-editor"
        with patch.dict(os.environ, {"GONGGONG_WORKSPACE": "PRIVATE_WORKSPACE_SENTINEL"}):
            with self.assertRaisesRegex(ValueError, "Inherited GONGGONG_WORKSPACE") as raised:
                isolation.copy_editor(self.source, target)
            self.assertNotIn("PRIVATE_WORKSPACE_SENTINEL", str(raised.exception))
        self.assertFalse(target.exists())

    def test_copy_is_private_and_restart_settings_persist(self):
        editor = isolation.copy_editor(self.source, self.root / "private")
        self.assertFalse(editor.samefile(self.source))
        self.assertEqual(editor.read_bytes(), self.source.read_bytes())
        self.assertTrue((editor.parent / "_sc_").is_file())
        (editor.parent / "editor_data/sentinel").write_text("restart")
        editor.write_text("changed")
        self.assertNotEqual(editor.read_bytes(), self.source.read_bytes())
        self.assertEqual((editor.parent / "editor_data/sentinel").read_text(), "restart")

    def test_existing_destination_and_symlinks_rejected(self):
        for target in [self.root, self.source]:
            with self.assertRaises(ValueError):
                isolation.copy_editor(self.source, target)
        link = self.root / "link"
        link.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError):
            isolation.copy_editor(self.source, link / "escape")
        self.assertFalse((self.root / "escape").exists())

    def test_missing_nonexecutable_and_bundle_rejected(self):
        with self.assertRaises(FileNotFoundError):
            isolation.copy_editor(self.root / "missing", self.root / "private")
        self.source.chmod(0o644)
        with self.assertRaises(ValueError):
            isolation.copy_editor(self.source, self.root / "private")
        bundle = self.root / "Godot.app/Contents/MacOS"
        bundle.mkdir(parents=True)
        executable = bundle / "Godot"
        executable.write_text("fixture")
        executable.chmod(0o755)
        with self.assertRaises(ValueError):
            isolation.copy_editor(executable, self.root / "private")
        self.assertFalse((self.root / "private").exists())

    def test_capacity_boundary_and_no_original_fallback(self):
        required = self.source.stat().st_size + isolation.RESERVE_BYTES
        usage = shutil.disk_usage(self.root)
        with patch.object(isolation.shutil, "disk_usage", return_value=usage._replace(free=required - 1)):
            with self.assertRaisesRegex(OSError, str(required)):
                isolation.copy_editor(self.source, self.root / "private")
        self.assertFalse((self.root / "private").exists())
        with patch.object(isolation.shutil, "disk_usage", return_value=usage._replace(free=required)):
            isolation.copy_editor(self.source, self.root / "boundary")
        with (
            patch.object(isolation.sys, "platform", "darwin"),
            patch.object(isolation.subprocess, "run", return_value=subprocess.CompletedProcess([], 1)),
            patch.object(isolation.shutil, "copy2", side_effect=OSError("copy failed")),
        ):
            with self.assertRaisesRegex(OSError, "copy failed"):
                isolation.copy_editor(self.source, self.root / "failed")
        self.assertFalse((self.root / "failed").exists())
        self.assertFalse((self.root / "_sc_").exists())

    def test_independent_instances_and_clone_fallback(self):
        with (
            patch.object(isolation.sys, "platform", "darwin"),
            patch.object(isolation.subprocess, "run", return_value=subprocess.CompletedProcess([], 1)),
        ):
            first = isolation.copy_editor(self.source, self.root / "first")
            second = isolation.copy_editor(self.source, self.root / "second")
        (first.parent / "editor_data/settings").write_text("first")
        self.assertFalse((second.parent / "editor_data/settings").exists())

    @unittest.skipUnless(os.environ.get("ISOLATION_TEST_EDITOR"), "real editor path not supplied")
    def test_real_editor_uses_private_settings_across_restart(self):
        before = digest_settings()
        binary = Path(os.environ["ISOLATION_TEST_EDITOR"]).resolve()
        binary_before = hashlib.sha256(binary.read_bytes()).hexdigest()
        editor = isolation.copy_editor(binary, self.root / "private")
        project = self.root / "project"
        project.mkdir()
        (project / "project.godot").write_text('[application]\nconfig/name="Isolation verification"\n')
        (project / "probe.gd").write_text("""@tool
extends SceneTree
func _initialize():
    call_deferred("probe")
func probe():
    var paths = EditorInterface.get_editor_paths()
    assert(paths.is_self_contained())
    assert(paths.get_config_dir() == OS.get_executable_path().get_base_dir().path_join("editor_data"))
    var settings = EditorInterface.get_editor_settings()
    if OS.get_environment("ISOLATION_PHASE") == "seed":
        settings.set_setting("isolation/private_sentinel", "PRIVATE_ONLY")
    else:
        assert(settings.get_setting("isolation/private_sentinel") == "PRIVATE_ONLY")
    print("EDITOR_ISOLATION_REAL_OK")
    quit()
""")
        try:
            for phase in ["seed", "restart"]:
                result = subprocess.run(
                    [str(editor), "--headless", "--editor", "--path", str(project), "--script", "res://probe.gd"],
                    env=dict(os.environ, ISOLATION_PHASE=phase),
                    capture_output=True,
                    text=True,
                    timeout=90,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("EDITOR_ISOLATION_REAL_OK", result.stdout)
                self.assertNotIn("SCRIPT ERROR", result.stderr)
            files = list((editor.parent / "editor_data").glob("editor_settings*"))
            self.assertTrue(files)
            self.assertTrue(any("PRIVATE_ONLY" in p.read_text() for p in files))
        finally:
            after = digest_settings()
            self.assertEqual(before, after, "Real EditorSettings changed")
            self.assertEqual(binary_before, hashlib.sha256(binary.read_bytes()).hexdigest())
            print(
                json.dumps(
                    {
                        "real_editor_settings_before": before,
                        "real_editor_settings_after": after,
                        "unchanged": before == after,
                        "source_editor_sha256": binary_before,
                    },
                    sort_keys=True,
                )
            )


if __name__ == "__main__":
    unittest.main()
