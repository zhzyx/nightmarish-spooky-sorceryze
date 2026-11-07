import hashlib
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import interop_publish
import portable_scene


class PortableScenePublicationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.bundle = self.root / "editor deployment"
        self.scripts = self.bundle / "scripts"
        self.scripts.mkdir(parents=True)
        (self.bundle / "tools").mkdir()
        self.output = self.root / "project without addons"
        self.output.mkdir()
        self.sources = {
            "hair_runtime.gd": b'extends Node3D\nconst I = preload("interop.gd")\n',
            "interop.gd": b"extends RefCounted\n",
            # Dynamic dependencies must be copied even when not direct scene refs.
            "hair.gd": b'extends RefCounted\nconst I = preload("interop.gd")\n',
        }
        for name, data in self.sources.items():
            (self.scripts / name).write_bytes(data)
        self.manifest = {
            "schema_version": 1,
            "runtime_files": {name: hashlib.sha256(data).hexdigest() for name, data in self.sources.items()},
        }
        (self.bundle / "manifest.json").write_text(json.dumps(self.manifest), encoding="utf-8")
        self.location = patch.object(portable_scene, "__file__", str(self.bundle / "tools" / "portable_scene.py"))
        self.location.start()
        self.addCleanup(self.location.stop)
        self.stage = self.root / "staged.tscn"
        self.target = self.output / "character-v1.tscn"
        self.source_hash = "a" * 64
        self.payload = (
            "[gd_scene load_steps=2 format=3]\n"
            '[ext_resource type="Script" uid="uid://editorcache" path='
            + json.dumps(str(self.scripts / "hair_runtime.gd"))
            + ' id="1"]\n'
            '[node name="Hair" type="Node3D"]\n'
            'script = ExtResource("1")\n'
            'metadata/source_sha256 = "' + self.source_hash + '"\n'
        ).encode("utf-8")
        self.stage.write_bytes(self.payload)

    def publish(self):
        return interop_publish.publish(self.stage, self.target)

    def runtime(self):
        return next(self.output.glob("*.ainative-*"))

    def test_builtin_runtime_is_portable_and_staged_source_is_immutable(self):
        receipt = self.publish()
        data = self.target.read_bytes()
        directory = self.runtime()
        self.assertNotIn(str(self.bundle).encode(), data)
        self.assertNotIn(b"uid://editorcache", data)
        self.assertIn(self.source_hash.encode(), data)
        self.assertIn(('path="' + directory.name + '/hair_runtime.gd"').encode(), data)
        self.assertEqual(receipt["sha256"], hashlib.sha256(data).hexdigest())
        self.assertEqual(receipt["bytes"], len(data))
        self.assertEqual(self.stage.read_bytes(), self.payload)
        self.assertEqual({path.name for path in directory.iterdir()}, set(self.sources))
        for name, original in self.sources.items():
            self.assertEqual((directory / name).read_bytes(), original)
            self.assertEqual((self.scripts / name).read_bytes(), original)
        self.assertFalse((self.output / "addons").exists())

    def test_project_script_and_ordinary_scene_bytes_are_unchanged(self):
        data = self.payload.replace(
            str(self.scripts / "hair_runtime.gd").encode(), b"res://addons/ainative/hair_runtime.gd"
        )
        self.stage.write_bytes(data)
        # Irrelevant manifests cannot break ordinary project publication.
        (self.bundle / "manifest.json").write_text("invalid manifest", encoding="utf-8")
        self.publish()
        self.assertEqual(self.target.read_bytes(), data)
        self.assertEqual(list(self.output.iterdir()), [self.target])

    def test_source_checkout_without_manifest_keeps_original_bytes(self):
        (self.bundle / "manifest.json").unlink()
        self.publish()
        self.assertEqual(self.target.read_bytes(), self.payload)
        self.assertEqual(list(self.output.iterdir()), [self.target])

    def test_no_clobber_keeps_existing_scene_and_runtime(self):
        self.publish()
        old = self.target.read_bytes()
        runtime = self.runtime()
        (runtime / "sentinel").write_bytes(b"keep")
        with self.assertRaises(FileExistsError):
            self.publish()
        self.assertEqual(self.target.read_bytes(), old)
        self.assertEqual((runtime / "sentinel").read_bytes(), b"keep")
        self.assertEqual(self.stage.read_bytes(), self.payload)

    def test_preexisting_runtime_directory_is_never_changed(self):
        self.publish()
        self.target.unlink()
        runtime = self.runtime()
        (runtime / "sentinel").write_bytes(b"keep")
        with self.assertRaises(FileExistsError):
            self.publish()
        self.assertFalse(self.target.exists())
        self.assertEqual((runtime / "sentinel").read_bytes(), b"keep")

    def test_dangling_destination_link_is_rejected_before_writes(self):
        self.target.symlink_to(self.output / "missing")
        with self.assertRaises(FileExistsError):
            self.publish()
        self.assertTrue(self.target.is_symlink())
        self.assertEqual(list(self.output.iterdir()), [self.target])

    def test_corrupt_or_linked_runtime_is_not_published(self):
        dependency = self.scripts / "interop.gd"
        dependency.write_bytes(b"modified")
        with self.assertRaisesRegex(ValueError, "differs"):
            self.publish()
        self.assertEqual(list(self.output.iterdir()), [])
        dependency.unlink()
        outside = self.root / "outside.gd"
        outside.write_bytes(self.sources["interop.gd"])
        dependency.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "linked"):
            self.publish()
        self.assertEqual(list(self.output.iterdir()), [])

    def test_missing_manifest_record_cannot_leave_an_editor_path(self):
        del self.manifest["runtime_files"]["hair_runtime.gd"]
        (self.bundle / "manifest.json").write_text(json.dumps(self.manifest), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "unregistered"):
            self.publish()
        self.assertEqual(list(self.output.iterdir()), [])

    def test_failed_scene_publication_removes_only_new_runtime(self):
        untouched = self.output / "other-version"
        untouched.mkdir()
        (untouched / "sentinel").write_bytes(b"keep")
        with patch.object(interop_publish, "publish_new", side_effect=OSError("hardlinks unavailable")):
            with self.assertRaisesRegex(OSError, "hardlinks unavailable"):
                self.publish()
        self.assertEqual(list(self.output.iterdir()), [untouched])
        self.assertEqual((untouched / "sentinel").read_bytes(), b"keep")
        self.assertEqual(self.stage.read_bytes(), self.payload)

    def test_incomplete_runtime_write_is_cleaned_up(self):
        write = portable_scene._write_file
        calls = 0

        def fail_second(path, payload):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("storage full")
            write(path, payload)

        with patch.object(portable_scene, "_write_file", side_effect=fail_second):
            with self.assertRaisesRegex(OSError, "storage full"):
                self.publish()
        self.assertEqual(list(self.output.iterdir()), [])

    def test_only_script_paths_change_and_crlf_survives(self):
        texture = (
            b'[ext_resource type="Texture2D" path='
            + json.dumps(str(self.scripts / "hair_runtime.gd")).encode()
            + b' id="2"]\n'
        )
        self.stage.write_bytes((self.payload + texture).replace(b"\n", b"\r\n"))
        self.publish()
        result = self.target.read_bytes()
        self.assertIn(texture.replace(b"\n", b"\r\n"), result)
        self.assertEqual(len(re.findall(rb"(?<!\r)\n", result)), 0)

    def test_versions_with_long_common_prefix_get_distinct_runtime_directories(self):
        prefix = "x" * 70
        self.target = self.output / (prefix + "one.tscn")
        self.publish()
        self.target = self.output / (prefix + "two.tscn")
        self.publish()
        self.assertEqual(len(list(self.output.glob("*.ainative-*"))), 2)


if __name__ == "__main__":
    unittest.main()
