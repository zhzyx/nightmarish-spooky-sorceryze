"""Regression checks for visual-target build inputs and package integrity."""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import BuildVisualRuntime
import PackageVisualRuntime


class VisualBuildTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.repo = Path(self.temporary.name)
        self.build = self.repo / "build/engine_next/visual"
        self.build.mkdir(parents=True)
        (self.repo / "LICENSE.txt").write_text("test license\n", encoding="utf-8")

    def prepare_package(self):
        sources = []
        for name in ["next_visual_client.exe", *sorted(PackageVisualRuntime.SHADER_FILES)]:
            path = self.build / name
            path.write_bytes(name.encode())
            sources.append({
                "path": path.relative_to(self.repo).as_posix(),
                "sha256": PackageVisualRuntime.digest(path),
            })
        manifest = self.build / "next_visual_clientLinkManifest.json"
        manifest.write_text("{}", encoding="utf-8")
        report = {
            "targets": [
                {
                    "name": "next_visual_client",
                    "artifact": sources[0],
                    "manifest": manifest.relative_to(self.repo).as_posix(),
                    "manifest_sha256": PackageVisualRuntime.digest(manifest),
                    "symbol_audit": {"forbidden": []},
                    "contract": {"passed": True},
                    "dynamic_dependencies": ["KERNEL32.dll", "D3D12.dll", "dxgi.dll", "USER32.dll"],
                }
            ],
            "shaders": sources[1:],
            "native_key": "1234",
            "compiler": "msvc",
            "platform": "win32",
        }
        BuildVisualRuntime.write_json(self.build / "VisualBuildReport.json", report)
        return report

    def test_package_has_exact_binary_shader_and_license_set(self):
        self.prepare_package()
        package = PackageVisualRuntime.create_package(self.repo, self.build)
        self.assertEqual(
            set(package["files"]),
            {"next_visual_client.exe", "LICENSE.txt", "VisualPackage.json", *PackageVisualRuntime.SHADER_FILES},
        )
        manifest = json.loads(package["manifest"].read_text(encoding="utf-8"))
        self.assertEqual(manifest["godot_runtime_dependencies"], [])
        for entry in manifest["files"]:
            self.assertEqual(entry["sha256"], PackageVisualRuntime.digest(package["directory"] / entry["path"]))

    def test_stale_shader_refuses_package_and_preserves_previous(self):
        self.prepare_package()
        package = PackageVisualRuntime.create_package(self.repo, self.build)
        previous = package["manifest"].read_bytes()
        (self.build / "FixedMesh.ps.cso").write_bytes(b"changed")
        with self.assertRaises(ValueError):
            PackageVisualRuntime.create_package(self.repo, self.build)
        self.assertEqual(package["manifest"].read_bytes(), previous)

    def test_unowned_release_file_is_preserved(self):
        self.prepare_package()
        package = PackageVisualRuntime.create_package(self.repo, self.build)
        extra = package["directory"] / "keep.txt"
        extra.write_text("owned elsewhere", encoding="utf-8")
        with self.assertRaises(ValueError):
            PackageVisualRuntime.create_package(self.repo, self.build)
        self.assertTrue(extra.is_file())

    def test_modified_existing_package_is_preserved(self):
        self.prepare_package()
        package = PackageVisualRuntime.create_package(self.repo, self.build)
        changed = package["directory"] / "FixedMesh.ps.cso"
        changed.write_bytes(b"changed package shader")
        with self.assertRaises(ValueError):
            PackageVisualRuntime.create_package(self.repo, self.build)
        self.assertEqual(changed.read_bytes(), b"changed package shader")

    def test_failed_publication_restores_previous_package(self):
        self.prepare_package()
        package = PackageVisualRuntime.create_package(self.repo, self.build)
        previous = package["manifest"].read_bytes()
        real_replace = PackageVisualRuntime.replace_directory
        calls = []

        def replace(source, destination):
            calls.append((source, destination))
            if len(calls) == 2:
                raise OSError("publication failed")
            real_replace(source, destination)

        with mock.patch.object(PackageVisualRuntime, "replace_directory", side_effect=replace):
            with self.assertRaises(OSError):
                PackageVisualRuntime.create_package(self.repo, self.build)
        self.assertEqual(package["manifest"].read_bytes(), previous)
        self.assertEqual(len(calls), 3)

    def test_shader_set_cannot_be_incomplete(self):
        report = self.prepare_package()
        report["shaders"].pop()
        BuildVisualRuntime.write_json(self.build / "VisualBuildReport.json", report)
        with self.assertRaises(ValueError):
            PackageVisualRuntime.create_package(self.repo, self.build)

    def test_changed_link_manifest_cannot_be_packaged(self):
        self.prepare_package()
        (self.build / "next_visual_clientLinkManifest.json").write_text('{"changed":true}', encoding="utf-8")
        with self.assertRaises(ValueError):
            PackageVisualRuntime.create_package(self.repo, self.build)

    def test_explicit_dxc_missing_fails_without_fallback(self):
        with self.assertRaises(ValueError):
            BuildVisualRuntime.find_dxc({}, self.repo / "missing.exe")

    def test_msvc_include_audit_rejects_godot_root(self):
        args = SimpleNamespace(compiler="msvc", repo=self.repo)
        dependency = self.build / "source.json"
        dependency.write_text(
            json.dumps({
                "Data": {"Source": str(self.repo / "engine_next/a.cpp"), "Includes": [str(self.repo / "core/object.h")]}
            }),
            encoding="utf-8",
        )
        with self.assertRaises(ValueError):
            BuildVisualRuntime.parse_includes(args, b"", dependency)

    def test_msvc_dependency_json_is_independent_of_console_locale(self):
        args = SimpleNamespace(compiler="msvc", repo=self.repo)
        dependency = self.build / "source.json"
        source = str(self.repo / "engine_next/a.cpp")
        header = str(self.repo / "engine_next/include/a.h")
        dependency.write_text(json.dumps({"Data": {"Source": source, "Includes": [header]}}), encoding="utf-8")
        result = BuildVisualRuntime.parse_includes(args, "注意: 包含文件".encode("gbk"), dependency)
        self.assertEqual(result, sorted([source, header]))

    def test_missing_msvc_dependency_json_fails_closed(self):
        args = SimpleNamespace(compiler="msvc", repo=self.repo)
        with self.assertRaises(ValueError):
            BuildVisualRuntime.parse_includes(args, b"", self.build / "missing.json")

    def test_empty_msvc_dependency_json_fails_closed(self):
        args = SimpleNamespace(compiler="msvc", repo=self.repo)
        dependency = self.build / "source.json"
        dependency.write_text(json.dumps({"Data": {"Source": "a.cpp", "Includes": []}}), encoding="utf-8")
        with self.assertRaises(ValueError):
            BuildVisualRuntime.parse_includes(args, b"", dependency)

    def test_object_names_disambiguate_same_basename(self):
        self.assertNotEqual(
            BuildVisualRuntime.object_name("engine_next/a/Test.cpp", ".obj"),
            BuildVisualRuntime.object_name("engine_next/b/Test.cpp", ".obj"),
        )


if __name__ == "__main__":
    unittest.main()
