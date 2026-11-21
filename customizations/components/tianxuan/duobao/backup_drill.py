"""多宝备份/恢复演练：在本地目录上端到端验证备份包。

演练流程：创建备份 → 验证清单/SHA256 → 恢复到新目录 → 逐文件比较仓库内容 →
对恢复出的 SQLite 执行 ``PRAGMA integrity_check``。不依赖 Docker，可用于本地
安装、CI 或部署前的数据卷副本。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import sys
import tempfile
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

import backup

CHUNK_SIZE = 1024 * 1024


class DrillError(RuntimeError):
    """演练失败：备份、恢复或一致性检查未通过。"""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _iter_files(root: Path) -> Iterable[Path]:
    if not root.is_dir():
        return
    for path in sorted(root.rglob("*")):
        if path.is_file() and not path.is_symlink():
            yield path


def run_drill(
    repo_root: str,
    database: str | None = None,
    *,
    workdir: str | None = None,
    keep: bool = False,
    label: str = "drill",
) -> dict[str, Any]:
    """执行一次备份/恢复演练并返回回执；失败抛 :class:`DrillError`。"""
    root = Path(repo_root)
    if not root.is_dir():
        raise DrillError(f"repository root is not a directory: {root}")
    database_path = Path(database) if database else None
    if database_path is not None and not database_path.is_file():
        raise DrillError(f"database not found: {database_path}")

    created_temp = False
    if workdir:
        base = Path(workdir)
        base.mkdir(parents=True, exist_ok=True)
    else:
        base = Path(tempfile.mkdtemp(prefix="duobao-drill-"))
        created_temp = True
    try:
        backup_dir = base / "backup"
        restore_dir = base / "restore"
        receipt = backup.create_backup(
            root,
            backup_dir,
            databases=[database_path] if database_path is not None else [],
            label=label,
        )
        verified = backup.verify_backup(receipt["archive"])
        restored = backup.restore_backup(receipt["archive"], restore_dir)

        source_files = {path.relative_to(root).as_posix(): _sha256(path) for path in _iter_files(root)}
        restored_root = restore_dir / "repos"
        restored_files = {
            path.relative_to(restored_root).as_posix(): _sha256(path) for path in _iter_files(restored_root)
        }
        if source_files != restored_files:
            missing = sorted(set(source_files) - set(restored_files))
            extra = sorted(set(restored_files) - set(source_files))
            changed = sorted(
                name for name in set(source_files) & set(restored_files) if source_files[name] != restored_files[name]
            )
            raise DrillError(
                f"restored repository differs: missing={missing[:3]} extra={extra[:3]} changed={changed[:3]}"
            )

        def directories(directory: Path) -> set[Path]:
            return {
                path.relative_to(directory) for path in directory.rglob("*") if not path.is_symlink() and path.is_dir()
            }

        if not restored_root.is_dir() or directories(root) != directories(restored_root):
            raise DrillError("restored repository directory structure differs")

        database_check: dict[str, Any] | None = None
        if database_path is not None:
            restored_db = restore_dir / "state" / database_path.name
            if not restored_db.is_file():
                raise DrillError(f"restored database is missing: {restored_db}")
            connection = sqlite3.connect(restored_db)
            try:
                integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            finally:
                connection.close()
            if integrity != "ok":
                raise DrillError(f"restored database integrity check failed: {integrity}")
            database_check = {"integrity": integrity, "path": str(restored_db)}

        return {
            "ok": True,
            "workdir": str(base),
            "archive": receipt["archive"],
            "archive_sha256": receipt["sha256"],
            "verified_files": verified["files"],
            "restored_files": restored["restored"],
            "repo_files": len(source_files),
            "database": database_check,
        }
    finally:
        if created_temp and not keep:
            shutil.rmtree(base, ignore_errors=True)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Duobao backup/restore drill")
    parser.add_argument("--repo-root", required=True, help="repository root to back up")
    parser.add_argument("--database", default=None, help="optional SQLite database")
    parser.add_argument("--workdir", default=None, help="working directory for backup/restore output")
    parser.add_argument("--keep", action="store_true", help="keep generated temporary files")
    parser.add_argument("--label", default="drill", help="backup label")
    parser.add_argument("--json-out", default=None, help="write the receipt JSON to this path")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = run_drill(
            args.repo_root,
            args.database,
            workdir=args.workdir,
            keep=args.keep,
            label=args.label,
        )
    except (DrillError, backup.BackupError, OSError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
    text = json.dumps(result, ensure_ascii=False)
    if args.json_out:
        Path(args.json_out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
