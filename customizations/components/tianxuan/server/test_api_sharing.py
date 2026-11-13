"""文档可见性与共享测试：私有隐藏、读/写共享、列表过滤与权限边界。"""

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
        json={"tenant_name": "共享工坊", "email": "admin@example.com", "password": "admin-pass"},
    ).json()
    return client, {"X-Actor": registered["user_id"]}


def _member(client: TestClient, headers: dict[str, str], email: str, role: str) -> dict[str, Any]:
    response = client.post(
        "/api/v1/users",
        headers=headers,
        json={"email": email, "password": "member-pass", "role": role},
    )
    assert response.status_code == 200, response.text
    return response.json()  # type: ignore[no-any-return]


def _token(client: TestClient, email: str) -> str:
    response = client.post("/api/v1/auth/session", json={"email": email, "password": "member-pass"})
    assert response.status_code == 200, response.text
    return response.json()["token"]  # type: ignore[no-any-return]


def test_private_document_hidden_until_shared() -> None:
    client, admin = _setup()
    viewer = _member(client, admin, "viewer@example.com", "viewer")
    viewer_headers = {"Authorization": f"Bearer {_token(client, 'viewer@example.com')}"}

    document = client.post("/api/v1/docs", headers=admin, json={"title": "私有文档", "body_md": "# 私有\n"}).json()
    private = client.patch(f"/api/v1/docs/{document['id']}/visibility", headers=admin, json={"visibility": "private"})
    assert private.status_code == 200
    assert private.json()["visibility"] == "private"

    assert document["id"] not in {
        item["id"] for item in client.get("/api/v1/docs", headers=viewer_headers).json()["docs"]
    }
    assert client.get(f"/api/v1/docs/{document['id']}", headers=viewer_headers).status_code == 403

    shared = client.post(
        f"/api/v1/docs/{document['id']}/shares",
        headers=admin,
        json={"user_id": viewer["user_id"], "permission": "read"},
    )
    assert shared.status_code == 200

    assert client.get(f"/api/v1/docs/{document['id']}", headers=viewer_headers).status_code == 200
    assert (
        client.patch(
            f"/api/v1/docs/{document['id']}",
            headers=viewer_headers,
            json={"body_md": "# 改", "expected_version": 1},
        ).status_code
        == 403
    )


def test_write_share_and_unshare() -> None:
    client, admin = _setup()
    editor = _member(client, admin, "editor@example.com", "editor")
    editor_headers = {"Authorization": f"Bearer {_token(client, 'editor@example.com')}"}

    document = client.post("/api/v1/docs", headers=admin, json={"title": "可写共享", "body_md": "# v1\n"}).json()
    client.patch(f"/api/v1/docs/{document['id']}/visibility", headers=admin, json={"visibility": "private"})
    client.post(
        f"/api/v1/docs/{document['id']}/shares",
        headers=admin,
        json={"user_id": editor["user_id"], "permission": "write"},
    )

    updated = client.patch(
        f"/api/v1/docs/{document['id']}",
        headers=editor_headers,
        json={"body_md": "# v2\n", "expected_version": 1},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["version"] == 2

    shares = client.get(f"/api/v1/docs/{document['id']}/shares", headers=admin).json()["shares"]
    assert len(shares) == 1
    assert shares[0]["user_id"] == editor["user_id"]
    assert shares[0]["permission"] == "write"

    client.delete(f"/api/v1/docs/{document['id']}/shares/{editor['user_id']}", headers=admin)
    assert client.get(f"/api/v1/docs/{document['id']}", headers=editor_headers).status_code == 403


def test_only_owner_or_admin_can_change_sharing() -> None:
    client, admin = _setup()
    editor = _member(client, admin, "owner2@example.com", "editor")
    editor_headers = {"Authorization": f"Bearer {_token(client, 'owner2@example.com')}"}

    document = client.post(
        "/api/v1/docs", headers=editor_headers, json={"title": "编辑者的文档", "body_md": "# x\n"}
    ).json()

    # 管理员可以改任意文档可见性。
    assert (
        client.patch(
            f"/api/v1/docs/{document['id']}/visibility", headers=admin, json={"visibility": "private"}
        ).status_code
        == 200
    )

    # 非所有者、非管理员不能改另一位成员文档的可见性。
    other = _member(client, admin, "other@example.com", "editor")
    other_headers = {"Authorization": f"Bearer {_token(client, 'other@example.com')}"}
    assert (
        client.patch(
            f"/api/v1/docs/{document['id']}/visibility",
            headers=other_headers,
            json={"visibility": "tenant"},
        ).status_code
        == 403
    )
    assert other["user_id"] != editor["user_id"]


def test_private_read_helpers_require_access() -> None:
    client, admin = _setup()
    viewer = _member(client, admin, "reader@example.com", "viewer")
    viewer_headers = {"Authorization": f"Bearer {_token(client, 'reader@example.com')}"}

    document = client.post("/api/v1/docs", headers=admin, json={"title": "私有只读", "body_md": "# 私有\n"}).json()
    client.patch(f"/api/v1/docs/{document['id']}/visibility", headers=admin, json={"visibility": "private"})

    assert client.get(f"/api/v1/docs/{document['id']}/export", headers=viewer_headers).status_code == 403
    assert client.get(f"/api/v1/docs/{document['id']}/ai-view", headers=viewer_headers).status_code == 403
    assert client.post(f"/api/v1/docs/{document['id']}/classify", headers=viewer_headers).status_code == 403

    client.post(
        f"/api/v1/docs/{document['id']}/shares",
        headers=admin,
        json={"user_id": viewer["user_id"], "permission": "read"},
    )
    assert client.get(f"/api/v1/docs/{document['id']}/export", headers=viewer_headers).status_code == 200
    assert client.get(f"/api/v1/docs/{document['id']}/ai-view", headers=viewer_headers).status_code == 200
    assert client.post(f"/api/v1/docs/{document['id']}/classify", headers=viewer_headers).status_code == 200
