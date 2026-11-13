"""角色与权限测试：管理员添加成员、viewer 只读、editor 可写、角色变更生效。"""

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
            "tenant_name": "角色工坊",
            "email": "admin@example.com",
            "password": "admin-pass",
            "name": "Admin",
        },
    ).json()
    return client, {"X-Actor": registered["user_id"]}


def _token(client: TestClient, email: str, password: str) -> str:
    response = client.post("/api/v1/auth/session", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["token"]  # type: ignore[no-any-return]


def _add(client: TestClient, headers: dict[str, str], email: str, role: str) -> dict[str, Any]:
    response = client.post(
        "/api/v1/users",
        headers=headers,
        json={"email": email, "password": "member-pass", "name": email.split("@")[0], "role": role},
    )
    assert response.status_code == 200, response.text
    return response.json()  # type: ignore[no-any-return]


def test_admin_adds_viewer_and_viewer_is_read_only() -> None:
    client, admin = _setup()
    member = _add(client, admin, "viewer@example.com", "viewer")
    token = _token(client, "viewer@example.com", "member-pass")
    viewer = {"Authorization": f"Bearer {token}"}

    assert client.get("/api/v1/docs", headers=viewer).status_code == 200
    denied = client.post("/api/v1/docs", headers=viewer, json={"title": "只读", "body_md": "# x\n"})
    assert denied.status_code == 403, denied.text

    members = client.get("/api/v1/users", headers=admin).json()["users"]
    roles = {item["email"]: item["role"] for item in members}
    assert roles["admin@example.com"] == "admin"
    assert roles["viewer@example.com"] == "viewer"
    assert member["user_id"] in {item["id"] for item in members}


def test_editor_can_write_but_not_manage_members() -> None:
    client, admin = _setup()
    _add(client, admin, "editor@example.com", "editor")
    token = _token(client, "editor@example.com", "member-pass")
    editor = {"Authorization": f"Bearer {token}"}

    created = client.post("/api/v1/docs", headers=editor, json={"title": "可写", "body_md": "# x\n"})
    assert created.status_code == 200, created.text

    forbidden = client.post(
        "/api/v1/users",
        headers=editor,
        json={"email": "other@example.com", "password": "pass", "role": "viewer"},
    )
    assert forbidden.status_code == 403


def test_role_change_takes_effect() -> None:
    client, admin = _setup()
    member = _add(client, admin, "promote@example.com", "viewer")
    token = _token(client, "promote@example.com", "member-pass")
    viewer = {"Authorization": f"Bearer {token}"}

    assert client.post("/api/v1/docs", headers=viewer, json={"title": "之前", "body_md": ""}).status_code == 403

    promoted = client.patch(f"/api/v1/users/{member['user_id']}/role", headers=admin, json={"role": "editor"})
    assert promoted.status_code == 200
    assert promoted.json()["role"] == "editor"

    assert client.post("/api/v1/docs", headers=viewer, json={"title": "之后", "body_md": ""}).status_code == 200


def test_invalid_role_and_non_admin_rejected() -> None:
    client, admin = _setup()
    assert (
        client.post(
            "/api/v1/users",
            headers=admin,
            json={"email": "bad@example.com", "password": "pass", "role": "owner"},
        ).status_code
        == 400
    )
