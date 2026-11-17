"""Immutable, bounded candidate intake for trusted local hosts (never publication)."""

from __future__ import annotations

import json
from contextlib import contextmanager

from native_store import Conflict, NativeStore, NativeStoreError, _digest, _identifier, _json, prepare_changes
from native_workspace import Limits, NativeWorkspace, portable

SCHEMA = """
CREATE TABLE IF NOT EXISTS native_candidate_receipts (
 tenant TEXT NOT NULL, actor TEXT NOT NULL, request_key TEXT NOT NULL,
 request_digest TEXT NOT NULL, result TEXT NOT NULL,
 PRIMARY KEY(tenant,actor,request_key));
"""


class _SnapshotStore(NativeStore):
    def __init__(self, db, allow):
        self.db, self.allow = db, allow

    @contextmanager
    def _connection(self, *, write=False):
        if write:
            raise NativeStoreError("Read-only candidate snapshot")
        yield self.db

    def _revision(self, db, tenant, module, revision):
        self.allow(module, "read")
        return NativeStore._revision(db, tenant, module, revision)


class NativeCandidates:
    """Authority(db, tenant, actor, module, action) must return exactly True.

    Identity and origin are authenticated host inputs, never workspace claims.
    Authority must be local and short; use db for mutable authorization state.
    """

    def __init__(self, store, authorize, limits=None):
        if not callable(authorize):
            raise NativeStoreError("Explicit host authority required")
        self.store, self.authorize = store, authorize
        self.limits = limits or Limits()
        with store._connection() as db:
            db.executescript(SCHEMA)

    def _allow(self, db, tenant, actor, module, action):
        if self.authorize(db, tenant, actor, module, action) is not True:
            raise NativeStoreError("Host authorization denied")

    def _prepare(self, changes):
        limits = self.limits
        if not isinstance(changes, list) or not 1 <= len(changes) <= limits.modules:
            raise NativeStoreError("Module count exceeds limit")
        count = total = reads = 0
        for change in changes:
            if not isinstance(change, dict) or not isinstance(change.get("edits"), dict):
                raise NativeStoreError("Expected change with edits")
            portable(change.get("module"))
            deps = change.get("dependencies", {})
            if not isinstance(deps, dict) or len(deps) > limits.modules:
                raise NativeStoreError("Dependency count exceeds limit")
            for name in deps:
                portable(name)
            names = change.get("reads")
            if names is not None:
                if not isinstance(names, list):
                    raise NativeStoreError("Reads must be list or null")
                reads += len(names)
                if reads > limits.files:
                    raise NativeStoreError("Read count exceeds limit")
                for name in names:
                    portable(name)
            count += len(change["edits"])
            if count > limits.files:
                raise NativeStoreError("Edit count exceeds limit")
            for name, content in change["edits"].items():
                portable(name)
                if content is not None:
                    if not isinstance(content, bytes) or len(content) > limits.file_bytes:
                        raise NativeStoreError("Object size/type exceeds limit")
                    total += len(content)
                    if total > limits.total_bytes:
                        raise NativeStoreError("Input bytes exceed limit")
        prepared, blobs = prepare_changes(changes)
        if len(_json(prepared).encode()) > limits.request_bytes:
            raise NativeStoreError("Request metadata exceeds limit")
        return prepared, blobs

    def receive(self, tenant, actor, request_key, changes, origin):
        for value in (tenant, actor, request_key):
            _identifier(value)
        if not isinstance(origin, dict) or set(origin) != {"source_ref", "worker_ref", "issue_url"}:
            raise NativeStoreError("Exact host origin required")
        if any(not isinstance(v, str) or not v.strip() or len(v) > 2048 for v in origin.values()):
            raise NativeStoreError("Bounded nonempty origin fields required")
        origin = dict(origin)
        prepared, blobs = self._prepare(changes)
        request = {"changes": prepared, "origin": origin}
        digest = _digest(_json(request).encode())
        with self.store._connection(write=True) as db:

            def allow(module, action):
                self._allow(db, tenant, actor, module, action)

            for module in prepared:
                allow(module, "receive")
            prior = db.execute(
                "SELECT request_digest,result FROM native_candidate_receipts WHERE tenant=? AND actor=? AND request_key=?",
                (tenant, actor, request_key),
            ).fetchone()
            if prior:
                if prior["request_digest"] != digest:
                    raise Conflict("Candidate request key already used for different input")
                return self._verified_receipt(db, tenant, actor, request_key, prior)
            workspace = NativeWorkspace(_SnapshotStore(db, allow), self.limits)
            states = {}
            for module, item in prepared.items():
                base = {"objects": {}, "dependencies": {}}
                if item["base"] is not None:
                    _, baseline = workspace.sources(tenant, {module: item["base"]})
                    base = baseline[module]
                objects = dict(base["objects"])
                for name, content in item["edits"].items():
                    if content is None:
                        objects.pop(name, None)
                    else:
                        objects[name] = content
                states[module] = {
                    "module": module,
                    "parent": item["base"],
                    "objects": objects,
                    "dependencies": dict(item.get("dependencies", base["dependencies"])),
                }
            for blob, content in blobs.items():
                previous = db.execute(
                    "SELECT content FROM native_blobs WHERE tenant=? AND digest=?", (tenant, blob)
                ).fetchone()
                if previous is not None and bytes(previous[0]) != content:
                    raise NativeStoreError("Object integrity failure on deduplication")
                db.execute("INSERT OR IGNORE INTO native_blobs VALUES (?,?,?)", (tenant, blob, content))
            revisions, visiting = {}, set()

            def save(module):
                if module in revisions:
                    return revisions[module]
                if module in visiting or module not in states:
                    raise NativeStoreError("Cyclic or missing @batch dependency")
                visiting.add(module)
                state = states[module]
                for dependency, revision in list(state["dependencies"].items()):
                    if revision == "@batch":
                        state["dependencies"][dependency] = save(dependency)
                payload = _json(state)
                if len(payload.encode()) > self.limits.request_bytes:
                    raise NativeStoreError("Revision metadata exceeds limit")
                revision = _digest(payload.encode())
                previous = db.execute(
                    "SELECT module,payload FROM native_revisions WHERE tenant=? AND id=?", (tenant, revision)
                ).fetchone()
                if previous is not None and (previous[0] != module or previous[1] != payload):
                    raise NativeStoreError("Revision integrity failure on deduplication")
                db.execute(
                    "INSERT OR IGNORE INTO native_revisions VALUES (?,?,?,?)", (tenant, revision, module, payload)
                )
                revisions[module] = revision
                visiting.remove(module)
                return revision

            for module in states:
                save(module)
            # Validate complete exact closure and original blobs in this same transaction.
            workspace.sources(tenant, revisions)
            result = {
                "state": "candidate_received",
                "tenant": tenant,
                "actor": actor,
                "request_key": request_key,
                "request_digest": digest,
                "origin": origin,
                "inputs": prepared,
                "revisions": revisions,
                "requires_final_composition_validation": True,
            }
            result["id"] = _digest(_json(result).encode())
            db.execute(
                "INSERT INTO native_candidate_receipts VALUES (?,?,?,?,?)",
                (tenant, actor, request_key, digest, _json(result)),
            )
            return result

    def _verified_receipt(self, db, tenant, actor, request_key, row):
        try:
            result = json.loads(row["result"])
            required = {
                "state",
                "tenant",
                "actor",
                "request_key",
                "request_digest",
                "origin",
                "inputs",
                "revisions",
                "requires_final_composition_validation",
                "id",
            }
            if (
                not isinstance(result, dict)
                or set(result) != required
                or result["state"] != "candidate_received"
                or (result["tenant"], result["actor"], result["request_key"]) != (tenant, actor, request_key)
                or result["requires_final_composition_validation"] is not True
                or not isinstance(result["inputs"], dict)
                or not isinstance(result["revisions"], dict)
                or not result["inputs"]
                or set(result["inputs"]) != set(result["revisions"])
                or not isinstance(result["origin"], dict)
                or set(result["origin"]) != {"source_ref", "worker_ref", "issue_url"}
                or any(not isinstance(v, str) or not v.strip() or len(v) > 2048 for v in result["origin"].values())
                or result["request_digest"] != row["request_digest"]
                or result["request_digest"]
                != _digest(_json({"changes": result["inputs"], "origin": result["origin"]}).encode())
                or result["id"] != _digest(_json({k: v for k, v in result.items() if k != "id"}).encode())
            ):
                raise NativeStoreError("Candidate receipt integrity failure")
            # Recheck original input and final output closures. A dependency removed
            # by this contribution can still occur in the original input metadata.
            workspace = NativeWorkspace(
                _SnapshotStore(db, lambda module, action: self._allow(db, tenant, actor, module, action)), self.limits
            )
            for module, item in result["inputs"].items():
                self._allow(db, tenant, actor, module, "read")
                if item["base"] is not None:
                    workspace.sources(tenant, {module: item["base"]})
            workspace.sources(tenant, result["revisions"])
            return result
        except NativeStoreError:
            raise
        except (KeyError, TypeError, ValueError, RecursionError) as error:
            raise NativeStoreError("Candidate receipt integrity failure") from error

    def receipt(self, tenant, actor, request_key):
        for value in (tenant, actor, request_key):
            _identifier(value)
        with self.store._connection() as db:
            db.execute("BEGIN")
            row = db.execute(
                "SELECT request_digest,result FROM native_candidate_receipts WHERE tenant=? AND actor=? AND request_key=?",
                (tenant, actor, request_key),
            ).fetchone()
            if row is None:
                raise NativeStoreError("Candidate receipt unavailable")
            return self._verified_receipt(db, tenant, actor, request_key, row)
