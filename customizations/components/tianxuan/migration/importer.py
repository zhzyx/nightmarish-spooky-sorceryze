"""Archive inventory records and supplied binaries in immutable Duobao revisions."""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "duobao"))
from native_store import Conflict, NativeStore

BLOCK_SIZE = 4 * 1024 * 1024


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(value).hexdigest()


def write_verified(store, tenant, actor, edits):
    fingerprints = {name: digest(data) for name, data in edits.items()}
    module = "migration-" + digest(canonical(fingerprints))
    revision = store.head(tenant, module)
    if revision is None:
        try:
            receipt = store.submit(tenant, actor, module, [dict(module=module, base=None, reads=[], edits=edits)])
            revision = receipt["revisions"][module]
        except Conflict:
            revision = store.head(tenant, module)
            if revision is None:
                raise
    state = store.revision(tenant, module, revision)
    if state["objects"] != fingerprints:
        raise ValueError("Archive checkpoint has different contents")
    for name, expected in fingerprints.items():
        if digest(store.read(tenant, module, revision, name)) != expected:
            raise ValueError("Archive readback failed")
    return {"module": module, "revision": revision}


def import_inventory(manifest_path, database, tenant, actor, *, artifacts=None):
    """Return a verified catalog pointer. Incomplete runs leave reusable private blocks."""
    database = Path(database).resolve()
    manifest_path = Path(manifest_path)
    report = json.loads(manifest_path.read_bytes())
    if report["historical_policy"] != "record_only":
        raise ValueError("Only record-only history can be archived")
    store = NativeStore(database)
    counts = Counter()
    sources = set()
    batches = []
    edits = {}
    total = 0
    checksum = hashlib.sha256()
    with manifest_path.with_name("records.jsonl").open("rb") as stream:
        for line in stream:
            checksum.update(line)
            row = json.loads(line)
            source_id = row["source_id"]
            prefix = "github:" + report["source"] + "/" + row["kind"] + "/"
            if (
                source_id in sources
                or not source_id.startswith(prefix)
                or source_id == prefix
                or row["mode"] != "record_only"
                or digest(canonical(row["content"])) != row["sha256"]
            ):
                raise ValueError("Invalid or duplicate inventory record")
            sources.add(source_id)
            counts[row["kind"]] += 1
            edits[digest(source_id.encode())] = line
            total += len(line)
            if len(edits) >= 512 or total >= BLOCK_SIZE:
                batches.append(dict(write_verified(store, tenant, actor, edits), order=list(edits)))
                edits = {}
                total = 0
    if dict(counts) != report["counts"] or checksum.hexdigest() != report["records_sha256"]:
        raise ValueError("Inventory counts or stream checksum mismatch")
    if edits:
        batches.append(dict(write_verified(store, tenant, actor, edits), order=list(edits)))
    binaries = {}
    for source_id, (path, expected) in sorted((artifacts or {}).items()):
        checksum = hashlib.sha256()
        blocks = []
        with Path(path).open("rb") as stream:
            while block := stream.read(BLOCK_SIZE):
                checksum.update(block)
                blocks.append(write_verified(store, tenant, actor, {"bytes": block}))
        if checksum.hexdigest() != expected:
            raise ValueError("Binary source checksum mismatch")
        binaries[source_id] = {"sha256": expected, "blocks": blocks}
    catalog = {"version": 1, "report": report, "record_batches": batches, "binaries": binaries}
    catalog_bytes = canonical(catalog)
    module = "migration-" + digest(canonical({"catalog.json": digest(catalog_bytes)}))
    from migration_status import prepare_import, stamp_import

    prepare_import(database, tenant, module)
    pointer = write_verified(store, tenant, actor, {"catalog.json": catalog_bytes})

    stamp_import(database, tenant, **pointer)
    return dict(
        pointer,
        counts=dict(counts),
        binary_count=len(binaries),
    )


def restore_inventory(database, tenant, module, revision, output):
    """Rebuild the archived report, exact input stream and binaries in a new directory."""
    import tempfile

    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError(output)
    database = Path(database).resolve()
    if not database.is_file():
        raise FileNotFoundError(database)
    store = NativeStore(database)

    def read(pointer, key):
        return store.read(tenant, pointer["module"], pointer["revision"], key)

    catalog = json.loads(store.read(tenant, module, revision, "catalog.json"))
    report = catalog["report"]
    if catalog["version"] != 1 or report["historical_policy"] != "record_only":
        raise ValueError("Unsupported history catalog")
    with tempfile.TemporaryDirectory(dir=output.parent) as staging:
        target = Path(staging) / "result"
        target.mkdir()
        counts = Counter()
        checksum = hashlib.sha256()
        with (target / "records.jsonl").open("xb") as stream:
            for batch in catalog["record_batches"]:
                for name in batch["order"]:
                    line = read(batch, name)
                    row = json.loads(line)
                    if (
                        digest(row["source_id"].encode()) != name
                        or row["mode"] != "record_only"
                        or digest(canonical(row["content"])) != row["sha256"]
                    ):
                        raise ValueError("Archived record identity or contents differ")
                    counts[row["kind"]] += 1
                    checksum.update(line)
                    stream.write(line)
        if checksum.hexdigest() != report["records_sha256"] or dict(counts) != report["counts"]:
            raise ValueError("Restored inventory differs from source")
        (target / "report.json").write_bytes(canonical(report) + b"\n")
        files = {}
        for source_id, binary in catalog["binaries"].items():
            name = "binary-" + digest(source_id.encode())
            checksum = hashlib.sha256()
            with (target / name).open("xb") as stream:
                for pointer in binary["blocks"]:
                    data = read(pointer, "bytes")
                    stream.write(data)
                    checksum.update(data)
            if checksum.hexdigest() != binary["sha256"]:
                raise ValueError("Restored binary differs from source")
            files[source_id] = {"file": name, "sha256": checksum.hexdigest()}
        (target / "binaries.json").write_bytes(canonical(files) + b"\n")
        target.rename(output)
    return {"counts": dict(counts), "records_sha256": report["records_sha256"], "binaries": files}
