"""Tests for the independent runtime build and clean-source export helpers."""

import json
import shutil
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import BuildRuntime
import ExportCleanSource
import PackageRuntime


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

    def test_package_contains_only_declared_runtime_files(self):
        targets = []
        for name in ("next_server", "next_client"):
            binary = self.temporary / name
            binary.write_bytes(name.encode("utf-8"))
            manifest = self.temporary / (name + "LinkManifest.json")
            manifest.write_text(json.dumps({"target": "next_runtime"}), encoding="utf-8")
            targets.append({
                "name": name,
                "artifact": {"path": binary.relative_to(self.repo).as_posix(), "sha256": PackageRuntime.digest(binary)},
                "manifest": manifest.relative_to(self.repo).as_posix(),
                "symbol_audit": {"forbidden": []},
                "dynamic_dependencies": [],
            })
        report = {
            "compiler": "clang",
            "platform": "test",
            "sanitize": False,
            "native_key": "fixture",
            "targets": targets,
        }
        (self.temporary / "RuntimeBuildReport.json").write_text(json.dumps(report), encoding="utf-8")
        result = PackageRuntime.create_package(self.repo, self.temporary)
        self.assertEqual(result["files"], ["ENet-LICENSE.txt", "RuntimePackage.json", "next_client", "next_server"])
        self.assertTrue(result["godot_free_package"])

    def test_package_rejects_stale_binary_digest(self):
        targets = []
        for name in ("next_server", "next_client"):
            binary = self.temporary / name
            binary.write_bytes(name.encode("utf-8"))
            manifest = self.temporary / (name + "LinkManifest.json")
            manifest.write_text(json.dumps({"target": "next_runtime"}), encoding="utf-8")
            targets.append({
                "name": name,
                "artifact": {"path": binary.relative_to(self.repo).as_posix(), "sha256": PackageRuntime.digest(binary)},
                "manifest": manifest.relative_to(self.repo).as_posix(),
                "symbol_audit": {"forbidden": []},
                "dynamic_dependencies": [],
            })
        (self.temporary / "RuntimeBuildReport.json").write_text(
            json.dumps({
                "compiler": "clang",
                "platform": "test",
                "sanitize": False,
                "native_key": "fixture",
                "targets": targets,
            }),
            encoding="utf-8",
        )
        (self.temporary / "next_client").write_bytes(b"stale")
        with self.assertRaises(ValueError):
            PackageRuntime.create_package(self.repo, self.temporary)

    def test_enet_clang_uses_posix_address_conversion(self):
        args = SimpleNamespace(
            compiler="clang",
            clang="clang",
            sanitize=False,
            repo=self.repo,
            tool_environment={},
        )
        commands = []
        includes = {}
        with (
            mock.patch.object(BuildRuntime.BuildSupport, "run", return_value=b""),
            mock.patch.object(BuildRuntime.BuildSupport, "parse_depfile", return_value=[]),
        ):
            BuildRuntime.compile_c_source(
                args,
                "engine_next/thirdparty/enet/unix.c",
                self.temporary / "unix.o",
                self.temporary / "unix.d",
                includes,
                commands,
            )
        self.assertEqual(len(commands), 1)
        self.assertIn("-DHAS_INET_PTON=1", commands[0])
        self.assertIn("-DHAS_INET_NTOP=1", commands[0])


if __name__ == "__main__":
    unittest.main()
