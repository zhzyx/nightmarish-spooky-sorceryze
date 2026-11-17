"""Authenticated, bounded HTTP adapter for candidate storage (never approval)."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
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
    if request.method != "GET" and store.role_of(actor) == "viewer":
        raise HTTPException(403, "read-only account")
    if request.query_params:
        raise HTTPException(422, "query parameters are not supported")
    return store._tenant_of(actor), str(actor)


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
    changes = payload["changes"]
    if not isinstance(changes, list) or not 1 <= len(changes) <= MAX_MODULES:
        raise HTTPException(422, "expected 1..128 module changes")
    decoded = 0
    entries = 0
    for change in changes:
        _fields(change, {"module", "base", "reads", "edits"}, {"dependencies"})
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


def _composition(store: NativeStore, tenant: str, candidate: str) -> dict[str, Any]:
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
        state = store.revision(tenant, module, revision)
        if any(payload["modules"].get(dep) != rev for dep, rev in state["dependencies"].items()):
            raise NativeStoreError("Composition dependency mismatch")
        for name in state["objects"]:
            store.read(tenant, module, revision, name)
    return {"id": candidate, **payload}


def create_native_router(store: NativeStore) -> APIRouter:
    router = APIRouter(prefix=PREFIX)

    @router.post("/batches")
    async def submit(request: Request) -> Any:
        tenant, actor = await run_in_threadpool(_identity, request)
        key, changes = _changes(await _body(request))
        return await _call(store.submit, tenant, actor, key, changes)

    @router.get("/modules/{module}/head")
    async def head(module: str, request: Request) -> Any:
        tenant, _ = await run_in_threadpool(_identity, request)
        return {"revision": await _call(store.head, tenant, module)}

    @router.get("/modules/{module}/revisions/{revision}")
    async def revision(module: str, revision: str, request: Request) -> Any:
        tenant, _ = await run_in_threadpool(_identity, request)
        return await _call(store.revision, tenant, module, revision)

    @router.get("/modules/{module}/revisions/{revision}/objects/{name:path}")
    async def read(module: str, revision: str, name: str, request: Request) -> Response:
        tenant, _ = await run_in_threadpool(_identity, request)
        value = await _call(store.read, tenant, module, revision, name)
        return Response(value, media_type="application/octet-stream", headers={"Cache-Control": "no-store"})

    @router.post("/compositions")
    async def compose(request: Request) -> Any:
        tenant, _ = await run_in_threadpool(_identity, request)
        payload = _fields(await _body(request), {"selected"})
        selected = payload["selected"]
        if not isinstance(selected, dict) or not 1 <= len(selected) <= MAX_MODULES:
            raise HTTPException(422, "expected 1..128 selected modules")
        return await _call(store.compose, tenant, selected)

    @router.get("/compositions/{candidate}")
    async def composition(candidate: str, request: Request) -> Any:
        tenant, _ = await run_in_threadpool(_identity, request)
        return await _call(_composition, store, tenant, candidate)

    return router
