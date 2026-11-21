"""Explicit links between business modules and immutable Duobao objects."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from native_api import PREFIX, _body, _call, _fields, _identity, _module_read
from native_store import NativeStore, NativeStoreError, _digest, _identifier, _json, _object_name
from tianxuan_core import DEFAULT_PROJECT, NotFound, PermissionDenied, Tianxuan, _connection_call


def _asset_id(source: str, revision: str, path: str) -> str:
    return str(_digest(_json([source, revision, path]).encode()))


def _actor(request: Request) -> str:
    return str(_identity(request, allow_project=True)[1])


def _scope(domain: Tianxuan, actor: str, project: str, module_id: str) -> tuple[str, str, str]:
    tenant = domain._tenant_of(actor)
    domain._validate_project(project)
    domain._business_module(tenant, project, module_id)
    return tenant, project, module_id


@_connection_call
def _list_assets(domain: Tianxuan, actor: str, project: str, module_id: str) -> list[dict[str, str]]:
    rows = domain.db.execute(
        "SELECT asset_id, source_module, revision, path FROM business_module_assets "
        "WHERE tenant_id=? AND project=? AND module_id=? ORDER BY asset_id",
        _scope(domain, actor, project, module_id),
    )
    assets = []
    for row in rows:
        try:
            _module_read(domain, actor, row["source_module"])
        except (PermissionDenied, NotFound):
            continue
        assets.append(dict(row))
    return assets


@_connection_call
def _list_modules(domain: Tianxuan, actor: str, project: str, asset_id: str) -> list[str]:
    domain._validate_project(project)
    rows = domain.db.execute(
        "SELECT module_id, source_module FROM business_module_assets WHERE tenant_id=? AND project=? "
        "AND asset_id=? ORDER BY module_id",
        (domain._tenant_of(actor), project, asset_id),
    ).fetchall()
    if rows:
        try:
            _module_read(domain, actor, rows[0]["source_module"])
        except (PermissionDenied, NotFound):
            return []
    return [row["module_id"] for row in rows]


@_connection_call
def _link(
    domain: Tianxuan, native: NativeStore, actor: str, project: str, module_id: str, reference: dict[str, str]
) -> dict[str, str]:
    domain._require_editor(actor)
    scope = _scope(domain, actor, project, module_id)
    source = _identifier(reference["source_module"])
    revision = reference["revision"]
    path = _object_name(reference["path"])
    _module_read(domain, actor, source)
    if path not in native.revision(scope[0], source, revision)["objects"]:
        raise NativeStoreError("Object unavailable")
    asset_id = _asset_id(source, revision, path)
    domain.db.execute(
        "INSERT INTO business_module_assets (tenant_id,project,module_id,asset_id,source_module,revision,path) "
        "VALUES(?,?,?,?,?,?,?) ON CONFLICT(tenant_id,project,module_id,asset_id) DO NOTHING",
        (*scope, asset_id, source, revision, path),
    )
    return {"asset_id": asset_id, **reference}


@_connection_call
def _linked_asset(
    domain: Tianxuan, actor: str, project: str, module_id: str, asset_id: str, *, remove: bool = False
) -> tuple[str, str, str, str]:
    if remove:
        domain._require_editor(actor)
    scope = _scope(domain, actor, project, module_id)
    key = (*scope, asset_id)
    where = "WHERE tenant_id=? AND project=? AND module_id=? AND asset_id=?"
    row = domain.db.execute("SELECT source_module,revision,path FROM business_module_assets " + where, key).fetchone()
    if row is None:
        raise NotFound("module asset link not found")
    _module_read(domain, actor, row["source_module"])
    if remove:
        domain.db.execute("DELETE FROM business_module_assets " + where, key)
    return scope[0], row["source_module"], row["revision"], row["path"]


@_connection_call
def _asset_context(
    domain: Tianxuan, native: NativeStore, actor: str, project: str, source: str, revision: str, path: str
) -> dict[str, Any]:
    domain._validate_project(project)
    tenant = domain._tenant_of(actor)
    _module_read(domain, actor, source)
    # An empty reverse index can also mean the caller lost access. Verify the source itself first.
    digest = _digest(native.read(tenant, source, revision, path))
    asset_id = _asset_id(source, revision, path)
    owners = []
    for module_id in _list_modules(domain, actor, project, asset_id):
        module = domain._business_module(tenant, project, module_id)
        owners.append({"id": module_id, "name": module["name"]})
    return {
        "asset_id": asset_id,
        "source_module": source,
        "revision": revision,
        "path": path,
        "sha256": digest,
        "modules": owners,
    }


def create_business_asset_router(domain: Tianxuan, native: NativeStore) -> APIRouter:
    router = APIRouter(prefix=PREFIX)
    collection = "/business-modules/{module_id}/assets"
    item = collection + "/{asset_id}"

    @router.get("/asset-context/{source}/{revision}/{path:path}")
    async def asset_context(
        source: str, revision: str, path: str, project: str = DEFAULT_PROJECT, actor: str = Depends(_actor)
    ) -> Any:
        return await _call(_asset_context, domain, native, actor, project, source, revision, path)

    @router.get(collection)
    def assets(module_id: str, project: str = DEFAULT_PROJECT, actor: str = Depends(_actor)) -> dict[str, Any]:
        return {"assets": _list_assets(domain, actor, project, module_id)}

    @router.get("/assets/{asset_id}/business-modules")
    def modules(asset_id: str, project: str = DEFAULT_PROJECT, actor: str = Depends(_actor)) -> dict[str, Any]:
        return {"module_ids": _list_modules(domain, actor, project, asset_id)}

    @router.post(collection)
    async def link(
        module_id: str, request: Request, project: str = DEFAULT_PROJECT, actor: str = Depends(_actor)
    ) -> Any:
        reference = _fields(await _body(request), {"source_module", "revision", "path"})
        if not all(isinstance(value, str) for value in reference.values()):
            raise HTTPException(422, "expected native object reference")
        return await _call(_link, domain, native, actor, project, module_id, reference)

    @router.get(item)
    async def open_asset(
        module_id: str, asset_id: str, project: str = DEFAULT_PROJECT, actor: str = Depends(_actor)
    ) -> Response:
        reference = await _call(_linked_asset, domain, actor, project, module_id, asset_id)
        content = await _call(native.read, *reference)
        return Response(content, media_type="application/octet-stream", headers={"Cache-Control": "no-store"})

    @router.delete(item, status_code=204)
    def unlink(module_id: str, asset_id: str, project: str = DEFAULT_PROJECT, actor: str = Depends(_actor)) -> Response:
        _linked_asset(domain, actor, project, module_id, asset_id, remove=True)
        return Response(status_code=204)

    return router
