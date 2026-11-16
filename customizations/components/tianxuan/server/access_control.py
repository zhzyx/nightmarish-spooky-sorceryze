"""Production access control using the existing user, role and hashed session store."""

from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from identity import allow_identity_attempt
from pydantic import BaseModel, Field
from starlette.requests import HTTPConnection
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from starlette.websockets import WebSocketDisconnect
from tianxuan_core import Tianxuan

COOKIE = "__Host-tianxuan_key"


class KeyLogin(BaseModel):
    key: str = Field(min_length=1, max_length=256)


class KeyCreate(BaseModel):
    user_id: str
    name: str = Field(min_length=1, max_length=100)
    days: int = Field(default=90, ge=1, le=365)


class AccessExpired(WebSocketDisconnect):
    pass


class ProductionAccess:
    """No network-address or caller-supplied actor bypass in production."""

    def __init__(self, app: ASGIApp, store: Tianxuan) -> None:
        self.app = app
        self.store = store

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return
        connection = HTTPConnection(scope)
        path = scope["path"]
        if scope["type"] == "http" and path in {"/api/v1/health", "/api/v1/auth/key-login"}:
            await self.app(scope, receive, send)
            return
        authorization = connection.headers.get("authorization", "")
        scheme, _, bearer = authorization.partition(" ")
        uses_bearer = scheme.lower() == "bearer"
        token = bearer.strip() if uses_bearer else connection.cookies.get(COOKIE, "")
        actor = self.store.user_for_access_key(token) if token else None

        async def reject(status: int, detail: str) -> None:
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 4401 if status == 401 else 4403})
            else:
                await JSONResponse({"detail": detail}, status_code=status)(scope, receive, send)

        if not actor:
            return await reject(401, "a valid personal access key is required")
        tenant = os.environ.get("TIANXUAN_TENANT_ID", "")
        if not tenant or self.store._tenant_of(actor) != tenant:
            return await reject(403, "account is not admitted to this deployment")
        role = self.store.role_of(actor)
        method = scope.get("method", "GET")
        origin = connection.headers.get("origin", "")
        expected = os.environ.get("TIANXUAN_PUBLIC_ORIGIN", "").rstrip("/")
        if scope["type"] == "websocket" or method not in {"GET", "HEAD", "OPTIONS"}:
            if (not uses_bearer or origin) and (not expected or origin != expected):
                return await reject(403, "same-origin request required")
        if path in {
            "/api/v1/auth/register",
            "/api/v1/auth/login",
            "/api/v1/auth/session",
            "/api/v1/identity/resolve",
            "/api/v1/invites/accept",
        }:
            return await reject(403, "account access is managed by the administrator")
        if role == "viewer" and method not in {"GET", "HEAD", "OPTIONS"} and path != "/api/v1/auth/key-logout":
            return await reject(403, "read-only account")
        if path.startswith("/api/v1/models") and role != "admin":
            return await reject(403, "model gateway administration requires admin")
        scope = dict(scope)
        scope["state"] = {**scope.get("state", {}), "verified_actor": actor}
        scope["headers"] = [(k, v) for k, v in scope["headers"] if k.lower() != b"x-actor"] + [
            (b"x-actor", actor.encode())
        ]
        if scope["type"] == "websocket":

            async def checked_receive() -> Message:
                message = await receive()
                if self.store.user_for_access_key(token) != actor:
                    await send({"type": "websocket.close", "code": 4401})
                    raise AccessExpired()
                return message

            async def checked_send(message: Message) -> None:
                if message["type"] == "websocket.send" and self.store.user_for_access_key(token) != actor:
                    await send({"type": "websocket.close", "code": 4401})
                    raise AccessExpired()
                await send(message)

            try:
                await self.app(scope, checked_receive, checked_send)
                return
            except AccessExpired:
                return
        await self.app(scope, receive, send)


def configure_access(app: FastAPI, store: Tianxuan) -> None:
    strict = os.environ.get("TIANXUAN_REQUIRE_KEYS") == "1"
    if strict:
        if not os.environ.get("TIANXUAN_TENANT_ID") or not os.environ.get("TIANXUAN_PUBLIC_ORIGIN", "").startswith(
            "https://"
        ):
            raise RuntimeError("production key access requires tenant ID and HTTPS public origin")
        app.add_middleware(ProductionAccess, store=store)

    def actor_for(request: Request) -> str:
        actor = getattr(request.state, "verified_actor", None)
        if actor:
            return str(actor)
        scheme, _, token = request.headers.get("authorization", "").partition(" ")
        actor = store.user_for_access_key(token.strip()) if scheme.lower() == "bearer" else None
        if not actor:
            raise HTTPException(401, "personal access key required")
        return str(actor)

    @app.post("/api/v1/auth/key-login")
    def login(payload: KeyLogin, request: Request) -> JSONResponse:
        origin = request.headers.get("origin", "")
        expected = os.environ.get("TIANXUAN_PUBLIC_ORIGIN", "").rstrip("/")
        if strict and origin != expected:
            raise HTTPException(403, "same-origin request required")
        if not allow_identity_attempt("access-key", request.client.host if request.client else "unknown"):
            raise HTTPException(429, "too many login attempts")
        actor = store.user_for_access_key(payload.key)
        if not actor or (strict and store._tenant_of(actor) != os.environ["TIANXUAN_TENANT_ID"]):
            raise HTTPException(401, "invalid or revoked key")
        response = JSONResponse({"user_id": actor, "role": store.role_of(actor)})
        response.set_cookie(COOKIE, payload.key, max_age=86400, secure=True, httponly=True, samesite="strict", path="/")
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.post("/api/v1/auth/key-logout")
    def logout() -> JSONResponse:
        response = JSONResponse({"ok": True})
        response.delete_cookie(COOKIE, path="/", secure=True, httponly=True, samesite="strict")
        return response

    @app.get("/api/v1/auth/me")
    def me(request: Request) -> dict[str, Any]:
        actor = actor_for(request)
        return next(user for user in store.list_members(actor) if user["id"] == actor)

    @app.get("/api/v1/auth/keys")
    def list_keys(request: Request) -> dict[str, Any]:
        return {"keys": store.list_access_keys(actor_for(request))}

    @app.post("/api/v1/auth/keys")
    def create_key(payload: KeyCreate, request: Request) -> JSONResponse:
        result = store.issue_access_key(actor_for(request), payload.user_id, payload.name, payload.days)
        return JSONResponse(result, headers={"Cache-Control": "no-store"})

    @app.delete("/api/v1/auth/keys/{key_id}")
    def revoke_key(key_id: str, request: Request) -> dict[str, bool]:
        return {"revoked": store.revoke_access_key(actor_for(request), key_id)}
