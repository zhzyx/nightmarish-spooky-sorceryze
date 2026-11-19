"""Authenticated issue planning and revision-specific human review."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from work_management import execute


def create_work_router(store, actor_dependency):
    router = APIRouter(prefix="/api/v1")
    actor_dep = Depends(actor_dependency)

    @router.get("/work/roadmap")
    def roadmap(actor: str = actor_dep):
        return store.dispatch_tool(actor, "work.roadmap", {})

    @router.get("/issues/{issue_id}/work")
    def read(issue_id: str, actor: str = actor_dep):
        return store.dispatch_tool(actor, "work.read", {"issue_id": issue_id})

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
