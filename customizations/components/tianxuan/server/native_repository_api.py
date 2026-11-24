"""Authenticated full-manifest repository transport; never accepts check claims."""

from __future__ import annotations

import asyncio
import sqlite3
from contextlib import contextmanager

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from fastapi.routing import APIRoute
from native_api import _body, _device_context, _fields, _identity
from native_repository import MAX_MANIFEST, MAX_OBJECT, NativeRepository, RepositoryForbidden
from native_store import Conflict, NativeStoreError
from starlette.concurrency import run_in_threadpool
from tianxuan_core import NotFound, PermissionDenied, TianxuanError


def domain_authority(domain):
    """Read current tenant/role on every operation, including release replay."""

    def authorize(tenant, actor, action):
        try:
            context = domain.actor_context(actor)
        except TianxuanError:
            return False
        if context["tenant"] != tenant:
            return False
        if action == "read":
            return context["role"] in {"viewer", "editor", "admin"}
        if action == "admin":
            return context["role"] == "admin"
        return action in {"write", "review", "publish"} and context["role"] in {"editor", "admin"}

    return authorize


def create_native_repository_router(repository: NativeRepository) -> APIRouter:
    # The deployment also bounds process workers. One resident repository body
    # per router prevents parallel 32 MiB uploads/manifests/checks multiplying RSS.
    capacity = asyncio.Semaphore(1)

    class BoundedRepositoryRoute(APIRoute):
        def get_route_handler(self):
            handler = super().get_route_handler()

            async def bounded(request):
                async with capacity:
                    return await handler(request)

            return bounded

    router = APIRouter(prefix="/api/v1/native/repos/{repo}", route_class=BoundedRepositoryRoute)

    async def call(request, method, *args, **kwargs):
        def invoke():
            # Refresh after a potentially long upload and in the same worker as
            # authority evaluation. Legacy actor/tenant headers never select identity.
            # ProductionAccess replaces X-Actor with its verified principal.
            # This trusted compatibility header must not reject valid key mode.
            if any(name in request.headers for name in ("x-tenant", "x-user-id", "x-tenant-id")) or (
                "x-actor" in request.headers
                and request.headers["x-actor"] != getattr(request.state, "verified_actor", None)
            ):
                raise HTTPException(422, "legacy identity headers are not supported")
            tenant, actor = _identity(request, refresh=True)
            try:
                with repository.device_context(**_device_context(request)):
                    return method(tenant, actor, request.path_params["repo"], *args, **kwargs)
            except RepositoryForbidden:
                raise HTTPException(403, "repository permission denied") from None
            except Conflict as error:
                raise HTTPException(409, str(error)) from None
            except (PermissionDenied, NotFound):
                raise HTTPException(403, "issue permission denied or unavailable") from None
            except (NativeStoreError, TianxuanError, UnicodeError, TypeError):
                raise HTTPException(422, "invalid or unavailable repository input") from None
            except sqlite3.Error as error:
                if getattr(error, "sqlite_errorcode", 0) & 255 in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED}:
                    raise HTTPException(503, "repository busy", headers={"Retry-After": "1"}) from None
                raise HTTPException(500, "repository storage error") from None

        return await run_in_threadpool(invoke)

    async def payload(request, required, limit=MAX_MANIFEST):
        await run_in_threadpool(_identity, request)
        return _fields(await _body(request, max_bytes=limit), set(required.split()))

    @router.post("/bootstrap")
    async def bootstrap(request: Request):
        return await call(request, repository.bootstrap, **await payload(request, "request_key"))

    @router.get("/branches")
    async def branches(request: Request):
        return await call(request, repository.branches)

    @router.get("/identity")
    async def identity(request: Request):
        def identify(tenant, actor, repo):
            repository._allow(tenant, actor, "read")
            repository._repo(repo)
            return {"tenant": tenant, "actor": actor, "repository": repo}

        return await call(request, identify)

    @router.get("/branches/{branch:path}")
    async def branch(branch: str, request: Request):
        return await call(request, repository.branch, branch)

    @router.post("/branches")
    async def create_branch(request: Request):
        return await call(request, repository.create_branch, **await payload(request, "request_key branch revision"))

    @router.post("/objects/missing")
    async def missing(request: Request):
        return await call(request, repository.missing, **await payload(request, "digests"))

    @router.put("/objects/{digest}")
    async def put_object(digest: str, request: Request):
        await run_in_threadpool(_identity, request)
        length = request.headers.get("content-length")
        if length is not None:
            try:
                size = int(length)
            except ValueError:
                raise HTTPException(422, "invalid content length") from None
            if size < 0:
                raise HTTPException(422, "invalid content length")
            if size > MAX_OBJECT:
                raise HTTPException(413, "object too large")
        data = bytearray()
        async for chunk in request.stream():
            if len(data) + len(chunk) > MAX_OBJECT:
                raise HTTPException(413, "object too large")
            data.extend(chunk)
        content = bytes(data)
        del data
        return await call(request, repository.put_object, digest, content)

    @router.get("/objects/{digest}")
    async def read_object(digest: str, request: Request):
        data = await call(request, repository.object, digest)
        return Response(data, media_type="application/octet-stream", headers={"ETag": '"' + digest + '"'})

    @router.post("/commits")
    async def commit(request: Request):
        return await call(
            request, repository.commit, **await payload(request, "request_key branch expected manifest message")
        )

    @router.get("/revisions/{revision}")
    async def revision(revision: str, request: Request):
        return await call(request, repository.revision, revision)

    @router.post("/candidates")
    async def create_candidate(request: Request):
        body = await payload(request, "request_key source target revision expected issue_id")

        def create(tenant, actor, repo, **inputs):
            snapshot = request.app.state.store.issue_snapshot(actor, inputs["issue_id"], write=True)
            return repository.create_candidate(tenant, actor, repo, issue_revision=snapshot["revision"], **inputs)

        return await call(request, create, **body)

    @router.get("/candidates/{identity}")
    async def candidate(identity: str, request: Request):
        return await call(request, repository.candidate, identity)

    @router.post("/candidates/{identity}/checks")
    async def checks(identity: str, request: Request):
        return await call(request, repository.run_checks, identity, **await payload(request, "request_key"))

    @router.get("/candidates/{identity}/checks")
    async def check_status(identity: str, request: Request):
        return await call(request, repository.check_status, identity)

    @router.post("/candidates/{identity}/reviews")
    async def reviews(identity: str, request: Request):
        return await call(request, repository.review, identity, **await payload(request, "request_key note"))

    @router.post("/candidates/{identity}/merge")
    async def merge(identity: str, request: Request):
        body = await payload(request, "request_key review")

        def deliver(tenant, actor, repo, **inputs):
            domain = request.app.state.store

            @contextmanager
            def issue_guard(candidate, *, replay):
                with domain._connection_lock:
                    snapshot = domain.issue_snapshot(actor, candidate["issue_id"], write=True)
                    if not replay and snapshot["revision"] != candidate.get("issue_revision"):
                        raise Conflict("Issue changed; create and review a new candidate")
                    yield

            result = repository.merge(tenant, actor, repo, identity, guard=issue_guard, **inputs)
            comment = domain.add_issue_comment(
                actor,
                result["issue_id"],
                "Native repository merge: "
                + result["repository"]
                + "/main\nRevision: "
                + result["revision"]
                + "\nCandidate: "
                + result["candidate"]
                + "\nRelease: "
                + result["release"],
                call_id="native-repository-" + result["release"],
            )
            return {**result, "issue_comment": comment["id"]}

        return await call(request, deliver, **body)

    return router
