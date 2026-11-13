"""邀请流程测试：管理员邀请、受邀者加入、角色生效、重复/越权。"""

from __future__ import annotations

from typing import Any

from api import create_app
from fastapi.testclient import TestClient
from tianxuan_core import Tianxuan


def _setup() -> tuple[TestClient, dict[str, str]]:
    store = Tianxuan(":memory:")
    client = TestClient(create_app(store))
    registered = client.post(
        "/api/v1/auth/register",
        json={
            "tenant_name": "邀请工坊",
            "email": "admin@example.com",
            "password": "admin-pass",
            "name": "Admin",
        },
    ).json()
    return client, {"X-Actor": registered["user_id"]}


def _invite(client: TestClient, headers: dict[str, str], email: str, role: str = "viewer") -> dict[str, Any]:
    response = client.post("/api/v1/invites", headers=headers, json={"email": email, "role": role})
    assert response.status_code == 200, response.text
    return response.json()  # type: ignore[no-any-return]


def test_invite_accept_and_role_take_effect() -> None:
    client, admin = _setup()
    invite = _invite(client, admin, "guest@example.com", "viewer")
    assert invite["code"].startswith("txi_")

    accepted = client.post(
        "/api/v1/invites/accept",
        json={"code": invite["code"], "password": "guest-pass", "name": "Guest"},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["role"] == "viewer"

    session = client.post("/api/v1/auth/session", json={"email": "guest@example.com", "password": "guest-pass"})
    assert session.status_code == 200
    token = session.json()["token"]
    viewer = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/v1/docs", headers=viewer).status_code == 200
    assert client.post("/api/v1/docs", headers=viewer, json={"title": "x", "body_md": ""}).status_code == 403


def test_invite_cannot_be_reused() -> None:
    client, admin = _setup()
    invite = _invite(client, admin, "once@example.com")
    first = client.post("/api/v1/invites/accept", json={"code": invite["code"], "password": "pass-1"})
    assert first.status_code == 200

    second = client.post("/api/v1/invites/accept", json={"code": invite["code"], "password": "pass-2"})
    assert second.status_code == 400


def test_non_admin_cannot_invite_and_bad_code_rejected() -> None:
    client, admin = _setup()
    member = client.post(
        "/api/v1/users",
        headers=admin,
        json={"email": "editor@example.com", "password": "editor-pass", "role": "editor"},
    )
    assert member.status_code == 200
    editor_session = client.post(
        "/api/v1/auth/session", json={"email": "editor@example.com", "password": "editor-pass"}
    ).json()
    editor = {"Authorization": f"Bearer {editor_session['token']}"}
    forbidden = client.post("/api/v1/invites", headers=editor, json={"email": "x@example.com", "role": "viewer"})
    assert forbidden.status_code == 403

    assert client.post("/api/v1/invites/accept", json={"code": "txi_missing", "password": "pass"}).status_code == 400
