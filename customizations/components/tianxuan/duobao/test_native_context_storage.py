"""Bounded trusted-storage evidence, independent of provider/model services."""

import hashlib
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sinan-workorders"))
from native_context import NativeContext
from native_store import NativeContextStorage, NativeStore


def setup(tmp_path, edits):
    store = NativeStore(tmp_path / "objects.sqlite")
    revision = store.submit("tenant", "actor", "first", [dict(module="code", base=None, reads=None, edits=edits)])[
        "revisions"
    ]["code"]
    binding = dict(
        execution="a" * 64,
        tenant="tenant",
        actor="actor",
        producer="producer",
        source_digest="source",
        installation_digest="installed",
        selected={"code": revision},
        limits=dict(response_bytes=16384, chunk_bytes=8192, total_bytes=8388608, max_reads=20),
    )
    return store, revision, binding


def test_metadata_pages_and_measured_cold_warm_io(tmp_path):
    store, revision, binding = setup(tmp_path, {f"f{i:03}.bin": bytes([i]) * 65536 for i in range(120)})
    c = NativeContext(store, lambda *a: True, binding, tmp_path / "ledger.sqlite")
    store.read = lambda *a: pytest.fail("Whole body API must not be used")
    cursor, count = None, 0
    while True:
        result = c.resolve(dict(op="manifest", cursor=cursor))
        count += len(result["content"])
        assert c.storage().io["body_bytes"] == 0
        cursor = result["next_cursor"]
        if cursor is None:
            break
    assert count == 120
    storage = c.storage()
    assert storage.read_range("code", revision, "f000.bin", 0, 2) == (b"\0\0", 65536)
    assert storage.io["body_bytes"] == 65536 + 8192
    before = storage.io["body_bytes"]
    storage.read_range("code", revision, "f000.bin", 1, 2)
    assert storage.io["body_bytes"] - before == 8192
    assert storage.io["cold_verifications"] == 1
    # Each execution starts cold; no authority/cache inheritance.
    other = NativeContextStorage(store, "tenant", [("code", revision)], "other")
    other.read_range("code", revision, "f000.bin", 0, 2)
    assert other.io["cold_verifications"] == 1
    with pytest.raises(ValueError):
        NativeContextStorage(store, "other", [("code", revision)], "other")


@pytest.mark.parametrize("warm", [False, True])
def test_corruption_is_rejected(tmp_path, warm):
    store, revision, _ = setup(tmp_path, {"f": b"a" * 65536})
    cache = NativeContextStorage(store, "tenant", [("code", revision)], "execution")
    if warm:
        cache.read_range("code", revision, "f", 0, 2)
    sha = hashlib.sha256(b"a" * 65536).hexdigest()
    with sqlite3.connect(store.database) as db:
        db.execute("UPDATE native_blobs SET content=? WHERE tenant=? AND digest=?", (b"b" * 65536, "tenant", sha))
    with pytest.raises(ValueError, match="integrity"):
        cache.read_range("code", revision, "f", 0, 2)
    assert not cache.hashes


def test_old_endpoint_budget_before_operation(tmp_path):
    store, old, binding = setup(tmp_path, {"large": b"a" * (2097152 + 1)})
    new = store.submit(
        "tenant", "actor", "next", [dict(module="code", base=old, reads=None, edits={"large": b"small"})]
    )["revisions"]["code"]
    c = NativeContext(
        store,
        lambda *a: True,
        {**binding, "selected": {"code": new}, "allowed_delta_pairs": [dict(module="code", before=old, after=new)]},
        tmp_path / "ledger.sqlite",
    )
    with pytest.raises(ValueError, match="budget"):
        c.check("launch")
    with pytest.raises(ValueError, match="budget"):
        c.resolve(dict(op="manifest", cursor=None))
    assert c.events() == []


def test_revision_and_database_identity_isolation(tmp_path):
    store, old, _ = setup(tmp_path, {"f": b"abcdef"})
    new = store.submit("tenant", "actor", "next", [dict(module="code", base=old, reads=None, edits={"f": b"ABCDEF"})])[
        "revisions"
    ]["code"]
    cache = NativeContextStorage(store, "tenant", [("code", old), ("code", new)], "execution")
    assert cache.read_range("code", old, "f", 0, 2)[0] == b"ab"
    assert cache.read_range("code", new, "f", 0, 2)[0] == b"AB"
    assert cache.io["cold_verifications"] == 2
    store.database.rename(tmp_path / "old.sqlite")
    NativeStore(store.database)
    with pytest.raises(ValueError, match="identity"):
        cache.read_range("code", old, "f", 0, 2)
    assert not cache.hashes


@pytest.mark.parametrize("kind", ["source", "metadata", "count"])
def test_budget_admission_without_body_io(tmp_path, kind):
    edits = {"f": b"x"}
    if kind == "source":
        edits = {str(i): b"a" * 2097152 for i in range(5)}
    elif kind == "metadata":
        edits = {str(i) + "x" * 1000: b"" for i in range(1050)}
    else:
        edits = {str(i): b"" for i in range(4097)}
    store, revision, binding = setup(tmp_path, edits)
    c = NativeContext(store, lambda *a: True, binding, tmp_path / "ledger.sqlite")
    with pytest.raises(ValueError, match="budget"):
        c.check("launch")
    with pytest.raises(ValueError, match="budget"):
        c.resolve(dict(op="manifest", cursor=None))
    assert c.events() == []


def test_boundary_range_length_change_and_metadata_integrity(tmp_path):
    data = bytes(range(256)) * 100
    store, revision, _ = setup(tmp_path, {"f": data})
    cache = NativeContextStorage(store, "tenant", [("code", revision)], "execution")
    assert cache.read_range("code", revision, "f", 8191, 2)[0] == data[8191:8193]
    before = cache.io["body_bytes"]
    cache.read_range("code", revision, "f", 8191, 2)
    assert cache.io["body_bytes"] - before == 16384
    with sqlite3.connect(store.database) as db:
        db.execute("UPDATE native_blobs SET content=?", (b"x",))
    with pytest.raises(ValueError, match="length"):
        cache.read_range("code", revision, "f", 0, 2)
    assert not cache.hashes
    with sqlite3.connect(store.database) as db:
        db.execute("UPDATE native_revisions SET payload=?", ("{}",))
    with pytest.raises(ValueError, match="integrity"):
        NativeContextStorage(store, "tenant", [("code", revision)], "execution")
