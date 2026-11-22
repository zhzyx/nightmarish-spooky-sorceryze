"""Production access control using the existing user, role and hashed session store."""

from __future__ import annotations

import os
from typing import Any, cast

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from identity import allow_identity_attempt
from pydantic import BaseModel, Field
from starlette.requests import HTTPConnection
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from starlette.websockets import WebSocketDisconnect
from tianxuan_core import Tianxuan

COOKIE = "__Host-tianxuan_key"
SESSION_COOKIE = "__Host-tianxuan_session"


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
        self.accounts = os.environ.get("TIANXUAN_AUTH_MODE") == "accounts"

    def resolve(self, token: str) -> str | None:
        if self.accounts:
            actor = self.store.user_for_access_key(token)
            tenant = os.environ.get("TIANXUAN_TENANT_ID")
            if actor:
                if tenant and self.store.actor_context(actor)["tenant"] == tenant:
                    return cast(str, actor)
                return None
            return cast(str | None, self.store.user_for_token(token))
        return cast(str | None, self.store.user_for_access_key(token))

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return
        connection = HTTPConnection(scope)
        path = scope["path"]
        public = {"/api/v1/health", "/api/v1/auth/config", "/api/v1/auth/key-login"}
        if self.accounts:
            public.update({"/api/v1/auth/register", "/api/v1/auth/session"})
        else:
            public.add("/api/v1/auth/key-login")
        if scope["type"] == "http" and path in public:
            await self.app(scope, receive, send)
            return
        authorization = connection.headers.get("authorization", "")
        scheme, _, bearer = authorization.partition(" ")
        uses_bearer = scheme.lower() == "bearer"
        cookie_token = connection.cookies.get(COOKIE, "")
        if self.accounts:
            cookie_token = connection.cookies.get(SESSION_COOKIE, "") or cookie_token
        token = bearer.strip() if uses_bearer else cookie_token
        actor = self.resolve(token) if token else None

        async def reject(status: int, detail: str) -> None:
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 4401 if status == 401 else 4403})
            else:
                await JSONResponse({"detail": detail}, status_code=status)(scope, receive, send)

        if not actor:
            return await reject(401, "a valid personal access key is required")
        tenant = os.environ.get("TIANXUAN_TENANT_ID", "")
        if not self.accounts and (not tenant or self.store.actor_context(actor)["tenant"] != tenant):
            return await reject(403, "account is not admitted to this deployment")
        role = self.store.role_of(actor)
        if self.accounts and self.store.actor_context(actor)["tenant"] != tenant:
            document_roots = (
                "/api/v1/docs",
                "/api/v1/comments",
                "/api/v1/users",
                "/api/v1/invites",
                "/api/v1/models",
                "/api/v1/ws/docs",
                "/api/v1/game-config",
                "/api/v1/ws/game-config",
            )
            document_paths = {
                "/api/v1/auth/me",
                "/api/v1/auth/logout",
                "/api/v1/auth/key-logout",
                "/api/v1/search",
                "/api/v1/events",
                "/api/v1/capabilities",
                "/api/v1/tools",
            }
            allowed = path in document_paths or any(
                path == root or path.startswith(root + "/") for root in document_roots
            )
            if not allowed:
                return await reject(403, "this workspace is limited to cloud document operations")
        method = scope.get("method", "GET")
        origin = connection.headers.get("origin", "")
        expected = os.environ.get("TIANXUAN_PUBLIC_ORIGIN", "").rstrip("/")
        if scope["type"] == "websocket" or method not in {"GET", "HEAD", "OPTIONS"}:
            if (not uses_bearer or origin) and (not expected or origin != expected):
                return await reject(403, "same-origin request required")
        if not self.accounts and path in {
            "/api/v1/auth/register",
            "/api/v1/auth/login",
            "/api/v1/auth/session",
            "/api/v1/identity/resolve",
            "/api/v1/invites/accept",
        }:
            return await reject(403, "account access is managed by the administrator")
        viewer_post_paths = {"/api/v1/auth/key-logout", "/api/v1/auth/logout", "/api/v1/tools"}
        if role == "viewer" and method not in {"GET", "HEAD", "OPTIONS"} and path not in viewer_post_paths:
            return await reject(403, "read-only account")
        if path.startswith("/api/v1/models") and role != "admin":
            return await reject(403, "model gateway administration requires admin")
        scope = dict(scope)
        scope["state"] = {
            **scope.get("state", {}),
            "verified_actor": actor,
            "refresh_verified_actor": lambda: self.resolve(token),
        }
        scope["headers"] = [(k, v) for k, v in scope["headers"] if k.lower() != b"x-actor"] + [
            (b"x-actor", actor.encode())
        ]
        if scope["type"] == "websocket":

            async def checked_receive() -> Message:
                message = await receive()
                if self.resolve(token) != actor:
                    await send({"type": "websocket.close", "code": 4401})
                    raise AccessExpired()
                return message

            async def checked_send(message: Message) -> None:
                if message["type"] == "websocket.send" and self.resolve(token) != actor:
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
    mode = os.environ.get("TIANXUAN_AUTH_MODE", "keys" if strict else "legacy")
    if mode not in {"keys", "accounts", "legacy"}:
        raise RuntimeError("invalid TIANXUAN_AUTH_MODE")
    if strict and mode == "accounts":
        raise RuntimeError("account mode requires TIANXUAN_REQUIRE_KEYS=0")
    if strict and mode == "legacy":
        raise RuntimeError("legacy mode conflicts with required key access")
    strict = strict or mode == "keys"
    if mode == "accounts":
        if not os.environ.get("TIANXUAN_PUBLIC_ORIGIN", "").startswith("https://"):
            raise RuntimeError("account mode requires HTTPS public origin")
        app.add_middleware(ProductionAccess, store=store)

    @app.get("/api/v1/auth/config")
    def auth_config() -> dict[str, str]:
        return {"mode": mode}

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
        if (strict or mode == "accounts") and origin != expected:
            raise HTTPException(403, "same-origin request required")
        if not allow_identity_attempt("access-key", request.client.host if request.client else "unknown"):
            raise HTTPException(429, "too many login attempts")
        actor = store.user_for_access_key(payload.key)
        if not actor or (
            (strict or mode == "accounts")
            and store.actor_context(actor)["tenant"] != os.environ.get("TIANXUAN_TENANT_ID")
        ):
            raise HTTPException(401, "invalid or revoked key")
        response = JSONResponse({"user_id": actor, "role": store.role_of(actor)})
        response.delete_cookie(SESSION_COOKIE, path="/", secure=True, httponly=True, samesite="strict")
        response.set_cookie(COOKIE, payload.key, max_age=86400, secure=True, httponly=True, samesite="strict", path="/")
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.post("/api/v1/auth/key-logout")
    def logout(request: Request) -> JSONResponse:
        if mode == "accounts":
            store.revoke_session(request.cookies.get(SESSION_COOKIE, ""))
        response = JSONResponse({"ok": True})
        response.delete_cookie(COOKIE, path="/", secure=True, httponly=True, samesite="strict")
        response.delete_cookie(SESSION_COOKIE, path="/", secure=True, httponly=True, samesite="strict")
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
