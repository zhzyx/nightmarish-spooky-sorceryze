"""Authenticated configuration HTTP and live snapshots with application receipts."""

from __future__ import annotations

import asyncio
import os
import time
import uuid
from typing import Any

import game_config as domain
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ConfigDict, Field, StrictInt
from tianxuan_core import TianxuanError


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    features: list[dict[str, Any]] = Field(default_factory=list, max_length=200)


class ProjectUpdate(ProjectCreate):
    expected_version: StrictInt = Field(ge=1)


def create_game_config_router(store, require_actor, notify_document_change) -> APIRouter:
    router = APIRouter()

    @router.get("/api/v1/game-config/projects")
    def list_projects(actor: str = Depends(require_actor)):
        return {"projects": domain.list_projects(store, actor)}

    @router.post("/api/v1/game-config/projects", status_code=201)
    def create_project(payload: ProjectCreate, actor: str = Depends(require_actor)):
        if not payload.title.strip():
            raise TianxuanError("project title is required")
        return domain.create_project(store, actor, payload.title, payload.features)

    @router.get("/api/v1/game-config/projects/{project_id}")
    def get_project(project_id: str, actor: str = Depends(require_actor)):
        return domain.read_project(store, actor, project_id)

    @router.put("/api/v1/game-config/projects/{project_id}")
    def update_project(project_id: str, payload: ProjectUpdate, actor: str = Depends(require_actor)):
        if not payload.title.strip():
            raise TianxuanError("project title is required")
        project = domain.update_project(
            store, actor, project_id, payload.title, payload.features, payload.expected_version
        )
        notify_document_change(store.get_doc(project_id))
        return project

    @router.get("/api/v1/game-config/projects/{project_id}/clients")
    def list_clients(project_id: str, actor: str = Depends(require_actor)):
        return {"clients": domain.clients(store, actor, project_id)}

    @router.websocket("/api/v1/ws/game-config/{project_id}")
    async def live(websocket: WebSocket, project_id: str):
        connection = uuid.uuid4().hex
        joined = False
        await websocket.accept()
        try:
            subscription = await asyncio.wait_for(websocket.receive_json(), timeout=10)
            if not isinstance(subscription, dict) or subscription.get("type") != "subscribe":
                await websocket.close(code=4400)
                return
            # ProductionAccess has already checked Cookie/Bearer and origin; it also
            # revalidates the credential on every send and receive.
            actor = getattr(websocket.state, "verified_actor", None)
            token = ""
            if not actor:
                authorization = websocket.headers.get("authorization", "")
                scheme, _, bearer = authorization.partition(" ")
                token = bearer.strip() if scheme.lower() == "bearer" else subscription.get("token", "")
                if not isinstance(token, str) or len(token) > 4096:
                    await websocket.close(code=4401)
                    return
                actor = store.user_for_token(token) if token else None
                if (
                    not actor
                    and not token
                    and os.environ.get("TIANXUAN_ALLOW_ACTOR_HEADER") == "1"
                    and not websocket.app.state.native_only
                ):
                    actor = subscription.get("actor")
            if not isinstance(actor, str) or not actor:
                await websocket.close(code=4401)
                return
            project = domain.read_project(store, actor, project_id)
            kind = websocket.query_params.get("kind", "editor")
            if kind not in {"editor", "runtime"}:
                await websocket.close(code=4400)
                return
            name = subscription.get("name", "Game runtime")
            if not isinstance(name, str) or not name.strip() or len(name) > 100:
                await websocket.close(code=4400)
                return
            if kind == "runtime":
                domain.connect_client(store, actor, project_id, connection, name)
                joined = True
            sent_version = 0
            acknowledged = 0
            last_received = time.monotonic()
            previous_clients = None
            while True:
                if token and store.user_for_token(token) != actor:
                    await websocket.close(code=4401)
                    return
                # Read persisted state, including ACL, so saves from any API worker,
                # ordinary document editor, restore, or AI tool are observed.
                document = store.get_doc_shared(actor, project_id)
                if document["version"] != sent_version:
                    project = domain.snapshot(document)
                    await websocket.send_json({"type": "snapshot", "project": project})
                    sent_version = project["version"]
                current_clients = domain.clients(store, actor, project_id)
                visible = [{k: v for k, v in row.items() if k != "last_seen"} for row in current_clients]
                if visible != previous_clients:
                    await websocket.send_json({"type": "clients", "clients": current_clients})
                    previous_clients = visible
                if time.monotonic() - last_received > 30:
                    await websocket.close(code=4408)
                    return
                try:
                    message = await asyncio.wait_for(websocket.receive_json(), timeout=0.25)
                except asyncio.TimeoutError:
                    continue
                last_received = time.monotonic()
                if joined:
                    domain.touch_client(store, connection)
                if not isinstance(message, dict):
                    await websocket.close(code=4400)
                    return
                if message.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                elif joined and message.get("type") in {"applied", "failed"}:
                    version = message.get("version")
                    # Only the latest snapshot actually sent on this connection may
                    # be acknowledged. A late old ack cannot mark a new revision live.
                    if type(version) is not int or version != sent_version or version < acknowledged:
                        await websocket.send_json({
                            "type": "error",
                            "message": "receipt must match the latest delivered version",
                        })
                        continue
                    error = message.get("error", "")
                    if not isinstance(error, str) or len(error) > 500:
                        await websocket.send_json({"type": "error", "message": "invalid application error"})
                        continue
                    acknowledged = version
                    domain.report_client(
                        store, connection, version, message["type"], error if message["type"] == "failed" else ""
                    )
                else:
                    await websocket.send_json({"type": "error", "message": "unsupported message"})
        except (WebSocketDisconnect, asyncio.TimeoutError):
            pass
        except TianxuanError:
            await websocket.close(code=4403)
        except (ValueError, TypeError):
            await websocket.close(code=4400)
        finally:
            if joined:
                domain.disconnect_client(store, connection)

    return router
