import json
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path

from git_archive import capture
from migration_archive import archive
from routing import configure, select_entry


class ArchiveCheck(unittest.TestCase):
    def test_independent_capture_and_mismatched_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work = root / "work"
            subprocess.run(["git", "init", "-q", str(work)], check=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(work),
                    "-c",
                    "user.name=test",
                    "-c",
                    "user.email=test@example.invalid",
                    "commit",
                    "--allow-empty",
                    "-qm",
                    "snapshot",
                ],
                check=True,
            )
            mirror = root / "archive.git"
            subprocess.run(["git", "clone", "-q", "--mirror", str(work), str(mirror)], check=True)
            subprocess.run(
                ["git", "-C", str(mirror), "remote", "set-url", "origin", "https://github.com/example/history.git"],
                check=True,
            )
            report = capture("example/history", root)
            data = json.loads(report.read_bytes())
            self.assertEqual(data["commit_count"], 1)
            inventory = root / "report.json"
            inventory.write_text(json.dumps({"source": "example/history", "revision": data["head"]}))
            data["refs"] = {}
            report.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "differ"):
                archive(inventory, root, root, root / "native.db", "test", "test")

    def test_new_tasks_and_archived_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "settings.db"
            self.assertEqual(select_entry(db, "a"), "existing")
            sqlite3.connect(db).close()
            self.assertEqual(select_entry(db, "a"), "existing")
            configure(db, "a", None, "tianxuan")
            configure(db, "a", "original", "existing")
            self.assertEqual(select_entry(db, "a", "original"), "existing")
            self.assertEqual(select_entry(db, "a", "new"), "tianxuan")
            self.assertEqual(select_entry(db, "b", "new"), "existing")
            self.assertEqual(select_entry(db, "a", historical=True), "archive")
