"""Git-independent module revisions. Trusted hosts supply authenticated identities.

This store receives content and resolves composition candidates, not approvals or
production releases. No model, compiler, network, or subprocess runs in a write
transaction. Database paths are explicit absolute host paths; object names never
become host paths. Each operation opens its own SQLite connection.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any


class NativeStoreError(ValueError):
    """Invalid input or unavailable revision."""


class Conflict(NativeStoreError):
    """Changed inputs or a reused request key with different content."""


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _identifier(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", value):
        raise NativeStoreError("Invalid identity")
    return value


def _revision_id(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value):
        raise NativeStoreError("Invalid revision")
    return value


def _object_name(value: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 1024
        or "\\" in value
        or ":" in value
        or any(ord(char) < 32 for char in value)
        or any(part in {"", ".", ".."} for part in value.split("/"))
    ):
        raise NativeStoreError("Invalid logical object name")
    return value


SCHEMA = """
CREATE TABLE IF NOT EXISTS native_blobs (
  tenant TEXT NOT NULL, digest TEXT NOT NULL, content BLOB NOT NULL,
  PRIMARY KEY (tenant,digest)
);
CREATE TABLE IF NOT EXISTS native_revisions (
  tenant TEXT NOT NULL, id TEXT NOT NULL, module TEXT NOT NULL, payload TEXT NOT NULL,
  PRIMARY KEY (tenant,id)
);
CREATE TABLE IF NOT EXISTS native_heads (
  tenant TEXT NOT NULL, module TEXT NOT NULL, revision TEXT NOT NULL,
  PRIMARY KEY (tenant,module),
  FOREIGN KEY (tenant,revision) REFERENCES native_revisions(tenant,id)
);
CREATE TABLE IF NOT EXISTS native_receipts (
  tenant TEXT NOT NULL, actor TEXT NOT NULL, request_key TEXT NOT NULL,
  request_digest TEXT NOT NULL, result TEXT NOT NULL,
  PRIMARY KEY (tenant,actor,request_key)
);
CREATE TABLE IF NOT EXISTS native_compositions (
  tenant TEXT NOT NULL, id TEXT NOT NULL, payload TEXT NOT NULL,
  PRIMARY KEY (tenant,id)
);
"""


def prepare_changes(changes: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, bytes]]:
    """Pure canonical validation shared by immediate submission and intake."""
    if not isinstance(changes, list) or not 1 <= len(changes) <= 128:
        raise NativeStoreError("Expected 1..128 module changes")
    prepared: dict[str, dict[str, Any]] = {}
    blobs: dict[str, bytes] = {}
    for change in changes:
        if not isinstance(change, dict) or set(change) - {"module", "base", "reads", "edits", "dependencies"}:
            raise NativeStoreError("Invalid change fields")
        if not {"module", "base", "reads", "edits"} <= set(change):
            raise NativeStoreError("Change is missing explicit base/read/write inputs")
        module = _identifier(change["module"])
        if module in prepared:
            raise NativeStoreError("Repeated module in batch")
        base = change["base"]
        if base is not None:
            _revision_id(base)
        reads = change["reads"]
        if reads is not None and not isinstance(reads, list):
            raise NativeStoreError("Reads must be a list or null (unknown)")
        reads = None if reads is None else sorted({_object_name(name) for name in reads})
        if not isinstance(change["edits"], dict):
            raise NativeStoreError("Edits must be a mapping")
        edits: dict[str, str | None] = {}
        for name, data in change["edits"].items():
            _object_name(name)
            if data is not None and not isinstance(data, bytes):
                raise NativeStoreError("Object content must be bytes or null")
            digest = None if data is None else _digest(data)
            edits[name] = digest
            if digest is not None and data is not None:
                blobs[digest] = data
        item = {"module": module, "base": base, "reads": reads, "edits": edits}
        if "dependencies" in change:
            deps = change["dependencies"]
            if not isinstance(deps, dict):
                raise NativeStoreError("Dependencies must be a mapping")
            for name, revision in deps.items():
                _identifier(name)
                if name == module:
                    raise NativeStoreError("Self dependency")
                if revision != "@batch":
                    _revision_id(revision)
            item["dependencies"] = dict(deps)
        prepared[module] = item
    return prepared, blobs


class NativeStore:
    def __init__(self, database: str | Path):
        self.database = Path(database)
        if not self.database.is_absolute():
            raise NativeStoreError("Database path must be absolute")
        # Parent creation belongs to the host; do not implicitly select a root.
        with self._connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript(SCHEMA)

    @contextmanager
    def _connection(self, *, write: bool = False) -> Generator[sqlite3.Connection, None, None]:
        db = sqlite3.connect(str(self.database), timeout=30, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            if write:
                db.execute("BEGIN IMMEDIATE")
            yield db
            if write:
                db.commit()
        except BaseException:
            if write:
                db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _revision(db: sqlite3.Connection, tenant: str, module: str, revision: str) -> dict[str, Any]:
        _revision_id(revision)
        row = db.execute(
            "SELECT payload FROM native_revisions WHERE tenant=? AND module=? AND id=?",
            (tenant, module, revision),
        ).fetchone()
        if row is None:
            raise NativeStoreError("Revision unavailable in this tenant/module")
        if _digest(row["payload"].encode("utf-8")) != revision:
            raise NativeStoreError("Revision integrity failure")
        result: dict[str, Any] = json.loads(row["payload"])
        return result

    def head(self, tenant: str, module: str) -> str | None:
        _identifier(tenant)
        _identifier(module)
        with self._connection() as db:
            row = db.execute(
                "SELECT revision FROM native_heads WHERE tenant=? AND module=?", (tenant, module)
            ).fetchone()
            return None if row is None else row["revision"]

    def revision(self, tenant: str, module: str, revision: str) -> dict[str, Any]:
        _identifier(tenant)
        _identifier(module)
        with self._connection() as db:
            return self._revision(db, tenant, module, revision)

    def read(self, tenant: str, module: str, revision: str, name: str) -> bytes:
        _identifier(tenant)
        _identifier(module)
        _object_name(name)
        with self._connection() as db:
            state = self._revision(db, tenant, module, revision)
            digest = state["objects"].get(name)
            row = db.execute(
                "SELECT content FROM native_blobs WHERE tenant=? AND digest=?", (tenant, digest)
            ).fetchone()
            if row is None:
                raise NativeStoreError("Object unavailable")
            content = bytes(row["content"])
            if _digest(content) != digest:
                raise NativeStoreError("Object integrity failure")
            return content

    def submit(self, tenant: str, actor: str, request_key: str, changes: list[dict[str, Any]]) -> dict[str, Any]:
        """Atomically receive module changes, rebasing only unchanged read/write sets.

        Each change: module, base (null for creation), reads (list or null for
        unknown), edits (logical name -> bytes or null for deletion), and optional
        dependencies (module -> immutable revision or @batch for this batch).
        Hosts must establish read-set completeness; an empty list is an explicit
        claim, not proof. Omitted dependencies retain the base dependency set.
        """
        _identifier(tenant)
        _identifier(actor)
        _identifier(request_key)
        prepared, blobs = prepare_changes(changes)
        request_digest = _digest(_json(prepared).encode("utf-8"))
        with self._connection(write=True) as db:
            prior = db.execute(
                "SELECT request_digest,result FROM native_receipts WHERE tenant=? AND actor=? AND request_key=?",
                (tenant, actor, request_key),
            ).fetchone()
            if prior is not None:
                if prior["request_digest"] != request_digest:
                    raise Conflict("Request key already used for different content")
                previous_result: dict[str, Any] = json.loads(prior["result"])
                return previous_result
            states: dict[str, dict[str, Any]] = {}
            for module, item in prepared.items():
                row = db.execute(
                    "SELECT revision FROM native_heads WHERE tenant=? AND module=?", (tenant, module)
                ).fetchone()
                current = None if row is None else row["revision"]
                if item["base"] is None:
                    if current is not None:
                        raise Conflict(f"Module already exists: {module}")
                    base: dict[str, Any] = {"objects": {}, "dependencies": {}}
                else:
                    base = self._revision(db, tenant, module, item["base"])
                    if current is None:
                        raise Conflict(f"Module head unavailable: {module}")
                # Unknown reads cannot reuse any drifted head. Reject using the
                # transaction's head identity before loading unneeded metadata.
                if current != item["base"] and item["reads"] is None:
                    raise Conflict(f"Unknown read dependencies after module drift: {module}")
                if current == item["base"]:
                    latest = base
                elif current is not None:
                    latest = self._revision(db, tenant, module, current)
                else:
                    raise Conflict(f"Module head unavailable: {module}")
                if current != item["base"]:
                    touched = set(item["reads"]) | set(item["edits"])
                    conflicts = sorted(
                        name for name in touched if base["objects"].get(name) != latest["objects"].get(name)
                    )
                    if conflicts or base["dependencies"] != latest["dependencies"]:
                        raise Conflict(f"Changed inputs in {module}: {conflicts or ['dependencies']}")
                objects = dict(latest["objects"])
                for name, digest in item["edits"].items():
                    if digest is None:
                        objects.pop(name, None)
                    else:
                        objects[name] = digest
                # File/directory collisions must not become invalid materialized trees.
                for name in objects:
                    parts = name.split("/")
                    if any("/".join(parts[:index]) in objects for index in range(1, len(parts))):
                        raise Conflict(f"Object prefix collision in {module}: {name}")
                states[module] = {
                    "module": module,
                    "parent": current,
                    "objects": objects,
                    "dependencies": dict(item.get("dependencies", base["dependencies"])),
                }
            revisions: dict[str, str] = {}
            visiting: set[str] = set()

            def save(module: str) -> str:
                if module in revisions:
                    return revisions[module]
                if module in visiting or module not in states:
                    raise NativeStoreError("Cyclic or missing @batch dependency")
                visiting.add(module)
                state = states[module]
                for dependency, revision in list(state["dependencies"].items()):
                    if revision == "@batch":
                        revision = save(dependency)
                        state["dependencies"][dependency] = revision
                    self._revision(db, tenant, dependency, revision)
                payload = _json(state)
                revision = _digest(payload.encode("utf-8"))
                db.execute("INSERT INTO native_revisions VALUES (?,?,?,?)", (tenant, revision, module, payload))
                db.execute(
                    "INSERT INTO native_heads VALUES (?,?,?) ON CONFLICT(tenant,module) DO UPDATE SET revision=excluded.revision",
                    (tenant, module, revision),
                )
                revisions[module] = revision
                visiting.remove(module)
                return revision

            for digest, content in blobs.items():
                existing = db.execute(
                    "SELECT content FROM native_blobs WHERE tenant=? AND digest=?", (tenant, digest)
                ).fetchone()
                if existing is not None and bytes(existing["content"]) != content:
                    raise NativeStoreError("Object integrity failure on deduplication")
                db.execute("INSERT OR IGNORE INTO native_blobs VALUES (?,?,?)", (tenant, digest, content))
            for module in states:
                save(module)
            result = {"state": "received", "revisions": revisions, "request_digest": request_digest}
            db.execute(
                "INSERT INTO native_receipts VALUES (?,?,?,?,?)",
                (tenant, actor, request_key, request_digest, _json(result)),
            )
            return result

    def compose(self, tenant: str, selected: Mapping[str, str]) -> dict[str, Any]:
        """Resolve exact dependency closure; persist a candidate, never a release."""
        _identifier(tenant)
        if not isinstance(selected, dict) or not selected:
            raise NativeStoreError("Select at least one module revision")
        pending = [(_identifier(module), _revision_id(revision)) for module, revision in selected.items()]
        resolved: dict[str, str] = {}
        with self._connection(write=True) as db:
            while pending:
                module, revision = pending.pop()
                if module in resolved:
                    if resolved[module] != revision:
                        raise Conflict(f"Incompatible pinned revisions for {module}")
                    continue
                state = self._revision(db, tenant, module, revision)
                resolved[module] = revision
                pending.extend(state["dependencies"].items())
            payload = _json({"state": "candidate", "modules": resolved})
            candidate = _digest(payload.encode("utf-8"))
            db.execute("INSERT OR IGNORE INTO native_compositions VALUES (?,?,?)", (tenant, candidate, payload))
            return {"id": candidate, **json.loads(payload)}


class NativeContextStorage:
    """Execution-local bounded index and authenticated ranges over immutable sources.

    Cold verification reads a whole blob once in 8192-byte blocks. Only block
    hashes survive; warm reads authenticate every touched block. No cache is
    shared across contexts, tenants, revisions or database identities.
    """

    BLOCK = 8192
    MAX_OBJECT = 2 * 1024 * 1024
    MAX_SOURCE = 8 * 1024 * 1024
    MAX_METADATA = 1024 * 1024
    MAX_OBJECTS = 4096
    MAX_REVISIONS = 128

    def __init__(self, store, tenant, revisions, execution):
        self.store, self.tenant, self.execution = store, _identifier(tenant), execution
        self.owner = store.database.stat()
        self.states, self.lengths, self.hashes = {}, {}, {}
        self.io = {"metadata_bytes": 0, "body_bytes": 0, "cold_verifications": 0}
        self.source_bytes = 0
        revisions = sorted(set(revisions))
        if len(revisions) > self.MAX_REVISIONS:
            raise NativeStoreError("Context revision budget exceeded")
        with store._connection() as db:
            db.execute("PRAGMA cache_size=-256")
            db.execute("PRAGMA mmap_size=0")
            db.execute("BEGIN")
            for module, revision in revisions:
                _identifier(module)
                _revision_id(revision)
                size = db.execute(
                    "SELECT length(CAST(payload AS BLOB)) FROM native_revisions WHERE tenant=? AND module=? AND id=?",
                    (tenant, module, revision),
                ).fetchone()
                if size is None:
                    raise NativeStoreError("Revision unavailable in this tenant/module")
                if self.io["metadata_bytes"] + size[0] > self.MAX_METADATA:
                    raise NativeStoreError("Context metadata budget exceeded")
                self.io["metadata_bytes"] += size[0]
                state = store._revision(db, tenant, module, revision)
                if sum(len(s["objects"]) for s in self.states.values()) + len(state["objects"]) > self.MAX_OBJECTS:
                    raise NativeStoreError("Context object count budget exceeded")
                self.states[module, revision] = state
                for name, sha in state["objects"].items():
                    _object_name(name)
                    row = db.execute(
                        "SELECT length(content) FROM native_blobs WHERE tenant=? AND digest=?", (tenant, sha)
                    ).fetchone()
                    if row is None or row[0] > self.MAX_OBJECT:
                        raise NativeStoreError("Context object budget exceeded or unavailable")
                    self.source_bytes += row[0]
                    if self.source_bytes > self.MAX_SOURCE:
                        raise NativeStoreError("Context source budget exceeded")
                    self.lengths[module, revision, name] = row[0]
        self.manifest = [
            dict(
                module=m,
                revision=r,
                name=n,
                object_digest=sha,
                byte_length=self.lengths[m, r, n],
                encoding_hint="unknown",
            )
            for (m, r), state in sorted(self.states.items())
            for n, sha in sorted(state["objects"].items())
        ]

    def _identity(self):
        now = self.store.database.stat()
        if (now.st_dev, now.st_ino) != (self.owner.st_dev, self.owner.st_ino):
            self.hashes.clear()
            raise NativeStoreError("Context database identity changed")

    def read_range(self, module, revision, name, offset, length):
        self._identity()
        key = (module, revision, name)
        total = self.lengths[key]
        if (
            type(offset) is not int
            or type(length) is not int
            or not 0 <= offset <= total
            or not 1 <= length <= self.BLOCK
        ):
            raise NativeStoreError("Invalid bounded range")
        sha = self.states[module, revision]["objects"][name]
        with self.store._connection() as db:
            db.execute("PRAGMA cache_size=-256")
            db.execute("PRAGMA mmap_size=0")
            db.execute("BEGIN")
            row = db.execute(
                "SELECT rowid,length(content) FROM native_blobs WHERE tenant=? AND digest=?", (self.tenant, sha)
            ).fetchone()
            if row is None or row[1] != total:
                self.hashes.pop(key, None)
                raise NativeStoreError("Object identity/length changed")
            with db.blobopen("native_blobs", "content", row[0], readonly=True) as blob:
                if key not in self.hashes:
                    whole, blocks = hashlib.sha256(), []
                    for start in range(0, total, self.BLOCK):
                        chunk = blob.read(min(self.BLOCK, total - start))
                        self.io["body_bytes"] += len(chunk)
                        whole.update(chunk)
                        blocks.append(_digest(chunk))
                    if whole.hexdigest() != sha:
                        raise NativeStoreError("Object integrity failure")
                    self.hashes[key] = blocks
                    self.io["cold_verifications"] += 1
                end = min(total, offset + length)
                result = bytearray()
                for index in range(offset // self.BLOCK, (end + self.BLOCK - 1) // self.BLOCK):
                    start = index * self.BLOCK
                    blob.seek(start)
                    chunk = blob.read(min(self.BLOCK, total - start))
                    self.io["body_bytes"] += len(chunk)
                    if _digest(chunk) != self.hashes[key][index]:
                        self.hashes.pop(key, None)
                        raise NativeStoreError("Object chunk integrity failure")
                    result.extend(chunk[max(offset - start, 0) : min(end - start, len(chunk))])
        self._identity()
        return bytes(result), total
