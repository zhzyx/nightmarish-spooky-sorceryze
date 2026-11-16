"""文档 ↔ 司南工单双向关联：幂等、权限与租户隔离。"""

from __future__ import annotations

from typing import Any

from api import create_app
from fastapi.testclient import TestClient
from tianxuan_core import Tianxuan


def _setup() -> tuple[TestClient, dict[str, str], Tianxuan, dict[str, Any], dict[str, Any]]:
    store = Tianxuan(":memory:")
    client = TestClient(create_app(store))
    registered = client.post(
        "/api/v1/auth/register",
        json={"tenant_name": "关联工坊", "email": "links@example.com", "password": "secret-pass"},
    ).json()
    headers = {"X-Actor": registered["user_id"]}
    document = client.post(
        "/api/v1/docs",
        headers=headers,
        json={"title": "关联文档", "body_md": "# 正文\n"},
    ).json()
    issue = store.create_issue(registered["user_id"], "关联工单")
    return client, headers, store, document, issue


def test_link_list_and_unlink_both_directions() -> None:
    client, headers, _, document, issue = _setup()

    created = client.post(
        f"/api/v1/docs/{document['id']}/issues",
        headers=headers,
        json={"issue_id": issue["id"]},
    )
    assert created.status_code == 200, created.text
    assert created.json()["issue_id"] == issue["id"]

    again = client.post(
        f"/api/v1/docs/{document['id']}/issues",
        headers=headers,
        json={"issue_id": issue["id"]},
    )
    assert again.status_code == 200
    assert again.json()["id"] == created.json()["id"]

    issues = client.get(f"/api/v1/docs/{document['id']}/issues", headers=headers).json()["issues"]
    assert [entry["id"] for entry in issues] == [issue["id"]]
    assert issues[0]["title"] == "关联工单"

    documents = client.get(f"/api/v1/issues/{issue['id']}/docs", headers=headers).json()["docs"]
    assert [entry["id"] for entry in documents] == [document["id"]]

    deleted = client.delete(f"/api/v1/docs/{document['id']}/issues/{issue['id']}", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True
    assert client.get(f"/api/v1/docs/{document['id']}/issues", headers=headers).json()["issues"] == []
    assert client.get(f"/api/v1/issues/{issue['id']}/docs", headers=headers).json()["docs"] == []


def test_link_requires_editor_and_rejects_foreign_tenant() -> None:
    client, headers, store, document, issue = _setup()
    viewer = store.add_member(headers["X-Actor"], "viewer@example.com", "secret-pass", role="viewer")
    viewer_headers = {"X-Actor": viewer["user_id"]}

    denied = client.post(
        f"/api/v1/docs/{document['id']}/issues",
        headers=viewer_headers,
        json={"issue_id": issue["id"]},
    )
    assert denied.status_code == 403

    other = client.post(
        "/api/v1/auth/register",
        json={"tenant_name": "另一个租户", "email": "other@example.com", "password": "secret-pass"},
    ).json()
    foreign_issue = store.create_issue(other["user_id"], "外部工单")
    cross = client.post(
        f"/api/v1/docs/{document['id']}/issues",
        headers=headers,
        json={"issue_id": foreign_issue["id"]},
    )
    assert cross.status_code == 404

    unknown = client.post(
        f"/api/v1/docs/{document['id']}/issues",
        headers=headers,
        json={"issue_id": "iss_missing"},
    )
    assert unknown.status_code == 404


def test_unlink_unknown_link_is_not_found() -> None:
    client, headers, _, document, issue = _setup()
    response = client.delete(f"/api/v1/docs/{document['id']}/issues/{issue['id']}", headers=headers)
    assert response.status_code == 404
