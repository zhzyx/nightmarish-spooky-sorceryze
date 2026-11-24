"""Authenticated migration status and entry selection shared by Web and AI."""

import json
import sys
from pathlib import Path
from typing import Literal
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from tianxuan_core import DEFAULT_PROJECT, PROJECT_PATTERN, _connection_call

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "migration"))
from migration_status import read_import_status
from routing import tenant_entry


class Selection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project: str = Field(default=DEFAULT_PROJECT, pattern=PROJECT_PATTERN)
    requirement: str | None = Field(default=None, min_length=1, max_length=200)


class EntrySetting(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entry: Literal["existing", "tianxuan"]


class NewTask(Selection):
    title: str = Field(min_length=1, max_length=512)
    call_id: str = Field(min_length=1, max_length=200)


def migration_routes(store, actor_dependency, native_store):
    router = APIRouter(prefix="/api/v1/migration")
    identity = Depends(actor_dependency)

    @_connection_call
    def handle(store, actor, name, data, call_id=None):
        try:
            if name == "migration.start":
                if call_id is not None and "call_id" in data and data["call_id"] != call_id:
                    raise HTTPException(422, "conflicting call_id")
                scope = NewTask.model_validate({**data, **({"call_id": call_id} if call_id is not None else {})})
            else:
                if call_id is not None:
                    raise HTTPException(422, "unexpected call_id")
                scope = Selection.model_validate(data)
        except ValidationError as exc:
            raise HTTPException(422, "invalid migration arguments") from exc
        context = store.actor_context(actor)
        tenant = context["tenant"]
        if scope.requirement:
            store.get_doc_shared(actor, scope.requirement)
        if name == "migration.status":
            result = read_import_status(native_store.database, tenant, scope.project) if native_store else None
            return (
                {
                    **result,
                    "available": True,
                    "revision": result["source_revision"],
                    "catalog_revision": result["revision"],
                }
                if result
                else {"available": False}
            )
        if name.startswith("configure."):
            if context["role"] != "admin":
                raise HTTPException(403, "administrator required")
            choice = name.split(".")[1]
            tenant_entry(store.db, tenant, scope.project, scope.requirement, entry=choice)
            return {"entry": choice}
        if isinstance(scope, NewTask):
            store._require_editor(actor)
            if not scope.title.strip():
                raise HTTPException(422, "title required")
            if not store.db.in_transaction:
                store.db.execute("BEGIN IMMEDIATE")
            store.db.execute(
                "CREATE TABLE IF NOT EXISTS migration_starts (tenant TEXT, actor TEXT, call_id TEXT, request TEXT NOT NULL, result TEXT NOT NULL, PRIMARY KEY(tenant,actor,call_id))"
            )
            key = (tenant, actor, scope.call_id)
            request = scope.model_dump_json()
            previous = store.db.execute(
                "SELECT request,result FROM migration_starts WHERE tenant=? AND actor=? AND call_id=?", key
            ).fetchone()
            if previous:
                if previous[0] != request:
                    raise HTTPException(409, "call_id already used for another task")
                saved = json.loads(previous[1])
                if saved.get("issue_id"):
                    store._require_tenant_issue(actor, saved["issue_id"], write=True)
                return saved
        entry = tenant_entry(store.db, tenant, scope.project, scope.requirement)
        if name == "migration.entry":
            return {"entry": entry}
        if not isinstance(scope, NewTask):
            raise HTTPException(400, "unknown migration tool")
        if entry == "existing":
            url = (
                f"https://github.com/{scope.project}/issues/new?" + urlencode({"title": scope.title})
                if "/" in scope.project
                else None
            )
            response = {"entry": entry, "url": url}
        else:
            issue = store.create_issue(
                actor, scope.title.strip(), requirement_id=scope.requirement, project=scope.project
            )
            response = {"entry": entry, "issue_id": issue["id"], "url": "/issues/" + issue["id"]}
        store.db.execute("INSERT INTO migration_starts VALUES(?,?,?,?,?)", (*key, request, json.dumps(response)))
        return response

    @router.get("/status")
    def status(project: str = "workspace", actor: str = identity):
        return handle(store, actor, "migration.status", {"project": project})

    @router.get("/entry")
    def read(project: str = "workspace", requirement: str | None = None, actor: str = identity):
        return handle(store, actor, "migration.entry", {"project": project, "requirement": requirement})

    @router.put("/entry")
    def set_entry(
        body: EntrySetting, project: str = "workspace", requirement: str | None = None, actor: str = identity
    ):
        return handle(store, actor, "configure." + body.entry, {"project": project, "requirement": requirement})

    @router.post("/tasks")
    def start(body: NewTask, actor: str = identity):
        return handle(store, actor, "migration.start", body.model_dump())

    return router, lambda actor, name, data, call_id: handle(store, actor, name, data, call_id)
