"""多宝备份/恢复演练：端到端一致性、缺失输入与 CLI 回执。"""

from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import backup_drill
from backup_drill import DrillError, run_drill


class BackupDrillTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory(prefix="duobao-drill-test-")
        self.addCleanup(self._temporary.cleanup)
        self.base = Path(self._temporary.name)
        self.root = self.base / "repos"
        pack = self.root / "a.git" / "objects" / "pack"
        pack.parent.mkdir(parents=True)
        pack.write_bytes(b"pack-data")
        (self.root / "a.git" / "HEAD").write_bytes(b"ref: refs/heads/main\n")
        self.database = self.base / "tianxuan.db"
        connection = sqlite3.connect(self.database)
        try:
            connection.execute("CREATE TABLE docs (id TEXT PRIMARY KEY, body TEXT)")
            connection.execute("INSERT INTO docs VALUES ('d1', 'body')")
            connection.commit()
        finally:
            connection.close()
        self.workdir = self.base / "work"

    def test_drill_round_trip(self) -> None:
        result = run_drill(str(self.root), str(self.database), workdir=str(self.workdir))
        self.assertTrue(result["ok"])
        self.assertEqual(result["repo_files"], 2)
        self.assertEqual(result["verified_files"], 3)
        self.assertEqual(result["restored_files"], 3)
        self.assertEqual(result["database"]["integrity"], "ok")
        self.assertTrue(Path(result["archive"]).is_file())
        restored_head = self.workdir / "restore" / "repos" / "a.git" / "HEAD"
        self.assertEqual(restored_head.read_bytes(), b"ref: refs/heads/main\n")

    def test_drill_rejects_missing_database(self) -> None:
        with self.assertRaises(DrillError):
            run_drill(
                str(self.root),
                str(self.base / "missing.db"),
                workdir=str(self.base / "work-missing"),
            )

    def test_cli_writes_receipt(self) -> None:
        receipt = self.base / "receipt.json"
        code = backup_drill.main([
            "--repo-root",
            str(self.root),
            "--database",
            str(self.database),
            "--workdir",
            str(self.base / "work-cli"),
            "--json-out",
            str(receipt),
        ])
        self.assertEqual(code, 0)
        payload = json.loads(receipt.read_text(encoding="utf-8"))
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["database"]["integrity"], "ok")


if __name__ == "__main__":
    unittest.main()
