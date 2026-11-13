"""Ordinary game receipt metadata availability; disposable Git, no engine candidate."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

import editor_provenance_guard as guard


class GameReceiptTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="game-receipts-")
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name).resolve()
        self.root = self.folder / "game"
        self.root.mkdir()
        self.private = self.folder / "private"
        self.private.mkdir()
        patch = mock.patch.dict(os.environ, {"LOCALAPPDATA": str(self.private)})
        patch.start()
        self.addCleanup(patch.stop)
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("remote", "add", "origin", "https://github.com/example/game.git")
        self.reporting = dict(
            actor="fixture",
            tenant_id="fixture",
            request_ref="game-test",
            source_ref="https://github.com/example/game/issues/948",
        )
        self.metadata = {
            "work-items.json": {"repository": "example/game", "tenant_id": "fixture"},
            "gonggong-diting-data/dataset.json": {
                "schema_version": 1,
                "dataset_id": str(uuid.uuid4()),
                "name": "gonggong-diting-data",
                "origin_framework": "gonggong",
            },
        }
        for name, value in self.metadata.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value), encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "-qm", "baseline")
        self.binding = Path(guard.game_binding(self.root, self.reporting, True)["binding_path"])
        self.before = {name: (self.root / name).read_bytes() for name in self.metadata}

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.root), *args], capture_output=True, text=True, check=True
        ).stdout.strip()

    def command(self, code, **options):
        return guard.run_guard(self.binding, [sys.executable, "-c", code], cwd=self.root, **options)

    def removal(self):
        return "from pathlib import Path; " + "; ".join("Path(" + repr(name) + ").unlink()" for name in self.metadata)

    def test_success_and_failed_commands_restore_before_next_step(self):
        for exit_code in (0, 7):
            result = self.folder / "result.json"
            self.assertEqual(
                self.command(self.removal() + "; raise SystemExit(" + str(exit_code) + ")", result_path=result),
                exit_code,
            )
            self.assertEqual(json.loads(result.read_text())["command_exit_code"], exit_code)
            for name, data in self.before.items():
                self.assertEqual((self.root / name).read_bytes(), data)
            self.assertTrue(guard.game_binding(self.root, self.reporting)["ok"])
            self.assertEqual(self.command("print('next step')"), 0)
        self.assertNotIn("engine_candidate", json.loads(self.binding.read_text()))
        self.assertFalse((self.root / ".git/gonggong-engine-candidates").exists())

    def test_cancel_restores_and_preserves_diagnostics(self):
        result = self.folder / "cancel-result.json"
        code = self.command(self.removal() + "; import time; time.sleep(30)", timeout=0.5, result_path=result)
        self.assertEqual(code, 143)
        self.assertTrue(json.loads(result.read_text())["cancelled"])
        for name, data in self.before.items():
            self.assertEqual((self.root / name).read_bytes(), data)

    def test_terminal_recovery_uses_exact_invocation_without_replay(self):
        result = self.folder / "terminal.json"
        invocation = guard.fingerprint(b"ordinary native command journal")
        self.assertEqual(
            self.command(
                self.removal() + "; Path('executions').write_text('once'); raise SystemExit(7)",
                result_path=result,
                cancel_file=Path(str(result) + ".cancel"),
                invocation=invocation,
            ),
            7,
        )
        binding = guard.game_binding(self.root, self.reporting)
        recovered = guard.completed_command(Path(binding["binding_path"]), result, invocation)
        self.assertEqual(recovered["exit_code"], 7)
        self.assertFalse(recovered["output_available"])
        self.assertEqual((self.root / "executions").read_text(), "once")
        with self.assertRaisesRegex(guard.GuardError, "command_outcome_unknown"):
            guard.completed_command(self.binding, result, "a" * 64)
        for name, data in self.before.items():
            self.assertEqual((self.root / name).read_bytes(), data)

    def test_recovery_does_not_require_missing_work_items(self):
        binding, digest = guard.bound(self.binding)
        path, record = guard.capture(binding, digest)
        record["runner"] = {"pid": 999999999, "birth": "dead-fixture"}
        guard.candidates.atomic_json(path, record)
        for name in self.metadata:
            (self.root / name).unlink()
        self.assertTrue(guard.game_binding(self.root, self.reporting)["ok"])
        for name, data in self.before.items():
            self.assertEqual((self.root / name).read_bytes(), data)

    @unittest.skipUnless(os.name == "nt", "Windows junction boundary")
    def test_junction_metadata_parent_is_rejected(self):
        target = self.folder / "foreign-dataset"
        (self.root / "gonggong-diting-data").rename(target)
        link = self.root / "gonggong-diting-data"
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "New-Item -ItemType Junction -Path $env:RECEIPT_TEST_LINK -Target $env:RECEIPT_TEST_TARGET | Out-Null",
            ],
            env={**os.environ, "RECEIPT_TEST_LINK": str(link), "RECEIPT_TEST_TARGET": str(target)},
            check=True,
            capture_output=True,
        )
        before = (target / "dataset.json").read_bytes()
        with self.assertRaises(guard.GuardError):
            guard.capture_entries(guard.bound(self.binding)[0])
        self.assertEqual((target / "dataset.json").read_bytes(), before)

    def test_queue_history_and_foreign_worker_files_are_untouched(self):
        sentinels = [
            ".gonggong-outbox/chat/foreign.json",
            "gonggong-diting-data/events/foreign/history.json",
            "foreign-worker/source.txt",
        ]
        for name in sentinels:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"unchanged foreign worker")
        self.assertEqual(self.command(self.removal()), 0)
        for name in sentinels:
            self.assertEqual((self.root / name).read_bytes(), b"unchanged foreign worker")

    @unittest.skipUnless(os.name == "nt", "Windows junction boundaries")
    def test_outbox_and_private_junctions_never_create_foreign_files(self):
        binding, digest = guard.bound(self.binding)
        private = guard.guard_folder(binding, digest)
        for index, link in enumerate((self.root / ".gonggong-outbox", private / "pending", private / "closed")):
            target = self.folder / ("foreign-" + str(index))
            target.mkdir()
            subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "New-Item -ItemType Junction -Path $env:RECEIPT_TEST_LINK -Target $env:RECEIPT_TEST_TARGET | Out-Null",
                ],
                env={**os.environ, "RECEIPT_TEST_LINK": str(link), "RECEIPT_TEST_TARGET": str(target)},
                check=True,
                capture_output=True,
            )
            try:
                with self.assertRaises(guard.GuardError):
                    if link.name == "closed":
                        guard.archive(private / "pending/fixture.json", {})
                    else:
                        guard.capture(binding, digest)
                self.assertEqual(list(target.iterdir()), [])
            finally:
                link.rmdir()  # Remove only this junction, never its target.

    def test_changed_identity_is_preserved_and_blocks_flush(self):
        code = "import json; from pathlib import Path; p=Path('work-items.json'); v=json.loads(p.read_text()); v['tenant_id']='foreign'; p.write_text(json.dumps(v))"
        self.assertEqual(self.command(code), guard.EXIT_VIOLATION)
        self.assertEqual(json.loads((self.root / "work-items.json").read_text())["tenant_id"], "foreign")
        self.assertFalse(guard.game_binding(self.root, self.reporting)["ok"])

    @unittest.skipUnless(os.name == "nt", "Windows cold-read junction boundary")
    def test_terminal_recovery_rejects_junction_before_reading_receipt(self):
        result = self.folder / "terminal.json"
        invocation = "b" * 64
        self.assertEqual(
            self.command(
                "print('one real command')",
                result_path=result,
                cancel_file=Path(str(result) + ".cancel"),
                invocation=invocation,
            ),
            0,
        )
        binding, digest = guard.bound(self.binding)
        folder = guard.guard_folder(binding, digest)
        for name in ("closed", "pending"):
            link = folder / name
            target = self.folder / ("foreign-" + name)
            link.rename(target)
            subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "New-Item -ItemType Junction -Path $env:RECEIPT_TEST_LINK -Target $env:RECEIPT_TEST_TARGET | Out-Null",
                ],
                env={**os.environ, "RECEIPT_TEST_LINK": str(link), "RECEIPT_TEST_TARGET": str(target)},
                check=True,
                capture_output=True,
            )
            try:
                with self.assertRaisesRegex(guard.GuardError, "provenance_path_linked"):
                    guard.completed_command(self.binding, result, invocation)
            finally:
                link.rmdir()
                target.rename(link)

    def test_legitimate_fast_forward_updates_baseline(self):
        self.git("checkout", "-qb", "update")
        for name, value in self.metadata.items():
            value["description"] = "legitimate update"
            (self.root / name).write_text(json.dumps(value))
        self.git("add", ".")
        self.git("commit", "-qm", "configuration update")
        self.git("checkout", "-q", "main")
        self.assertEqual(
            self.command("import subprocess; subprocess.run(['git','merge','--ff-only','update'],check=True)"), 0
        )
        updated = {name: (self.root / name).read_bytes() for name in self.metadata}
        self.assertEqual(self.command(self.removal()), 0)
        for name, data in updated.items():
            self.assertEqual((self.root / name).read_bytes(), data)

    def test_foreign_reporting_and_invalid_boundaries(self):
        binding, _ = guard.bound(self.binding)
        binding["owner"] = "foreign"
        guard.candidates.atomic_json(self.binding, binding)
        with self.assertRaises(guard.GuardError):
            guard.bound(self.binding)
        with self.assertRaises(guard.GuardError):
            guard.game_identity(self.root / ".." / "game", self.reporting)
        with self.assertRaises(guard.GuardError):
            guard.checked(self.root, "../work-items.json")

    def test_symlink_metadata_is_rejected_without_touching_target(self):
        target = self.folder / "foreign.json"
        target.write_text("foreign")
        path = self.root / "work-items.json"
        path.unlink()
        try:
            path.symlink_to(target)
        except OSError as error:
            self.skipTest(str(error))
        with self.assertRaises(guard.GuardError):
            guard.capture_entries(guard.bound(self.binding)[0])
        self.assertEqual(target.read_text(), "foreign")


if __name__ == "__main__":
    unittest.main()
