"""Explicit narrow outer mount: machine auth never enters ProductionAccess."""

import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response
from native_store import NativeStoreError
from starlette.applications import Starlette
from starlette.routing import Mount


def mount_native_nodes(user_app, worker):
    nodes = FastAPI()
    waits = asyncio.Semaphore(8)
    uploads = asyncio.Semaphore(2)

    def identity(request):
        value = request.headers.get("authorization", "")
        if not value.startswith("Bearer "):
            raise HTTPException(401, "Node bearer required")
        token = value[7:]
        try:
            return token, worker.authenticate(token)
        except NativeStoreError:
            raise HTTPException(403, "Node unavailable") from None

    @nodes.exception_handler(NativeStoreError)
    async def rejected(request, error):
        return Response("Node request rejected", status_code=409)

    @nodes.get("/events")
    async def events(request: Request, cursor: int = 0):
        token, _ = identity(request)
        if waits.locked():
            raise HTTPException(429, "Node wait capacity")
        async with waits:
            return await asyncio.to_thread(worker.events, token, cursor)

    @nodes.get("/execution/{execution}")
    def manifest(request: Request, execution: str):
        _, node = identity(request)
        return worker.manifest(node, execution)

    @nodes.get("/execution/{execution}/blob/{digest}")
    def blob(request: Request, execution: str, digest: str):
        _, node = identity(request)
        return Response(worker.blob(node, execution, digest), media_type="application/octet-stream")

    @nodes.post("/execution/{execution}/receipt")
    async def receipt(request: Request, execution: str):
        if uploads.locked():
            raise HTTPException(429, "Receipt upload capacity")
        async with uploads:
            return await receive_receipt(request, execution)

    async def receive_receipt(request, execution):
        _, node = identity(request)
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > 9 * 1024 * 1024:
                raise HTTPException(413, "Receipt budget exceeded")
            body.extend(chunk)
        identity(request)
        try:
            value = json.loads(body)
        except ValueError:
            raise HTTPException(400, "JSON required") from None
        try:
            return await asyncio.to_thread(worker.receipt, node, execution, value)
        except (ValueError, TypeError, KeyError):
            raise HTTPException(409, "Invalid typed receipt") from None

    @asynccontextmanager
    async def lifespan(app):
        try:
            async with user_app.router.lifespan_context(user_app):
                yield
        finally:
            worker.close()

    return Starlette(routes=[Mount("/native-nodes", app=nodes), Mount("/", app=user_app)], lifespan=lifespan)
