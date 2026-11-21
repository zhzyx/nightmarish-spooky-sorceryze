"""多宝数据备份与恢复：仓库根目录与 SQLite 状态的离线快照。

备份包是一个 zip 文件，布局固定：

- ``repos/``：仓库根目录内的文件（保持相对路径）；
- ``state/``：对给定 SQLite 数据库执行一致性快照后的副本；
- ``manifest.json``：格式版本、创建时间、文件清单、大小与 SHA256。

恢复前先完整验证清单、路径与摘要，拒绝目录穿越、绝对路径、重复条目、清单缺失
和内容被篡改的包；验证通过后才写入目标目录。工具只读取源目录，不修改仓库或
数据库本身。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import zipfile
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

FORMAT_VERSION = 2
MANIFEST_NAME = "manifest.json"
REPOS_PREFIX = "repos/"
STATE_PREFIX = "state/"
CHUNK_SIZE = 1024 * 1024


class BackupError(RuntimeError):
    """备份或恢复输入不合法，或备份包未通过验证。"""


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sqlite_snapshot(database: Path) -> bytes:
    """用 SQLite 在线备份 API 生成一致性副本，避免直接复制活动数据库文件。"""
    with tempfile.TemporaryDirectory(prefix="duobao-backup-db-") as temporary:
        snapshot = Path(temporary) / "snapshot.db"
        try:
            source = sqlite3.connect(str(database))
            try:
                destination = sqlite3.connect(str(snapshot))
                try:
                    source.backup(destination)
                finally:
                    destination.close()
            finally:
                source.close()
        except sqlite3.Error as error:
            raise BackupError(f"cannot snapshot database {database}: {error}") from error
        return snapshot.read_bytes()


def _entry(prefix: str, relative: str, data: bytes) -> dict[str, Any]:
    return {
        "path": prefix + relative,
        "size": len(data),
        "sha256": _sha256_bytes(data),
    }


def create_backup(
    root: str | os.PathLike[str],
    destination: str | os.PathLike[str],
    *,
    databases: Sequence[str | os.PathLike[str]] = (),
    label: str = "",
) -> dict[str, Any]:
    """创建备份包并返回回执（路径、大小、摘要与清单摘要）。

    ``root`` 是仓库根目录；``databases`` 是需要一致性快照的 SQLite 文件。目标目录
    不存在时创建，但从不覆盖已有备份文件（文件名含微秒时间戳）。
    """
    root_path = Path(root)
    if not root_path.is_dir():
        raise BackupError(f"repository root is not a directory: {root_path}")

    destination_path = Path(destination)
    destination_path.mkdir(parents=True, exist_ok=True)

    database_paths = [Path(item) for item in databases]
    seen_names: set[str] = set()
    for database in database_paths:
        if not database.is_file():
            raise BackupError(f"database not found: {database}")
        if database.name in seen_names:
            raise BackupError(f"duplicate database name: {database.name}")
        seen_names.add(database.name)

    created_at = datetime.now(timezone.utc)
    archive_name = f"duobao-backup-{created_at.strftime('%Y%m%dT%H%M%S%fZ')}.zip"
    archive_path = destination_path / archive_name
    if archive_path.exists():
        raise BackupError(f"backup already exists: {archive_path}")

    entries: list[dict[str, Any]] = []
    directories = [REPOS_PREFIX.rstrip("/")]
    skipped_symlinks = 0
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for file_path in sorted(root_path.rglob("*")):
            relative = file_path.relative_to(root_path).as_posix()
            if file_path.is_symlink():
                skipped_symlinks += 1
                continue
            if file_path.is_dir():
                directories.append(REPOS_PREFIX + relative)
                continue
            if not file_path.is_file():
                continue
            data = file_path.read_bytes()
            archive.writestr(REPOS_PREFIX + relative, data)
            entries.append(_entry(REPOS_PREFIX, relative, data))

        for database in sorted(database_paths, key=lambda item: item.name):
            data = _sqlite_snapshot(database)
            archive.writestr(STATE_PREFIX + database.name, data)
            entries.append(_entry(STATE_PREFIX, database.name, data))

        manifest = {
            "format": FORMAT_VERSION,
            "created_at": created_at.isoformat(),
            "label": label,
            "root_name": root_path.resolve().name,
            "skipped_symlinks": skipped_symlinks,
            "directories": directories,
            "databases": sorted(database.name for database in database_paths),
            "entries": entries,
        }
        archive.writestr(MANIFEST_NAME, json.dumps(manifest, ensure_ascii=False, indent=2))

    return {
        "archive": str(archive_path),
        "created_at": created_at.isoformat(),
        "files": len(entries),
        "size": archive_path.stat().st_size,
        "sha256": _sha256_file(archive_path),
        "label": label,
    }


def _read_manifest(archive: zipfile.ZipFile) -> dict[str, Any]:
    names = archive.namelist()
    if names.count(MANIFEST_NAME) != 1:
        raise BackupError("backup must contain exactly one manifest.json")
    try:
        manifest = json.loads(archive.read(MANIFEST_NAME).decode("utf-8"))
    except (KeyError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BackupError(f"cannot read backup manifest: {error}") from error
    if not isinstance(manifest, dict):
        raise BackupError("backup manifest must be a JSON object")
    if manifest.get("format") not in (1, FORMAT_VERSION):
        raise BackupError(f"unsupported backup format: {manifest.get('format')!r}")
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        raise BackupError("backup manifest entries must be a list")
    return manifest


def _safe_member(name: str) -> PurePosixPath:
    """把清单/压缩包成员名规范化为安全的相对路径。"""
    if not isinstance(name, str) or not name:
        raise BackupError(f"unsafe backup member: {name!r}")
    if "\\" in name or "\x00" in name:
        raise BackupError(f"unsafe backup member: {name!r}")
    path = PurePosixPath(name)
    if (
        not path.parts
        or path.is_absolute()
        or any(part in {"..", ""} or (os.name == "nt" and PureWindowsPath(part).drive) for part in path.parts)
    ):
        raise BackupError(f"unsafe backup member: {name!r}")
    if path.parts[0] not in {REPOS_PREFIX.rstrip("/"), STATE_PREFIX.rstrip("/")}:
        raise BackupError(f"unexpected backup member: {name!r}")
    return path


def _repo_directories(manifest: dict[str, Any]) -> list[str]:
    if manifest["format"] == 1:
        return []
    directories = manifest.get("directories")
    if not isinstance(directories, list) or not directories:
        raise BackupError("backup manifest requires repository directories")
    for name in directories:
        member = _safe_member(name)
        if member.parts[0] != "repos" or member.as_posix() != name:
            raise BackupError("invalid backup directory")
    if "repos" not in directories or len(set(directories)) != len(directories):
        raise BackupError("invalid backup directory tree")
    return directories


def _validate_archive(archive: zipfile.ZipFile, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    members = set(archive.namelist())
    if MANIFEST_NAME not in members:
        raise BackupError("backup is missing manifest.json")
    entries = manifest["entries"]
    seen: set[str] = set()
    validated: list[dict[str, Any]] = []
    for raw in entries:
        if not isinstance(raw, dict):
            raise BackupError(f"invalid manifest entry: {raw!r}")
        name = raw.get("path")
        size = raw.get("size")
        digest = raw.get("sha256")
        if not isinstance(name, str) or not name:
            raise BackupError(f"invalid entry path: {raw!r}")
        if not isinstance(digest, str) or len(digest) != 64:
            raise BackupError(f"invalid entry digest: {raw!r}")
        if not isinstance(size, int) or size < 0:
            raise BackupError(f"invalid entry size: {raw!r}")
        member = _safe_member(name)
        key = member.as_posix()
        if key in seen:
            raise BackupError(f"duplicate backup entry: {key}")
        seen.add(key)
        try:
            info = archive.getinfo(key)
        except KeyError as error:
            raise BackupError(f"backup entry missing from archive: {key}") from error
        if info.file_size != size:
            raise BackupError(f"backup entry size mismatch: {key}")
        with archive.open(key) as handle:
            digest_check = hashlib.sha256()
            for chunk in iter(lambda: handle.read(CHUNK_SIZE), b""):
                digest_check.update(chunk)
        if digest_check.hexdigest() != digest:
            raise BackupError(f"backup entry digest mismatch: {key}")
        validated.append({"path": key, "size": size, "sha256": digest})
    directories = _repo_directories(manifest)
    directory_set = set(directories)
    if seen & directory_set:
        raise BackupError("backup directory conflicts with a file")
    if manifest["format"] == FORMAT_VERSION:
        for name in directory_set | {name for name in seen if name.startswith(REPOS_PREFIX)}:
            if name != "repos" and PurePosixPath(name).parent.as_posix() not in directory_set:
                raise BackupError("backup directory tree is incomplete")
    unexpected = members - seen - {MANIFEST_NAME}
    if unexpected:
        raise BackupError(f"backup contains unlisted members: {sorted(unexpected)[:3]}")
    return validated


def verify_backup(archive_path: str | os.PathLike[str]) -> dict[str, Any]:
    """只读验证备份包，返回清单摘要；不写入任何文件。"""
    path = Path(archive_path)
    if not path.is_file():
        raise BackupError(f"backup not found: {path}")
    try:
        with zipfile.ZipFile(path) as archive:
            manifest = _read_manifest(archive)
            entries = _validate_archive(archive, manifest)
    except zipfile.BadZipFile as error:
        raise BackupError(f"not a valid zip backup: {path}") from error
    return {
        "archive": str(path),
        "created_at": manifest.get("created_at"),
        "label": manifest.get("label", ""),
        "root_name": manifest.get("root_name", ""),
        "files": len(entries),
        "state_files": sum(1 for entry in entries if entry["path"].startswith(STATE_PREFIX)),
        "sha256": _sha256_file(path),
    }


def restore_backup(
    archive_path: str | os.PathLike[str],
    destination: str | os.PathLike[str],
    *,
    overwrite: bool = False,
) -> dict[str, Any]:
    """验证后恢复备份；``repos/`` 与 ``state/`` 保持原布局写入目标目录。

    目标目录非空且未显式 ``overwrite`` 时拒绝；验证在写入前完成，避免把损坏或
    被篡改的包解压到目标位置。恢复成功返回文件数与目标路径。
    """
    destination_path = Path(destination)
    if destination_path.exists():
        if not destination_path.is_dir():
            raise BackupError(f"restore destination is not a directory: {destination_path}")
        if any(destination_path.iterdir()) and not overwrite:
            raise BackupError(
                f"restore destination is not empty: {destination_path}; pass overwrite=True to replace files"
            )
    else:
        destination_path.mkdir(parents=True, exist_ok=True)

    path = Path(archive_path)
    if not path.is_file():
        raise BackupError(f"backup not found: {path}")
    try:
        with zipfile.ZipFile(path) as archive:
            manifest = _read_manifest(archive)
            entries = _validate_archive(archive, manifest)
            directories = _repo_directories(manifest)
            for name in directories + [entry["path"] for entry in entries]:
                target = destination_path
                for part in PurePosixPath(name).parts:
                    target = target / part
                    if target.is_symlink():
                        raise BackupError("restore destination contains a symbolic link")
            for name in directories:
                destination_path.joinpath(*PurePosixPath(name).parts).mkdir(parents=True, exist_ok=True)
            restored = 0
            for entry in entries:
                target = destination_path.joinpath(*PurePosixPath(entry["path"]).parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(entry["path"]) as source, open(target, "wb") as handle:
                    shutil.copyfileobj(source, handle, CHUNK_SIZE)
                restored += 1
    except zipfile.BadZipFile as error:
        raise BackupError(f"not a valid zip backup: {path}") from error
    return {
        "archive": str(path),
        "destination": str(destination_path),
        "restored": restored,
        "root_name": manifest.get("root_name", ""),
        "databases": manifest.get("databases", []),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Duobao repository backup and restore")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create", help="create a backup archive")
    create.add_argument("--root", required=True, help="repository root directory")
    create.add_argument("--destination", required=True, help="directory that receives the archive")
    create.add_argument("--database", action="append", default=[], help="SQLite database to snapshot (repeatable)")
    create.add_argument("--label", default="", help="optional human-readable label")

    verify = subparsers.add_parser("verify", help="verify an existing backup archive")
    verify.add_argument("archive")

    restore = subparsers.add_parser("restore", help="restore a verified backup archive")
    restore.add_argument("archive")
    restore.add_argument("--destination", required=True)
    restore.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "create":
            result = create_backup(
                args.root,
                args.destination,
                databases=args.database,
                label=args.label,
            )
        elif args.command == "verify":
            result = verify_backup(args.archive)
        else:
            result = restore_backup(args.archive, args.destination, overwrite=args.overwrite)
    except BackupError as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps({"ok": True, **result}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
