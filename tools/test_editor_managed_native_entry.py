"""Real signed disposable App transactions; no user configuration or network."""

import json
import os
import subprocess
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

import editor_candidate_activation as activation
import editor_engine_candidate as candidate
import editor_managed_native_entry as managed
import editor_native_app as native
import editor_self_build as build
import test_editor_engine_candidate as fixtures
from editor_source_manifest import artifact_manifest, source_snapshot


@unittest.skipUnless(sys.platform == "darwin", "real macOS signed App transaction")
class ManagedEntryTests(unittest.TestCase):
    setUp = fixtures.CandidateTests.setUp
    run_git = fixtures.CandidateTests.run_git
    prepare = fixtures.CandidateTests.prepare
    journal = fixtures.CandidateTests.journal
    private_native_home = fixtures.CandidateTests.private_native_home
    built_native_candidate = fixtures.CandidateTests.built_native_candidate

    def fixture(self):
        initial, binding, source, manifest = self.built_native_candidate(local_store=True)
        root = Path(binding["source_root"])
        head = self.run_git(root, "rev-parse", "HEAD")
        report = {
            "pr_state": "MERGED",
            "candidate": head,
            "signed_commit": "2" * 40,
            "tree": self.run_git(root, "rev-parse", "HEAD^{tree}"),
            "current_main": head,
            "repository": "example/test",
            "issue": 390,
            "request_id": "runtime-test",
            "delivered_paths_differ": [],
            "issue_receipt": {"state": "CLOSED", "reason": "COMPLETED", "labels": ["status:done"]},
        }
        return initial, binding, source, manifest, report

    def activate(self, manifest, report):
        return activation.activate(manifest, report, entry_type=managed.ENTRY_TYPE)

    def record_path(self, binding, initial):
        import hashlib

        return (
            Path(binding["common_dir"])
            / "gonggong-engine-launchers"
            / (hashlib.sha256(str(initial).encode()).hexdigest()[:24] + ".json")
        )

    def test_signed_copy_source_preserved_retained_and_reused(self):
        initial, binding, source, manifest, report = self.fixture()
        subprocess.run(["/usr/bin/xattr", "-w", "local.gonggong.fixture", "custom", str(source)], check=True)
        before = managed.fingerprint(source)
        result = self.activate(manifest, report)
        payload = Path(result["canonical_payload"])
        self.assertNotEqual(payload, source)
        self.assertNotEqual(payload.stat().st_ino, source.stat().st_ino)
        self.assertEqual(result["entry_type"], managed.ENTRY_TYPE)
        self.assertTrue(native.app_for_executable(initial).is_symlink())
        self.assertEqual(source, Path(result["source_bundle"]))
        self.assertEqual(before, managed.fingerprint(source))
        self.assertEqual(result["source_manifest_sha256"], native.digest(manifest))
        time.sleep(1)
        managed.registered_entry(initial, Path(binding["common_dir"]))
        native.verify_signature(native.app_for_executable(initial))
        native.verify_signature(payload)
        self.assertTrue(activation.activate(manifest, report)["reused"])
        self.assertEqual(before, managed.fingerprint(source))
        self.assertTrue(Path(result["backup"]).is_dir())

    def test_quarantine_copy_records_platform_difference_without_manual_change(self):
        _, _, source, manifest, report = self.fixture()
        subprocess.run(
            ["/usr/bin/xattr", "-w", "com.apple.quarantine", "0081;00000000;PrivateFixture;", str(source)], check=True
        )
        before = managed.fingerprint(source)
        result = self.activate(manifest, report)
        copied = managed.fingerprint(Path(result["canonical_payload"]))
        self.assertIn("com.apple.quarantine", copied["."]["attrs"])
        self.assertEqual(before, managed.fingerprint(source))
        self.assertEqual(result["quarantine_differences"], managed.copy_metadata(before, copied))

    def test_same_executable_new_acceptance_has_distinct_immutable_snapshot(self):
        _, _, _, manifest, report = self.fixture()
        first = self.activate(manifest, report)
        old = Path(first["canonical_payload"])
        before = managed.fingerprint(old)
        second = self.activate(manifest, dict(report, signed_commit="3" * 40))
        self.assertNotEqual(first["canonical_payload"], second["canonical_payload"])
        self.assertEqual(first["artifact_sha256"], second["artifact_sha256"])
        self.assertEqual(before, managed.fingerprint(old))
        self.assertEqual(os.readlink(second["backup"]), str(old))

    def test_manifest_or_payload_change_rejects_registered_entry(self):
        initial, binding, _, manifest, report = self.fixture()
        result = self.activate(manifest, report)
        original = manifest.read_bytes()
        value = json.loads(original)
        value["extra_install_metadata"] = True
        manifest.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, "changed"):
            managed.registered_entry(initial, Path(binding["common_dir"]))
        manifest.write_bytes(original)
        (Path(result["canonical_payload"]) / "Contents/Info.plist").write_text("changed")
        with self.assertRaises(ValueError):
            managed.registered_entry(initial, Path(binding["common_dir"]))

    def test_unregistered_relative_foreign_or_crossuser_link_rejected(self):
        initial, _, source, manifest, report = self.fixture()
        app = native.app_for_executable(initial)
        saved = app.with_name("Saved.app")
        app.rename(saved)
        for target in (str(source), os.path.relpath(source, app.parent), str(saved)):
            os.symlink(target, app, target_is_directory=True)
            with self.assertRaises(ValueError):
                self.activate(manifest, report)
            app.unlink()
        saved.rename(app)
        result = self.activate(manifest, report)
        with mock.patch.object(managed.os, "getuid", return_value=os.getuid() + 1):
            with self.assertRaisesRegex(ValueError, "invalid|changed"):
                managed.verify_link(app, Path(result["canonical_payload"]))

    def test_candidate_and_build_options_accept_only_registered_snapshot(self):
        initial, binding, _, manifest, report = self.fixture()
        result = self.activate(manifest, report)
        physical = Path(result["payload_executable"])
        for entry in (initial, physical):
            self.assertEqual(build.configuration_snapshot(entry), {"extra_suffix": "self_update_a"})
        for issue, request, entry in ((391, "next-physical", physical), (392, "next-logical", initial)):
            next_binding = candidate.prepare(self.root, issue, request, "next-chat", launch_executable=entry)
            self.assertEqual(next_binding["initial_launch_executable"], str(initial))
            self.assertEqual(self.journal(next_binding)[1]["initial_launch_inherited_from"], binding["binding_path"])
        self.record_path(binding, initial).unlink()
        Path(str(Path(result["canonical_payload"])) + ".build.json").write_text('{"untrusted":true}')
        with self.assertRaises(ValueError):
            build.configuration_snapshot(physical)
        with self.assertRaises(candidate.CandidateError):
            candidate.prepare(self.root, 393, "unknown-snapshot", "next-chat", launch_executable=physical)

    def test_new_candidate_update_keeps_original_payload_and_logical_entry(self):
        initial, _, _, manifest, report = self.fixture()
        first = self.activate(manifest, report)
        previous = Path(first["canonical_payload"])
        before = managed.fingerprint(previous)
        binding = candidate.prepare(
            self.root, 391, "next-release", "next-chat", launch_executable=Path(first["payload_executable"])
        )
        root = Path(binding["source_root"])
        source = native.native_output_dir(root) / "godot.self_update_a.app"
        native.package_app(root, "/usr/bin/true", binding, self.root, source, previous)
        next_manifest = Path(
            artifact_manifest(
                root,
                source / native.EXECUTABLE_RELATIVE,
                binding,
                self.root,
                {"extra_suffix": "self_update_a"},
                source_snapshot(root),
                source,
            )
        )
        path, private = self.journal(binding)
        private["artifact_manifest"] = str(next_manifest)
        path.write_text(json.dumps(private))
        report = dict(report, issue=391, request_id="next-release")
        second = activation.activate(next_manifest, report)
        self.assertNotEqual(second["canonical_payload"], str(previous))
        self.assertEqual(second["logical_entry"], str(initial))
        self.assertEqual(os.readlink(second["backup"]), str(previous))
        self.assertEqual(managed.fingerprint(previous), before)

    def test_postpublish_failure_restores_original_inode_and_keeps_snapshot(self):
        initial, _, _, manifest, report = self.fixture()
        app = native.app_for_executable(initial)
        before = app.stat().st_ino
        original = managed.verify_link

        def failing(path, *args):
            if path == app:
                raise managed.ManagedEntryError("private_postpublish_failure")
            return original(path, *args)

        with mock.patch.object(managed, "verify_link", side_effect=failing):
            with self.assertRaisesRegex(ValueError, "private_postpublish_failure"):
                self.activate(manifest, report)
        self.assertFalse(app.is_symlink())
        self.assertEqual(app.stat().st_ino, before)
        identity = managed.context(manifest, json.loads(manifest.read_text()), report)
        self.assertTrue(managed.snapshot_directory(identity).is_dir())
        self.assertEqual(self.activate(manifest, report)["state"], "activated")

    def test_race_before_old_move_restores_unknown_entry_without_deleting(self):
        initial, _, _, manifest, report = self.fixture()
        app = native.app_for_executable(initial)
        preserved = app.with_name("Externally moved original.app")
        original = managed.rename_exclusive

        def racing(source, destination):
            if source == app and not preserved.exists():
                app.rename(preserved)
                app.mkdir()
                (app / "unknown.txt").write_text("external entry")
            return original(source, destination)

        with mock.patch.object(managed, "rename_exclusive", side_effect=racing):
            with self.assertRaisesRegex(ValueError, "original_entry_changed"):
                self.activate(manifest, report)
        self.assertEqual((app / "unknown.txt").read_text(), "external entry")
        self.assertTrue(preserved.is_dir())

    def test_race_before_publish_does_not_overwrite_unknown_entry(self):
        initial, _, _, manifest, report = self.fixture()
        app = native.app_for_executable(initial)
        original = managed.rename_exclusive

        def racing(source, destination):
            if destination == app and source.is_symlink():
                app.mkdir()
                (app / "unknown.txt").write_text("external entry")
            return original(source, destination)

        with mock.patch.object(managed, "rename_exclusive", side_effect=racing):
            with self.assertRaises(OSError):
                self.activate(manifest, report)
        self.assertEqual((app / "unknown.txt").read_text(), "external entry")
        self.assertTrue(list(app.parent.glob(app.stem + "-previous-*.app")))

    def test_interrupted_publication_recovers_only_same_context(self):
        initial, binding, _, manifest, report = self.fixture()
        result = self.activate(manifest, report)
        journal = self.record_path(binding, initial)
        result = json.loads(journal.read_text())
        result["state"] = "old_saved"
        journal.write_text(json.dumps(result))
        self.assertTrue(self.activate(manifest, report)["reused"])
        result["state"] = "old_saved"
        journal.write_text(json.dumps(result))
        with self.assertRaisesRegex(ValueError, "recovery_context_changed"):
            self.activate(manifest, dict(report, signed_commit="3" * 40))


if __name__ == "__main__":
    unittest.main()
