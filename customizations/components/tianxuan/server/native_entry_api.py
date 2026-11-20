"""Ordinary authenticated entry: only a requirement and installed scope choices."""

import json
import os
import re

from access_control import COOKIE, SESSION_COOKIE
from api import _require_actor
from fastapi import APIRouter, HTTPException, Request
from native_api import _body, _fields, _identity
from native_execution_host import entry_key
from native_store import NativeStoreError


def model_choices(spec):
    return [
        {"id": model["id"], "capabilities": model.get("capabilities", [])}
        for model in spec["catalog"]
        if model.get("available") is True
        and "agent" in model.get("targets", [])
        and any(set(required) <= set(model.get("capabilities", [])) for required in spec["complexity"].values())
    ]


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
            models=model_choices(spec),
            limit="Finite installed outputs; semantic quality depends on admitted runtimes",
        )

    @router.post("/execute")
    async def execute(request: Request):
        _, actor = _identity(request)
        payload = _fields(await _body(request), {"requirement", "call_id", "scopes"}, {"dependencies", "model"})
        spec = entry.installation.verify()
        scopes = payload["scopes"]
        if (
            not isinstance(scopes, list)
            or not scopes
            or not all(isinstance(x, str) and x in spec["scopes"] for x in scopes)
        ):
            raise HTTPException(422, "Select installed scopes")
        model = payload.get("model")
        if "model" in payload and not any(item["id"] == model for item in model_choices(spec)):
            raise HTTPException(422, "Select an available installed model profile")
        scheme, _, token = request.headers.get("authorization", "").partition(" ")
        token = token.strip() if scheme.lower() == "bearer" else request.cookies.get(COOKIE, "")
        try:
            with entry.ledger.transaction():
                dependencies = entry.validate_dependencies(
                    actor, payload["requirement"], payload.get("dependencies", [])
                )
                choices = {"scopes": scopes, "dependencies": dependencies}
                if model is not None:
                    choices["model"] = model
                key = entry.ledger.enqueue(
                    actor,
                    payload["requirement"],
                    payload["call_id"],
                    choices,
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

    @router.post("/calls/status")
    async def call_status(request: Request):
        tenant, actor = _identity(request, read_only=True)
        try:
            payload = _fields(await _body(request), {"call_id"})
            key = entry_key(tenant, actor, payload["call_id"])
        except NativeStoreError as error:
            raise HTTPException(422, str(error)) from None
        return await status(key, request)

    @router.get("/{key}/releases")
    async def releases(key: str, request: Request, after: int = 0, limit: int = 100):
        if set(request.query_params) - {"after", "limit"}:
            raise HTTPException(422, "Unsupported history query parameter")
        actor = _require_actor(request, None, request.headers.get("authorization"))
        tenant = entry.domain.actor_context(actor)["tenant"]
        try:
            return entry.release_history(tenant, actor, key, after, limit)
        except NativeStoreError as error:
            raise HTTPException(409, str(error)) from None

    @router.post("/{key}/rollback")
    async def rollback(key: str, request: Request):
        tenant, actor = _identity(request)
        payload = _fields(await _body(request), {"call_id", "selection", "expected"})
        if not all(
            isinstance(payload[f], str) and re.fullmatch(r"[0-9a-f]{64}", payload[f]) for f in ("selection", "expected")
        ):
            raise HTTPException(422, "Exact historical selection and current head required")
        try:
            scheme, _, token = request.headers.get("authorization", "").partition(" ")
            if scheme.lower() != "bearer":
                token = request.cookies.get(COOKIE, "")
                if os.environ.get("TIANXUAN_AUTH_MODE") == "accounts":
                    token = request.cookies.get(SESSION_COOKIE, "") or token
            return entry.rollback(
                tenant, actor, key, payload["call_id"], payload["selection"], payload["expected"],
                credential=token.strip(),
            )
        except NativeStoreError as error:
            raise HTTPException(409, str(error)) from None

    @router.get("/{key}")
    async def status(key: str, request: Request):
        tenant, actor = _identity(request, read_only=True)
        with entry.domain._connection_lock:
            row = entry.domain.db.execute(
                "SELECT * FROM native_entry_intents WHERE id=? AND actor=? AND tenant=?", (key, actor, tenant)
            ).fetchone()
            if row is None:
                raise HTTPException(404, "Entry unavailable")
            document = entry.domain.get_doc_shared(actor, row["requirement"])
            result = dict(
                entry=key,
                tasks=entry.task_references(key, actor),
                policy=entry.policy_reference(actor, row["requirement"]),
                state=row["state"],
                source_digest=row["source"],
                requested_profile=json.loads(row["payload"])["choices"].get("model"),
                progress=document["progress"],
                failures=[r for r in entry.consumer.failures if r["id"] == key],
            )

        if row["state"] == "delivered":
            try:
                result["progress"]["publication"] = entry.workflow.release.publication_progress(
                    tenant, actor, entry.product(row), "stable"
                )
            except NativeStoreError as error:
                raise HTTPException(409, str(error)) from None
        return result

    return router
