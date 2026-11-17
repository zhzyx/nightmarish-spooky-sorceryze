"""Trusted-host independent review and atomic content selection (not deployment).

All authority callbacks must be local, use the supplied transaction for mutable
authority, and perform no external work. The database is inside the host trust
boundary. Actor strings must come from authenticated host sessions.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Generator
from contextlib import contextmanager, nullcontext
from typing import Any

from native_evidence import EvidenceCache
from native_store import Conflict, NativeStore, NativeStoreError, _digest, _identifier, _json, _revision_id

SCHEMA = """
CREATE TABLE IF NOT EXISTS native_release_policy (
 tenant TEXT NOT NULL, product TEXT NOT NULL, payload TEXT NOT NULL,
 PRIMARY KEY(tenant,product));
CREATE TABLE IF NOT EXISTS native_release_records (
 tenant TEXT NOT NULL, id TEXT NOT NULL, payload TEXT NOT NULL,
 PRIMARY KEY(tenant,id));
CREATE TABLE IF NOT EXISTS native_release_requests (
 tenant TEXT NOT NULL, actor TEXT NOT NULL, request_key TEXT NOT NULL,
 digest TEXT NOT NULL, record TEXT NOT NULL, PRIMARY KEY(tenant,actor,request_key));
CREATE TABLE IF NOT EXISTS native_review_revocations (
 tenant TEXT NOT NULL, review TEXT NOT NULL, receipt TEXT NOT NULL,
 PRIMARY KEY(tenant,review));
CREATE TABLE IF NOT EXISTS native_release_heads (
 tenant TEXT NOT NULL, product TEXT NOT NULL, channel TEXT NOT NULL, record TEXT NOT NULL,
 PRIMARY KEY(tenant,product,channel));
CREATE TABLE IF NOT EXISTS native_release_events (
 sequence INTEGER PRIMARY KEY AUTOINCREMENT, tenant TEXT NOT NULL, product TEXT NOT NULL, record TEXT NOT NULL,
 UNIQUE(tenant,record));
