"""多宝数据备份与恢复：清单校验、路径安全与 SQLite 一致性。"""

from __future__ import annotations

import contextlib
import io
import json
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path
from typing import Any, cast

import backup
from backup import BackupError, create_backup, restore_backup, verify_backup


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _rewrite_archive(source: Path, destination: Path, mutate) -> None:
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(destination, "w") as target:
        for name in original.namelist():
            data = original.read(name)
            result = mutate(name, data)
            if result is not None:
                target.writestr(name, result)


class BackupTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory(prefix="duobao-backup-test-")
        self.addCleanup(self._temporary.cleanup)
        self.base = Path(self._temporary.name)
        self.root = self.base / "repos"
        _write(self.root / "a.git" / "HEAD", b"ref: refs/heads/main\n")
        _write(self.root / "a.git" / "objects" / "info" / "packs", b"")
        _write(self.root / "b.md", b"# doc\n")
        self.database = self.base / "tianxuan.db"
        connection = sqlite3.connect(self.database)
        try:
            connection.execute("CREATE TABLE docs (id TEXT PRIMARY KEY, body TEXT)")
            connection.execute("INSERT INTO docs VALUES ('d1', '# one')")
            connection.commit()
        finally:
            connection.close()
        self.destination = self.base / "out"

    def _backup(self, **kwargs: Any) -> dict[str, Any]:
        return cast(dict[str, Any], create_backup(self.root, self.destination, **kwargs))


class BackupRoundTripTests(BackupTestCase):
    def test_roundtrip_restores_files_and_database(self) -> None:
        receipt = self._backup(databases=[self.database], label="checkpoint")
        self.assertTrue(Path(receipt["archive"]).is_file())
        self.assertEqual(receipt["files"], 4)

        verified = verify_backup(receipt["archive"])
        self.assertEqual(verified["files"], 4)
        self.assertEqual(verified["state_files"], 1)
        self.assertEqual(verified["label"], "checkpoint")
        self.assertEqual(verified["root_name"], "repos")

        restored = self.base / "restored"
        result = restore_backup(receipt["archive"], restored)
        self.assertEqual(result["restored"], 4)
        self.assertEqual((restored / "repos" / "a.git" / "HEAD").read_bytes(), b"ref: refs/heads/main\n")
        self.assertEqual((restored / "repos" / "b.md").read_bytes(), b"# doc\n")
        connection = sqlite3.connect(restored / "state" / "tianxuan.db")
        try:
            self.assertEqual(connection.execute("SELECT body FROM docs").fetchone()[0], "# one")
        finally:
            connection.close()

    def test_receipt_exposes_digest_and_size(self) -> None:
        receipt = self._backup()
        self.assertEqual(len(receipt["sha256"]), 64)
        self.assertGreater(receipt["size"], 0)
        self.assertEqual(receipt["files"], 3)

    def test_restore_requires_empty_destination_without_overwrite(self) -> None:
        receipt = self._backup()
        restored = self.base / "restored"
        restored.mkdir()
        (restored / "keep.txt").write_text("x", encoding="utf-8")
        with self.assertRaises(BackupError):
            restore_backup(receipt["archive"], restored)
        self.assertEqual(restore_backup(receipt["archive"], restored, overwrite=True)["restored"], 3)
        self.assertEqual((restored / "keep.txt").read_text(encoding="utf-8"), "x")

    def test_missing_database_is_rejected(self) -> None:
        with self.assertRaises(BackupError):
            self._backup(databases=[self.base / "missing.db"])
        self.assertEqual(list(self.destination.glob("*.zip")), [])

    def test_symlinks_are_skipped_and_counted(self) -> None:
        target = self.root / "b.md"
        link = self.root / "link.md"
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("symlink creation is not permitted on this platform")
        receipt = self._backup()
        self.assertEqual(receipt["files"], 3)
        with zipfile.ZipFile(receipt["archive"]) as archive:
            manifest = json.loads(archive.read("manifest.json"))
        self.assertEqual(manifest["skipped_symlinks"], 1)


class BackupValidationTests(BackupTestCase):
    def _valid_archive(self) -> Path:
        return Path(self._backup(databases=[self.database])["archive"])

    def test_tampered_payload_is_rejected(self) -> None:
        source = self._valid_archive()
        tampered = self.base / "tampered.zip"

        def mutate(name: str, data: bytes) -> bytes | None:
            return data + b"changed" if name == "repos/b.md" else data

        _rewrite_archive(source, tampered, mutate)
        with self.assertRaises(BackupError):
            verify_backup(tampered)
        with self.assertRaises(BackupError):
            restore_backup(tampered, self.base / "restored")
        self.assertFalse((self.base / "restored" / "repos" / "b.md").exists())

    def test_unlisted_member_is_rejected(self) -> None:
        source = self._valid_archive()
        with zipfile.ZipFile(source, "a") as archive:
            archive.writestr("repos/extra.md", b"extra")
        with self.assertRaises(BackupError):
            verify_backup(source)

    def test_path_traversal_is_rejected_before_writing(self) -> None:
        archive_path = self.base / "traversal.zip"
        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.writestr(
                "manifest.json",
                json.dumps({
                    "format": backup.FORMAT_VERSION,
                    "entries": [{"path": "repos/../../escape.md", "size": 1, "sha256": "0" * 64}],
                }),
            )
            archive.writestr("repos/../../escape.md", b"x")
        with self.assertRaises(BackupError):
            restore_backup(archive_path, self.base / "restored")
        self.assertFalse((self.base / "escape.md").exists())

    def test_missing_manifest_is_rejected(self) -> None:
        archive_path = self.base / "no-manifest.zip"
        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.writestr("repos/a.md", b"x")
        with self.assertRaises(BackupError):
            verify_backup(archive_path)

    def test_unsupported_format_is_rejected(self) -> None:
        archive_path = self.base / "format.zip"
        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.writestr("manifest.json", json.dumps({"format": 99, "entries": []}))
        with self.assertRaises(BackupError):
            verify_backup(archive_path)


class BackupCommandLineTests(BackupTestCase):
    def test_cli_create_and_verify(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = backup.main([
                "create",
                "--root",
                str(self.root),
                "--destination",
                str(self.destination),
                "--label",
                "cli",
            ])
        self.assertEqual(code, 0)
        receipt = json.loads(stdout.getvalue())
        self.assertTrue(receipt["ok"])
        self.assertTrue(Path(receipt["archive"]).is_file())

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = backup.main(["verify", receipt["archive"]])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout.getvalue())["label"], "cli")

    def test_cli_error_returns_non_zero(self) -> None:
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = backup.main(["restore", str(self.base / "missing.zip"), "--destination", str(self.base / "r")])
        self.assertEqual(code, 1)
        self.assertIn("backup not found", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
