"""Read-only published history. All HTTP and AI reads resolve the same tenant and catalog."""

import base64
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError

OPERATIONS = ("branches", "search", "detail", "body", "commits", "commit", "tags", "tag_object", "file", "attachment")
HISTORY_TOOLS = frozenset("migration.history." + name for name in OPERATIONS)


class Scope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project: str = Field(default="workspace", max_length=201, min_length=1)
    revision: str | None = Field(default=None, pattern="^[0-9a-f]{64}$")


class Page(Scope):
    offset: int = Field(default=0, ge=0, le=10000000)
    limit: int = Field(default=20, ge=1, le=100)


class Search(Page):
    query: str = Field(default="", max_length=256)
    kind: str | None = Field(default=None, max_length=48)


class Detail(Page):
    source_id: str = Field(min_length=1, max_length=4096)


class Commits(Page):
    commit: str | None = Field(default=None, pattern="^[0-9a-f]{40}([0-9a-f]{24})?$")
    path: str | None = Field(default=None, max_length=1024)


class Commit(Scope):
    commit: str = Field(pattern="^[0-9a-f]{40}([0-9a-f]{24})?$")


class TagObject(Scope):
    oid: str = Field(pattern="^[0-9a-f]{40}([0-9a-f]{24})?$")
    byte_offset: int = Field(default=0, ge=0)


class File(Scope):
    commit: str | None = Field(default=None, pattern="^[0-9a-f]{40}([0-9a-f]{24})?$")
    path: str = Field(min_length=1, max_length=1024)


class Body(Scope):
    source_id: str = Field(min_length=1, max_length=4096)
    offset: int = Field(default=0, ge=0, le=1000000000)
    limit: int = Field(default=16384, ge=1, le=16384)


class Attachment(Scope):
    source_id: str = Field(min_length=1, max_length=4096)


def history_routes(store, actor_dependency, native_store):
    from history_git import commit_mapping, list_branches, list_commits, list_tags, read_file, read_tag_object
    from history_records import read_attachment, record_detail, search_records
    from migration_status import read_import_status

    router = APIRouter(prefix="/api/v1/migration/history")

    def execute(actor, operation, payload):
        model = {
            "branches": Page,
            "search": Search,
            "detail": Detail,
            "body": Body,
            "commits": Commits,
            "commit": Commit,
            "tags": Page,
            "tag_object": TagObject,
            "file": File,
            "attachment": Attachment,
        }[operation]
        try:
            args = model.model_validate(payload).model_dump()
        except ValidationError as exc:
            raise HTTPException(422, "Invalid history query") from exc
        tenant = store.actor_context(actor)["tenant"]
        project = args.pop("project")
        requested = args.pop("revision")
        publication = read_import_status(native_store.database, tenant, project) if native_store else None
        if publication is None or (requested is not None and requested != publication["revision"]):
            raise HTTPException(404, "Publication unavailable")
        scope = (native_store.database, tenant, project, publication["revision"])
        try:
            if operation == "branches":
                return list_branches(*scope, **args)
            if operation == "search":
                return search_records(*scope, **args)
            if operation == "detail":
                detail = record_detail(*scope, **args)
                row = detail["record"]
                if row["kind"] == "requirement":
                    content = row["content"]
                    detail["document"] = read_file(*scope, content["commit"], content["path"])
                return detail
            if operation == "body":
                from history_records import read_body

                return read_body(*scope, **args)
            if operation == "commits":
                return list_commits(*scope, **args)
            if operation == "commit":
                return commit_mapping(*scope, **args)
            if operation == "tags":
                return list_tags(*scope, **args)
            if operation == "tag_object":
                return read_tag_object(*scope, **args)
            if operation == "file":
                args["commit"] = args["commit"] or publication["source_revision"]
                return read_file(*scope, **args)
            return read_attachment(*scope, args["source_id"])
        except LookupError as exc:
            raise HTTPException(404, "Archive item unavailable") from exc
        except ValueError as exc:
            raise HTTPException(422, "Invalid or unsupported archive content or query") from exc

    @router.get("/{operation}")
    def read(
        operation: Literal[
            "branches", "search", "detail", "body", "commits", "commit", "tags", "tag_object", "file", "attachment"
        ],
        request: Request,
        actor: str = Depends(actor_dependency),
    ):
        result = execute(actor, operation, dict(request.query_params))
        if operation == "attachment":
            return Response(
                result,
                media_type="application/octet-stream",
                headers={
                    "Content-Disposition": "attachment",
                    "X-Content-Type-Options": "nosniff",
                    "Cache-Control": "private, no-store",
                },
            )
        return result

    def tool(actor, name, payload, call_id):
        if call_id is not None:
            raise HTTPException(422, "History reads do not accept execution identifiers")
        operation = name.removeprefix("migration.history.")
        if operation == "attachment":
            payload = dict(payload)
            offset = payload.pop("byte_offset", 0)
            if type(offset) is not int or offset < 0:
                raise HTTPException(422, "Invalid attachment offset")
            content = execute(actor, operation, payload)
            if offset > len(content):
                raise HTTPException(422, "Invalid attachment offset")
            chunk = content[offset : offset + 49152]
            end = offset + len(chunk)
            return {
                "source_id": payload["source_id"],
                "size": len(content),
                "encoding": "base64",
                "data": base64.b64encode(chunk).decode("ascii"),
                "next_offset": end if end < len(content) else None,
            }
        return execute(actor, operation, payload)

    return router, tool
