"""Prepare a portable Git pack index from an explicitly published native archive."""

import argparse
import hashlib
import json
import re
import tempfile
from pathlib import Path

from history_git import _git
from history_records import export_binary
from migration_status import read_import_status


def parse_bundle_header(stream):
    """Read a complete SHA-1 v2/v3 bundle header, leaving the cursor at PACK."""
    signature = stream.readline(32)
    if signature not in (b"# v2 git bundle\n", b"# v3 git bundle\n"):
        raise ValueError("Unsupported Git bundle signature")
    refs = {}
    explicit_format = False
    while True:
        raw = stream.readline(8193)
        if len(raw) > 8192 or not raw.endswith(b"\n") or stream.tell() > 16 * 1024 * 1024:
            raise ValueError("Invalid or oversized bundle header")
        if raw == b"\n":
            break
        line = raw[:-1].decode("utf-8")
        if line.startswith("-"):
            raise ValueError("A prerequisite bundle cannot prewarm a complete archive")
        if line.startswith("@"):
            if signature != b"# v3 git bundle\n" or refs or explicit_format or line != "@object-format=sha1":
                raise ValueError("Unsupported Git bundle capability")
            explicit_format = True
            continue
        oid, sep, ref = line.partition(" ")
        if (
            not sep
            or not re.fullmatch(r"[0-9a-f]{40}", oid)
            or (ref != "HEAD" and not ref.startswith("refs/"))
            or any(ord(c) <= 32 or ord(c) == 127 for c in ref)
            or ref in refs
        ):
            raise ValueError("Invalid or repeated bundle reference")
        refs[ref] = oid
    if "HEAD" not in refs:
        raise ValueError("Bundle has no advertised HEAD")
    return "sha1", refs


def prepare(database, tenant, project, revision, output):
    """Publish a new index kit directory and return its independently transferable manifest checksum."""
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError(output)
    status = read_import_status(database, tenant, project)
    if not status or status["revision"] != revision:
        raise LookupError("Selected native publication unavailable")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as temporary:
        stage = Path(temporary)
        bundle = stage / "history.bundle"
        source = status["source"]
        receipt = export_binary(database, tenant, project, revision, f"github:{source}/history.bundle", bundle)
        bare = stage / "verify.git"
        _git(stage, "init", "--quiet", "--bare", "--template=", "--object-format=sha1", str(bare))
        pack = bare / "objects" / "pack" / "archive.pack"
        checksum = hashlib.sha256()
        with bundle.open("rb") as stream, pack.open("xb") as dest:
            fmt, refs = parse_bundle_header(stream)
            offset = stream.tell()
            if stream.read(4) != b"PACK":
                raise ValueError("Git pack missing at header boundary")
            stream.seek(offset)
            while block := stream.read(1024 * 1024):
                dest.write(block)
                checksum.update(block)
        oid = _git(bare, "index-pack", "--strict", "--index-version=2", str(pack)).decode().strip()
        if not re.fullmatch("[a-f0-9]{40}", oid):
            raise ValueError("Unexpected Git pack identifier")
        with pack.open("rb") as stream:
            stream.seek(-20, 2)
            if stream.read().hex() != oid:
                raise ValueError("Pack trailer differs from index identity")
        index = pack.with_suffix(".idx")
        pack.rename(pack.with_name("pack-" + oid + ".pack"))
        indexed = index.with_name("pack-" + oid + ".idx")
        index.rename(indexed)
        commands = "".join(f"create {name} {value}\n" for name, value in refs.items() if name != "HEAD")
        _git(bare, "update-ref", "--stdin", data=commands.encode())
        _git(bare, "update-ref", "--no-deref", "HEAD", refs["HEAD"])
        _git(bare, "cat-file", "-e", refs["HEAD"] + "^{commit}")
        _git(bare, "fsck", "--connectivity-only", "--no-dangling")
        kit = stage / "kit"
        kit.mkdir()
        target = kit / "index.idx"
        indexed.rename(target)
        with target.open("rb") as stream:
            index_hash = hashlib.file_digest(stream, "sha256").hexdigest()
        manifest = dict(
            version=1,
            tenant=tenant,
            project=project,
            revision=revision,
            source=source,
            catalog_sha256=status["catalog_sha256"],
            source_revision=status["source_revision"],
            bundle_sha256=receipt["sha256"],
            bundle_size=receipt["size"],
            pack_offset=offset,
            pack_size=receipt["size"] - offset,
            pack_oid=oid,
            pack_sha256=checksum.hexdigest(),
            index_sha256=index_hash,
            index_size=target.stat().st_size,
            object_format=fmt,
            refs=refs,
        )
        raw = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()
        (kit / "manifest.json").write_bytes(raw)
        kit.rename(output)
        return hashlib.sha256(raw).hexdigest()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ("database", "tenant", "project", "revision", "output"):
        parser.add_argument(argument)
    print(prepare(**vars(parser.parse_args())))
