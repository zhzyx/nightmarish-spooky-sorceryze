import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from editor_source_manifest import artifact_manifest, source_snapshot, verify_source


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        (self.root / "source.cpp").write_text("source")
        (self.root / "design-docs").mkdir()
        (self.root / "design-docs/task.md").write_text("task")
        self.git("add", ".")
        self.git("commit", "-m", "fixture")

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args], stderr=subprocess.DEVNULL)

    def test_only_source_changes_affect_digest(self):
        first = source_snapshot(self.root)
        (self.root / "design-docs/task.md").write_text("changed requirement")
        self.assertEqual(first, source_snapshot(self.root))
        (self.root / "source.cpp").write_text("changed source")
        self.assertNotEqual(first["source_digest"], source_snapshot(self.root)["source_digest"])

    def test_deletions_are_explicit(self):
        (self.root / "source.cpp").unlink()
        self.assertEqual(source_snapshot(self.root)["source_inputs"]["source.cpp"], {"absent": True})

    def test_new_source_and_executable_mode_are_bound(self):
        path = self.root / "new.py"
        path.write_text("new source")
        path.chmod(0o755)
        if os.name == "nt":
            self.assertEqual(source_snapshot(self.root)["source_inputs"]["new.py"]["mode"], "100644")
            self.git("add", "--chmod=+x", "new.py")
        item = source_snapshot(self.root)["source_inputs"]["new.py"]
        self.assertEqual(item, {"mode": "100755", "sha256": hashlib.sha256(b"new source").hexdigest()})

    def test_manifest_binds_exact_artifact_and_build_options(self):
        artifact = self.root / "bin/editor"
        artifact.parent.mkdir()
        artifact.write_bytes(b"editor bytes")
        before = source_snapshot(self.root)
        path = artifact_manifest(self.root, artifact, {"issue": 390}, self.root, {"arch": "arm64"}, before)
        value = json.loads(Path(path).read_text())
        self.assertEqual(value["artifact_sha256"], hashlib.sha256(b"editor bytes").hexdigest())
        self.assertEqual(value["source_inputs"], before["source_inputs"])
        self.assertEqual(value["build_options"], {"arch": "arm64"})

    def test_raw_slot_binds_its_own_package_on_restart(self):
        artifact = self.root / "bin/godot.windows.editor.x86_64.self_update_a.exe"
        artifact.parent.mkdir()
        artifact.write_bytes(b"editor")
        package = artifact.with_name("tianshu-ui.self_update_a.json")
        package.write_bytes(b"accepted UI package")
        artifact.with_name("tianshu-ui.json").write_bytes(b"other distribution")
        path = artifact_manifest(self.root, artifact, {"issue": 689}, self.root, {}, source_snapshot(self.root))
        expected = hashlib.sha256(package.read_bytes()).hexdigest()
        self.assertEqual(json.loads(Path(path).read_text())["tianshu_ui_sha256"], expected)
        self.assertTrue(verify_source(self.root, path)["ok"])
        package.write_bytes(b"unexpected replacement")
        with self.assertRaisesRegex(ValueError, "candidate_tianshu_ui_changed"):
            verify_source(self.root, path)

    def test_source_change_during_build_never_publishes_manifest(self):
        artifact = self.root / "bin/editor"
        artifact.parent.mkdir()
        artifact.write_bytes(b"editor bytes")
        before = source_snapshot(self.root)
        (self.root / "source.cpp").write_text("raced build source")
        with self.assertRaisesRegex(ValueError, "candidate_source_changed_during_build"):
            artifact_manifest(self.root, artifact, {}, self.root, {}, before)
        self.assertFalse(Path(str(artifact) + ".candidate.json").exists())

    def test_committing_same_source_keeps_restart_proof_valid(self):
        artifact = self.root / "bin/editor"
        artifact.parent.mkdir()
        artifact.write_bytes(b"editor bytes")
        (self.root / "source.cpp").write_text("built source")
        manifest = artifact_manifest(self.root, artifact, {}, self.root, {}, source_snapshot(self.root))
        self.git("add", "source.cpp")
        self.git("commit", "-m", "built candidate")
        self.assertTrue(verify_source(self.root, manifest)["ok"])

    def test_restart_refuses_source_changes_after_build(self):
        artifact = self.root / "bin/editor"
        artifact.parent.mkdir()
        artifact.write_bytes(b"editor bytes")
        manifest = artifact_manifest(self.root, artifact, {}, self.root, {}, source_snapshot(self.root))
        (self.root / "source.cpp").write_text("unbuilt source")
        with self.assertRaisesRegex(ValueError, "candidate_source_changed_since_build"):
            verify_source(self.root, manifest)

    def test_committed_deletion_and_rename_keep_restart_proof(self):
        artifact = self.root / "bin/editor"
        artifact.parent.mkdir()
        artifact.write_bytes(b"editor bytes")
        (self.root / "source.cpp").rename(self.root / "renamed.cpp")
        manifest = artifact_manifest(self.root, artifact, {}, self.root, {}, source_snapshot(self.root))
        self.git("add", "-A")
        self.git("commit", "-m", "rename built input")
        self.assertTrue(verify_source(self.root, manifest)["ok"])
        (self.root / "source.cpp").write_text("returned source")
        with self.assertRaisesRegex(ValueError, "candidate_source_changed_since_build"):
            verify_source(self.root, manifest)


if __name__ == "__main__":
    unittest.main()
