"""Git-free repository refs over NativeStore objects and NativeRelease governance.

The host supplies current authority and optional trusted checks. Check callbacks
receive (repository, tenant, immutable_revision), return (bool, nonempty bytes),
and must bind any semantic tests to those exact stored inputs. No caller-uploaded
check status is accepted. Integrity alone is deliberately named as such.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import re
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

from native_evidence import EvidenceCache
from native_release import NativeRelease
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

MAX_OBJECT = 32 * 1024 * 1024
MAX_MANIFEST = 32 * 1024 * 1024
MAX_FILES = 100000
MODULE = "native-repository-gonggong"
RUNNER = "native-repository-checker"
SCHEMA = """
CREATE TABLE IF NOT EXISTS native_repo_refs (
 tenant TEXT NOT NULL, repository TEXT NOT NULL, branch TEXT NOT NULL, revision TEXT,
 PRIMARY KEY(tenant,repository,branch));
CREATE TABLE IF NOT EXISTS native_repo_requests (
 tenant TEXT NOT NULL, actor TEXT NOT NULL, request_key TEXT NOT NULL,
 digest TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(tenant,actor,request_key));
CREATE TABLE IF NOT EXISTS native_repo_device_requests (
 tenant TEXT NOT NULL, actor TEXT NOT NULL, device_id TEXT NOT NULL, request_key TEXT NOT NULL,
 digest TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(tenant,actor,device_id,request_key));
CREATE TABLE IF NOT EXISTS native_repo_candidates (
 tenant TEXT NOT NULL, id TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(tenant,id));
