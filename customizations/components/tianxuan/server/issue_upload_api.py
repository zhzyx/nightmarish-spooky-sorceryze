"""Receive a bounded local file and bind its immutable Duobao object to a numbered issue."""

import hashlib

from fastapi import APIRouter, Depends, HTTPException, Request
from native_api import MAX_OBJECT, _body, _call, _fields, _identity, decode_object
from native_store import Conflict, NativeStoreError, _object_name
from tianxuan_core import _connection_call
from work_management import record_work_mutation


@_connection_call
def _target(domain, actor, project, number):
    domain._require_editor(actor)
    issue = domain.read_issue_number(actor, project, number)
    return domain._require_tenant_issue(actor, issue["id"], write=True)


@_connection_call
def _bind(domain, actor, project, number, issue_id, reference, key):
    # Serialize the duplicate check and append across independent service processes.
    if not domain.db.in_transaction:
        domain.db.execute("BEGIN IMMEDIATE")
    issue = _target(domain, actor, project, number)
    if issue["id"] != issue_id:
        raise Conflict("issue binding changed")
    existing = domain.db.execute(
        "SELECT version FROM issue_work_events WHERE issue_id=? AND action='work.submit_asset' "
        "AND json_extract(data,'$.module')=? AND json_extract(data,'$.revision')=? "
        "AND json_extract(data,'$.path')=? AND json_extract(data,'$.kind')='attachment' ORDER BY version LIMIT 1",
        (issue_id, reference["module"], reference["revision"], reference["path"]),
    ).fetchone()
    if existing:
        return existing["version"]
    current = domain.db.execute(
        "SELECT COALESCE(MAX(version),0) FROM issue_work_events WHERE issue_id=?", (issue_id,)
    ).fetchone()[0]
    receipt = record_work_mutation(
        domain, actor, "work.submit_asset", dict(issue_id=issue_id, expected_version=current, **reference), call_id=key
    )
    return receipt["version"]


def _upload(domain, native, actor, project, number, name, content):
    if not isinstance(name, str) or len(name) > 255 or "/" in name:
        raise HTTPException(422, "expected a single filename")
    _object_name(name)
    try:
        encoded_name = name.encode("utf-8")
    except UnicodeEncodeError:
        raise HTTPException(422, "filename must be valid Unicode") from None
    issue = _target(domain, actor, project, number)
    digest = hashlib.sha256(content).hexdigest()
    binding = hashlib.sha256(encoded_name + b"\0" + digest.encode("ascii")).hexdigest()
    module = f"requirement-attachment-{issue['id']}-{binding}"
    key = "snapshot-attachment-" + hashlib.sha256(module.encode()).hexdigest()
    tenant = issue["tenant_id"]
    # Native storage owns its transaction. A retry can bind an already-stored
    # object even if the first process failed before committing the issue event.
    revision = native.head(tenant, module)
    if not revision:
        try:
            revision = native.submit(
                tenant, actor, key, [dict(module=module, base=None, reads=None, edits={name: content})]
            )["revisions"][module]
        except Conflict:
            revision = native.head(tenant, module)
            if not revision:
                raise
    if native.read(tenant, module, revision, name) != content:
        raise NativeStoreError("stored attachment content mismatch")
    reference = dict(kind="attachment", module=module, revision=revision, path=name)
    version = _bind(domain, actor, project, number, issue["id"], reference, key)
    return dict(**reference, version=version, digest=digest)


def _writer(request: Request):
    return _identity(request, allow_project=True)[1]


def create_issue_upload_router(domain, native):
    router = APIRouter(prefix="/api/v1")

    @router.post("/issues/by-number/{number}/artifacts")
    async def upload(number: int, project: str, request: Request, actor: str = Depends(_writer)):
        body = _fields(await _body(request, max_bytes=4 * ((MAX_OBJECT + 2) // 3) + 4096), {"name", "content"})
        return await _call(
            _upload, domain, native, actor, project, number, body["name"], decode_object(body["content"])
        )

    return router
