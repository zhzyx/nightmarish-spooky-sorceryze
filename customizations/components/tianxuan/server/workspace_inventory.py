"""Read-only workspace projections of admitted native storage and execution ledgers."""

import re
from typing import Any, cast

from fastapi import APIRouter, HTTPException, Request
from native_api import _call, _identity, _module_read
from starlette.concurrency import run_in_threadpool
from tianxuan_core import NotFound, PermissionDenied

PAGE_SIZE = 30
TASK_LIMIT = 12


def _page(items: list[dict[str, Any]], key: str, field: str) -> dict[str, Any]:
    visible = items[:PAGE_SIZE]
    return {
        "available": True,
        key: visible,
        "next_cursor": visible[-1][field] if len(items) > PAGE_SIZE else None,
    }


def _native_modules(store: Any, domain: Any, tenant: str, actor: str, after: str) -> dict[str, Any]:
    modules: list[dict[str, Any]] = []
    with store._connection() as db:
        rows = db.execute(
            "SELECT module,revision FROM native_heads WHERE tenant=? AND module>? ORDER BY module",
            (tenant, after),
        )
        for row in rows:
            try:
                _module_read(domain, actor, row["module"])
            except (NotFound, PermissionDenied):
                continue
            modules.append({"module": row["module"], "revision": row["revision"]})
            if len(modules) > PAGE_SIZE:
                break
    return _page(modules, "modules", "module")


def _entry_runs(entry: Any, tenant: str, actor: str, after: str) -> dict[str, Any]:
    domain = entry.domain
    runs: list[dict[str, Any]] = []
    with domain._connection_lock:
        db = domain.db
        if after:
            previous = db.execute(
                "SELECT rowid,requirement FROM native_entry_intents WHERE tenant=? AND actor=? AND id=?",
                (tenant, actor, after),
            ).fetchone()
            if previous is None:
                raise HTTPException(404, "run cursor unavailable")
            try:
                domain._require_requirement(actor, previous["requirement"])
            except (NotFound, PermissionDenied):
                raise HTTPException(404, "run cursor unavailable") from None
            rows = db.execute(
                "SELECT id,requirement,state FROM native_entry_intents WHERE tenant=? AND actor=? AND rowid<? "
                "ORDER BY rowid DESC",
                (tenant, actor, previous["rowid"]),
            )
        else:
            rows = db.execute(
                "SELECT id,requirement,state FROM native_entry_intents WHERE tenant=? AND actor=? ORDER BY rowid DESC",
                (tenant, actor),
            )
        for row in rows:
            try:
                requirement = domain._require_requirement(actor, row["requirement"])
            except (NotFound, PermissionDenied):
                continue
            tasks = []
            for task in db.execute(
                "SELECT * FROM native_tasks WHERE tenant=? AND json_extract(task,'$.mandate')=? ORDER BY ready_at,id",
                (tenant, row["id"]),
            ):
                try:
                    entry.workflow._read_allowed(actor, task)
                    issue = domain.get_issue(task["issue"])
                except (NotFound, PermissionDenied):
                    continue
                tasks.append({
                    "id": task["id"],
                    "issue_id": task["issue"],
                    "title": issue["title"],
                    "state": task["state"],
                })
                if len(tasks) > TASK_LIMIT:
                    break
            runs.append({
                "id": row["id"],
                "requirement_id": row["requirement"],
                "title": requirement["title"],
                "state": row["state"],
                "updated_at": None,
                "tasks": tasks[:TASK_LIMIT],
                "tasks_truncated": len(tasks) > TASK_LIMIT,
            })
            if len(runs) > PAGE_SIZE:
                break
    return _page(runs, "runs", "id")


def create_workspace_inventory_router(native_entry: Any, native_store: Any) -> APIRouter:
    router = APIRouter(prefix="/api/v1/workspace")

    async def list_runs(request: Request, after: str) -> dict[str, Any]:
        tenant, actor = await run_in_threadpool(_identity, request)
        if after and not re.fullmatch(r"[a-f0-9]{64}", after):
            raise HTTPException(422, "invalid run cursor")
        if native_entry is None:
            return {"available": False, "runs": [], "next_cursor": None}
        if native_entry.domain is not request.app.state.store:
            raise HTTPException(503, "native execution store unavailable")
        return cast(dict[str, Any], await _call(_entry_runs, native_entry, tenant, actor, after))

    async def list_modules(request: Request, after: str) -> dict[str, Any]:
        tenant, actor = await run_in_threadpool(_identity, request)
        if after and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", after):
            raise HTTPException(422, "invalid module cursor")
        if native_store is None:
            return {"available": False, "modules": [], "next_cursor": None}
        return cast(
            dict[str, Any], await _call(_native_modules, native_store, request.app.state.store, tenant, actor, after)
        )

    @router.get("/runs")
    async def runs(request: Request) -> dict[str, Any]:
        return await list_runs(request, "")

    @router.get("/runs/after/{after}")
    async def more_runs(request: Request, after: str) -> dict[str, Any]:
        return await list_runs(request, after)

    @router.get("/modules")
    async def modules(request: Request) -> dict[str, Any]:
        return await list_modules(request, "")

    @router.get("/modules/after/{after}")
    async def more_modules(request: Request, after: str) -> dict[str, Any]:
        return await list_modules(request, after)

    return router
