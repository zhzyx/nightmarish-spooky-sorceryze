"""Disposable Git and subprocess tests; no provider calls or user settings."""

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from pathlib import Path
from unittest import mock

import editor_engine_candidate as candidates
import editor_provenance_guard as guard


class ProvenanceGuardTests(unittest.TestCase):
    request = "active-test"

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="provenance-guard-test-")
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name).resolve()
        self.original = self.folder / "workspace"
        self.original.mkdir()
        self.remote = self.folder / "origin.git"
        self.git(self.folder, "init", "--bare", str(self.remote))
        self.git(self.original, "init", "-b", "main")
        self.git(self.original, "config", "user.name", "Provenance Test")
        self.git(self.original, "config", "user.email", "fixture@example.invalid")
        self.git(self.original, "remote", "add", "origin", "https://github.com/example/test.git")
        self.git(
            self.original, "config", "url." + str(self.remote) + ".insteadOf", "https://github.com/example/test.git"
        )
        (self.original / "work-items.json").write_text(
            json.dumps({"repository": "example/test", "tenant_id": "fixture"})
        )
        (self.original / "SConstruct").write_text("# fixture engine\n")
        (self.original / ".gitignore").write_text(".gonggong-outbox/\n")
        (self.original / "source.txt").write_text("original source\n")
        (self.original / "tools").mkdir()
        (self.original / "tools/editor_self_build.py").write_text("# fixture build worker\n")
        dataset = self.original / "gonggong-diting-data"
        dataset.mkdir()
        (dataset / "dataset.json").write_text(
            json.dumps({
                "schema_version": 1,
                "dataset_id": str(uuid.uuid4()),
                "name": "gonggong-diting-data",
                "origin_framework": "gonggong",
            })
        )
        (dataset / ".gitattributes").write_text("* text eol=lf\n")
        self.git(self.original, "add", ".")
        self.git(self.original, "commit", "-qm", "fixture baseline")
        self.git(self.original, "push", "-q", "origin", "main")
        doc = self.original / "design-docs" / (self.request + ".md")
        doc.parent.mkdir()
        doc.write_text("active authorized requirement\n")
        events = dataset / "events/fixture" / self.request
        events.mkdir(parents=True)
        event = guard.events_module().event(self.event("request-source", kind="request"))
        (events / "request-source.json").write_text(json.dumps(event, indent=2) + "\n")
        with mock.patch.object(candidates, "verify_work_order"):
            self.candidate = candidates.prepare(self.original, 423, self.request, "guard-chat")
        self.root = Path(self.candidate["source_root"])
        self.binding = Path(self.candidate["binding_path"])
        self.doc = self.root / "design-docs" / (self.request + ".md")
        self.event_path = self.root / "gonggong-diting-data/events/fixture" / self.request / "request-source.json"
        self.collection = self.root / "data-collection/active-source.json"
        self.collection.parent.mkdir()
        self.collection.write_text(json.dumps({"request_id": self.request, "issue": 423, "result": "fixture"}))
        self.before = {path: path.read_bytes() for path in (self.doc, self.event_path, self.collection)}

    def git(self, root, *arguments):
        return subprocess.run(
            ["git", "-C", str(root), *arguments], capture_output=True, text=True, check=True
        ).stdout.strip()

    def event(self, identifier, kind="message", request=None):
        return {
            "schema_version": 1,
            "event_id": identifier,
            "tenant_id": "fixture",
            "request_id": request or self.request,
            "kind": kind,
            "occurred_at": "2026-11-07T10:00:00Z",
            "source_ref": "https://github.com/example/test/issues/423",
            "agent": {"id": "fixture", "version": "1", "definition_sha256": "0" * 64, "origin": "isolated-test"},
            "payload": {"phase": "fixture"},
            "evidence_refs": [],
        }

    def command(self, code, **options):
        return guard.run_guard(self.binding, [sys.executable, "-c", code], cwd=self.root, **options)

    def journals(self, state="closed"):
        binding, digest = guard.bound(self.binding)
        return sorted(
            path
            for path in (guard.guard_folder(binding, digest) / state).glob("*.json")
            if json.loads(path.read_text()).get("state") != "checkpoint"
        )

    def checkpoint(self):
        binding, digest = guard.bound(self.binding)
        path = guard.guard_folder(binding, digest) / "pending" / (guard.checkpoint_token(digest) + ".json")
        return path, json.loads(path.read_text())

    def orphan(self):
        binding, digest = guard.bound(self.binding)
        path, record = guard.capture(binding, digest)
        record["runner"] = {"pid": 999999999, "birth": "fixture-dead"}
        record["child"] = None
        candidates.atomic_json(path, record)
        return path, record

    def pending(self, identifier="pending-message"):
        path = self.root / ".gonggong-outbox/chat" / (identifier + ".json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.event(identifier)))
        return path

    def test_real_stash_u_restores_active_sources_and_reports_violation(self):
        code = guard.run_guard(self.binding, ["git", "stash", "push", "--quiet", "--include-untracked"], cwd=self.root)
        self.assertEqual(code, guard.EXIT_VIOLATION)
        for path, content in self.before.items():
            self.assertEqual(path.read_bytes(), content)
        self.assertTrue(self.git(self.root, "stash", "list"))
        self.assertFalse(self.journals("pending"))
        record = json.loads(self.journals()[0].read_text())
        self.assertEqual(record["state"], "violated")
        self.assertEqual(len(record["restored"]), 3)

    def test_selective_stash_and_merge_preserve_active_provenance(self):
        self.git(self.root, "checkout", "-qb", "fixture-feature")
        (self.root / "feature.txt").write_text("new feature\n")
        self.git(self.root, "add", "feature.txt")
        self.git(self.root, "commit", "-qm", "feature")
        self.git(self.root, "checkout", "-q", self.candidate["branch"])
        (self.root / "source.txt").write_text("temporary source change\n")
        code = guard.run_guard(
            self.binding,
            ["/bin/sh", "-c", "git stash push --quiet -- source.txt && git merge --quiet --no-edit fixture-feature"],
            cwd=self.root,
        )
        self.assertEqual(code, 0)
        for path, content in self.before.items():
            self.assertEqual(path.read_bytes(), content)
        self.assertTrue((self.root / "feature.txt").exists())

    def test_document_edit_new_evidence_and_real_commit_are_allowed(self):
        code = self.command(
            "from pathlib import Path; import subprocess; "
            "p=Path('design-docs/active-test.md'); p.write_text(p.read_text()+'authorized clarification\\n'); "
            'Path(\'data-collection/new-evidence.json\').write_text(\'{"request_id":"active-test","passed":true}\'); '
            "subprocess.run(['git','add','.'],check=True); subprocess.run(['git','commit','-qm','candidate evidence'],check=True)"
        )
        self.assertEqual(code, 0)
        self.assertIn("authorized clarification", self.doc.read_text())
        # Newly committed same-request records become immutable in the next command.
        binding, _ = guard.bound(self.binding)
        entries = guard.capture_entries(binding)
        self.assertEqual(entries["data-collection/new-evidence.json"]["kind"], "immutable")

    def test_complete_canonical_pending_consumption_is_allowed(self):
        pending = self.pending()
        binding, digest = guard.bound(self.binding)
        path, record = guard.capture(binding, digest)
        receipt = guard.events_module().record(self.root, pending)
        self.assertEqual(receipt["state"], "recorded_file")
        pending.unlink()
        result = guard.verify_record(path, record, binding)
        self.assertTrue(result["ok"])
        self.assertEqual(result["consumed"], [pending.relative_to(self.root).as_posix()])
        self.assertFalse(pending.exists())

    def test_idempotent_pending_consumption_without_receipt_path_is_allowed(self):
        pending = self.pending()
        guard.events_module().record(self.root, pending)
        binding, digest = guard.bound(self.binding)
        path, record = guard.capture(binding, digest)
        receipt = guard.events_module().record(self.root, pending)
        self.assertNotIn("path", receipt)
        pending.unlink()
        self.assertTrue(guard.verify_record(path, record, binding)["ok"])

    def test_legacy_idempotent_pending_consumption_is_allowed(self):
        pending = self.pending()
        legacy = self.root / "olympus-hermes-data"
        legacy.mkdir()
        (legacy / "dataset.json").write_text(
            json.dumps({
                "schema_version": 1,
                "dataset_id": str(uuid.uuid4()),
                "name": "olympus-hermes-data",
                "origin_framework": "olympus",
            })
        )
        old = legacy / "events/fixture" / self.request / pending.name
        old.parent.mkdir(parents=True)
        old.write_text(json.dumps(guard.events_module().event(self.event("pending-message"))))
        binding, digest = guard.bound(self.binding)
        path, record = guard.capture(binding, digest)
        receipt = guard.events_module().record(self.root, pending)
        self.assertTrue(receipt["historical_read_only"])
        pending.unlink()
        self.assertTrue(guard.verify_record(path, record, binding)["ok"])

    def test_missing_pending_without_complete_record_is_restored(self):
        pending = self.pending()
        content = pending.read_bytes()
        code = self.command("from pathlib import Path; Path('.gonggong-outbox/chat/pending-message.json').unlink()")
        self.assertEqual(code, guard.EXIT_VIOLATION)
        self.assertEqual(pending.read_bytes(), content)

    def test_pending_record_with_wrong_hash_does_not_acknowledge_delivery(self):
        pending = self.pending()
        binding, digest = guard.bound(self.binding)
        path, record = guard.capture(binding, digest)
        target = self.root / "gonggong-diting-data/events/fixture" / self.request / pending.name
        value = guard.events_module().event(self.event("pending-message"))
        value["sha256"] = "f" * 64
        target.write_text(json.dumps(value))
        pending.unlink()
        result = guard.verify_record(path, record, binding)
        self.assertFalse(result["ok"])
        # Keep the original envelope available without overwriting conflicting storage.
        self.assertTrue(pending.exists())
        self.assertEqual(json.loads(pending.read_text()), self.event("pending-message"))
        self.assertEqual(json.loads(target.read_text())["sha256"], "f" * 64)

    def test_directory_rename_recovers_missing_provenance_without_deleting_moved_copy(self):
        moved = self.folder / "moved-design"
        code = self.command("from pathlib import Path; Path('design-docs').rename(" + repr(str(moved)) + ")")
        self.assertEqual(code, guard.EXIT_VIOLATION)
        self.assertEqual(self.doc.read_bytes(), self.before[self.doc])
        self.assertEqual((moved / self.doc.name).read_bytes(), self.before[self.doc])

    def test_conflicting_event_is_not_overwritten_and_remains_pending(self):
        code = self.command(
            "from pathlib import Path; Path(" + repr(str(self.event_path)) + ").write_text('conflicting event')"
        )
        self.assertEqual(code, guard.EXIT_VIOLATION)
        self.assertEqual(self.event_path.read_text(), "conflicting event")
        self.assertEqual(len(self.journals("pending")), 1)

    def test_orphan_recovery_restores_missing_and_keeps_original_failure_semantics(self):
        path, record = self.orphan()
        os.chmod(self.doc, 0o640)
        # The guard restores the mode observed at capture, not later changes.
        self.doc.unlink()
        self.event_path.unlink()
        result = guard.recover(self.binding)
        self.assertTrue(result["ok"])
        self.assertFalse(result["commands_replayed"])
        self.assertFalse(result["guards"][0]["ok"])
        self.assertTrue(result["guards"][0]["can_flush"])
        self.assertFalse(path.exists())
        self.assertEqual(self.doc.read_bytes(), self.before[self.doc])
        self.assertEqual(
            self.doc.stat().st_mode & 0o777, record["entries"][self.doc.relative_to(self.root).as_posix()]["mode"]
        )

    def test_active_runner_is_not_recovered_or_called_complete(self):
        binding, digest = guard.bound(self.binding)
        path, _ = guard.capture(binding, digest)
        result = guard.recover(self.binding)
        self.assertTrue(result["ok"])
        self.assertEqual(result["state"], "active")
        self.assertTrue(path.exists())

    def test_active_runner_does_not_hide_later_orphan_conflict(self):
        binding, digest = guard.bound(self.binding)
        first, active = guard.capture(binding, digest)
        second, dead = guard.capture(binding, digest)
        active["token"] = "0" * 32
        dead.update(token="f" * 32, runner={"pid": 99999999, "birth": "gone"})
        candidates.atomic_json(first.with_name(active["token"] + ".json"), active)
        candidates.atomic_json(second.with_name(dead["token"] + ".json"), dead)
        first.unlink()
        second.unlink()
        self.event_path.write_text("conflicting active event")
        result = guard.recover(self.binding)
        self.assertFalse(result["ok"])
        self.assertEqual(result["active"][0]["token"], active["token"])
        self.assertFalse(result["guards"][0]["can_flush"])

    def test_orphan_live_child_is_reported_without_signalling(self):
        path, record = self.orphan()
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        try:
            record["child"] = guard.process_identity(child.pid)
            candidates.atomic_json(path, record)
            result = guard.recover(self.binding)
            self.assertFalse(result["ok"])
            self.assertEqual(result["state"], "orphan_child_alive")
            self.assertIsNone(child.poll())
        finally:
            child.terminate()
            child.wait(timeout=5)

    def test_result_file_and_streams_preserve_child_exit(self):
        result_path = self.folder / "guard-result.json"
        tool = Path(guard.__file__).resolve()
        process = subprocess.run(
            [
                sys.executable,
                str(tool),
                "--binding",
                str(self.binding),
                "--run",
                "--invocation",
                "a" * 64,
                "--cancel-file",
                str(result_path) + ".cancel",
                "--result",
                str(result_path),
                "--",
                sys.executable,
                "-c",
                "import sys; print('stdout-marker'); print('stderr-marker',file=sys.stderr); sys.exit(7)",
            ],
            cwd=self.root,
            capture_output=True,
            text=True,
        )
        self.assertEqual(process.returncode, 7)
        self.assertEqual(process.stdout, "stdout-marker\n")
        self.assertEqual(process.stderr, "stderr-marker\n")
        result = json.loads(result_path.read_text())
        self.assertTrue(result["ok"])
        self.assertEqual(result["command_exit_code"], 7)

        recovered = guard.completed_command(self.binding, result_path, "a" * 64)
        self.assertEqual(recovered["exit_code"], 7)
        self.assertFalse(recovered["output_available"])
        with self.assertRaisesRegex(guard.GuardError, "command_outcome_unknown"):
            guard.completed_command(self.binding, result_path, "b" * 64)
        other = self.folder / "unrelated-result.json"
        other.write_bytes(result_path.read_bytes())
        with self.assertRaisesRegex(guard.GuardError, "command_outcome_unknown"):
            guard.completed_command(self.binding, other, "a" * 64)
        result["command_exit_code"] = 0
        result_path.write_text(json.dumps(result))
        with self.assertRaisesRegex(guard.GuardError, "command_outcome_unknown"):
            guard.completed_command(self.binding, result_path, "a" * 64)

    def test_preexisting_cancel_marker_prevents_command_start(self):
        marker = self.folder / "cancel-before-start"
        marker.touch()
        child_marker = self.folder / "child-must-not-start"
        result_path = self.folder / "cancelled-result.json"
        process = subprocess.run(
            [
                sys.executable,
                str(Path(guard.__file__).resolve()),
                "--binding",
                str(self.binding),
                "--run",
                "--cancel-file",
                str(marker),
                "--result",
                str(result_path),
                "--",
                sys.executable,
                "-c",
                "from pathlib import Path; Path(" + repr(str(child_marker)) + ").touch()",
            ],
            cwd=self.root,
            capture_output=True,
        )
        self.assertEqual(process.returncode, 143)
        self.assertFalse(child_marker.exists())
        result = json.loads(result_path.read_text())
        self.assertTrue(result["cancelled"])
        self.assertFalse(result["started"])
        self.assertTrue(result["ok"])

    def test_cancel_marker_arriving_during_snapshot_prevents_spawn(self):
        marker = self.folder / "cancel-during-snapshot"
        original = guard.capture

        def capture(*arguments):
            result = original(*arguments)
            marker.touch()
            return result

        with mock.patch.object(guard, "capture", side_effect=capture):
            code = self.command("raise AssertionError('cancelled command started')", cancel_file=marker)
        self.assertEqual(code, 143)
        self.assertFalse(json.loads(self.journals()[0].read_text())["started"])

    @unittest.skipIf(os.name == "nt", "POSIX process group cancellation fixture")
    def test_cancel_file_terminates_real_child_group_and_recovers_source(self):
        marker = self.folder / "cancel-running"
        ready = self.folder / "child-group-ready"
        result_path = self.folder / "cancel-running-result.json"
        code = (
            "from pathlib import Path; import subprocess,sys,time; Path('design-docs/active-test.md').unlink(); "
            "descendant=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); "
            "Path(" + repr(str(ready)) + ").write_text(str(descendant.pid)); time.sleep(30)"
        )
        process = subprocess.Popen(
            [
                sys.executable,
                str(Path(guard.__file__).resolve()),
                "--binding",
                str(self.binding),
                "--run",
                "--cancel-file",
                str(marker),
                "--result",
                str(result_path),
                "--",
                sys.executable,
                "-c",
                code,
            ],
            cwd=self.root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        descendant = None
        try:
            deadline = time.monotonic() + 5
            while not ready.exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(ready.exists())
            descendant = guard.process_identity(int(ready.read_text()))
            marker.touch()
            process.communicate(timeout=5)
            self.assertEqual(process.returncode, guard.EXIT_VIOLATION)
            self.assertFalse(guard.alive(descendant))
            self.assertEqual(self.doc.read_bytes(), self.before[self.doc])
            self.assertTrue(json.loads(result_path.read_text())["cancelled"])
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)
            if descendant and guard.alive(descendant):
                os.kill(descendant["pid"], signal.SIGTERM)

    def test_windows_cancellation_invokes_absolute_owned_taskkill_tree(self):
        child = mock.Mock(pid=4321)
        child.poll.return_value = None
        with (
            mock.patch.dict(os.environ, {"SystemRoot": str(self.folder)}),
            mock.patch.object(os.path, "isfile", return_value=True),
            mock.patch.object(guard.subprocess, "run", return_value=mock.Mock(returncode=0)) as execute,
        ):
            guard.windows_taskkill(child)
        self.assertEqual(
            execute.call_args.args[0], [str(self.folder / "System32/taskkill.exe"), "/PID", "4321", "/T", "/F"]
        )
        self.assertEqual(execute.call_args.kwargs["timeout"], 5)

    def test_cancel_marker_rejects_relative_linked_and_source_paths(self):
        with self.assertRaisesRegex(guard.GuardError, "provenance_cancel_path_invalid"):
            self.command("raise AssertionError('command started')", cancel_file="relative-marker")
        with self.assertRaisesRegex(guard.GuardError, "provenance_cancel_path_invalid"):
            self.command("raise AssertionError('command started')", cancel_file=self.root / "marker")

    @unittest.skipIf(os.name == "nt", "POSIX owned process group fixture")
    def test_background_descendant_cannot_write_after_leader_exits(self):
        pending = self.pending()
        late = self.folder / "late-write-must-not-happen"
        result_path = self.folder / "background-result.json"
        descendant = (
            "from pathlib import Path; import time; time.sleep(.6); Path(" + repr(str(pending)) + ").unlink(); "
            "Path(" + repr(str(late)) + ").touch()"
        )
        code = "import subprocess,sys; subprocess.Popen([sys.executable,'-c'," + repr(descendant) + "])"
        result = self.command(code, result_path=result_path)
        self.assertEqual(result, guard.EXIT_VIOLATION)
        report = json.loads(result_path.read_text())
        self.assertTrue(report["background_descendants_terminated"])
        self.assertEqual(report["error"], "provenance_background_descendants_terminated")
        self.assertEqual(report["command_exit_code"], 0)
        time.sleep(0.7)
        self.assertTrue(pending.exists())
        self.assertFalse(late.exists())

    def test_reused_group_leader_pid_is_never_signalled(self):
        with (
            mock.patch.object(guard, "process_group_members", return_value=[4321]),
            mock.patch.object(guard, "process_identity", return_value={"pid": 4321, "birth": "new-process"}),
            mock.patch.object(guard.os, "killpg") as signal_group,
        ):
            with self.assertRaisesRegex(guard.GuardError, "provenance_owned_group_owner_changed"):
                guard.quiesce_owned_group(4321, {"pid": 4321, "birth": "original-process"})
        signal_group.assert_not_called()

    @unittest.skipIf(os.name == "nt", "POSIX detached session fixture")
    def test_checkpoint_restores_detached_late_unlink_until_real_consumption(self):
        pending = self.pending()
        original = pending.read_bytes()
        release = self.folder / "release-detached"
        done = self.folder / "detached-done"
        detached = (
            "from pathlib import Path; import time; release=Path(" + repr(str(release)) + "); "
            "deadline=time.monotonic()+10\nwhile not release.exists() and time.monotonic()<deadline: time.sleep(.01)\n"
            "if release.exists(): Path(" + repr(str(pending)) + ").unlink(); Path(" + repr(str(done)) + ").touch()"
        )
        launch = (
            "import subprocess,sys; subprocess.Popen([sys.executable,'-c'," + repr(detached) + "], "
            "start_new_session=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)"
        )
        try:
            self.assertEqual(self.command(launch), 0)
            receipt = self.journals()[0]
            original_receipt = receipt.read_bytes()
            checkpoint, _ = self.checkpoint()
            self.assertTrue(checkpoint.exists())
            release.touch()
            deadline = time.monotonic() + 5
            while not done.exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(done.exists())
            self.assertFalse(pending.exists())
            result = guard.recover(self.binding)
            self.assertTrue(result["ok"])
            self.assertFalse(result["guards"][0]["ok"])
            self.assertTrue(result["guards"][0]["can_flush"])
            self.assertTrue(result["guards"][0]["original_command_result_unchanged"])
            self.assertEqual(pending.read_bytes(), original)
            self.assertEqual(receipt.read_bytes(), original_receipt)
            guard.events_module().record(self.root, pending)
            pending.unlink()
            result = guard.recover(self.binding)
            self.assertTrue(result["ok"])
            self.assertIn(pending.relative_to(self.root).as_posix(), result["guards"][0]["consumed"])
            self.assertNotIn(pending.relative_to(self.root).as_posix(), self.checkpoint()[1]["entries"])
        finally:
            release.touch(exist_ok=True)

    def test_checkpoint_keeps_latest_document_and_completed_command_result(self):
        self.assertEqual(
            self.command(
                "from pathlib import Path; Path('design-docs/active-test.md').write_text('command document update')"
            ),
            0,
        )
        receipt = self.journals()[0]
        original_receipt = receipt.read_bytes()
        self.doc.write_text("authorized host document update")
        self.assertTrue(guard.recover(self.binding)["ok"])
        self.doc.unlink()
        self.event_path.unlink()
        self.collection.unlink()
        result = guard.recover(self.binding)
        self.assertTrue(result["ok"])
        self.assertFalse(result["guards"][0]["ok"])
        self.assertEqual(self.doc.read_text(), "authorized host document update")
        self.assertEqual(self.event_path.read_bytes(), self.before[self.event_path])
        self.assertEqual(self.collection.read_bytes(), self.before[self.collection])
        self.assertEqual(receipt.read_bytes(), original_receipt)
        self.assertTrue(self.checkpoint()[0].exists())

    def test_checkpoint_violation_prevents_next_command_and_keeps_ignored_collection(self):
        self.assertEqual(self.command("pass"), 0)
        with (self.root / ".gitignore").open("a") as stream:
            stream.write("data-collection/active-source.json\n")
        self.assertTrue(guard.recover(self.binding)["ok"])
        self.collection.unlink()
        child_marker = self.folder / "blocked-child-must-not-start"
        code = self.command("from pathlib import Path; Path(" + repr(str(child_marker)) + ").touch()")
        self.assertEqual(code, guard.EXIT_VIOLATION)
        self.assertFalse(child_marker.exists())
        self.assertEqual(self.collection.read_bytes(), self.before[self.collection])
        self.assertEqual(self.command("pass"), 0)

    def test_checkpoint_conflict_keeps_original_before_image(self):
        self.assertEqual(self.command("pass"), 0)
        path, record = self.checkpoint()
        before = record["entries"][self.event_path.relative_to(self.root).as_posix()]
        self.event_path.write_text("conflicting immutable content")
        result = guard.recover(self.binding)
        self.assertFalse(result["ok"])
        self.assertEqual(self.event_path.read_text(), "conflicting immutable content")
        self.assertEqual(
            json.loads(path.read_text())["entries"][self.event_path.relative_to(self.root).as_posix()], before
        )

    def test_checkpoint_updates_wait_for_private_lock_and_keep_current_document(self):
        self.assertEqual(self.command("pass"), 0)
        ready = self.folder / "checkpoint-lock-ready"
        source = Path(guard.__file__).resolve().parent
        code = (
            "import sys,time; from pathlib import Path; sys.path.insert(0," + repr(str(source)) + "); "
            "import editor_provenance_guard as g; binding,digest=g.bound(Path(" + repr(str(self.binding)) + ")); "
            "lock=g.checkpoint_lock(binding,digest); lock.__enter__(); "
            "Path(" + repr(str(self.doc)) + ").write_text('latest checkpoint document'); "
            "Path(" + repr(str(ready)) + ").touch(); time.sleep(.3); lock.__exit__(None,None,None)"
        )
        child = subprocess.Popen([sys.executable, "-c", code])
        try:
            deadline = time.monotonic() + 5
            while not ready.exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(ready.exists())
            binding, digest = guard.bound(self.binding)
            self.assertTrue(guard.checkpoint_sync(binding, digest)["ok"])
            child.wait(timeout=5)
            item = self.checkpoint()[1]["entries"][self.doc.relative_to(self.root).as_posix()]
            self.assertEqual(guard.entry_bytes(item), b"latest checkpoint document")
        finally:
            if child.poll() is None:
                child.terminate()
                child.wait(timeout=5)

    @unittest.skipIf(os.name == "nt", "POSIX orphan group fixture")
    def test_recovery_refuses_live_group_after_known_leader_exited(self):
        path, record = self.orphan()
        code = "import subprocess,sys; subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'])"
        leader = subprocess.Popen([sys.executable, "-c", code], start_new_session=True)
        try:
            leader.wait(timeout=5)
            self.assertTrue(guard.process_group_members(leader.pid))
            record.update(state="running", child={"pid": leader.pid, "birth": "already-exited"}, owned_pgid=leader.pid)
            candidates.atomic_json(path, record)
            self.doc.unlink()
            result = guard.recover(self.binding)
            self.assertFalse(result["ok"])
            self.assertEqual(result["state"], "orphan_group_alive")
            self.assertFalse(self.doc.exists())
            self.assertTrue(guard.process_group_members(leader.pid))
        finally:
            try:
                os.killpg(leader.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            if leader.poll() is None:
                leader.wait(timeout=5)

    def test_timeout_posts_recovery_after_terminating_child(self):
        code = self.command(
            "from pathlib import Path; import time; Path('design-docs/active-test.md').unlink(); time.sleep(30)",
            timeout=0.2,
        )
        self.assertEqual(code, guard.EXIT_VIOLATION)
        self.assertEqual(self.doc.read_bytes(), self.before[self.doc])

    @unittest.skipIf(os.name == "nt", "POSIX signal fixture")
    def test_sigterm_runs_postcheck_and_writes_result(self):
        tool = Path(guard.__file__).resolve()
        marker = self.folder / "child-ready"
        result_path = self.folder / "cancel-result.json"
        code = (
            "from pathlib import Path; import time; Path('design-docs/active-test.md').unlink(); Path("
            + repr(str(marker))
            + ").write_text('ready'); time.sleep(30)"
        )
        process = subprocess.Popen(
            [
                sys.executable,
                str(tool),
                "--binding",
                str(self.binding),
                "--run",
                "--result",
                str(result_path),
                "--",
                sys.executable,
                "-c",
                code,
            ],
            cwd=self.root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            deadline = time.monotonic() + 5
            while not marker.exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(marker.exists())
            process.terminate()
            process.communicate(timeout=5)
            self.assertEqual(process.returncode, guard.EXIT_VIOLATION)
            self.assertEqual(self.doc.read_bytes(), self.before[self.doc])
            result = json.loads(result_path.read_text())
            self.assertFalse(result["ok"])
            self.assertTrue(result["cancelled"])
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)

    @unittest.skipIf(os.name == "nt", "POSIX hard-kill fixture")
    def test_hardkill_refuses_live_orphan_then_recovers_after_owned_child_exits(self):
        tool = Path(guard.__file__).resolve()
        marker = self.folder / "child-ready"
        code = (
            "from pathlib import Path; import time; Path('design-docs/active-test.md').unlink(); Path("
            + repr(str(marker))
            + ").write_text('ready'); time.sleep(30)"
        )
        process = subprocess.Popen(
            [sys.executable, str(tool), "--binding", str(self.binding), "--run", "--", sys.executable, "-c", code],
            cwd=self.root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        child_identity = None
        try:
            deadline = time.monotonic() + 5
            while not marker.exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(marker.exists())
            journal = self.journals("pending")[0]
            child_identity = json.loads(journal.read_text())["child"]
            process.kill()
            process.wait(timeout=5)
            result = guard.recover(self.binding)
            self.assertEqual(result["state"], "orphan_child_alive")
            self.assertFalse(result["ok"])
            self.assertEqual(guard.process_identity(child_identity["pid"]), child_identity)
            os.killpg(child_identity["pid"], signal.SIGTERM)
            deadline = time.monotonic() + 5
            while guard.alive(child_identity) and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertFalse(guard.alive(child_identity))
            result = guard.recover(self.binding)
            self.assertTrue(result["ok"])
            self.assertEqual(self.doc.read_bytes(), self.before[self.doc])
            self.assertFalse(result["commands_replayed"])

        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
            if child_identity and guard.alive(child_identity):
                os.killpg(child_identity["pid"], signal.SIGTERM)

    def test_interrupted_launch_refuses_to_assume_no_unknown_child(self):
        binding, digest = guard.bound(self.binding)
        path, record = guard.capture(binding, digest)
        record.update(state="launching", runner={"pid": 99999999, "birth": "gone"})
        candidates.atomic_json(path, record)
        self.doc.unlink()
        result = guard.recover(self.binding)
        self.assertFalse(result["ok"])
        self.assertEqual(result["state"], "orphan_child_unknown")
        self.assertFalse(self.doc.exists())
        self.assertTrue(path.exists())

    def test_snapshot_waits_for_real_concurrent_consumer(self):
        pending = self.pending()
        marker = self.folder / "flush-locked"
        source = Path(guard.__file__).resolve().parent
        code = (
            "import sys,time; from pathlib import Path; sys.path.insert(0," + repr(str(source)) + "); "
            "import editor_provenance_guard as g; root=Path(" + repr(str(self.root)) + "); "
            "lock=g.outbox_snapshot(root); lock.__enter__(); Path(" + repr(str(marker)) + ").write_text('locked'); "
            "time.sleep(.2); g.events_module().record(root,Path("
            + repr(str(pending))
            + ")); Path("
            + repr(str(pending))
            + ").unlink(); lock.__exit__(None,None,None)"
        )
        process = subprocess.Popen([sys.executable, "-c", code])
        try:
            deadline = time.monotonic() + 5
            while not marker.exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(marker.exists())
            binding, digest = guard.bound(self.binding)
            path, record = guard.capture(binding, digest)
            process.wait(timeout=5)
            self.assertEqual(process.returncode, 0)
            self.assertNotIn(pending.relative_to(self.root).as_posix(), record["entries"])
            self.assertTrue(guard.verify_record(path, record, binding)["ok"])
            self.assertFalse(pending.exists())
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=5)

    def test_unrelated_committed_collection_is_not_read_as_active_history(self):
        unrelated = self.root / "data-collection/unrelated-history.json"
        unrelated.write_text('{"request_id":"other-task","history":"preserved"}')
        self.git(self.root, "add", str(unrelated.relative_to(self.root)))
        self.git(self.root, "commit", "-qm", "unrelated fixture history")
        original = guard.read_json

        def active_only(path, *arguments):
            if Path(path) == unrelated:
                raise AssertionError("unrelated historical collection was read")
            return original(path, *arguments)

        with mock.patch.object(guard, "read_json", side_effect=active_only):
            binding, digest = guard.bound(self.binding)
            _, record = guard.capture(binding, digest)
        self.assertNotIn(unrelated.relative_to(self.root).as_posix(), record["entries"])

    def test_guard_start_error_writes_result_and_does_not_start_child(self):
        tool = Path(guard.__file__).resolve()
        result_path = self.folder / "failure-result.json"
        marker = self.folder / "must-not-start"
        self.doc.unlink()
        process = subprocess.run(
            [
                sys.executable,
                str(tool),
                "--binding",
                str(self.binding),
                "--run",
                "--result",
                str(result_path),
                "--",
                sys.executable,
                "-c",
                "from pathlib import Path; Path(" + repr(str(marker)) + ").touch()",
            ],
            cwd=self.root,
            capture_output=True,
            text=True,
        )
        self.assertEqual(process.returncode, guard.EXIT_VIOLATION)
        self.assertFalse(marker.exists())
        self.assertEqual(json.loads(result_path.read_text())["state"], "guard_error")
        self.assertTrue(process.stderr.startswith(guard.PREFIX))

    def test_multiline_tracked_collection_request_is_protected(self):
        multiline = self.root / "data-collection/multiline-source.json"
        multiline.write_text('{"request_id":\n"' + self.request + '", "evidence":"fixture"}\n')
        self.git(self.root, "add", str(multiline.relative_to(self.root)))
        self.git(self.root, "commit", "-qm", "multiline request fixture")
        binding, digest = guard.bound(self.binding)
        _, record = guard.capture(binding, digest)
        self.assertIn(multiline.relative_to(self.root).as_posix(), record["entries"])

    def test_spawn_tracking_write_failure_terminates_real_child_and_reports_failure(self):
        original_write = candidates.atomic_json
        original_spawn = guard.subprocess.Popen
        children = []
        result_path = self.folder / "tracking-failure.json"
        failed = False

        def write(path, value):
            nonlocal failed
            if value.get("state") == "running" and not failed:
                failed = True
                raise OSError("injected journal write failure")
            return original_write(path, value)

        def spawn(*arguments, **options):
            process = original_spawn(*arguments, **options)
            if options.get("start_new_session") or options.get("creationflags") == guard.processes.CREATE_SUSPENDED:
                children.append(process)
            return process

        with (
            mock.patch.object(candidates, "atomic_json", side_effect=write),
            mock.patch.object(guard.subprocess, "Popen", side_effect=spawn),
        ):
            code = self.command("import time; time.sleep(30)", result_path=result_path)
        self.assertEqual(code, guard.EXIT_VIOLATION)
        self.assertEqual(len(children), 1)
        self.assertIsNotNone(children[0].poll())
        result = json.loads(result_path.read_text())
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "provenance_child_tracking_failed")

    def test_conflicting_complete_pending_record_restores_queue_and_blocks_flush(self):
        pending = self.pending()
        binding, digest = guard.bound(self.binding)
        path, record = guard.capture(binding, digest)
        record["runner"] = {"pid": 99999999, "birth": "gone"}
        candidates.atomic_json(path, record)
        different = self.event("pending-message")
        different["payload"] = {"phase": "different-event"}
        target = self.root / "gonggong-diting-data/events/fixture" / self.request / pending.name
        target.write_text(json.dumps(guard.events_module().event(different)))
        pending.unlink()
        result = guard.recover(self.binding)
        self.assertFalse(result["ok"])
        self.assertTrue(pending.exists())
        self.assertTrue(path.exists())
        self.assertIn("persisted_event_conflict", {item["reason"] for item in result["guards"][0]["violations"]})

    def test_schema_valid_pending_event_with_invalid_graph_does_not_count_as_delivery(self):
        pending = self.pending()
        value = self.event("pending-message")
        value["evidence_refs"] = ["missing-evidence"]
        pending.write_text(json.dumps(value))
        binding, digest = guard.bound(self.binding)
        path, record = guard.capture(binding, digest)
        target = self.root / "gonggong-diting-data/events/fixture" / self.request / pending.name
        target.write_text(json.dumps(guard.events_module().event(value)))
        pending.unlink()
        result = guard.verify_record(path, record, binding)
        self.assertFalse(result["ok"])
        self.assertFalse(result["consumed"])
        self.assertTrue(pending.exists())
        with self.assertRaisesRegex(ValueError, "Missing evidence"):
            guard.events_module().load(self.root)

    def test_profile_allows_new_names_and_keeps_pending_writable(self):
        pending = self.pending()
        binding, digest = guard.bound(self.binding)
        _, record = guard.capture(binding, digest)
        profile = guard.profile_for("(version 1)(allow default)", record)
        self.assertIn("deny file-write-unlink", profile)
        self.assertIn("deny file-write*", profile)
        self.assertNotIn(str(pending), profile)
        self.assertNotIn("new-evidence.json", profile)
        self.assertIn(str(self.doc), profile)
        self.assertIn(str(guard.guard_folder(binding, digest)), profile)
        self.assertIn(str(self.binding), profile)

    def test_symlink_and_snapshot_budget_fail_closed_before_command(self):
        self.collection.unlink()
        self.collection.symlink_to(self.doc)
        with self.assertRaisesRegex(guard.GuardError, "provenance_path_linked"):
            self.command("raise AssertionError('command must not start')")
        self.collection.unlink()
        self.collection.write_bytes(self.before[self.collection])
        with mock.patch.object(guard, "MAX_TOTAL", 1):
            with self.assertRaisesRegex(guard.GuardError, "provenance_snapshot_limit"):
                self.command("raise AssertionError('command must not start')")


if __name__ == "__main__":
    unittest.main()
