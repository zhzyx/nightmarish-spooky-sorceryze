"""Project-local work order links to immutable native module revisions."""

from typing import cast

from fastapi import APIRouter, Depends, Request
from native_api import PREFIX, _body, _call, _fields, _identity, _module_read
from native_store import Conflict, _identifier, _revision_id
from tianxuan_core import DEFAULT_PROJECT, NotFound, PermissionDenied, _connection_call


def _actor(request: Request) -> str:
    return cast(str, _identity(request, allow_project=True)[1])


def _begin(domain, *, write=False):
    if not domain.db.in_transaction:
        domain.db.execute("BEGIN IMMEDIATE" if write else "BEGIN")


@_connection_call
def _links(domain, actor, project, issue_id):
    _begin(domain)
    issue = domain._project_issue(actor, issue_id, project)
    rows = domain.db.execute(
        "SELECT module,revision,tag FROM issue_revision_links WHERE tenant_id=? AND project=? AND issue_id=? "
        "ORDER BY module,revision",
        (issue["tenant_id"], project, issue_id),
    )
    visible = []
    for row in rows:
        try:
            _module_read(domain, actor, row["module"])
        except (PermissionDenied, NotFound):
            continue
        visible.append(dict(row))
    return {"links": visible}


@_connection_call
def _link(domain, native, actor, project, issue_id, body):
    _begin(domain, write=True)
    domain._require_editor(actor)
    issue = domain._project_issue(actor, issue_id, project, write=True)
    module, revision = _identifier(body["module"]), _revision_id(body["revision"])
    tag = _identifier(body["tag"]) if "tag" in body else None
    _module_read(domain, actor, module)
    native.revision(issue["tenant_id"], module, revision)
    key = (issue["tenant_id"], project, issue_id, module, revision)
    existing = domain.db.execute(
        "SELECT tag FROM issue_revision_links WHERE tenant_id=? AND project=? AND issue_id=? AND module=? AND revision=?",
        key,
    ).fetchone()
    if existing is not None:
        return {"module": module, "revision": revision, "tag": existing["tag"]}
    if tag is not None and _tag_target(domain, (issue["tenant_id"], project, module, tag)) != revision:
        raise Conflict("Tag no longer selects the submitted revision")
    domain.db.execute("INSERT INTO issue_revision_links VALUES (?,?,?,?,?,?)", (*key, tag))
    return {"module": module, "revision": revision, "tag": tag}


@_connection_call
def _revision_context(domain, native, actor, project, module, revision):
    _begin(domain)
    domain._validate_project(project)
    tenant = domain._tenant_of(actor)
    _module_read(domain, actor, module)
    state = native.revision(tenant, module, revision)
    rows = domain.db.execute(
        "SELECT issue_id FROM issue_revision_links WHERE tenant_id=? AND project=? AND module=? AND revision=? "
        "ORDER BY issue_id",
        (tenant, project, module, revision),
    )
    issues = []
    for row in rows:
        try:
            issue = domain._project_issue(actor, row["issue_id"], project)
        except (PermissionDenied, NotFound):
            continue
        issues.append({field: issue[field] for field in ("id", "number", "title")})
    return {
        "module": module,
        "revision": revision,
        "parent": state["parent"],
        "objects": len(state["objects"]),
        "issues": issues,
    }


def _tag_target(domain, key):
    row = domain.db.execute(
        "SELECT revision FROM project_revision_tags WHERE tenant_id=? AND project=? AND module=? AND tag=?", key
    ).fetchone()
    return row["revision"] if row else None


@_connection_call
def _tag(domain, native, actor, project, module, tag, body=None):
    _begin(domain, write=body is not None)
    domain._validate_project(project)
    key = (domain._tenant_of(actor), project, _identifier(module), _identifier(tag))
    _module_read(domain, actor, module)
    current = _tag_target(domain, key)
    if body is None:
        if current is None:
            raise NotFound("Unknown revision tag")
        return {"module": module, "tag": tag, "revision": current}
    domain._require_editor(actor)
    revision = _revision_id(body["revision"])
    expected = body["expected"]
    if expected is not None:
        _revision_id(expected)
    native.revision(key[0], module, revision)
    if current != revision:
        if current != expected:
            raise Conflict("Tag target changed")
        domain.db.execute(
            "INSERT INTO project_revision_tags VALUES(?,?,?,?,?) ON CONFLICT(tenant_id,project,module,tag) "
            "DO UPDATE SET revision=excluded.revision",
            (*key, revision),
        )
    return {"module": module, "tag": tag, "revision": revision}


def create_issue_revision_router(domain, native):
    router = APIRouter(prefix=PREFIX)
    identity = Depends(_actor)

    @router.get("/issues/{issue_id}/revisions")
    async def links(issue_id: str, project: str = DEFAULT_PROJECT, actor: str = identity):
        return await _call(_links, domain, actor, project, issue_id)

    @router.post("/issues/{issue_id}/revisions")
    async def link(issue_id: str, request: Request, project: str = DEFAULT_PROJECT, actor: str = identity):
        body = _fields(await _body(request), {"module", "revision"}, {"tag"})
        return await _call(_link, domain, native, actor, project, issue_id, body)

    @router.get("/modules/{module}/revisions/{revision}/issue-context")
    async def context(module: str, revision: str, project: str = DEFAULT_PROJECT, actor: str = identity):
        return await _call(_revision_context, domain, native, actor, project, module, revision)

    @router.get("/modules/{module}/tags/{tag}")
    async def read_tag(module: str, tag: str, project: str = DEFAULT_PROJECT, actor: str = identity):
        return await _call(_tag, domain, native, actor, project, module, tag)

    @router.put("/modules/{module}/tags/{tag}")
    async def move_tag(module: str, tag: str, request: Request, project: str = DEFAULT_PROJECT, actor: str = identity):
        body = _fields(await _body(request), {"expected", "revision"})
        return await _call(_tag, domain, native, actor, project, module, tag, body)

    return router
