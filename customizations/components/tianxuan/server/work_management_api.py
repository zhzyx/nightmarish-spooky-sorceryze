"""Authenticated issue planning and revision-specific human review."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from work_management import execute, godot_inputs, read_approved_asset


def create_work_router(store, actor_dependency):
    router = APIRouter(prefix="/api/v1")
    actor_dep = Depends(actor_dependency)

    @router.get("/work/roadmap")
    def roadmap(actor: str = actor_dep):
        return store.dispatch_tool(actor, "work.roadmap", {})

    @router.get("/issues/{issue_id}/work")
    def read(issue_id: str, actor: str = actor_dep):
        return store.dispatch_tool(actor, "work.read", {"issue_id": issue_id})

    @router.get("/issues/{issue_id}/work/godot-inputs", response_class=Response)
    def current_godot_inputs(issue_id: str, request: Request, actor: str = actor_dep):
        if request.query_params:
            raise HTTPException(422, "Godot inputs are determined by the current issue")
        return Response(
            godot_inputs(store, actor, issue_id),
            media_type="application/zip",
            headers={
                "Cache-Control": "private, no-store",
                "Content-Disposition": "attachment",
                "X-Content-Type-Options": "nosniff",
            },
        )

    @router.get("/issues/{issue_id}/work/approved-asset", response_class=Response)
    def approved_asset(
        issue_id: str, kind: Literal["concept", "model"], module: str, revision: str, path: str, actor: str = actor_dep
    ):
        content = read_approved_asset(store, actor, issue_id, kind, module, revision, path)
        return Response(
            content,
            media_type="application/octet-stream",
            headers={
                "Cache-Control": "private, no-store",
                "X-Content-Type-Options": "nosniff",
                "Content-Disposition": "attachment",
            },
        )

    @router.post("/issues/{issue_id}/work/{operation}")
    def mutate(
        issue_id: str,
        operation: Literal["plan", "log", "submit_asset", "decide"],
        body: dict,
        actor: str = actor_dep,
    ):
        if "issue_id" in body:
            raise HTTPException(422, "issue_id belongs in the request path")
        payload = {**body, "issue_id": issue_id}
        call_id = payload.pop("call_id", None)
        if not isinstance(call_id, str) or not call_id.strip():
            raise HTTPException(422, "a stable call_id is required")
        if operation == "decide":
            return execute(store, actor, "work.decide", payload, call_id=call_id, human=True)
        return store.dispatch_tool(actor, f"work.{operation}", payload, call_id=call_id)

    return router
