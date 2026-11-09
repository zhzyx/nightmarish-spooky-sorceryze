"""Packaging and rollback regressions. Native acceptance runs on each target OS."""

import argparse
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import package_maliang_editor as package


class PackageTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def editor(self):
        source = self.root / "native"
        source.mkdir()
        exe = source / "godot.windows.editor.x86_64.exe"
        image = bytearray(160)
        image[:2] = b"MZ"
        image[60:64] = (128).to_bytes(4, "little")
        image[128:134] = b"PE\0\0\x64\x86"
        exe.write_bytes(image)
        (source / "editor.dll").write_bytes(b"original companion")
        (source / "editor.pck").write_bytes(b"exported data")
        return exe

    def previous(self):
        output = self.root / "shipping"
        runtime = package.resource_path(output, "windows")
        runtime.mkdir(parents=True)
        package.write_json(runtime / "config.json", package.CONFIG)
        (output / "previous.txt").write_text("shipped")
        return output

    def test_editor_file_and_directory_preserve_companions(self):
        exe = self.editor()
        for count, source in enumerate((exe, exe.parent)):
            dest = self.root / f"with spaces {count}"
            result = package.copy_editor(source, dest, "windows")
            self.assertEqual(result.name, exe.name)
            self.assertEqual(result.read_bytes(), exe.read_bytes())
            self.assertEqual((dest / "editor.dll").read_bytes(), b"original companion")
            self.assertEqual((dest / "editor.pck").read_bytes(), b"exported data")

    def test_failed_checksum_leaves_previous_distribution_in_place(self):
        exe, output = self.editor(), self.previous()
        prepared = self.root / "prepared"
        (prepared / "ComfyUI-src").mkdir(parents=True)
        (prepared / "python").mkdir()
        (prepared / "python/python.exe").write_bytes(b"unexecuted fixture")
        checkpoint = self.root / "corrupt.safetensors"
        checkpoint.write_bytes(b"unexpected")
        args = argparse.Namespace(
            editor=exe, output=output, runtime=prepared, checkpoint=checkpoint, license=None, sign_identity=None
        )
        with (
            mock.patch.object(package, "platform_name", return_value="windows"),
            mock.patch.object(package, "verify_comfy"),
            mock.patch.object(package, "MODEL_SIZE", checkpoint.stat().st_size),
        ):
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                package.build(args)
        self.assertEqual((output / "previous.txt").read_text(), "shipped")
        self.assertEqual(list(self.root.glob(".maliang-build-*")), [])

    def test_failed_final_rename_rolls_back(self):
        output = self.previous()
        staged = self.root / "staged"
        staged.mkdir()
        original = Path.rename

        def fail_install(path, to):
            if path == staged:
                raise OSError("candidate rename failed")
            return original(path, to)

        with mock.patch.object(Path, "rename", fail_install):
            with self.assertRaisesRegex(OSError, "candidate rename failed"):
                package.publish(staged, output, "windows")
        self.assertEqual((output / "previous.txt").read_text(), "shipped")
        self.assertTrue(staged.is_dir())
        self.assertFalse((self.root / ".shipping.maliang-previous").exists())

    def test_verification_failure_after_publish_restores_previous(self):
        output = self.previous()
        staged = self.root / "staged"
        staged.mkdir()
        (staged / "candidate.txt").touch()

        def verify(path):
            self.assertTrue((path / "candidate.txt").exists())
            raise ValueError("invalid after moving")

        with self.assertRaisesRegex(ValueError, "invalid after moving"):
            package.publish(staged, output, "windows", verify)
        self.assertTrue((staged / "candidate.txt").exists())
        self.assertEqual((output / "previous.txt").read_text(), "shipped")

    def test_runtime_cannot_link_to_a_build_interpreter(self):
        runtime = self.root / "runtime"
        runtime.mkdir()
        other = self.root / "python"
        other.touch()
        try:
            (runtime / "python").symlink_to(other)
        except OSError:
            self.skipTest("This Windows user cannot create symlinks")
        with self.assertRaisesRegex(ValueError, "outside the distribution"):
            package.validate_links(runtime)

    def test_prepared_comfy_excludes_local_user_data_and_other_models(self):
        source = self.root / "prebuilt" / "ComfyUI-src"
        for directory in ("input", "output", "custom_nodes", "models", "user"):
            (source / directory).mkdir(parents=True)
            (source / directory / "private").touch()
        (source / "main.py").touch()
        destination = self.root / "copied"
        package.copy_prepared_comfy(source, destination)
        self.assertTrue((destination / "main.py").is_file())
        self.assertEqual(list(destination.rglob("private")), [])
        self.assertTrue((destination / "input").is_dir())

    @unittest.skipIf(sys.platform == "win32", "macOS script aliases")
    def test_removing_console_wrappers_keeps_no_dangling_aliases(self):
        binary = self.root / "bin"
        binary.mkdir()
        (binary / "python3.12").write_bytes(b"interpreter")
        (binary / "idle3.12").write_bytes(b"#!/build/host/python")
        (binary / "idle3").symlink_to("idle3.12")
        (binary / "python3").symlink_to("python3.12")
        package.strip_build_launchers(self.root, "macos")
        package.validate_links(self.root)
        self.assertFalse((binary / "idle3").is_symlink())
        self.assertEqual((binary / "python3").read_bytes(), b"interpreter")

    def test_wheels_and_tencent_notice_are_digest_pinned(self):
        self.assertEqual(package.digest(package.RECIPE / "HUNYUAN-NOTICE"), package.NOTICE_SHA)
        for target in package.PYTHONS:
            requirements = (package.RECIPE / (target + "-cp312.txt")).read_text().splitlines()
            dependencies = {}
            for line in requirements:
                if not line or line.startswith("#"):
                    continue
                name, source = line.split(" @ ")
                url, sha = source.split(" --hash=sha256:")
                self.assertRegex(sha, r"^[a-f0-9]{64}$")
                self.assertRegex(
                    url, r"^https://(files\.pythonhosted\.org/packages/|download-r2\.pytorch\.org/whl/cu128/)"
                )
                self.assertTrue(url.endswith(".whl"))
                self.assertNotIn(name, dependencies)
                dependencies[name] = url
            self.assertIn("torch-2.9.1", dependencies["torch"])
            self.assertIn("torchvision-0.24.1", dependencies["torchvision"])
            self.assertIn("scikit-image", dependencies)
            self.assertIn("trimesh", dependencies)
            self.assertEqual("%2Bcu128" in dependencies["torch"], target == "windows")


if __name__ == "__main__":
    unittest.main()