CREATE INDEX IF NOT EXISTS native_release_event_cursor ON native_release_events(tenant,product,sequence);
"""

Authority = Callable[[sqlite3.Connection, str, str, str, str], bool]
Contributors = Callable[[sqlite3.Connection, str, str], set[str] | None]


class _TransactionStore(NativeStore):
    """Reuse evidence validation without opening a second read snapshot."""

    def __init__(self, db: sqlite3.Connection):
        self.db = db

    @contextmanager
    def _connection(self, *, write: bool = False) -> Generator[sqlite3.Connection, None, None]:
        if write:
            raise NativeStoreError("Read-only evidence adapter")
        yield self.db


class NativeRelease:
    def __init__(self, cache: EvidenceCache, authorize: Authority, contributors: Contributors):
        if not callable(authorize) or not callable(contributors):
            raise NativeStoreError("Explicit trusted authority and source resolver required")
        self.cache = cache
        self.store = cache.store
        self.authorize = authorize
        self.contributors = contributors
        with self.store._connection() as db:
            db.executescript(SCHEMA)

    def _allow(self, db: sqlite3.Connection, tenant: str, actor: str, product: str, action: str) -> None:
        for value in (tenant, actor, product):
            _identifier(value)
        if self.authorize(db, tenant, actor, product, action) is not True:
            raise NativeStoreError("Host authorization denied")

    @contextmanager
    def _snapshot(self) -> Generator[sqlite3.Connection, None, None]:
        # A WAL read snapshot is coherent across authority, evidence and head reads
        # without taking the writer reservation used by actual publication.
        with self.store._connection() as db:
            db.execute("PRAGMA query_only=ON")
            db.execute("BEGIN")
            try:
                yield db
            finally:
                db.rollback()

    def configure(self, tenant: str, actor: str, product: str, policy: dict[str, Any]) -> str:
        """Install trusted product policy, separate from candidate submission."""
        policy = json.loads(_json(policy))
        if set(policy) != {"checks", "review_max_age_seconds"}:
            raise NativeStoreError("Invalid release policy")
        age = policy["review_max_age_seconds"]
        checks = policy["checks"]
        if type(age) is not int or not 0 < age <= 31536000 or not isinstance(checks, dict) or not checks:
            raise NativeStoreError("Required checks and bounded review lifetime required")
        whole = False
        for check, context in checks.items():
            installed = self.cache._policy(check)
            if set(context) != {"toolchain", "environment", "parameters"}:
                raise NativeStoreError("Exact execution context required")
            _revision_id(context["toolchain"])
            _revision_id(context["environment"])
            if not isinstance(context["parameters"], dict):
                raise NativeStoreError("Parameters must be an object")
            whole |= installed["reads"] is None
        if not whole:
            raise NativeStoreError("A whole-composition check is required")
        policy["check_policies"] = {check: self.cache._policy(check) for check in checks}
        payload = _json(policy)
        with self.store._connection(write=True) as db:
            self._allow(db, tenant, actor, product, "configure")
            db.execute(
                "INSERT INTO native_release_policy VALUES (?,?,?) ON CONFLICT(tenant,product) "
                "DO UPDATE SET payload=excluded.payload",
                (tenant, product, payload),
            )
        return str(_digest(payload.encode()))

    def _policy(self, db: sqlite3.Connection, tenant: str, product: str) -> tuple[str, dict[str, Any]]:
        row = db.execute(
            "SELECT payload FROM native_release_policy WHERE tenant=? AND product=?", (tenant, product)
        ).fetchone()
        if row is None:
            raise NativeStoreError("Product policy unavailable")
        policy = json.loads(row[0])
        if policy["check_policies"] != {check: self.cache._policy(check) for check in policy["checks"]}:
            raise NativeStoreError("Installed check policy drift")
        return _digest(row[0].encode()), policy

    @staticmethod
    def _record(db: sqlite3.Connection, tenant: str, identity: str) -> dict[str, Any]:
        _revision_id(identity)
        row = db.execute(
            "SELECT payload FROM native_release_records WHERE tenant=? AND id=?", (tenant, identity)
        ).fetchone()
        if row is None or _digest(row[0].encode()) != identity:
            raise NativeStoreError("Release record unavailable or corrupt")
        result: dict[str, Any] = json.loads(row[0])
        if result.get("tenant") != tenant:
            raise NativeStoreError("Release tenant mismatch")
        return {"id": identity, **result}

    def _existing(self, db: sqlite3.Connection, request: dict[str, Any]) -> dict[str, Any] | None:
        _identifier(request["request_key"])
        row = db.execute(
            "SELECT digest,record FROM native_release_requests WHERE tenant=? AND actor=? AND request_key=?",
            (request["tenant"], request["actor"], request["request_key"]),
        ).fetchone()
        if row is None:
            return None
        if row[0] != _digest(_json(request).encode()):
            raise Conflict("Request key reused with different content")
        record = self._record(db, request["tenant"], row[1])
        if record["request"] != request:
            raise NativeStoreError("Request receipt integrity failure")
        return record

    def _save(self, db: sqlite3.Connection, request: dict[str, Any], **facts: Any) -> dict[str, Any]:
        payload = _json({"tenant": request["tenant"], "request": request, "recorded_at": self.cache._time(), **facts})
        identity = _digest(payload.encode())
        db.execute("INSERT INTO native_release_records VALUES (?,?,?)", (request["tenant"], identity, payload))
        db.execute(
            "INSERT INTO native_release_requests VALUES (?,?,?,?,?)",
            (request["tenant"], request["actor"], request["request_key"], _digest(_json(request).encode()), identity),
        )
        return {"id": identity, **json.loads(payload)}

    def _facts(
        self,
        db: sqlite3.Connection,
        tenant: str,
        candidate: str,
        reviewer: str,
        policy: dict[str, Any],
        evidence: dict[str, str],
    ) -> list[str]:
        _revision_id(candidate)
        authors = self.contributors(db, tenant, candidate)
        if not isinstance(authors, set) or not authors or reviewer in authors:
            raise NativeStoreError("Unknown contribution source or non-independent reviewer")
        for author in authors:
            _identifier(author)
        if set(evidence) != set(policy["checks"]):
            raise NativeStoreError("Exact required evidence set missing")
        # Do not call __init__: it executes schema SQL and would commit this transaction.
        cache = object.__new__(EvidenceCache)
        cache.store = _TransactionStore(db)
        cache.policies = json.loads(_json(self.cache.policies))
        cache.clock = self.cache.clock
        cache.authorize = lambda t, a, c, op: (
            self.authorize(db, t, a, c, "evidence:" + op) is True and self.cache.authorize(t, a, c, op) is True
        )
        for check, context in policy["checks"].items():
            hit = cache.lookup(tenant, candidate, check, **context)
            if hit is None or hit["evidence"]["id"] != evidence[check]:
                raise NativeStoreError("Required check evidence invalid or superseded")
        return sorted(authors)

    def approve(
        self,
        tenant: str,
        actor: str,
        request_key: str,
        product: str,
        candidate: str,
        evidence: dict[str, str],
        review_note: str,
    ) -> dict[str, Any]:
        if not isinstance(review_note, str) or not review_note.strip() or len(review_note) > 16384:
            raise NativeStoreError("Independent review record required")
        request = json.loads(
            _json(
                dict(
                    tenant=tenant,
                    actor=actor,
                    request_key=request_key,
                    product=product,
                    candidate=candidate,
                    evidence=evidence,
                    review_note=review_note,
                    action="approve",
                )
            )
        )
        with self.store._connection(write=True) as db:
            self._allow(db, tenant, actor, product, "approve")
            old = self._existing(db, request)
            if old is not None:
                return old
            digest, policy = self._policy(db, tenant, product)
            authors = self._facts(db, tenant, candidate, actor, policy, request["evidence"])
            return self._save(db, request, state="independent_review", policy=digest, contributors=authors)

    def _valid_review(self, db: sqlite3.Connection, tenant: str, review: str) -> dict[str, Any]:
        result = self._record(db, tenant, review)
        request = result["request"]
        if result["state"] != "independent_review":
            raise NativeStoreError("Not an independent review")
        self._allow(db, tenant, request["actor"], request["product"], "approve")
        digest, policy = self._policy(db, tenant, request["product"])
        revoked = db.execute(
            "SELECT 1 FROM native_review_revocations WHERE tenant=? AND review=?", (tenant, review)
        ).fetchone()
        if (
            revoked
            or digest != result["policy"]
            or not 0 <= self.cache._time() - result["recorded_at"] < policy["review_max_age_seconds"]
        ):
            raise NativeStoreError("Review revoked, expired or policy changed")
        authors = self._facts(db, tenant, request["candidate"], request["actor"], policy, request["evidence"])
        if authors != result["contributors"]:
            raise NativeStoreError("Verified contribution source changed")
        return result

    def revoke(self, tenant: str, actor: str, request_key: str, review: str, reason: str) -> dict[str, Any]:
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 4096:
            raise NativeStoreError("Revocation reason required")
        with self.store._connection(write=True) as db:
            target = self._record(db, tenant, review)
            if target["state"] != "independent_review":
                raise NativeStoreError("Not a review")
            product = target["request"]["product"]
            self._allow(db, tenant, actor, product, "revoke")
            request = dict(
                tenant=tenant, actor=actor, request_key=request_key, review=review, reason=reason, action="revoke"
            )
            old = self._existing(db, request)
            if old is not None:
                return old
            record = self._save(db, request, state="review_revoked")
            db.execute("INSERT OR IGNORE INTO native_review_revocations VALUES (?,?,?)", (tenant, review, record["id"]))
            return record

    def publish(
        self,
        tenant: str,
        actor: str,
        request_key: str,
        product: str,
        channel: str,
        review: str,
        expected: str | None,
        *,
        guard=None,
    ) -> dict[str, Any]:
        """Rollback uses this same operation with a valid review of old content."""
        _identifier(channel)
        if expected is not None:
            _revision_id(expected)
        request = dict(
            tenant=tenant,
            actor=actor,
            request_key=request_key,
            product=product,
            channel=channel,
            review=review,
            expected=expected,
            action="publish",
        )
        with self.store._connection(write=True) as db, guard(db) if guard is not None else nullcontext():
            self._allow(db, tenant, actor, product, "publish")
            old = self._existing(db, request)
            if old is not None:
                return old  # Historical receipt only; does not reselect or revalidate it.
            approval = self._valid_review(db, tenant, review)
            if approval["request"]["product"] != product:
                raise NativeStoreError("Review product mismatch")
            row = db.execute(
                "SELECT record FROM native_release_heads WHERE tenant=? AND product=? AND channel=?",
                (tenant, product, channel),
            ).fetchone()
            if (row[0] if row else None) != expected:
                raise Conflict("Channel changed; reread before selecting")
            candidate = approval["request"]["candidate"]
            composition = db.execute(
                "SELECT payload FROM native_compositions WHERE tenant=? AND id=?", (tenant, candidate)
            ).fetchone()
            record = self._save(
                db,
                request,
                state="content_selected",
                candidate=candidate,
                modules=json.loads(composition[0])["modules"],
                policy=approval["policy"],
            )
            db.execute(
                "INSERT INTO native_release_heads VALUES (?,?,?,?) ON CONFLICT(tenant,product,channel) "
                "DO UPDATE SET record=excluded.record",
                (tenant, product, channel, record["id"]),
            )
            db.execute(
                "INSERT INTO native_release_events(tenant,product,record) VALUES (?,?,?)",
                (tenant, product, record["id"]),
            )
            # A trusted local domain guard must remain held until publication is
            # committed, not merely until SQL statements have been issued.
            db.commit()
            return record

    def selected(self, tenant: str, actor: str, product: str, channel: str) -> dict[str, Any] | None:
        """Fail closed on invalid current review; historical receipts remain available."""
        _identifier(channel)
        with self._snapshot() as db:
            self._allow(db, tenant, actor, product, "read")
            row = db.execute(
                "SELECT record FROM native_release_heads WHERE tenant=? AND product=? AND channel=?",
                (tenant, product, channel),
            ).fetchone()
            if row is None:
                return None
            record = self._record(db, tenant, row[0])
            request = record["request"]
            if record["state"] != "content_selected" or (request["product"], request["channel"]) != (product, channel):
                raise NativeStoreError("Selected pointer integrity failure")
            approval = self._valid_review(db, tenant, request["review"])
            if record["candidate"] != approval["request"]["candidate"]:
                raise NativeStoreError("Selected candidate mismatch")
            event = db.execute(
                "SELECT 1 FROM native_release_events WHERE tenant=? AND product=? AND record=?",
                (tenant, product, record["id"]),
            ).fetchone()
            if event is None:
                raise NativeStoreError("Atomic event missing")
            return record

    def events(
        self, tenant: str, actor: str, product: str, *, after: int = 0, limit: int = 100
    ) -> list[dict[str, Any]]:
        if type(after) is not int or after < 0 or type(limit) is not int or not 1 <= limit <= 1000:
            raise NativeStoreError("Expected nonnegative cursor and 1..1000 event limit")
        with self._snapshot() as db:
            self._allow(db, tenant, actor, product, "read")
            result = []
            for row in db.execute(
                "SELECT record,sequence FROM native_release_events WHERE tenant=? AND product=? "
                "AND sequence>? ORDER BY sequence LIMIT ?",
                (tenant, product, after, limit),
            ):
                record = self._record(db, tenant, row[0])
                if record["state"] != "content_selected" or record["request"].get("product") != product:
                    raise NativeStoreError("Event product integrity failure")
                result.append({"sequence": row[1], "record": record})
            return result
