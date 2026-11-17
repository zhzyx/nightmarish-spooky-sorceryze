"""Input-addressed check evidence for a trusted host, never release approval.

Hosts install check scopes and authenticate runners. Callers select a check ID;
they cannot replace its scope with their own declarations. Unknown scopes bind
the whole immutable composition. Logs are supplied by the authorized runner.
No check or model executes while a database write transaction is held.
"""

from __future__ import annotations

import json
import math
import time
from collections.abc import Callable, Mapping
from typing import Any

from native_store import (
    Conflict,
    NativeStore,
    NativeStoreError,
    _digest,
    _identifier,
    _json,
    _object_name,
    _revision_id,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS native_check_evidence (
  sequence INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant TEXT NOT NULL, id TEXT NOT NULL, cache_key TEXT NOT NULL,
  payload TEXT NOT NULL, log BLOB NOT NULL,
  UNIQUE (tenant,id)
);
CREATE INDEX IF NOT EXISTS native_check_lookup
  ON native_check_evidence (tenant,cache_key,sequence DESC);
CREATE TABLE IF NOT EXISTS native_check_requests (
  tenant TEXT NOT NULL, actor TEXT NOT NULL, request_key TEXT NOT NULL,
  request_digest TEXT NOT NULL, evidence_id TEXT NOT NULL,
  PRIMARY KEY (tenant,actor,request_key)
);
CREATE TABLE IF NOT EXISTS native_check_revocations (
  tenant TEXT NOT NULL, evidence_id TEXT NOT NULL, payload TEXT NOT NULL,
  PRIMARY KEY (tenant,evidence_id)
);
"""


class EvidenceCache:
    def __init__(
        self,
        store: NativeStore,
        policies: Mapping[str, dict[str, Any]],
        authorize: Callable[[str, str, str, str], bool],
        clock: Callable[[], float] = time.time,
    ):
        if not callable(authorize) or not isinstance(policies, dict) or not policies:
            raise NativeStoreError("Trusted runner authorization and check policies are required")
        self.store = store
        self.authorize = authorize
        self.clock = clock
        self.policies: dict[str, dict[str, Any]] = {}
        for check_id, policy in policies.items():
            _identifier(check_id)
            if not isinstance(policy, dict) or set(policy) != {"version", "reads", "max_age_seconds"}:
                raise NativeStoreError("Check policy needs version, reads and max_age_seconds")
            _identifier(policy["version"])
            age = policy["max_age_seconds"]
            if type(age) is not int or not 0 < age <= 31536000:
                raise NativeStoreError("Check evidence lifetime must be 1..31536000 seconds")
            reads = policy["reads"]
            if reads is not None:
                if not isinstance(reads, dict) or not reads or len(reads) > 128:
                    raise NativeStoreError("Expected explicit module read scopes or null for unknown")
                for module, names in reads.items():
                    _identifier(module)
                    if names is not None:
                        if not isinstance(names, list) or len(names) > 4096:
                            raise NativeStoreError("Expected object names or null for whole module")
                        for name in names:
                            _object_name(name)
            # Freeze the host input; mutating the caller's dictionary cannot weaken it.
            self.policies[check_id] = json.loads(_json(policy))
        with self.store._connection() as db:
            db.executescript(SCHEMA)

    def _time(self) -> float:
        now = self.clock()
        if not isinstance(now, (int, float)) or isinstance(now, bool) or not math.isfinite(now) or now < 0:
            raise NativeStoreError("Invalid host clock")
        return float(now)

    def _policy(self, check_id: str) -> dict[str, Any]:
        _identifier(check_id)
        if check_id not in self.policies:
            raise NativeStoreError("Check is not installed by the host")
        return self.policies[check_id]

    def binding(
        self,
        tenant: str,
        candidate: str,
        check_id: str,
        *,
        toolchain: str,
        environment: str,
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        """Build a key from immutable content and the host's installed check scope."""
        _identifier(tenant)
        _revision_id(candidate)
        _revision_id(toolchain)
        _revision_id(environment)
        policy = self._policy(check_id)
        if not isinstance(parameters, dict) or len(_json(parameters).encode("utf-8")) > 65536:
            raise NativeStoreError("Expected bounded JSON check parameters")
        with self.store._connection() as db:
            row = db.execute(
                "SELECT payload FROM native_compositions WHERE tenant=? AND id=?", (tenant, candidate)
            ).fetchone()
            if row is None or _digest(row["payload"].encode("utf-8")) != candidate:
                raise NativeStoreError("Composition unavailable or corrupt")
            modules = json.loads(row["payload"])["modules"]
            scopes = policy["reads"]
            scopes = dict.fromkeys(modules) if scopes is None else scopes
            inputs = {}
            dependencies = []
            for module, names in scopes.items():
                if module not in modules:
                    raise NativeStoreError("Required module is absent from composition")
                state = self.store._revision(db, tenant, module, modules[module])
                # Whole-module / unknown scopes include history identity conservatively.
                selected = list(state["objects"]) if names is None else sorted(set(names))
                objects = {}
                for name in selected:
                    digest = state["objects"].get(name)
                    objects[name] = digest
                    if digest is not None:
                        blob = db.execute(
                            "SELECT content FROM native_blobs WHERE tenant=? AND digest=?", (tenant, digest)
                        ).fetchone()
                        if blob is None or _digest(bytes(blob["content"])) != digest:
                            raise NativeStoreError("Check input integrity failure")
                inputs[module] = {"objects": objects, "dependencies": state["dependencies"]}
                dependencies.extend(state["dependencies"].items())
                if names is None:
                    inputs[module]["revision"] = modules[module]
            # An exact dependency pin includes its content, not just a healthy manifest.
            checked_dependencies = set()
            while dependencies:
                module, revision = dependencies.pop()
                if (module, revision) in checked_dependencies:
                    continue
                if modules.get(module) != revision:
                    raise NativeStoreError("Composition dependency pin mismatch")
                state = self.store._revision(db, tenant, module, revision)
                for digest in state["objects"].values():
                    blob = db.execute(
                        "SELECT content FROM native_blobs WHERE tenant=? AND digest=?", (tenant, digest)
                    ).fetchone()
                    if blob is None or _digest(bytes(blob["content"])) != digest:
                        raise NativeStoreError("Check dependency integrity failure")
                checked_dependencies.add((module, revision))
                dependencies.extend(state["dependencies"].items())
        value = {
            "format": "duobao-check-input/1",
            "check": check_id,
            "policy": _digest(_json(policy).encode("utf-8")),
            "inputs": inputs,
            "toolchain": toolchain,
            "environment": environment,
            "parameters": json.loads(_json(parameters)),
        }
        return {"key": _digest(_json(value).encode("utf-8")), "binding": value}

    def record(
        self,
        tenant: str,
        actor: str,
        request_key: str,
        candidate: str,
        check_id: str,
        *,
        toolchain: str,
        environment: str,
        parameters: dict[str, Any],
        outcome: str,
        log: bytes,
    ) -> dict[str, Any]:
        """Receive an authenticated runner's fact; it is not an independent approval."""
        _identifier(actor)
        _identifier(request_key)
        if outcome not in {"passed", "failed", "unknown"}:
            raise NativeStoreError("Invalid check outcome")
        if not isinstance(log, bytes) or not 0 < len(log) <= 1048576:
            raise NativeStoreError("Expected 1..1048576 bytes of runner evidence")
        bound = self.binding(
            tenant, candidate, check_id, toolchain=toolchain, environment=environment, parameters=parameters
        )
        if self.authorize(tenant, actor, check_id, "record") is not True:
            raise NativeStoreError("Runner is not authorized for this check")
        request = {**bound, "candidate": candidate, "actor": actor, "outcome": outcome, "log_sha256": _digest(log)}
        request_digest = _digest(_json(request).encode("utf-8"))
        with self.store._connection(write=True) as db:
            old = db.execute(
                "SELECT request_digest,evidence_id FROM native_check_requests "
                "WHERE tenant=? AND actor=? AND request_key=?",
                (tenant, actor, request_key),
            ).fetchone()
            if old is not None:
                if old["request_digest"] != request_digest:
                    raise Conflict("Evidence request key already used for different input")
                previous = self._evidence(db, tenant, old["evidence_id"])
                if previous["request_key"] != request_key or any(previous.get(k) != v for k, v in request.items()):
                    raise NativeStoreError("Evidence request receipt integrity failure")
                return previous
            payload = _json({**request, "recorded_at": self._time(), "request_key": request_key})
            evidence = _digest(payload.encode("utf-8"))
            db.execute(
                "INSERT INTO native_check_evidence (tenant,id,cache_key,payload,log) VALUES (?,?,?,?,?)",
                (tenant, evidence, bound["key"], payload, log),
            )
            db.execute(
                "INSERT INTO native_check_requests VALUES (?,?,?,?,?)",
                (tenant, actor, request_key, request_digest, evidence),
            )
            return {"id": evidence, **json.loads(payload)}

    @staticmethod
    def _evidence(db, tenant: str, evidence: str) -> dict[str, Any]:
        row = db.execute(
            "SELECT payload,log FROM native_check_evidence WHERE tenant=? AND id=?", (tenant, evidence)
        ).fetchone()
        if row is None or _digest(row["payload"].encode("utf-8")) != evidence:
            raise NativeStoreError("Evidence unavailable or corrupt")
        result = json.loads(row["payload"])
        if _digest(bytes(row["log"])) != result["log_sha256"]:
            raise NativeStoreError("Evidence log integrity failure")
        return {"id": evidence, **result}

    def lookup(
        self,
        tenant: str,
        candidate: str,
        check_id: str,
        *,
        toolchain: str,
        environment: str,
        parameters: dict[str, Any],
    ) -> dict[str, Any] | None:
        bound = self.binding(
            tenant, candidate, check_id, toolchain=toolchain, environment=environment, parameters=parameters
        )
        with self.store._connection() as db:
            row = db.execute(
                "SELECT id FROM native_check_evidence WHERE tenant=? AND cache_key=? ORDER BY sequence DESC LIMIT 1",
                (tenant, bound["key"]),
            ).fetchone()
            if row is None:
                return None
            evidence = self._evidence(db, tenant, row["id"])
            revoked = db.execute(
                "SELECT 1 FROM native_check_revocations WHERE tenant=? AND evidence_id=?", (tenant, row["id"])
            ).fetchone()
        age = self._time() - evidence["recorded_at"]
        if (
            evidence["key"] != bound["key"]
            or evidence["binding"] != bound["binding"]
            or evidence["outcome"] != "passed"
            or revoked is not None
            or not 0 <= age < self._policy(check_id)["max_age_seconds"]
            or self.authorize(tenant, evidence["actor"], check_id, "record") is not True
        ):
            return None
        return {"state": "cached_check_fact", "requested_candidate": candidate, "evidence": evidence}

    def revoke(self, tenant: str, actor: str, evidence_id: str, reason: str) -> None:
        _identifier(tenant)
        _identifier(actor)
        _revision_id(evidence_id)
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 4096:
            raise NativeStoreError("Revocation reason required")
        with self.store._connection(write=True) as db:
            evidence = self._evidence(db, tenant, evidence_id)
            if self.authorize(tenant, actor, evidence["binding"]["check"], "revoke") is not True:
                raise NativeStoreError("Runner is not authorized to revoke evidence")
            existing = db.execute(
                "SELECT payload FROM native_check_revocations WHERE tenant=? AND evidence_id=?", (tenant, evidence_id)
            ).fetchone()
            payload = _json({"actor": actor, "reason": reason})
            if existing is not None and existing["payload"] != payload:
                raise Conflict("Evidence already revoked with a different receipt")
            db.execute("INSERT OR IGNORE INTO native_check_revocations VALUES (?,?,?)", (tenant, evidence_id, payload))
