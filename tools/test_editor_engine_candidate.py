"""Disposable Git integration tests for the editor-owned candidate lifecycle."""

import json
import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import editor_engine_candidate as candidate
import editor_native_app as native
from editor_source_manifest import artifact_manifest, source_snapshot


class CandidateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="engine-candidate-test-")
        self.folder = Path(self.temporary.name).resolve()
        self.root = self.folder / "workspace"
        self.remote = self.folder / "origin.git"
        self.root.mkdir()
        self.run_git(self.folder, "init", "--bare", str(self.remote))
        self.run_git(self.root, "init", "-b", "main")
        self.run_git(self.root, "config", "user.name", "Candidate Test")
        self.run_git(self.root, "config", "user.email", "candidate-test@example.invalid")
        self.run_git(self.root, "remote", "add", "origin", "https://github.com/example/test.git")
        self.run_git(
            self.root, "config", "url." + str(self.remote) + ".insteadOf", "https://github.com/example/test.git"
        )
        (self.root / "work-items.json").write_text(json.dumps({"repository": "example/test", "tenant_id": "test"}))
        (self.root / "SConstruct").write_text("# isolated test source\n")
        (self.root / "source.txt").write_text("main\n")
        (self.root / "tools").mkdir()
        (self.root / "tools/editor_self_build.py").write_text("# isolated test worker\n")
        self.run_git(self.root, "add", ".")
        self.run_git(self.root, "commit", "-m", "fixture")
        self.run_git(self.root, "push", "origin", "main")
        self.base = self.run_git(self.root, "rev-parse", "HEAD")
        self.gate = mock.patch.object(candidate, "verify_work_order")
        self.verify = self.gate.start()
        self.addCleanup(self.gate.stop)
        self.addCleanup(self.temporary.cleanup)

    def run_git(self, root, *arguments):
        result = subprocess.run(["git", "-C", str(root), *arguments], capture_output=True, text=True, check=True)
        return result.stdout.strip()

    def prepare(self, owner="chat-123", validate_only=False):
        return candidate.prepare(self.root, 390, "runtime-test", owner, validate_only)

    def journal(self, result):
        path = Path(result["binding_path"])
        return path, json.loads(path.read_text())

    def test_creates_clean_main_candidate_without_touching_working_files(self):
        self.run_git(self.root, "checkout", "-b", "existing-task")
        (self.root / "source.txt").write_text("uncommitted caller work\n")
        result = self.prepare()
        target = Path(result["source_root"])
        self.assertEqual(result["state"], "created")
        self.assertEqual(result["base_sha"], self.base)
        self.assertEqual((target / "source.txt").read_text(), "main\n")
        self.assertEqual(self.run_git(target, "status", "--porcelain"), "")
        self.assertEqual((self.root / "source.txt").read_text(), "uncommitted caller work\n")
        self.assertEqual(self.run_git(self.root, "branch", "--show-current"), "existing-task")
        self.assertTrue(result["branch"].startswith("codex/engine-candidate/runtime-test-"))
        self.assertNotEqual(result["branch"], "main")
        self.verify.assert_called_once_with(self.root, 390, "runtime-test")

    def special_workspace_candidate(self, component):
        parent = self.folder / component
        parent.mkdir()
        workspace = parent / "workspace"
        self.run_git(self.root, "worktree", "add", "-b", "special-workspace", str(workspace), "main")
        workspace = workspace.resolve()
        result = candidate.prepare(workspace, 390, "special-runtime-test", "special-chat")
        target = Path(result["source_root"])
        self.assertIn(workspace, candidate.registered_worktrees(self.root))
        self.assertIn(target, candidate.registered_worktrees(self.root))
        self.assertIn(str(workspace), result["protected_roots"])
        self.assertIn(str(self.root), result["protected_roots"])
        self.assertNotIn(str(target), result["protected_roots"])
        self.assertEqual(
            candidate.prepare(workspace, 390, "special-runtime-test", "special-chat", validate_only=True)["state"],
            "validated",
        )

    def test_registered_unicode_and_space_worktree_uses_raw_paths(self):
        self.special_workspace_candidate("工作区 with space")

    @unittest.skipIf(os.name == "nt", "Windows filenames cannot contain newline characters")
    def test_registered_newline_worktree_is_one_raw_path(self):
        self.special_workspace_candidate("work\nspace")

    def test_stale_reverse_registration_does_not_adopt_unregistered_worktree(self):
        first = self.prepare()
        target = Path(first["source_root"])
        marker = (target / ".git").read_text().strip().removeprefix("gitdir: ")
        metadata = Path(marker)
        if not metadata.is_absolute():
            metadata = target / metadata
        reverse = metadata / "gitdir"
        original = reverse.read_bytes()
        try:
            reverse.write_text(str(self.folder / "unregistered-worktree/.git") + "\n")
            self.assertNotIn(target, candidate.registered_worktrees(self.root))
            with self.assertRaisesRegex(candidate.CandidateError, "candidate_worktree_unregistered"):
                self.prepare(validate_only=True)
        finally:
            reverse.write_bytes(original)
        self.assertEqual(self.prepare(validate_only=True)["state"], "validated")

    def test_fetches_current_main_instead_of_callers_old_head(self):
        (self.root / "source.txt").write_text("new remote main\n")
        self.run_git(self.root, "add", "source.txt")
        self.run_git(self.root, "commit", "-m", "advance main")
        current_main = self.run_git(self.root, "rev-parse", "HEAD")
        self.run_git(self.root, "push", "origin", "main")
        self.run_git(self.root, "checkout", "-b", "old-task", self.base)
        result = self.prepare()
        self.assertEqual(result["base_sha"], current_main)
        self.assertEqual((Path(result["source_root"]) / "source.txt").read_text(), "new remote main\n")
        self.assertEqual(self.run_git(self.root, "rev-parse", "HEAD"), self.base)

    def test_transfers_only_this_requirements_provenance_once(self):
        doc = self.root / "design-docs/runtime-test.md"
        doc.parent.mkdir()
        doc.write_text("current requirement")
        events = self.root / "gonggong-diting-data/events/test/runtime-test"
        events.mkdir(parents=True)
        event = {"request_id": "runtime-test", "tenant_id": "test", "event_id": "test-source"}
        (events / "source.json").write_text(json.dumps(event))
        (doc.parent / "unrelated.md").write_text("unrelated")
        result = self.prepare()
        target = Path(result["source_root"])
        self.assertEqual((target / doc.relative_to(self.root)).read_text(), "current requirement")
        self.assertEqual(json.loads((target / events.relative_to(self.root) / "source.json").read_text()), event)
        self.assertFalse((target / "design-docs/unrelated.md").exists())
        (target / doc.relative_to(self.root)).write_text("candidate refinement")
        doc.write_text("later original root change")
        self.prepare()
        self.assertEqual((target / doc.relative_to(self.root)).read_text(), "candidate refinement")
        self.assertIn(str(self.root), result["protected_roots"])
        self.assertNotIn(str(target), result["protected_roots"])

    def test_updates_clean_main_requirement_with_current_intake(self):
        doc = self.root / "design-docs/runtime-test.md"
        doc.parent.mkdir()
        doc.write_text("old requirement")
        self.run_git(self.root, "add", ".")
        self.run_git(self.root, "commit", "-m", "old requirement")
        self.run_git(self.root, "push", "origin", "main")
        doc.write_text("current authorized requirement")
        result = self.prepare()
        self.assertEqual(
            (Path(result["source_root"]) / doc.relative_to(self.root)).read_text(), "current authorized requirement"
        )

    def test_rejects_other_identity_in_requirement_event_folder(self):
        events = self.root / "gonggong-diting-data/events/test/runtime-test"
        events.mkdir(parents=True)
        (events / "source.json").write_text(json.dumps({"request_id": "other-request", "tenant_id": "test"}))
        with self.assertRaisesRegex(candidate.CandidateError, "candidate_provenance_identity_mismatch"):
            self.prepare()

    def migration_fixture(self):
        doc = self.root / "design-docs/runtime-test.md"
        doc.parent.mkdir()
        doc.write_text("original intake snapshot")
        events = self.root / "gonggong-diting-data/events/test/runtime-test"
        events.mkdir(parents=True)
        event = {"request_id": "runtime-test", "tenant_id": "test", "event_id": "initial-event"}
        (events / "source.json").write_text(json.dumps(event))
        return doc, events, event

    def interrupted_migration(self):
        original = candidate.atomic_migration_file
        copies = []

        def fail_after_first_copy(target, destination, content):
            original(target, destination, content)
            copies.append(destination)
            if len(copies) == 1:
                raise OSError("injected process failure after first atomic copy")

        with mock.patch.object(candidate, "atomic_migration_file", side_effect=fail_after_first_copy):
            with self.assertRaisesRegex(OSError, "injected process failure"):
                self.prepare()
        path = next((self.root / ".git/gonggong-engine-candidates").glob("*.json"))
        binding = json.loads(path.read_text())
        self.assertEqual(binding["state"], "reserved")
        self.assertIn("migration_plan", binding)
        self.assertIn(str(self.root), binding["protected_roots"])
        return path, binding, Path(binding["source_root"])

    def test_resumes_partial_migration_from_persisted_snapshot_after_source_changes(self):
        doc, events, event = self.migration_fixture()
        path, binding, target = self.interrupted_migration()
        self.assertTrue((target / doc.relative_to(self.root)).exists())
        self.assertFalse((target / events.relative_to(self.root) / "source.json").exists())
        doc.write_text("later unrelated source mutation")
        (events / "source.json").write_text(json.dumps(dict(event, event_id="later-event")))
        result = self.prepare()
        self.assertEqual(result["state"], "reused")
        self.assertEqual((target / doc.relative_to(self.root)).read_text(), "original intake snapshot")
        self.assertEqual(json.loads((target / events.relative_to(self.root) / "source.json").read_text()), event)
        recovered = json.loads(path.read_text())
        self.assertEqual(recovered["state"], "prepared")
        self.assertEqual(
            set(recovered["provenance"]),
            {doc.relative_to(self.root).as_posix(), (events.relative_to(self.root) / "source.json").as_posix()},
        )
        self.assertIn(str(self.root), result["protected_roots"])

    def test_partial_migration_keeps_exact_bom_and_crlf_bytes(self):
        doc, _, _ = self.migration_fixture()
        data = b"\xef\xbb\xbfintake snapshot\r\nsecond line\r\n"
        doc.write_bytes(data)
        _, _, target = self.interrupted_migration()
        self.prepare()
        self.assertEqual((target / doc.relative_to(self.root)).read_bytes(), data)

    def test_partial_migration_rejects_unknown_candidate_changes(self):
        self.migration_fixture()
        _, _, target = self.interrupted_migration()
        source = target / "source.txt"
        source.write_text("another worker's edits")
        with self.assertRaisesRegex(candidate.CandidateError, "candidate_initial_tree_dirty"):
            self.prepare()
        self.assertEqual(source.read_text(), "another worker's edits")
        self.assertFalse((target / "gonggong-diting-data/events/test/runtime-test/source.json").exists())

    def test_partial_migration_rejects_modified_planned_content(self):
        doc, _, _ = self.migration_fixture()
        _, _, target = self.interrupted_migration()
        destination = target / doc.relative_to(self.root)
        destination.write_text("candidate edit not in the persisted migration plan")
        with self.assertRaisesRegex(candidate.CandidateError, "candidate_initial_tree_dirty"):
            self.prepare()
        self.assertEqual(destination.read_text(), "candidate edit not in the persisted migration plan")

    def test_partial_migration_rejects_staging_even_for_planned_content(self):
        doc, _, _ = self.migration_fixture()
        _, _, target = self.interrupted_migration()
        self.run_git(target, "add", str(doc.relative_to(self.root)))
        with self.assertRaisesRegex(candidate.CandidateError, "candidate_initial_tree_dirty"):
            self.prepare()

    def test_partial_migration_rejects_unknown_ignored_content(self):
        self.migration_fixture()
        _, _, target = self.interrupted_migration()
        ignore = self.folder / "ignore-rules"
        ignore.write_text("ignored-output\n")
        self.run_git(target, "config", "core.excludesfile", str(ignore))
        (target / "ignored-output").write_text("unknown ignored output")
        with self.assertRaisesRegex(candidate.CandidateError, "candidate_initial_tree_dirty"):
            self.prepare()

    def test_recovers_crash_after_all_copies_before_prepared_journal(self):
        doc, events, event = self.migration_fixture()
        original = candidate.atomic_json

        def fail_before_prepared(path, value):
            if value.get("state") == "prepared":
                raise OSError("injected final journal failure")
            original(path, value)

        with mock.patch.object(candidate, "atomic_json", side_effect=fail_before_prepared):
            with self.assertRaisesRegex(OSError, "injected final journal failure"):
                self.prepare()
        path = next((self.root / ".git/gonggong-engine-candidates").glob("*.json"))
        binding = json.loads(path.read_text())
        self.assertEqual(binding["state"], "reserved")
        target = Path(binding["source_root"])
        self.assertTrue((target / events.relative_to(self.root) / "source.json").is_file())
        doc.write_text("source changed after migration completed")
        result = self.prepare()
        self.assertEqual(result["state"], "reused")
        self.assertEqual((target / doc.relative_to(self.root)).read_text(), "original intake snapshot")
        self.assertEqual(json.loads((target / events.relative_to(self.root) / "source.json").read_text()), event)

    def test_clean_reserved_without_plan_replays_migration_and_protection(self):
        doc, _, _ = self.migration_fixture()
        with mock.patch.object(candidate, "requirement_migration_plan", side_effect=OSError("injected before plan")):
            with self.assertRaisesRegex(OSError, "injected before plan"):
                self.prepare()
        path = next((self.root / ".git/gonggong-engine-candidates").glob("*.json"))
        binding = json.loads(path.read_text())
        self.assertNotIn("migration_plan", binding)
        result = self.prepare()
        self.assertEqual(
            (Path(result["source_root"]) / doc.relative_to(self.root)).read_text(), "original intake snapshot"
        )
        self.assertIn(str(self.root), result["protected_roots"])
        self.assertEqual(json.loads(path.read_text())["state"], "prepared")

    def test_reserved_without_plan_cannot_adopt_even_matching_untracked_files(self):
        doc, _, _ = self.migration_fixture()
        with mock.patch.object(candidate, "requirement_migration_plan", side_effect=OSError("injected before plan")):
            with self.assertRaises(OSError):
                self.prepare()
        path = next((self.root / ".git/gonggong-engine-candidates").glob("*.json"))
        target = Path(json.loads(path.read_text())["source_root"])
        destination = target / doc.relative_to(self.root)
        destination.parent.mkdir()
        destination.write_bytes(doc.read_bytes())
        with self.assertRaisesRegex(candidate.CandidateError, "candidate_initial_tree_dirty"):
            self.prepare()

    def test_prepared_reuse_never_replays_migration(self):
        doc, _, _ = self.migration_fixture()
        result = self.prepare()
        destination = Path(result["source_root"]) / doc.relative_to(self.root)
        destination.write_text("model refined this prepared candidate")
        with mock.patch.object(
            candidate, "migrate_requirement", side_effect=AssertionError("must not migrate prepared candidate")
        ):
            self.prepare()
            self.prepare(validate_only=True)
        self.assertEqual(destination.read_text(), "model refined this prepared candidate")

    def test_recovers_same_binding_preserving_edits(self):
        first = self.prepare()
        target = Path(first["source_root"])
        (target / "source.txt").write_text("candidate edits\n")
        (target / "new.txt").write_text("untracked edits\n")
        again = self.prepare()
        self.assertEqual(again["state"], "reused")
        self.assertEqual(first["source_root"], again["source_root"])
        self.assertEqual((target / "source.txt").read_text(), "candidate edits\n")
        self.assertTrue((target / "new.txt").exists())
        self.assertEqual(self.verify.call_count, 2)

    def test_validate_only_has_no_fetch_or_worktree_mutation(self):
        first = self.prepare()
        original = candidate.git
        with mock.patch.object(candidate, "git", wraps=original) as operations:
            result = self.prepare(validate_only=True)
        self.assertEqual(result["state"], "validated")
        self.assertFalse(
            any(
                call.args[1] in {"fetch", "worktree"} and (call.args[1] != "worktree" or call.args[2] != "list")
                for call in operations.call_args_list
            )
        )
        self.assertEqual(first["base_sha"], result["base_sha"])
        self.assertEqual(self.verify.call_count, 2)

    def test_resume_after_process_switch_using_candidate_as_workspace(self):
        first = self.prepare()
        result = candidate.prepare(Path(first["source_root"]), 390, "runtime-test", "chat-123", True)
        self.assertEqual(result["source_root"], first["source_root"])
        self.assertEqual(result["binding_path"], first["binding_path"])

    def test_initial_launch_executable_survives_process_switch(self):
        initial = self.folder / "Initial Editor"
        candidate_editor = self.folder / "Candidate Editor"
        initial.write_text("initial fixture executable")
        candidate_editor.write_text("candidate fixture executable")
        first = candidate.prepare(self.root, 390, "runtime-test", "chat-123", launch_executable=initial)
        result = candidate.prepare(Path(first["source_root"]), 390, "runtime-test", "chat-123", True, candidate_editor)
        self.assertEqual(result["initial_launch_executable"], str(initial))
        self.assertEqual(result["repository"], "example/test")
        _, journal = self.journal(result)
        self.assertEqual(journal["initial_launch_executable"], str(initial))

    def built_candidate(self, owner="original-chat", initial=None):
        initial = initial or self.folder / (owner + "-managed-editor")
        initial.write_text("managed application entry")
        result = candidate.prepare(self.root, 390, "runtime-test", owner, launch_executable=initial)
        target = Path(result["source_root"])
        artifact = target / "bin/godot.editor.fixture"
        artifact.parent.mkdir()
        artifact.write_bytes(b"verified fixture artifact")
        manifest = artifact_manifest(target, artifact, result, self.root, {}, source_snapshot(target))
        binding_path, binding = self.journal(result)
        binding["artifact_manifest"] = manifest
        binding_path.write_text(json.dumps(binding))
        return initial, result, artifact, Path(manifest)

    def test_new_issue_inherits_managed_entry_from_exact_running_artifact(self):
        initial, first, artifact, _ = self.built_candidate()
        result = candidate.prepare(self.root, 391, "next-request", "new-chat", launch_executable=artifact)
        self.assertEqual(result["initial_launch_executable"], str(initial))
        _, binding = self.journal(result)
        self.assertEqual(binding["initial_launch_inherited_from"], first["binding_path"])

    def private_native_home(self):
        user = type("FixtureUser", (), {"pw_dir": str(self.folder / "private-user")})()
        home_patch = mock.patch("pwd.getpwuid", return_value=user)
        home_patch.start()
        self.addCleanup(home_patch.stop)

    def built_native_candidate(self, local_store=False):
        self.private_native_home()
        initial_app = self.folder / "Original Native.app"
        initial = initial_app / native.EXECUTABLE_RELATIVE
        initial.parent.mkdir(parents=True)
        shutil.copyfile("/usr/bin/true", initial)
        initial.chmod(0o755)
        (initial_app / "Contents/Resources").mkdir()
        with (initial_app / "Contents/Info.plist").open("wb") as stream:
            plistlib.dump(
                {
                    "CFBundleExecutable": "Godot",
                    "CFBundleIdentifier": "local.gonggong.lineage",
                    "CFBundleName": "Private fixture",
                    "CFBundlePackageType": "APPL",
                    "CFBundleVersion": "1",
                },
                stream,
            )
        (self.root / "project.godot").write_text("config_version=5\n")
        result = candidate.prepare(self.root, 390, "runtime-test", "native-chat", launch_executable=initial)
        target = Path(result["source_root"])
        (target / "bin").mkdir()
        output = native.native_output_dir(target) if local_store else target / "bin"
        app = output / "godot.self_update_a.app"
        native.package_app(target, "/usr/bin/true", result, self.root, app, initial_app)
        manifest = artifact_manifest(
            target,
            app / native.EXECUTABLE_RELATIVE,
            result,
            self.root,
            {"extra_suffix": "self_update_a"},
            source_snapshot(target),
            app,
        )
        binding_path, binding = self.journal(result)
        binding["artifact_manifest"] = manifest
        binding_path.write_text(json.dumps(binding))
        return initial, result, app, Path(manifest)

    @unittest.skipUnless(sys.platform == "darwin", "real native App lineage")
    def test_native_candidate_nested_godot_inherits_original_entry(self):
        initial, first, app, _ = self.built_native_candidate()
        result = candidate.prepare(
            self.root, 391, "next-request", "new-chat", launch_executable=app / native.EXECUTABLE_RELATIVE
        )
        self.assertEqual(result["initial_launch_executable"], str(initial))
        self.assertEqual(self.journal(result)[1]["initial_launch_inherited_from"], first["binding_path"])

    @unittest.skipUnless(sys.platform == "darwin", "real local-store native lineage")
    def test_local_store_native_candidate_preserves_binding_and_original_entry(self):
        initial, first, app, manifest = self.built_native_candidate(local_store=True)
        self.assertEqual(manifest.parent, native.native_output_dir(first["source_root"]))
        result = candidate.prepare(
            self.root, 391, "next-request", "new-chat", launch_executable=app / native.EXECUTABLE_RELATIVE
        )
        self.assertEqual(result["initial_launch_executable"], str(initial))
        self.assertEqual(self.journal(result)[1]["initial_launch_inherited_from"], first["binding_path"])

    @unittest.skipUnless(sys.platform == "darwin", "real installed local-store native lineage")
    def test_installed_local_store_copy_inherits_accepted_external_manifest(self):
        initial, first, app, _ = self.built_native_candidate(local_store=True)
        installed = initial.parent.parent.parent
        shutil.rmtree(installed)
        native.copy_app(app, installed)
        result = candidate.prepare(self.root, 391, "next-request", "new-chat", launch_executable=initial)
        self.assertEqual(result["initial_launch_executable"], str(initial))
        self.assertEqual(self.journal(result)[1]["initial_launch_inherited_from"], first["binding_path"])

    @unittest.skipUnless(sys.platform == "darwin", "native store must not admit raw artifacts")
    def test_raw_artifact_cannot_inherit_from_native_store(self):
        self.private_native_home()
        _, first, artifact, manifest = self.built_candidate()
        output = native.prepare_native_output_dir(first["source_root"])
        moved_artifact = output / artifact.name
        moved_manifest = Path(str(moved_artifact) + ".candidate.json")
        shutil.move(artifact, moved_artifact)
        value = json.loads(manifest.read_text())
        value["executable"] = str(moved_artifact)
        moved_manifest.write_text(json.dumps(value))
        binding_path, binding = self.journal(first)
        binding["artifact_manifest"] = str(moved_manifest)
        binding_path.write_text(json.dumps(binding))
        with self.assertRaisesRegex(candidate.CandidateError, "candidate_inherited_artifact_invalid"):
            candidate.prepare(self.root, 391, "next-request", "new-chat", launch_executable=moved_artifact)

    @unittest.skipUnless(sys.platform == "darwin", "real installed native App lineage")
    def test_installed_exact_native_copy_inherits_external_manifest(self):
        initial, first, app, _ = self.built_native_candidate()
        shutil.rmtree(initial.parent.parent.parent)
        shutil.copytree(app, initial.parent.parent.parent)
        result = candidate.prepare(self.root, 391, "next-request", "new-chat", launch_executable=initial)
        self.assertEqual(result["initial_launch_executable"], str(initial))
        self.assertEqual(self.journal(result)[1]["initial_launch_inherited_from"], first["binding_path"])

    @unittest.skipUnless(sys.platform == "darwin", "real installed native App refusal")
    def test_installed_native_copy_requires_same_macho_and_sealed_locator(self):
        initial, _, app, _ = self.built_native_candidate()
        installed = initial.parent.parent.parent
        shutil.rmtree(installed)
        shutil.copytree(app, installed)
        origin = installed / native.ORIGIN_RELATIVE
        value = json.loads(origin.read_text())
        value["project_root"] = str(self.folder / "redirected-project")
        origin.write_text(json.dumps(value))
        subprocess.run(
            ["/usr/bin/codesign", "--force", "--deep", "--sign", "-", str(installed)], check=True, capture_output=True
        )
        with self.assertRaisesRegex(candidate.CandidateError, "candidate_inherited_artifact_invalid"):
            candidate.prepare(self.root, 391, "next-request", "new-chat", launch_executable=initial)

    def test_new_issue_inherits_managed_entry_from_exact_candidate_workspace(self):
        initial, first, _, _ = self.built_candidate()
        other_host = self.folder / "another-actual-host-editor"
        other_host.write_text("host executable")
        result = candidate.prepare(
            Path(first["source_root"]), 391, "next-request", "new-chat", launch_executable=other_host
        )
        self.assertEqual(result["initial_launch_executable"], str(initial))

    def test_inherited_entry_rejects_artifact_hash_mismatch(self):
        _, _, artifact, _ = self.built_candidate()
        artifact.write_bytes(b"artifact was changed")
        with self.assertRaisesRegex(candidate.CandidateError, "candidate_inherited_artifact_invalid"):
            candidate.prepare(self.root, 391, "next-request", "new-chat", launch_executable=artifact)

    def test_inherited_entry_does_not_guess_after_associated_manifest_corruption(self):
        _, _, artifact, manifest = self.built_candidate()
        manifest.write_text("invalid interrupted manifest")
        with self.assertRaisesRegex(candidate.CandidateError, "candidate_inherited_artifact_invalid"):
            candidate.prepare(self.root, 391, "next-request", "new-chat", launch_executable=artifact)

    def test_inherited_entry_rejects_linked_manifest_before_reading_it(self):
        _, _, artifact, manifest = self.built_candidate()
        external = self.folder / "external-manifest.json"
        manifest.rename(external)
        manifest.symlink_to(external)
        with self.assertRaisesRegex(candidate.CandidateError, "candidate_inherited_artifact_invalid"):
            candidate.prepare(self.root, 391, "next-request", "new-chat", launch_executable=artifact)

    def test_inherited_entry_rejects_manifest_binding_mismatch(self):
        _, _, artifact, manifest = self.built_candidate()
        value = json.loads(manifest.read_text())
        value["binding"]["owner"] = "not-the-recorded-owner"
        manifest.write_text(json.dumps(value))
        with self.assertRaisesRegex(candidate.CandidateError, "candidate_inherited_binding_invalid"):
            candidate.prepare(self.root, 391, "next-request", "new-chat", launch_executable=artifact)

    def test_inherited_entry_rejects_ambiguous_source_and_artifact_lineage(self):
        _, first, _, _ = self.built_candidate(owner="first-chat")
        _, _, second_artifact, _ = self.built_candidate(owner="second-chat")
        with self.assertRaisesRegex(candidate.CandidateError, "candidate_inherited_launch_ambiguous"):
            candidate.prepare(
                Path(first["source_root"]), 391, "next-request", "new-chat", launch_executable=second_artifact
            )

    def test_rejects_invalid_first_launch_executable(self):
        for launch in (Path("relative-editor"), self.folder / "missing-editor", self.folder):
            with self.assertRaisesRegex(candidate.CandidateError, "candidate_launch_executable_invalid"):
                candidate.prepare(self.root, 390, "runtime-test", "chat-123", launch_executable=launch)

    def test_other_owner_has_distinct_branch_and_worktree(self):
        first = self.prepare()
        second = self.prepare(owner="other-chat")
        self.assertNotEqual(first["branch"], second["branch"])
        self.assertNotEqual(first["source_root"], second["source_root"])

    def test_requires_current_issue_verification_on_reuse(self):
        first = self.prepare()
        self.verify.side_effect = candidate.CandidateError("candidate_issue_not_verified")
        with self.assertRaisesRegex(candidate.CandidateError, "candidate_issue_not_verified"):
            self.prepare(validate_only=True)
        self.assertTrue(Path(first["source_root"]).is_dir())

    def test_rejects_branch_changed_by_other_worker(self):
        first = self.prepare()
        target = Path(first["source_root"])
        self.run_git(target, "checkout", "-b", "other-worker")
        with self.assertRaisesRegex(candidate.CandidateError, "candidate_branch_mismatch"):
            self.prepare(validate_only=True)
        self.assertEqual(self.run_git(target, "branch", "--show-current"), "other-worker")

    def test_rejects_journal_owner_tampering(self):
        first = self.prepare()
        path, value = self.journal(first)
        value["owner"] = "other-chat"
        path.write_text(json.dumps(value))
        with self.assertRaisesRegex(candidate.CandidateError, "candidate_binding_mismatch"):
            self.prepare()

    def test_rejects_occupied_target_without_adoption(self):
        first = self.prepare()
        path, _ = self.journal(first)
        path.unlink()
        with self.assertRaisesRegex(candidate.CandidateError, "candidate_target_occupied"):
            self.prepare()
        self.assertEqual(self.run_git(Path(first["source_root"]), "rev-parse", "HEAD"), self.base)

    def test_rejects_unrelated_base(self):
        first = self.prepare()
        path, value = self.journal(first)
        tree = self.run_git(self.root, "rev-parse", "HEAD^{tree}")
        unrelated = self.run_git(self.root, "commit-tree", tree, "-m", "unrelated root")
        value["base_sha"] = unrelated
        path.write_text(json.dumps(value))
        with self.assertRaisesRegex(candidate.CandidateError, "candidate_base_changed"):
            self.prepare(validate_only=True)

    def test_rejects_missing_journal_for_validation(self):
        with self.assertRaisesRegex(candidate.CandidateError, "candidate_binding_missing"):
            self.prepare(validate_only=True)

    def test_rejects_repository_origin_change(self):
        self.prepare()
        self.run_git(self.root, "config", "remote.origin.url", "https://github.com/other/repo.git")
        with self.assertRaisesRegex(candidate.CandidateError, "candidate_origin_mismatch"):
            self.prepare(validate_only=True)

    def test_recovers_reserved_binding_after_verified_clean_creation(self):
        first = self.prepare()
        path, value = self.journal(first)
        value["state"] = "reserved"
        path.write_text(json.dumps(value))
        with self.assertRaisesRegex(candidate.CandidateError, "candidate_preparation_incomplete"):
            self.prepare(validate_only=True)
        self.assertEqual(self.prepare()["state"], "reused")
        self.assertEqual(json.loads(path.read_text())["state"], "prepared")

    def test_reserved_binding_does_not_adopt_dirty_source(self):
        first = self.prepare()
        path, value = self.journal(first)
        value["state"] = "reserved"
        path.write_text(json.dumps(value))
        (Path(first["source_root"]) / "source.txt").write_text("someone edited interrupted worktree")
        with self.assertRaisesRegex(candidate.CandidateError, "candidate_initial_tree_dirty"):
            self.prepare()


if __name__ == "__main__":
    unittest.main()
