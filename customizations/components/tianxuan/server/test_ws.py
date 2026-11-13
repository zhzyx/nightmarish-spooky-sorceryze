"""文曲实时协同 WebSocket 测试：快照、更新广播、冲突与连接拒绝。"""

from __future__ import annotations

from typing import Any

import pytest
from api import create_app
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from tianxuan_core import Tianxuan


def _setup() -> tuple[TestClient, str, dict[str, Any]]:
    store = Tianxuan(":memory:")
    client = TestClient(create_app(store))
    registered = client.post(
        "/api/v1/auth/register",
        json={
            "tenant_name": "实时工坊",
            "email": "realtime@example.com",
            "password": "secret-pass",
            "name": "Owner",
        },
    ).json()
    actor = registered["user_id"]
    document = client.post(
        "/api/v1/docs",
        headers={"X-Actor": actor},
        json={"title": "实时协同", "body_md": "# v1\n"},
    ).json()
    return client, actor, document


def _read_until(ws, kind: str) -> dict[str, Any]:
    for _ in range(10):
        message = ws.receive_json()
        if message.get("type") == kind:
            return message  # type: ignore[no-any-return]
    raise AssertionError(f"did not receive {kind}")


def test_ws_snapshot_update_and_ping() -> None:
    client, actor, document = _setup()
    with client.websocket_connect(f"/api/v1/ws/docs/{document['id']}?actor={actor}") as ws:
        snapshot = ws.receive_json()
        assert snapshot["type"] == "snapshot"
        assert snapshot["doc"]["version"] == 1
        presence = ws.receive_json()
        assert presence["type"] == "presence"
        assert actor in presence["actors"]

        ws.send_json({"type": "update", "body_md": "# v2\n", "expected_version": 1})
        updated = _read_until(ws, "updated")
        assert updated["doc"]["version"] == 2
        assert updated["doc"]["body_md"] == "# v2\n"

        ws.send_json({"type": "ping"})
        assert _read_until(ws, "pong") == {"type": "pong"}


def test_ws_broadcast_and_version_conflict() -> None:
    client, actor, document = _setup()
    with client.websocket_connect(f"/api/v1/ws/docs/{document['id']}?actor={actor}") as first:
        with client.websocket_connect(f"/api/v1/ws/docs/{document['id']}?actor={actor}") as second:
            _read_until(first, "presence")
            _read_until(second, "snapshot")

            first.send_json({"type": "update", "body_md": "# 协作\n", "expected_version": 1})
            assert _read_until(first, "updated")["doc"]["version"] == 2
            assert _read_until(second, "updated")["doc"]["version"] == 2

            second.send_json({"type": "update", "body_md": "stale", "expected_version": 1})
            error = _read_until(second, "error")
            assert error["code"] == "VersionConflict"


def test_ws_rejects_missing_actor_and_unknown_doc() -> None:
    client, _, document = _setup()
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/api/v1/ws/docs/{document['id']}") as ws:
            ws.receive_json()
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/v1/ws/docs/doc_missing?actor=someone") as ws:
            ws.receive_json()
