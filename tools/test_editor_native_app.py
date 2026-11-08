"""Real codesign checks on private temporary Apps; never launch a user App."""

import hashlib
import json
import plistlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import editor_native_app as native
from editor_source_manifest import artifact_manifest, source_snapshot


@unittest.skipUnless(sys.platform == "darwin", "real macOS signing")
class NativeAppTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="private_sc_native_app_")
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name).resolve()
        self.home = self.folder / "private-user"
        user = type("FixtureUser", (), {"pw_dir": str(self.home)})()
        home_patch = patch("pwd.getpwuid", return_value=user)
        home_patch.start()
        self.addCleanup(home_patch.stop)
        self.root = self.folder / "source"
        self.root.mkdir()
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(self.root),
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "commit",
                "--allow-empty",
                "-qm",
                "fixture",
            ],
            check=True,
        )
        (self.root / "bin").mkdir()
        self.template = self.folder / "Template.app"
        resources = self.template / "Contents/Resources"
        resources.mkdir(parents=True)
        (resources / "fixture.txt").write_text("sealed resource")
        with (self.template / "Contents/Info.plist").open("wb") as stream:
            plistlib.dump(
                {
                    "CFBundleExecutable": "old-shell",
                    "CFBundleIdentifier": "local.gonggong.native-fixture",
                    "CFBundleName": "Native fixture",
                    "CFBundlePackageType": "APPL",
                    "CFBundleVersion": "1",
                    "LSEnvironment": {"GONGGONG_NODE": "/obsolete/path"},
                },
                stream,
            )
        self.project = self.folder / "project"
        self.project.mkdir()
        (self.project / "project.godot").write_text("config_version=5\n")
        self.binding = {"source_root": str(self.root), "binding_path": str(self.root / ".git/private-binding.json")}
        self.app = self.root / "bin/godot.self_update_a.app"

    def package(self):
        return native.package_app(self.root, "/usr/bin/true", self.binding, self.project, self.app, self.template)

    def manifest(self):
        path = artifact_manifest(
            self.root,
            self.app / native.EXECUTABLE_RELATIVE,
            self.binding,
            self.project,
            {"extra_suffix": "self_update_a"},
            source_snapshot(self.root),
            self.app,
        )
        return Path(path), json.loads(Path(path).read_text())

    def test_final_signature_precedes_external_manifest_and_digest(self):
        self.package()
        before = {str(p.relative_to(self.app)): p.read_bytes() for p in self.app.rglob("*") if p.is_file()}
        path, value = self.manifest()
        self.assertEqual(path, Path(str(self.app) + ".candidate.json"))
        self.assertEqual(value["artifact_sha256"], native.digest(self.app / native.EXECUTABLE_RELATIVE))
        self.assertEqual(value["native_app"]["origin_relative"], native.ORIGIN_RELATIVE)
        self.assertEqual(native.validate_native_app(self.root, value, path), self.app)
        self.assertEqual(
            before, {str(p.relative_to(self.app)): p.read_bytes() for p in self.app.rglob("*") if p.is_file()}
        )
        self.assertFalse(list(self.app.rglob("*.candidate.json")))
        with (self.app / "Contents/Info.plist").open("rb") as stream:
            info = plistlib.load(stream)
        self.assertEqual(info["CFBundleExecutable"], "Godot")
        self.assertNotIn("LSEnvironment", info)
        self.assertEqual(
            native.read_locator(self.app / native.EXECUTABLE_RELATIVE),
            native.origin_value(self.root, self.binding, self.project, self.app),
        )

    def test_local_store_is_pure_and_derived_from_canonical_utf8_source(self):
        source = self.folder / "源 root with space"
        source.mkdir()
        expected = (
            self.home
            / "Library/Application Support/gonggong/engine-artifacts"
            / hashlib.sha256(str(source.resolve()).encode("utf-8")).hexdigest()
        )
        self.assertEqual(native.native_output_dir(source), expected)
        self.assertFalse(self.home.exists())
        self.assertNotEqual(native.native_output_dir(self.root), expected)

    def test_local_store_preserves_existing_directories_and_uses_private_new_directories(self):
        existing = self.home / "Library/Application Support/gonggong"
        existing.mkdir(parents=True)
        existing.chmod(0o750)
        self.app = native.native_output_dir(self.root) / self.app.name
        self.package()
        path, value = self.manifest()
        self.assertEqual(native.validate_native_app(self.root, value, path), self.app)
        self.assertEqual(existing.stat().st_mode & 0o777, 0o750)
        self.assertEqual(self.app.parent.stat().st_mode & 0o777, 0o700)
        self.assertEqual(self.app.parent.parent.stat().st_mode & 0o777, 0o700)
        self.assertEqual(path.parent, self.app.parent)
        installed = self.folder / "Installed Local Store.app"
        native.copy_app(self.app, installed)
        native.verify_bundle(
            installed, native.read_locator(self.app / native.EXECUTABLE_RELATIVE), value["artifact_sha256"]
        )

    def test_local_store_rejects_other_source_and_arbitrary_output_parent(self):
        self.app = native.native_output_dir(self.root) / self.app.name
        self.package()
        other = self.folder / "other-source"
        other.mkdir()
        with self.assertRaisesRegex(ValueError, "app_path_invalid"):
            native.descriptor(other, self.app)
        with self.assertRaisesRegex(ValueError, "app_path_invalid"):
            native.descriptor(self.root, self.folder / self.app.name)

    def test_local_store_rejects_linked_ancestor_before_writing(self):
        self.home.mkdir()
        outside = self.folder / "outside"
        outside.mkdir()
        (self.home / "Library").symlink_to(outside, target_is_directory=True)
        self.app = native.native_output_dir(self.root) / self.app.name
        with self.assertRaisesRegex(ValueError, "app_path_invalid"):
            self.package()
        self.assertEqual(list(outside.iterdir()), [])

    def test_signing_cleans_only_staged_finder_metadata_and_preserves_source(self):
        resource = self.template / "Contents/Resources/fixture.txt"
        resources = resource.parent
        prohibited = {"com.apple.FinderInfo": b"TEST" + bytes(28), "com.apple.ResourceFork": b"fixture fork"}
        retained = {
            "com.apple.quarantine": b"0081;00000000;NativeFixture;",
            "org.gonggong.native-fixture": b"preserved metadata",
        }
        for path in (self.template, resources, resource):
            for name, value in {**prohibited, **retained}.items():
                if name == "com.apple.ResourceFork" and path.is_dir():
                    continue
                subprocess.run(["/usr/bin/xattr", "-s", "-w", "-x", name, value.hex(), str(path)], check=True)
        resource.chmod(0o640)

        def metadata(path):
            return {
                name: bytes.fromhex(
                    subprocess.check_output(["/usr/bin/xattr", "-s", "-p", "-x", name, str(path)]).decode()
                )
                for name in subprocess.check_output(["/usr/bin/xattr", "-s", str(path)]).decode().splitlines()
            }

        before = {path: metadata(path) for path in (self.template, resources, resource)}
        self.package()
        native.verify_signature(self.app)
        for source, attributes in before.items():
            self.assertEqual(metadata(source), attributes)
            copied = self.app / source.relative_to(self.template)
            copied_attributes = metadata(copied)
            for name in prohibited:
                self.assertNotIn(name, copied_attributes)
            for name, value in retained.items():
                if name == "com.apple.quarantine":
                    # ditto may normalize quarantine flags/agent metadata, but
                    # the downloaded-file restriction must remain in place.
                    self.assertTrue(int(copied_attributes[name].split(b";")[0], 16) & 1)
                else:
                    self.assertEqual(copied_attributes[name], value)
        self.assertEqual(resource.stat().st_mode & 0o777, 0o640)
        self.assertEqual((self.app / resource.relative_to(self.template)).stat().st_mode & 0o777, 0o640)

    def test_refuses_shell_as_native_executable(self):
        shell = self.folder / "shell"
        shell.write_text("#!/bin/sh\nexit 0\n")
        shell.chmod(0o755)
        with self.assertRaisesRegex(ValueError, "not_macho"):
            native.package_app(self.root, shell, self.binding, self.project, self.app, self.template)
        self.assertFalse(self.app.exists())

    def test_manifest_cannot_redirect_bundle_or_move_sidecar_inside_it(self):
        self.package()
        path, value = self.manifest()
        with self.assertRaisesRegex(ValueError, "manifest_path_invalid"):
            native.validate_native_app(self.root, value, self.app / "Contents/manifest.candidate.json")
        value["native_app"]["executable_relative"] = "Contents/MacOS/Other"
        with self.assertRaisesRegex(ValueError, "native_app_invalid"):
            native.validate_native_app(self.root, value, path)

    def test_locator_and_resource_tampering_fail_closed(self):
        self.package()
        path, value = self.manifest()
        (self.app / "Contents/Resources/fixture.txt").write_text("changed after signing")
        with self.assertRaisesRegex(ValueError, "signature_invalid"):
            native.validate_native_app(self.root, value, path)
        self.package()
        locator = self.app / native.ORIGIN_RELATIVE
        origin = json.loads(locator.read_text())
        origin["binding_path"] = str(self.folder / "other-binding.json")
        locator.write_text(json.dumps(origin))
        with self.assertRaisesRegex(ValueError, "origin_invalid"):
            native.validate_native_app(self.root, value, path)

    def test_failed_signature_does_not_replace_inactive_slot(self):
        self.package()
        original = native.digest(self.app / native.EXECUTABLE_RELATIVE)
        with patch.object(native, "verify_signature", side_effect=ValueError("fixture_signature_failed")):
            with self.assertRaisesRegex(ValueError, "fixture_signature_failed"):
                self.package()
        self.assertEqual(original, native.digest(self.app / native.EXECUTABLE_RELATIVE))
        native.verify_signature(self.app)

    def test_signing_failure_keeps_bounded_tool_reason_and_existing_slot(self):
        self.package()
        original = native.digest(self.app / native.EXECUTABLE_RELATIVE)
        stderr = b"fixture codesign reason: \xff" + b"x" * 3000
        real_run = subprocess.run

        def reject_signing(arguments, *args, **kwargs):
            if arguments[0] == "/usr/bin/codesign" and "--force" in arguments:
                return subprocess.CompletedProcess(arguments, 1, b"", stderr)
            return real_run(arguments, *args, **kwargs)

        with patch.object(native.subprocess, "run", side_effect=reject_signing):
            with self.assertRaises(ValueError) as caught:
                self.package()
        self.assertEqual(
            str(caught.exception),
            "candidate_native_signing_failed: " + stderr.decode("utf-8", errors="replace").strip()[:2000],
        )
        self.assertEqual(original, native.digest(self.app / native.EXECUTABLE_RELATIVE))
        native.verify_signature(self.app)

    def test_template_links_cannot_write_through_to_original_files(self):
        original = self.template / "Contents/Info.plist"
        outside = self.folder / "original-plist"
        original.rename(outside)
        expected = outside.read_bytes()
        original.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "template_invalid"):
            self.package()
        self.assertEqual(expected, outside.read_bytes())
        self.assertFalse(self.app.exists())

    def test_installed_godot_reads_slot_from_accepted_external_manifest(self):
        import editor_self_build as worker

        self.package()
        self.manifest()
        installed = self.folder / "Installed Native.app"
        native.copy_app(self.app, installed)
        self.assertEqual(
            worker.configuration_snapshot(installed / native.EXECUTABLE_RELATIVE), {"extra_suffix": "self_update_a"}
        )
        self.assertFalse(list(installed.rglob("*.build.json")))

    def test_complete_distribution_template_keeps_signature_when_copied(self):
        template = Path(__file__).resolve().parents[1] / "misc/dist/macos_tools.app"
        native.package_app(self.root, "/usr/bin/true", self.binding, self.project, self.app, template)
        installed = self.folder / "Installed Full Template.app"
        native.copy_app(self.app, installed)
        native.verify_signature(installed)
        self.assertEqual(
            native.digest(installed / native.EXECUTABLE_RELATIVE), native.digest(self.app / native.EXECUTABLE_RELATIVE)
        )


if __name__ == "__main__":
    unittest.main()
