"""认证模式：默认关闭 X-Actor，Bearer 会话是默认身份来源。"""

from __future__ import annotations

import pytest
from api import create_app
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from tianxuan_core import Tianxuan

EMAIL = "authmode@example.com"
PASSWORD = "secret-pass"


def _setup() -> tuple[TestClient, dict[str, str]]:
    store = Tianxuan(":memory:")
    client = TestClient(create_app(store))
    registered = client.post(
        "/api/v1/auth/register",
        json={"tenant_name": "认证模式", "email": EMAIL, "password": PASSWORD},
    ).json()
    return client, registered


def _token(client: TestClient) -> str:
    login = client.post("/api/v1/auth/session", json={"email": EMAIL, "password": PASSWORD})
    assert login.status_code == 200, login.text
    return str(login.json()["token"])


def test_actor_header_is_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TIANXUAN_ALLOW_ACTOR_HEADER", raising=False)
    client, registered = _setup()

    denied = client.get("/api/v1/docs", headers={"X-Actor": registered["user_id"]})
    assert denied.status_code == 401
    assert "Bearer" in denied.json()["detail"]

    login = client.post("/api/v1/auth/session", json={"email": EMAIL, "password": PASSWORD})
    assert login.status_code == 200
    token = login.json()["token"]
    allowed = client.get("/api/v1/docs", headers={"Authorization": f"Bearer {token}"})
    assert allowed.status_code == 200


def test_unknown_actor_header_keeps_not_found_semantics(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TIANXUAN_ALLOW_ACTOR_HEADER", "1")
    client, _ = _setup()

    response = client.get("/api/v1/events", headers={"X-Actor": "usr_missing"})
    assert response.status_code == 404


def test_bearer_token_takes_precedence_over_actor_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TIANXUAN_ALLOW_ACTOR_HEADER", "1")
    client, registered = _setup()
    login = client.post("/api/v1/auth/session", json={"email": EMAIL, "password": PASSWORD}).json()

    document = client.post(
        "/api/v1/docs",
        headers={
            "Authorization": f"Bearer {login['token']}",
            "X-Actor": "usr_missing",
        },
        json={"title": "Bearer 优先", "body_md": "# 正文\n"},
    )
    assert document.status_code == 200, document.text
    assert document.json()["created_by"] == registered["user_id"]


def test_websocket_accepts_token_query(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TIANXUAN_ALLOW_ACTOR_HEADER", raising=False)
    client, _ = _setup()
    token = _token(client)
    document = client.post(
        "/api/v1/docs",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "实时文档", "body_md": "# 正文\n"},
    ).json()

    with client.websocket_connect(f"/api/v1/ws/docs/{document['id']}?token={token}") as websocket:
        message = websocket.receive_json()
    assert message["type"] == "snapshot"
    assert message["doc"]["id"] == document["id"]


def test_websocket_rejects_actor_when_header_mode_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TIANXUAN_ALLOW_ACTOR_HEADER", raising=False)
    client, registered = _setup()

    with pytest.raises(WebSocketDisconnect) as failure:
        with client.websocket_connect(f"/api/v1/ws/merge-queue?actor={registered['user_id']}") as websocket:
            websocket.receive_json()
    assert failure.value.code == 4401
