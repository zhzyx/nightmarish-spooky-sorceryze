"""Ordinary authenticated entry: only a requirement and installed scope choices."""

from access_control import COOKIE
from fastapi import APIRouter, HTTPException, Request
from native_api import _body, _fields, _identity
from native_store import NativeStoreError


def create_entry_router(entry):
    router = APIRouter(prefix="/api/v1/native/entry")

    @router.get("/capabilities")
    async def capabilities(request: Request):
        _identity(request)
        spec = entry.installation.verify()
        return dict(
            automatic_execution=True,
            mode=spec["mode"],
            context_tools=entry.runtime_installation is not None,
            execution_nodes=entry.execution_nodes,
            identity=spec["identity"],
            scopes=spec["scopes"],
            limit="Finite installed outputs; semantic quality depends on admitted runtimes",
        )

    @router.post("/execute")
    async def execute(request: Request):
        _, actor = _identity(request)
        payload = _fields(await _body(request), {"requirement", "call_id", "scopes"}, {"dependencies"})
        spec = entry.installation.verify()
        scopes = payload["scopes"]
        if (
            not isinstance(scopes, list)
            or not scopes
            or not all(isinstance(x, str) and x in spec["scopes"] for x in scopes)
        ):
            raise HTTPException(422, "Select installed scopes")
        scheme, _, token = request.headers.get("authorization", "").partition(" ")
        token = token.strip() if scheme.lower() == "bearer" else request.cookies.get(COOKIE, "")
        try:
            with entry.ledger.transaction():
                dependencies = entry.validate_dependencies(
                    actor, payload["requirement"], payload.get("dependencies", [])
                )
                key = entry.ledger.enqueue(
                    actor,
                    payload["requirement"],
                    payload["call_id"],
                    {"scopes": scopes, "dependencies": dependencies},
                    credential=token,
                )
            entry.consumer.notify(key)
            return {"entry": key}
        except NativeStoreError as error:
            raise HTTPException(409, str(error)) from None

    @router.post("/handoff")
    async def handoff(request: Request):
        _, actor = _identity(request)
        payload = _fields(await _body(request), {"requirement", "expected_policy"})
        try:
            return entry.handoff(actor, payload["requirement"], payload["expected_policy"])
        except NativeStoreError as error:
            raise HTTPException(409, str(error)) from None

    @router.get("/{key}")
    async def status(key: str, request: Request):
        tenant, actor = _identity(request)
        row = next(
            (r for r in entry.entries() if r["id"] == key and r["actor"] == actor and r["tenant"] == tenant), None
        )
        if row is None:
            raise HTTPException(404, "Entry unavailable")
        with entry.domain._connection_lock:
            entry.domain._require_requirement(actor, row["requirement"], write=False)
            if row["state"] != "delivered":
                entry.ledger.authorize(key)
            return dict(
                entry=key,
                tasks=entry.task_references(key),
                policy=entry.policy_reference(actor, row["requirement"]),
                state=row["state"],
                progress=entry.domain.sync_progress(row["requirement"], actor=actor),
                failures=[r for r in entry.consumer.failures if r["id"] == key],
            )

    return router