"""


class RepositoryForbidden(NativeStoreError):
    pass


def branch_name(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_./-]{0,199}", value):
        raise NativeStoreError("Invalid branch")
    if any(p in {"", ".", ".."} for p in value.split("/")):
        raise NativeStoreError("Invalid branch")
    return value


def manifest_paths(manifest):
    if not isinstance(manifest, dict) or len(manifest) > MAX_FILES:
        raise NativeStoreError("Expected bounded full manifest")
    if len(_json(manifest).encode("utf-8")) > MAX_MANIFEST:
        raise NativeStoreError("Manifest too large")
    folded = {}
    for name, digest in manifest.items():
        _object_name(name)
        name.encode("utf-8")
        _revision_id(digest)
        parts = name.split("/")
        for part in parts:
            stem = part.split(".")[0].upper()
            if (
                part.endswith((".", " "))
                or part.casefold() in {".git", ".duobao"}
                or any(c in part for c in '<>"|?*')
                or stem in {"CON", "PRN", "AUX", "NUL"}
                or re.fullmatch(r"(?:COM|LPT)[1-9\u00b9\u00b2\u00b3]", stem)
            ):
                raise NativeStoreError("Unsafe materialization path")
        key = name.casefold()
        if key in folded:
            raise NativeStoreError("Case-colliding paths")
        folded[key] = name
    for key in folded:
        parts = key.split("/")
        if any("/".join(parts[:i]) in folded for i in range(1, len(parts))):
            raise NativeStoreError("File/directory collision")


class NativeRepository:
    def __init__(self, store: NativeStore, authorize, checks=None, check_context=None):
        if not callable(authorize):
            raise NativeStoreError("Trusted authority required")
        self.store, self.authorize = store, authorize
        self._device = ContextVar("native_repository_device", default=(None, None))
        if checks and "repository-integrity" in checks:
            raise NativeStoreError("Built-in integrity check cannot be replaced")
        self.checks = {"repository-integrity": self._integrity, **(checks or {})}
        if any(not callable(fn) for fn in self.checks.values()):
            raise NativeStoreError("Installed check callable required")
        policies = {name: {"version": "v1", "reads": None, "max_age_seconds": 86400} for name in self.checks}
        # A newly installed implementation must never relabel an old passing run.
        from native_release import NativeRelease as ReleaseImplementation

        installed = {
            inspect.getsourcefile(value)
            for value in (NativeRepository, NativeStore, EvidenceCache, ReleaseImplementation, *self.checks.values())
        }
        if None in installed and check_context is None:
            raise NativeStoreError("Explicit execution context required for opaque installed checks")
        implementation = sorted((Path(path).name, _digest(Path(path).read_bytes())) for path in installed if path)
        self.context = dict(
            toolchain=_digest(_json(implementation).encode()),
            environment=_digest(b"native-repository-host-v1"),
            parameters={},
        )
        if check_context is not None:
            if not isinstance(check_context, dict) or set(check_context) != {"toolchain", "environment", "parameters"}:
                raise NativeStoreError("Exact installed check execution context required")
            _revision_id(check_context["toolchain"])
            _revision_id(check_context["environment"])
            self.context = json.loads(_json(check_context))
            self.context["toolchain"] = _digest(_json([implementation, check_context["toolchain"]]).encode())
        self.cache = EvidenceCache(store, policies, lambda t, a, c, op: a == RUNNER and c in self.checks)
        self.release = NativeRelease(self.cache, self._release_authority, self._contributors)
        with store._connection() as db:
            db.executescript(SCHEMA)

    def _allow(self, tenant, actor, action):
        _identifier(tenant)
        _identifier(actor)
        if self.authorize(tenant, actor, action) is not True:
            raise RepositoryForbidden("Repository permission denied")

    def _release_authority(self, db, tenant, actor, product, action):
        if action.startswith("evidence:"):
            return actor == RUNNER and product in self.checks
        if product != MODULE:
            return False
        return (
            self.authorize(
                tenant, actor, {"configure": "admin", "approve": "review", "revoke": "admin"}.get(action, action)
            )
            is True
        )

    @staticmethod
    def _repo(repo):
        if repo != "gonggong":
            raise NativeStoreError("Repository unavailable")

    def _ready(self, db, tenant, repo):
        self._repo(repo)
        if (
            db.execute(
                "SELECT 1 FROM native_repo_refs WHERE tenant=? AND repository=? AND branch='main'", (tenant, repo)
            ).fetchone()
            is None
        ):
            raise NativeStoreError("Repository requires administrator bootstrap")

    @staticmethod
    def _tip(db, tenant, repo, branch):
        branch_name(branch)
        row = db.execute(
            "SELECT revision FROM native_repo_refs WHERE tenant=? AND repository=? AND branch=?", (tenant, repo, branch)
        ).fetchone()
        if row is None:
            raise NativeStoreError("Branch unavailable")
        return row[0]

    @contextmanager
    def device_context(self, *, device_id=None, credential_id=None):
        """Trusted host binding; account authority remains the original actor.

        Bind and invoke in the same worker. ContextVar tokens restore nested
        bindings and clear failed calls without leaking into a reused worker.
        """
        if device_id is not None or credential_id is not None:
            _identifier(device_id)
            _identifier(credential_id)
        token = self._device.set((device_id, credential_id))
        try:
            yield
        finally:
            self._device.reset(token)

    def _request_scope(self, tenant, actor, key):
        _identifier(key)
        device, _ = self._device.get()
        if device is None:
            return "native_repo_requests", "tenant=? AND actor=? AND request_key=?", (tenant, actor, key)
        return (
            "native_repo_device_requests",
            "tenant=? AND actor=? AND device_id=? AND request_key=?",
            (tenant, actor, device, key),
        )

    def _operation_key(self, operation, key):
        # Preserve historical release request keys. Credentials are audit data:
        # rotating a credential must not change the device's replay namespace.
        device, _ = self._device.get()
        if device is None:
            return "repo-" + operation + "-" + _digest(key.encode())
        return "repo-device-" + operation + "-" + _digest(_json([device, key]).encode())

    def _audit(self, actor, key):
        device, credential = self._device.get()
        return dict(actor=actor, device_id=device, credential_id=credential, request_key=key)

    def _old(self, db, tenant, actor, key, request):
        table, predicate, scope = self._request_scope(tenant, actor, key)
        row = db.execute(f"SELECT digest,payload FROM {table} WHERE {predicate}", scope).fetchone()
        if row:
            if row[0] != _digest(_json(request).encode()):
                raise Conflict("Request key reused for different inputs")
            return json.loads(row[1])
        return None

    def _save(self, db, tenant, actor, key, request, result):
        table, _, scope = self._request_scope(tenant, actor, key)
        db.execute(
            f"INSERT INTO {table} VALUES ({','.join('?' for _ in range(len(scope) + 2))})",
            (*scope, _digest(_json(request).encode()), _json(result)),
        )
        return result

    def bootstrap(self, tenant, actor, repo, request_key):
        self._allow(tenant, actor, "admin")
        self._repo(repo)
        self.release.configure(
            tenant,
            actor,
            MODULE,
            {"checks": {name: self.context for name in self.checks}, "review_max_age_seconds": 86400},
        )
        request = dict(operation="bootstrap", repository=repo)
        with self.store._connection(write=True) as db:
            old = self._old(db, tenant, actor, request_key, request)
            if old is not None:
                return old
            db.execute("INSERT OR IGNORE INTO native_repo_refs VALUES (?,?,?,NULL)", (tenant, repo, "main"))
            return self._save(
                db,
                tenant,
                actor,
                request_key,
                request,
                dict(repository=repo, branch="main", revision=self._tip(db, tenant, repo, "main"), state="initialized"),
            )

    def branches(self, tenant, actor, repo):
        self._allow(tenant, actor, "read")
        with self.store._connection() as db:
            self._ready(db, tenant, repo)
            rows = db.execute(
                "SELECT branch,revision FROM native_repo_refs WHERE tenant=? AND repository=? ORDER BY branch",
                (tenant, repo),
            )
            return dict(repository=repo, branches=[dict(row) for row in rows])

    def branch(self, tenant, actor, repo, branch):
        self._allow(tenant, actor, "read")
        with self.store._connection() as db:
            self._ready(db, tenant, repo)
            return dict(repository=repo, branch=branch, revision=self._tip(db, tenant, repo, branch))

    def _revision(self, db, tenant, revision):
        state = self.store._revision(db, tenant, MODULE, revision)
        if state.get("repository") != "gonggong" or not state.get("author") or state.get("dependencies") != {}:
            raise NativeStoreError("Repository provenance missing")
        return state

    def revision(self, tenant, actor, repo, revision):
        self._allow(tenant, actor, "read")
        with self.store._connection() as db:
            self._ready(db, tenant, repo)
            return self._revision(db, tenant, revision)

    def create_branch(self, tenant, actor, repo, request_key, branch, revision):
        self._allow(tenant, actor, "write")
        branch_name(branch)
        if branch == "main":
            raise RepositoryForbidden("Protected main requires reviewed merge")
        request = dict(operation="branch", repository=repo, branch=branch, revision=revision)
        with self.store._connection(write=True) as db:
            self._ready(db, tenant, repo)
            old = self._old(db, tenant, actor, request_key, request)
            if old is not None:
                return old
            if revision is not None:
                self._revision(db, tenant, revision)
            if db.execute(
                "SELECT 1 FROM native_repo_refs WHERE tenant=? AND repository=? AND branch=?", (tenant, repo, branch)
            ).fetchone():
                raise Conflict("Branch already exists")
            db.execute("INSERT INTO native_repo_refs VALUES (?,?,?,?)", (tenant, repo, branch, revision))
            return self._save(
                db, tenant, actor, request_key, request, dict(repository=repo, branch=branch, revision=revision)
            )

    @staticmethod
    def _verify_blob(db, tenant, digest):
        row = db.execute(
            "SELECT rowid,length(content) FROM native_blobs WHERE tenant=? AND digest=?", (tenant, digest)
        ).fetchone()
        if row is None or row[1] > MAX_OBJECT:
            raise NativeStoreError("Object missing or oversized")
        sha = hashlib.sha256()
        with db.blobopen("native_blobs", "content", row[0], readonly=True) as blob:
            while chunk := blob.read(65536):
                sha.update(chunk)
        if sha.hexdigest() != digest:
            raise NativeStoreError("Object integrity failure")
        return row[1]

    def put_object(self, tenant, actor, repo, digest, content):
        self._allow(tenant, actor, "write")
        _revision_id(digest)
        if not isinstance(content, bytes) or len(content) > MAX_OBJECT or _digest(content) != digest:
            raise NativeStoreError("Object digest or size mismatch")
        with self.store._connection(write=True) as db:
            self._ready(db, tenant, repo)
            db.execute("INSERT OR IGNORE INTO native_blobs VALUES (?,?,?)", (tenant, digest, content))
            self._verify_blob(db, tenant, digest)
        return dict(digest=digest, size=len(content), state="stored")

    def object(self, tenant, actor, repo, digest):
        self._allow(tenant, actor, "read")
        _revision_id(digest)
        with self.store._connection() as db:
            db.execute("BEGIN")
            self._ready(db, tenant, repo)
            self._verify_blob(db, tenant, digest)
            return bytes(
                db.execute("SELECT content FROM native_blobs WHERE tenant=? AND digest=?", (tenant, digest)).fetchone()[
                    0
                ]
            )

    def missing(self, tenant, actor, repo, digests):
        self._allow(tenant, actor, "write")
        if not isinstance(digests, list) or len(digests) > MAX_FILES:
            raise NativeStoreError("Expected bounded digest list")
        digests = sorted({_revision_id(d) for d in digests})
        with self.store._connection() as db:
            self._ready(db, tenant, repo)
            return {
                "missing": [
                    d
                    for d in digests
                    if db.execute("SELECT 1 FROM native_blobs WHERE tenant=? AND digest=?", (tenant, d)).fetchone()
                    is None
                ]
            }

    def commit(self, tenant, actor, repo, request_key, branch, expected, manifest, message):
        self._allow(tenant, actor, "write")
        branch_name(branch)
        if branch == "main":
            raise RepositoryForbidden("Protected main requires reviewed merge")
        if expected is not None:
            _revision_id(expected)
        if not isinstance(message, str) or not message.strip() or len(message) > 16384:
            raise NativeStoreError("Commit message required")
        manifest = dict(manifest) if isinstance(manifest, dict) else manifest
        manifest_paths(manifest)
        request = dict(
            operation="commit", repository=repo, branch=branch, expected=expected, manifest=manifest, message=message
        )
        with self.store._connection(write=True) as db:
            self._ready(db, tenant, repo)
            old = self._old(db, tenant, actor, request_key, request)
            if old is not None:
                return old
            if self._tip(db, tenant, repo, branch) != expected:
                raise Conflict("Branch changed; reread before commit")
            if expected is not None:
                self._revision(db, tenant, expected)
            for digest in set(manifest.values()):
                self._verify_blob(db, tenant, digest)
            state = dict(
                module=MODULE,
                parent=expected,
                objects=manifest,
                dependencies={},
                repository=repo,
                author=actor,
                **self._audit(actor, request_key),
                branch=branch,
                expected=expected,
                message=message,
            )
            payload = _json(state)
            revision = _digest(payload.encode())
            db.execute("INSERT OR IGNORE INTO native_revisions VALUES (?,?,?,?)", (tenant, revision, MODULE, payload))
            db.execute(
                "UPDATE native_repo_refs SET revision=? WHERE tenant=? AND repository=? AND branch=?",
                (revision, tenant, repo, branch),
            )
            return self._save(
                db,
                tenant,
                actor,
                request_key,
                request,
                dict(
                    state="received",
                    repository=repo,
                    branch=branch,
                    revision=revision,
                    parent=expected,
                    expected=expected,
                    manifest=manifest,
                    **self._audit(actor, request_key),
                    request_digest=_digest(_json(request).encode()),
                ),
            )

    def _authors(self, db, tenant, revision, expected):
        authors, seen = set(), set()
        while revision != expected:
            if revision is None or revision in seen:
                raise Conflict("Source does not descend from exact target")
            seen.add(revision)
            state = self._revision(db, tenant, revision)
            authors.add(state["author"])
            revision = state["parent"]
        if not authors:
            raise Conflict("Candidate has no new revision")
        return authors

    def _contributors(self, db, tenant, composition):
        row = db.execute(
            "SELECT payload FROM native_repo_candidates WHERE tenant=? AND id=?", (tenant, composition)
        ).fetchone()
        if not row:
            return None
        candidate = self._candidate(db, tenant, "gonggong", composition)
        return self._authors(db, tenant, candidate["revision"], candidate["expected"])

    def create_candidate(
        self, tenant, actor, repo, request_key, source, target, revision, expected, issue_id, issue_revision=None
    ):
        self._allow(tenant, actor, "write")
        branch_name(source)
        _revision_id(revision)
        if target != "main" or source == "main":
            raise NativeStoreError("Expected task branch to protected main")
        if not isinstance(issue_id, str) or not re.fullmatch(r"iss_[a-f0-9]{32}", issue_id):
            raise NativeStoreError("Exact Tianxuan issue required")
        if issue_revision is not None:
            _revision_id(issue_revision)
        request = dict(
            operation="candidate",
            repository=repo,
            source=source,
            target=target,
            revision=revision,
            expected=expected,
            issue_id=issue_id,
            issue_revision=issue_revision,
        )
        with self.store._connection(write=True) as db:
            self._ready(db, tenant, repo)
            old = self._old(db, tenant, actor, request_key, request)
            if old is not None:
                return old
            if self._tip(db, tenant, repo, source) != revision or self._tip(db, tenant, repo, target) != expected:
                raise Conflict("Exact source or target moved")
            self._authors(db, tenant, revision, expected)
            selected = db.execute(
                "SELECT record FROM native_release_heads WHERE tenant=? AND product=? AND channel='main'",
                (tenant, MODULE),
            ).fetchone()
            composition = dict(
                state="candidate",
                modules={MODULE: revision},
                repository=repo,
                source=source,
                target=target,
                expected=expected,
                issue_id=issue_id,
                issue_revision=issue_revision,
                release_expected=selected[0] if selected else None,
            )
            payload = _json(composition)
            identity = _digest(payload.encode())
            db.execute("INSERT OR IGNORE INTO native_compositions VALUES (?,?,?)", (tenant, identity, payload))
            result = dict(
                id=identity,
                state="candidate",
                repository=repo,
                source=source,
                target=target,
                revision=revision,
                expected=expected,
                composition=identity,
                release_expected=composition["release_expected"],
                issue_id=issue_id,
                issue_revision=issue_revision,
            )
            db.execute("INSERT OR IGNORE INTO native_repo_candidates VALUES (?,?,?)", (tenant, identity, _json(result)))
            return self._save(db, tenant, actor, request_key, request, result)

    def _candidate(self, db, tenant, repo, identity):
        self._ready(db, tenant, repo)
        _revision_id(identity)
        row = db.execute(
            "SELECT payload FROM native_repo_candidates WHERE tenant=? AND id=?", (tenant, identity)
        ).fetchone()
        if row is None:
            raise NativeStoreError("Candidate unavailable")
        result = json.loads(row[0])
        composition = dict(
            state="candidate",
            modules={MODULE: result["revision"]},
            **{
                key: result[key]
                for key in (
                    "repository",
                    "source",
                    "target",
                    "expected",
                    "issue_id",
                    "issue_revision",
                    "release_expected",
                )
            },
        )
        if result["id"] != identity or _digest(_json(composition).encode()) != identity:
            raise NativeStoreError("Candidate integrity failure")
        return result

    def candidate(self, tenant, actor, repo, identity):
        self._allow(tenant, actor, "read")
        with self.store._connection() as db:
            return self._candidate(db, tenant, repo, identity)

    def check_status(self, tenant, actor, repo, identity):
        self.candidate(tenant, actor, repo, identity)
        evidence, checks = {}, {}
        for name in self.checks:
            bound = self.cache.binding(tenant, identity, name, **self.context)
            with self.store._connection() as db:
                row = db.execute(
                    "SELECT id,log FROM native_check_evidence WHERE tenant=? AND cache_key=? ORDER BY sequence DESC LIMIT 1",
                    (tenant, bound["key"]),
                ).fetchone()
                if row is None:
                    checks[name] = {"outcome": "missing"}
                    continue
                fact = self.cache._evidence(db, tenant, row["id"])
                evidence[name] = fact["id"]
                checks[name] = {
                    "outcome": fact["outcome"],
                    "log_sha256": fact["log_sha256"],
                    "log": bytes(row["log"]).decode("utf-8", errors="replace"),
                }
            if self.cache.lookup(tenant, identity, name, **self.context) is None and fact["outcome"] == "passed":
                checks[name]["outcome"] = "invalidated"
        return dict(
            candidate=identity,
            state="checked" if all(c["outcome"] == "passed" for c in checks.values()) else "not-passed",
            evidence=evidence,
            checks=checks,
        )

    def _fresh(self, db, tenant, candidate):
        repo = candidate["repository"]
        if (
            self._tip(db, tenant, repo, candidate["source"]) != candidate["revision"]
            or self._tip(db, tenant, repo, "main") != candidate["expected"]
        ):
            raise Conflict("Candidate stale: source or target changed")

    @staticmethod
    def _integrity(repository, tenant, revision):
        with repository.store._connection() as db:
            db.execute("BEGIN")
            state = repository._revision(db, tenant, revision)
            manifest_paths(state["objects"])
            size = sum(repository._verify_blob(db, tenant, digest) for digest in set(state["objects"].values()))
            log = dict(check="repository-integrity", revision=revision, files=len(state["objects"]), unique_bytes=size)
            return True, _json(log).encode()

    def run_checks(self, tenant, actor, repo, identity, request_key):
        self._allow(tenant, actor, "write")
        _identifier(request_key)
        with self.store._connection() as db:
            candidate = self._candidate(db, tenant, repo, identity)
            self._fresh(db, tenant, candidate)
        evidence, checks = {}, {}
        for name, check in self.checks.items():
            binding = self.cache.binding(tenant, identity, name, **self.context)
            inputs = [actor, request_key, identity, name]
            if self._device.get()[0] is not None:
                inputs.append(self._device.get()[0])
            key = _digest(_json(inputs).encode())
            with self.store._connection() as db:
                previous = db.execute(
                    "SELECT evidence_id FROM native_check_requests WHERE tenant=? AND actor=? AND request_key=?",
                    (tenant, RUNNER, key),
                ).fetchone()
                record = self.cache._evidence(db, tenant, previous[0]) if previous else None
            if record is not None:
                if record["binding"] != binding["binding"] or record["candidate"] != identity:
                    raise Conflict("Check execution context changed; use a new request key")
            else:
                try:
                    passed, log = check(self, tenant, candidate["revision"])
                    if type(passed) is not bool or not isinstance(log, bytes) or not log:
                        raise NativeStoreError("Invalid trusted check result")
                except Exception:
                    passed, log = False, b"Trusted repository check failed; inspect host diagnostics"
                record = self.cache.record(
                    tenant,
                    RUNNER,
                    key,
                    identity,
                    name,
                    **self.context,
                    outcome="passed" if passed else "failed",
                    log=log,
                    expected_binding=binding,
                )
            evidence[name] = record["id"]
            checks[name] = {k: record[k] for k in ("outcome", "log_sha256")}
        return dict(
            candidate=identity,
            state="checked" if all(v["outcome"] == "passed" for v in checks.values()) else "failed",
            evidence=evidence,
            checks=checks,
        )

    def review(self, tenant, actor, repo, identity, request_key, note):
        self._allow(tenant, actor, "review")
        _identifier(request_key)
        with self.store._connection() as db:
            self._fresh(db, tenant, self._candidate(db, tenant, repo, identity))
        evidence = {}
        for name in self.checks:
            result = self.cache.lookup(tenant, identity, name, **self.context)
            if result is None:
                raise NativeStoreError("Required check not passed")
            evidence[name] = result["evidence"]["id"]
        return self.release.approve(
            tenant, actor, self._operation_key("review", request_key), MODULE, identity, evidence, note
        )

    def merge(self, tenant, actor, repo, identity, request_key, review, guard=None):
        self._allow(tenant, actor, "publish")
        _identifier(request_key)
        candidate = self.candidate(tenant, actor, repo, identity)
        key = self._operation_key("merge", request_key)

        @contextmanager
        def publication_guard(db):
            self._allow(tenant, actor, "publish")
            approval = self.release._record(db, tenant, review)
            if approval["request"].get("candidate") != identity:
                raise NativeStoreError("Review belongs to another candidate")
            old = db.execute(
                "SELECT 1 FROM native_release_requests WHERE tenant=? AND actor=? AND request_key=?",
                (tenant, actor, key),
            ).fetchone()
            from contextlib import nullcontext

            with guard(candidate, replay=bool(old)) if guard else nullcontext():
                if not old:
                    self._fresh(db, tenant, candidate)
                    db.execute(
                        "UPDATE native_repo_refs SET revision=? WHERE tenant=? AND repository=? AND branch='main'",
                        (candidate["revision"], tenant, repo),
                    )
                yield

        record = self.release.publish(
            tenant, actor, key, MODULE, "main", review, candidate["release_expected"], guard=publication_guard
        )
        return dict(
            state="merged",
            candidate=identity,
            repository=repo,
            branch="main",
            revision=candidate["revision"],
            release=record["id"],
            issue_id=candidate["issue_id"],
        )
