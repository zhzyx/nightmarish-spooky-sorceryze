"""Adopt an authenticated offline Git index using only the target's published native bundle."""

import argparse
import hashlib
import io
import json
import re
import stat
import tempfile
from pathlib import Path

from history_git import _cache_lock, _cache_root, _check_commit, _git, _promote, _publication
from history_records import _copy_binary, _published
from prewarm_prepare import parse_bundle_header


def _regular(path):
    attrs = path.lstat()
    if not stat.S_ISREG(attrs.st_mode) or getattr(attrs, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
        raise ValueError("Kit input must be a regular file")
    return path


def _sha(value):
    if not isinstance(value, str) or not re.fullmatch("[0-9a-f]{64}", value):
        raise ValueError("Expected a lowercase SHA-256 digest")
    return value


class _BundlePack:
    """Consume verified native chunks; write only their pack payload to the target."""

    def __init__(self, manifest, output):
        self.manifest = manifest
        self.output = output
        self.header = bytearray()
        self.pack_hash = hashlib.sha256()
        self.size = 0
        self.tail = b""
        self.refs = None
        self.prefix = b""

    def write(self, data):
        if self.refs is None:
            take = min(self.manifest["pack_offset"] - len(self.header), len(data))
            self.header.extend(data[:take])
            data = data[take:]
            if len(self.header) == self.manifest["pack_offset"]:
                stream = io.BytesIO(self.header)
                fmt, self.refs = parse_bundle_header(stream)
                if (
                    stream.tell() != len(self.header)
                    or fmt != self.manifest["object_format"]
                    or self.refs != self.manifest["refs"]
                ):
                    raise ValueError("Native bundle header differs from offline kit")
        if data:
            self.prefix += data[: 12 - len(self.prefix)]
            self.size += len(data)
            self.pack_hash.update(data)
            self.tail = (self.tail + data[-20:])[-20:]
            if self.output is not None:
                self.output.write(data)

    def verify(self, binary):
        m = self.manifest
        if (
            self.refs is None
            or self.prefix[:4] != b"PACK"
            or len(self.prefix) != 12
            or self.size != m["pack_size"]
            or self.tail.hex() != m["pack_oid"]
            or self.pack_hash.hexdigest() != m["pack_sha256"]
            or binary != {"sha256": m["bundle_sha256"], "size": m["bundle_size"]}
        ):
            raise ValueError("Native bundle and prepared pack identity differ")


def _index(source, destination, manifest, object_count):
    length = source.stat().st_size
    if length != manifest["index_size"] or length > 1100 + object_count * 40:
        raise ValueError("Invalid prepared index size")
    checksum = hashlib.sha256()
    total = 0
    tail = b""
    with source.open("rb") as f:
        while chunk := f.read(1024 * 1024):
            total += len(chunk)
            if total > length:
                raise ValueError("Prepared index changed during read")
            checksum.update(chunk)
            tail = (tail + chunk[-40:])[-40:]
            if destination:
                destination.write(chunk)
    if total != length or checksum.hexdigest() != manifest["index_sha256"] or tail[:20].hex() != manifest["pack_oid"]:
        raise ValueError("Prepared index checksum or pack binding mismatch")


def _verify_mirror(repo, refs, revision):
    actual = {}
    for row in _git(repo, "for-each-ref", "--format=%(objectname) %(refname)").decode().splitlines():
        oid, name = row.split(" ", 1)
        actual[name] = oid
    actual["HEAD"] = _git(repo, "rev-parse", "--verify", "HEAD").decode().strip()
    if actual != refs:
        raise ValueError("Target cache refs differ from the native bundle")
    _git(repo, "fsck", "--full", "--no-dangling")
    _check_commit(repo, revision)
    if _git(repo, "log", "-1", "--format=%H", revision, "--").decode().strip() != revision:
        raise ValueError("Archived source commit query failed")


def _file_identity(path):
    s = path.stat()
    return dict(device=s.st_dev, inode=s.st_ino, size=s.st_size, mtime_ns=s.st_mtime_ns)


def _empty_wal(db):
    wal = Path(str(db) + "-wal")
    if wal.exists() and wal.stat().st_size:
        raise ValueError("A physical DB digest requires a quiescent database with an empty WAL")


def adopt(
    database,
    tenant,
    project,
    revision,
    prepared_dir,
    *,
    expected_manifest_sha256,
    cache_dir=None,
    expected_db_sha256=None,
):
    database = Path(database).resolve(strict=True)
    identity = _file_identity(database)
    if expected_db_sha256 is not None:
        _sha(expected_db_sha256)
        _empty_wal(database)
        with database.open("rb") as f:
            if hashlib.file_digest(f, "sha256").hexdigest() != expected_db_sha256:
                raise ValueError("Target database checksum mismatch")
    status = _publication(database, tenant, project, revision)
    kit = Path(prepared_dir).resolve(strict=True)
    with _regular(kit / "manifest.json").open("rb") as f:
        raw = f.read(16 * 1024 * 1024 + 1)
    if len(raw) > 16 * 1024 * 1024 or hashlib.sha256(raw).hexdigest() != _sha(expected_manifest_sha256):
        raise ValueError("Prepared manifest is oversized or differs from the deployment receipt")
    m = json.loads(raw)
    expected = dict(
        version=1,
        tenant=tenant,
        project=project,
        revision=revision,
        source=status["source"],
        source_revision=status["source_revision"],
        catalog_sha256=status["catalog_sha256"],
        object_format="sha1",
    )
    if not isinstance(m, dict) or any(m.get(k) != v for k, v in expected.items()):
        raise ValueError("Offline kit does not match the target publication")
    for k in ("pack_sha256", "index_sha256", "bundle_sha256"):
        _sha(m.get(k))
    if not re.fullmatch("[a-f0-9]{40}", m.get("pack_oid", "")):
        raise ValueError("Invalid pack identity")
    for k in ("index_size", "pack_offset", "pack_size", "bundle_size"):
        if type(m.get(k)) is not int or m[k] <= 0:
            raise ValueError("Invalid kit size")
    if m["pack_offset"] > 16 * 1024 * 1024 or m["pack_offset"] + m["pack_size"] != m["bundle_size"]:
        raise ValueError("Invalid bundle bounds")

    index = _regular(kit / "index.idx")
    root = _cache_root(database, tenant, project, revision, cache_dir)
    mirror = root / "archive.git"
    with _cache_lock(root), tempfile.TemporaryDirectory(dir=root) as temp:
        reused = mirror.is_dir()
        staged = mirror if reused else Path(temp) / "archive.git"
        if not reused:
            _git(temp, "init", "--bare", "--template=", "--object-format=sha1", str(staged))
        pack = staged / "objects" / "pack" / ("pack-" + m["pack_oid"] + ".pack")
        from contextlib import nullcontext

        with nullcontext(None) if reused else pack.open("xb") as target:
            sink = _BundlePack(m, target)
            with _published(database, tenant, project, revision) as (db, catalog):
                binary = _copy_binary(db, tenant, catalog, "github:" + status["source"] + "/history.bundle", sink)
            sink.verify(binary)
        idx = pack.with_suffix(".idx")
        with nullcontext(None) if reused else idx.open("xb") as target:
            _index(index, target, m, int.from_bytes(sink.prefix[8:12], "big"))
        refs = sink.refs
        if not reused:
            _git(staged, "verify-pack", "--", str(idx))
            commands = bytearray()
            for name, oid in refs.items():
                if name != "HEAD":
                    commands.extend(("create " + name + "\0" + oid + "\0").encode())
            _git(staged, "update-ref", "--stdin", "-z", data=commands)
            _git(staged, "update-ref", "--no-deref", "HEAD", refs["HEAD"])
            _git(staged, "pack-refs", "--all", "--prune")
        _verify_mirror(staged, refs, m["source_revision"])
        now = _file_identity(database)
        if (now["device"], now["inode"]) != (identity["device"], identity["inode"]):
            raise ValueError("Target database was replaced")
        if expected_db_sha256 is not None:
            _empty_wal(database)
            if now != identity:
                raise ValueError("Target database changed during adoption")
        _publication(database, tenant, project, revision)
        if not reused:
            _promote(database, tenant, project, revision, staged, mirror)
    return dict(
        reused=reused,
        database=str(database),
        database_identity=identity,
        database_sha256=expected_db_sha256,
        tenant=tenant,
        project=project,
        revision=revision,
        source_revision=m["source_revision"],
        catalog_sha256=m["catalog_sha256"],
        manifest_sha256=expected_manifest_sha256,
        bundle_sha256=m["bundle_sha256"],
        mirror=str(mirror),
        ref_count=len(refs) - 1,
        head=refs["HEAD"],
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("database", "tenant", "project", "revision", "prepared-dir", "expected-manifest-sha256"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--cache-dir")
    parser.add_argument("--expected-db-sha256")
    print(json.dumps(adopt(**vars(parser.parse_args())), indent=2))
