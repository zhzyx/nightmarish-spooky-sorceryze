"""Authenticated, bounded HTTP adapter for candidate storage (never approval)."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
import sqlite3
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from native_store import Conflict, NativeStore, NativeStoreError
from starlette.concurrency import run_in_threadpool

PREFIX = "/api/v1/native"
MAX_BODY = 8 * 1024 * 1024
MAX_DECODED = 4 * 1024 * 1024
MAX_OBJECT = 1024 * 1024
MAX_ENTRIES = 1024
MAX_MODULES = 128


def _identity(request: Request) -> tuple[str, str]:
    store = request.app.state.store
    actor = getattr(request.state, "verified_actor", None)
    if not actor:
        scheme, _, token = request.headers.get("authorization", "").partition(" ")
        actor = store.user_for_token(token.strip()) if scheme.lower() == "bearer" else None
    if not actor:
        raise HTTPException(401, "valid authenticated identity required")
    context = store.actor_context(actor)
    if request.method != "GET" and context["role"] == "viewer":
        raise HTTPException(403, "read-only account")
    if request.query_params:
        raise HTTPException(422, "query parameters are not supported")
    return context["tenant"], str(actor)


def _fields(value: Any, required: set[str], optional: set[str] | None = None) -> dict[str, Any]:
    if not isinstance(value, dict) or not required <= value.keys() or value.keys() - required - (optional or set()):
        raise HTTPException(422, "invalid request fields")
    return value


async def _body(request: Request) -> Any:
    length = request.headers.get("content-length")
    if length is not None:
        try:
            size = int(length)
        except ValueError:
            raise HTTPException(422, "invalid content length") from None
        if size < 0:
            raise HTTPException(422, "invalid content length")
        if size > MAX_BODY:
            raise HTTPException(413, "request too large")
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > MAX_BODY:
            raise HTTPException(413, "request too large")
        data.extend(chunk)
    try:
        return json.loads(data)
    except (ValueError, UnicodeError, RecursionError):
        raise HTTPException(422, "invalid JSON") from None


def _changes(payload: Any) -> tuple[str, list[dict[str, Any]]]:
    payload = _fields(payload, {"request_key", "changes"})
    if isinstance(payload["request_key"], str) and payload["request_key"].startswith("snapshot-"):
        raise HTTPException(422, "reserved operation namespace")
    changes = payload["changes"]
    if not isinstance(changes, list) or not 1 <= len(changes) <= MAX_MODULES:
        raise HTTPException(422, "expected 1..128 module changes")
    decoded = 0
    entries = 0
    for change in changes:
        _fields(change, {"module", "base", "reads", "edits"}, {"dependencies"})
        if isinstance(change["module"], str) and change["module"].startswith("requirement-"):
            raise HTTPException(422, "reserved source module namespace")
        # No trusted read-set completeness proof exists at this HTTP boundary.
        if change["reads"] is not None:
            raise HTTPException(422, "reads must be null until trusted read tracking is available")
        edits = change["edits"]
        deps = change.get("dependencies", {})
        if not isinstance(edits, dict) or not isinstance(deps, dict):
            raise HTTPException(422, "edits and dependencies must be mappings")
        entries += len(edits) + len(deps)
        if entries > MAX_ENTRIES:
            raise HTTPException(413, "too many objects or dependencies")
        for name, content in edits.items():
            try:
                name.encode("utf-8")
            except UnicodeEncodeError:
                raise HTTPException(422, "object name must be valid Unicode") from None
            if content is None:
                continue
            if not isinstance(content, str):
                raise HTTPException(422, "object content must be base64 or null")
            if len(content) > 4 * ((MAX_OBJECT + 2) // 3):
                raise HTTPException(413, "object too large")
            try:
                value = base64.b64decode(content, validate=True)
            except (ValueError, binascii.Error):
                raise HTTPException(422, "invalid base64") from None
            decoded += len(value)
            if len(value) > MAX_OBJECT or decoded > MAX_DECODED:
                raise HTTPException(413, "decoded content too large")
            edits[name] = value
    return payload["request_key"], changes


async def _call(function: Callable[..., Any], *args: Any) -> Any:
    try:
        return await run_in_threadpool(function, *args)
    except Conflict:
        raise HTTPException(409, "candidate conflicts with stored inputs or request key") from None
    except NativeStoreError:
        raise HTTPException(422, "invalid or unavailable native content") from None
    except sqlite3.Error as error:
        code = getattr(error, "sqlite_errorcode", 0) & 255
        # SQLite primary result codes are stable across Python versions.
        if code in {5, 6}:
            raise HTTPException(503, "native storage busy", headers={"Retry-After": "1"}) from None
        raise HTTPException(500, "native storage failure") from None


def _module_read(domain: Any, actor: str, module: str) -> None:
    if module.startswith("requirement-"):
        domain.require_native_module_read(actor, module)


def _compose(store: NativeStore, domain: Any, tenant: str, actor: str, selected: dict[str, str]) -> dict[str, Any]:
    # Authorize the full immutable dependency closure before creating a record.
    pending = list(selected.items())
    seen: dict[str, str] = {}
    while pending:
        module, revision = pending.pop()
        if module in seen:
            if seen[module] != revision:
                raise Conflict("incompatible dependency revisions")
            continue
        if len(seen) >= MAX_MODULES:
            raise HTTPException(413, "too many dependency modules")
        _module_read(domain, actor, module)
        state = store.revision(tenant, module, revision)
        seen[module] = revision
        pending.extend(state["dependencies"].items())
    result: dict[str, Any] = store.compose(tenant, selected)
    return result


def _composition(store: NativeStore, domain: Any, tenant: str, actor: str, candidate: str) -> dict[str, Any]:
    # NativeStore has no composition lookup yet. This read-only adapter uses its
    # connection/revision primitives and verifies every pinned object's bytes.
    if len(candidate) != 64 or any(c not in "0123456789abcdef" for c in candidate):
        raise NativeStoreError("Invalid composition")
    with store._connection() as db:
        row = db.execute(
            "SELECT payload FROM native_compositions WHERE tenant=? AND id=?", (tenant, candidate)
        ).fetchone()
    if row is None or hashlib.sha256(row[0].encode()).hexdigest() != candidate:
        raise NativeStoreError("Composition unavailable or corrupt")
    payload = json.loads(row[0])
    for module, revision in payload["modules"].items():
        _module_read(domain, actor, module)
        state = store.revision(tenant, module, revision)
        if any(payload["modules"].get(dep) != rev for dep, rev in state["dependencies"].items()):
            raise NativeStoreError("Composition dependency mismatch")
        for name in state["objects"]:
            store.read(tenant, module, revision, name)
    return {"id": candidate, **payload}


def _source(domain: Any, actor: str, doc_id: str) -> dict[str, Any]:
    snapshot = domain.requirement_snapshot(actor, doc_id)
    try:
        encoded = json.dumps(snapshot, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    except UnicodeError:
        raise HTTPException(422, "source must be valid Unicode") from None
    if len(encoded) > MAX_OBJECT:
        raise HTTPException(413, "requirement snapshot too large")
    return {"source_version": hashlib.sha256(encoded).hexdigest(), "snapshot": snapshot}


def _snapshot(
    store: NativeStore, domain: Any, tenant: str, actor: str, doc_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    # Recheck current ACL even on historical replay; never rebuild historical bytes.
    domain.get_doc_shared(actor, doc_id, write=True)
    key = payload["request_key"]
    if not isinstance(key, str) or not 1 <= len(key) <= 128:
        raise HTTPException(422, "request_key must contain 1..128 characters")
    if (
        not isinstance(payload["source_version"], str)
        or re.fullmatch(r"[0-9a-f]{64}", payload["source_version"]) is None
    ):
        raise HTTPException(422, "source_version must be a SHA256 digest")
    base = payload["base"]
    if base is not None and (not isinstance(base, str) or re.fullmatch(r"[0-9a-f]{64}", base) is None):
        raise HTTPException(422, "base must be null or a SHA256 revision")
    binding = {"doc_id": doc_id, **payload}
    try:
        native_key = "snapshot-" + hashlib.sha256(key.encode()).hexdigest()
    except UnicodeError:
        raise HTTPException(422, "request_key must be valid Unicode") from None
    module = domain.bind_native_requirement(actor, doc_id)
    with store._connection() as db:
        receipt = db.execute(
            "SELECT result FROM native_receipts WHERE tenant=? AND actor=? AND request_key=?",
            (tenant, actor, native_key),
        ).fetchone()
    if receipt:
        result = json.loads(receipt[0])
        revision = result["revisions"].get(module)
        if not revision:
            raise Conflict("operation key reused for another requirement")
        saved = json.loads(store.read(tenant, module, revision, "snapshot.json"))
        if saved["binding"] != binding:
            raise Conflict("operation key reused for different inputs")
    else:
        source = _source(domain, actor, doc_id)
        if source["source_version"] != payload["source_version"]:
            raise Conflict("source version changed")
        content = json.dumps(
            {"binding": binding, **source}, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode()
        result = store.submit(
            tenant,
            actor,
            native_key,
            [{"module": module, "base": payload["base"], "reads": None, "edits": {"snapshot.json": content}}],
        )
        revision = result["revisions"][module]
    composition = store.compose(tenant, {module: revision})
    return {
        "source_version": payload["source_version"],
        "module": module,
        "revision": revision,
        "composition": composition,
        "state": "candidate",
    }


def create_native_router(store: NativeStore) -> APIRouter:
    router = APIRouter(prefix=PREFIX)

    @router.get("/requirements/{doc_id}/source")
    async def source(doc_id: str, request: Request) -> Any:
        _, actor = await run_in_threadpool(_identity, request)
        return await _call(_source, request.app.state.store, actor, doc_id)

    @router.post("/requirements/{doc_id}/snapshots")
    async def snapshot(doc_id: str, request: Request) -> Any:
        tenant, actor = await run_in_threadpool(_identity, request)
        payload = _fields(await _body(request), {"request_key", "source_version", "base"})
        return await _call(_snapshot, store, request.app.state.store, tenant, actor, doc_id, payload)

    @router.post("/batches")
    async def submit(request: Request) -> Any:
        tenant, actor = await run_in_threadpool(_identity, request)
        key, changes = _changes(await _body(request))
        return await _call(store.submit, tenant, actor, key, changes)

    @router.get("/modules/{module}/head")
    async def head(module: str, request: Request) -> Any:
        tenant, actor = await run_in_threadpool(_identity, request)
        await _call(_module_read, request.app.state.store, actor, module)
        return {"revision": await _call(store.head, tenant, module)}

    @router.get("/modules/{module}/revisions/{revision}")
    async def revision(module: str, revision: str, request: Request) -> Any:
        tenant, actor = await run_in_threadpool(_identity, request)
        await _call(_module_read, request.app.state.store, actor, module)
        return await _call(store.revision, tenant, module, revision)

    @router.get("/modules/{module}/revisions/{revision}/objects/{name:path}")
    async def read(module: str, revision: str, name: str, request: Request) -> Response:
        tenant, actor = await run_in_threadpool(_identity, request)
        await _call(_module_read, request.app.state.store, actor, module)
        value = await _call(store.read, tenant, module, revision, name)
        return Response(value, media_type="application/octet-stream", headers={"Cache-Control": "no-store"})

    @router.post("/compositions")
    async def compose(request: Request) -> Any:
        tenant, actor = await run_in_threadpool(_identity, request)
        payload = _fields(await _body(request), {"selected"})
        selected = payload["selected"]
        if not isinstance(selected, dict) or not 1 <= len(selected) <= MAX_MODULES:
            raise HTTPException(422, "expected 1..128 selected modules")
        return await _call(_compose, store, request.app.state.store, tenant, actor, selected)

    @router.get("/compositions/{candidate}")
    async def composition(candidate: str, request: Request) -> Any:
        tenant, actor = await run_in_threadpool(_identity, request)
        return await _call(_composition, store, request.app.state.store, tenant, actor, candidate)

    return router
