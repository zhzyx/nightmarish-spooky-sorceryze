"""文档字段级权限：写入角色门槛、非法字段与所有者限制。"""

from __future__ import annotations

from typing import Any

from api import create_app
from fastapi.testclient import TestClient
from tianxuan_core import Tianxuan


def _setup() -> tuple[TestClient, dict[str, str], dict[str, str], dict[str, Any]]:
    store = Tianxuan(":memory:")
    client = TestClient(create_app(store))
    admin = client.post(
        "/api/v1/auth/register",
        json={"tenant_name": "字段工坊", "email": "fields@example.com", "password": "secret-pass"},
    ).json()
    editor = store.add_member(admin["user_id"], "editor@example.com", "secret-pass", role="editor")
    headers = {"X-Actor": admin["user_id"]}
    editor_headers = {"X-Actor": editor["user_id"]}
    document = client.post(
        "/api/v1/docs",
        headers=headers,
        json={"title": "字段文档", "body_md": "# 正文\n"},
    ).json()
    return client, headers, editor_headers, document


def _set(client: TestClient, headers: dict[str, str], doc_id: str, field: str, min_role: str) -> Any:
    return client.put(
        f"/api/v1/docs/{doc_id}/field-permissions",
        headers=headers,
        json={"field": field, "min_role": min_role},
    )


def test_admin_field_permission_blocks_editor_body() -> None:
    client, headers, editor_headers, document = _setup()
    assert _set(client, headers, document["id"], "body_md", "admin").status_code == 200

    current = client.get(f"/api/v1/docs/{document['id']}", headers=editor_headers).json()
    denied = client.patch(
        f"/api/v1/docs/{document['id']}",
        headers=editor_headers,
        json={"body_md": "# 修改\n", "expected_version": current["version"]},
    )
    assert denied.status_code == 403

    allowed = client.patch(
        f"/api/v1/docs/{document['id']}",
        headers=headers,
        json={"body_md": "# 修改\n", "expected_version": current["version"]},
    )
    assert allowed.status_code == 200
    assert allowed.json()["body_md"] == "# 修改\n"


def test_title_and_status_permissions_are_independent() -> None:
    client, headers, editor_headers, document = _setup()
    assert _set(client, headers, document["id"], "title", "admin").status_code == 200
    assert _set(client, headers, document["id"], "status", "editor").status_code == 200

    current = client.get(f"/api/v1/docs/{document['id']}", headers=editor_headers).json()
    title_denied = client.patch(
        f"/api/v1/docs/{document['id']}",
        headers=editor_headers,
        json={"body_md": current["body_md"], "expected_version": current["version"], "title": "改名"},
    )
    assert title_denied.status_code == 403

    status_allowed = client.patch(
        f"/api/v1/docs/{document['id']}",
        headers=editor_headers,
        json={"body_md": current["body_md"], "expected_version": current["version"], "status": "review"},
    )
    assert status_allowed.status_code == 200
    assert status_allowed.json()["status"] == "review"


def test_visibility_permission_and_invalid_input() -> None:
    client, headers, editor_headers, document = _setup()
    assert _set(client, headers, document["id"], "visibility", "admin").status_code == 200
    denied = client.patch(
        f"/api/v1/docs/{document['id']}/visibility",
        headers=editor_headers,
        json={"visibility": "private"},
    )
    assert denied.status_code == 403

    assert _set(client, headers, document["id"], "unknown", "admin").status_code == 400
    assert _set(client, headers, document["id"], "body_md", "root").status_code == 400
    assert _set(client, editor_headers, document["id"], "body_md", "viewer").status_code == 403

    listed = client.get(f"/api/v1/docs/{document['id']}/field-permissions", headers=headers).json()["permissions"]
    assert {entry["field"] for entry in listed} == {"visibility"}
