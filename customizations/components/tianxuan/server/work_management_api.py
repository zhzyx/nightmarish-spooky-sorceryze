"""Authenticated issue planning and revision-specific human review."""

from typing import Literal

import issue_lifecycle
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from issue_flow import execute_flow
from pydantic import BaseModel, ConfigDict, StrictInt
from tianxuan_core import DEFAULT_PROJECT
from work_management import (
    define_text_field,
    execute,
    godot_inputs,
    list_issue_artifacts,
    plan_membership,
    project_fields,
    read_approved_asset,
    read_issue_artifact,
)


class LifecycleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: StrictInt
    asset_version: StrictInt
    revision: str
    call_id: str
    comment: str | None = None


def create_work_router(store, actor_dependency):
    router = APIRouter(prefix="/api/v1")
    actor_dep = Depends(actor_dependency)

    def issue_actor(issue_id: str, project: str | None = None, actor: str = actor_dep):
        if project is not None and store.read_issue(actor, issue_id)["project"] != project:
            raise HTTPException(404, "issue not found in project")
        return actor

    scoped_actor = Depends(issue_actor)

    @router.get("/work/field-definitions")
    def fields(project: str, actor: str = actor_dep):
        return project_fields(store, actor, project)

    @router.put("/work/field-definitions/{key}")
    def define_field(key: str, project: str, body: dict, actor: str = actor_dep):
        if body.keys() != {"label"}:
            raise HTTPException(422, "text field label required")
        return define_text_field(store, actor, project, key, body["label"])

    @router.get("/work/roadmap")
    def roadmap(actor: str = actor_dep):
        return store.dispatch_tool(actor, "work.roadmap", {})

    @router.get("/issues/{issue_id}/work")
    def read(issue_id: str, actor: str = scoped_actor):
        return store.dispatch_tool(actor, "work.read", {"issue_id": issue_id})

    @router.get("/issues/{issue_id}/work/plan")
    def read_plan(issue_id: str, project: str, actor: str = actor_dep):
        return plan_membership(store, actor, issue_id, project)

    @router.get("/issues/by-number/{number}/artifacts")
    def artifacts(number: int, project: str = DEFAULT_PROJECT, actor: str = actor_dep):
        return {"artifacts": list_issue_artifacts(store, actor, project, number)}

    @router.get("/issues/by-number/{number}/artifacts/{version}", response_class=Response)
    def artifact(number: int, version: int, project: str = DEFAULT_PROJECT, actor: str = actor_dep):
        return Response(
            read_issue_artifact(store, actor, project, number, version),
            media_type="application/octet-stream",
            headers={
                "Cache-Control": "private, no-store",
                "Content-Disposition": "attachment",
                "X-Content-Type-Options": "nosniff",
            },
        )

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

    @router.get("/issues/{issue_id}/lifecycle")
    def lifecycle(issue_id: str, project: str = DEFAULT_PROJECT, actor: str = actor_dep):
        return issue_lifecycle.read(store, actor, issue_id, project)

    @router.post("/issues/{issue_id}/lifecycle/{operation}")
    def change_lifecycle(
        issue_id: str,
        operation: Literal["accept", "close", "reopen"],
        body: LifecycleRequest,
        project: str = DEFAULT_PROJECT,
        actor: str = actor_dep,
    ):
        return issue_lifecycle.mutate(store, actor, issue_id, project, operation, **body.model_dump())

    @router.get("/issues/{issue_id}/work/flow")
    def read_flow(issue_id: str, actor: str = scoped_actor):
        return store.dispatch_tool(actor, "flow.read", {"issue_id": issue_id})

    @router.post("/issues/{issue_id}/work/flow/{operation}")
    def mutate_flow(
        issue_id: str,
        operation: Literal["configure", "dependencies", "advance", "judge"],
        body: dict,
        actor: str = scoped_actor,
    ):
        if "issue_id" in body:
            raise HTTPException(422, "issue_id belongs in the request path")
        return execute_flow(
            store, actor, f"flow.{operation}", {**body, "issue_id": issue_id}, human=operation == "judge"
        )

    @router.post("/issues/{issue_id}/work/{operation}")
    def mutate(
        issue_id: str,
        operation: Literal["plan", "log", "submit_asset", "decide"],
        body: dict,
        actor: str = scoped_actor,
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
