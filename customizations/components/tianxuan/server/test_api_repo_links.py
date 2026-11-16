"""仓库绑定 API：租户隔离、管理员权限与幂等冲突。"""

from __future__ import annotations

from typing import Any, cast

from api import create_app
from fastapi.testclient import TestClient
from tianxuan_core import Tianxuan


def _setup() -> tuple[TestClient, dict[str, str], Tianxuan]:
    store = Tianxuan(":memory:")
    client = TestClient(create_app(store))
    registered = client.post(
        "/api/v1/auth/register",
        json={"tenant_name": "仓库绑定", "email": "rb@example.com", "password": "secret-pass"},
    ).json()
    return client, {"X-Actor": registered["user_id"]}, store


def _bind(client: TestClient, headers: dict[str, str], owner: str = "octo") -> dict[str, Any]:
    response = client.post(
        "/api/v1/repo-links",
        headers=headers,
        json={"provider": "gitea", "owner": owner, "name": "duobao"},
    )
    assert response.status_code == 200, response.text
    return cast(dict[str, Any], response.json())


def test_bind_list_and_unbind_repo_link() -> None:
    client, headers, _ = _setup()
    link = _bind(client, headers)
    assert link["provider"] == "gitea"
    assert link["owner"] == "octo"

    listed = client.get("/api/v1/repo-links", headers=headers).json()["links"]
    assert [entry["id"] for entry in listed] == [link["id"]]

    duplicate = client.post(
        "/api/v1/repo-links",
        headers=headers,
        json={"provider": "gitea", "owner": "octo", "name": "duobao"},
    )
    assert duplicate.status_code == 400
    assert "already linked" in duplicate.json()["detail"]

    deleted = client.delete(f"/api/v1/repo-links/{link['id']}", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True
    assert client.get("/api/v1/repo-links", headers=headers).json()["links"] == []


def test_editor_cannot_bind_or_unbind() -> None:
    client, headers, store = _setup()
    link = _bind(client, headers)
    editor = store.add_member(headers["X-Actor"], "editor@example.com", "secret-pass", role="editor")
    editor_headers = {"X-Actor": editor["user_id"]}

    denied = client.post(
        "/api/v1/repo-links",
        headers=editor_headers,
        json={"provider": "gitea", "owner": "other", "name": "repo"},
    )
    assert denied.status_code == 403
    assert client.delete(f"/api/v1/repo-links/{link['id']}", headers=editor_headers).status_code == 403


def test_repo_links_are_tenant_scoped_and_globally_unique() -> None:
    client, headers, _ = _setup()
    link = _bind(client, headers)
    other = client.post(
        "/api/v1/auth/register",
        json={"tenant_name": "另一个租户", "email": "other@example.com", "password": "secret-pass"},
    ).json()
    other_headers = {"X-Actor": other["user_id"]}

    assert client.get("/api/v1/repo-links", headers=other_headers).json()["links"] == []

    clash = client.post(
        "/api/v1/repo-links",
        headers=other_headers,
        json={"provider": "gitea", "owner": "octo", "name": "duobao"},
    )
    assert clash.status_code == 400

    assert client.delete(f"/api/v1/repo-links/{link['id']}", headers=other_headers).status_code == 404


def test_invalid_provider_and_segments_rejected() -> None:
    client, headers, _ = _setup()
    for payload in (
        {"provider": "gitlab", "owner": "octo", "name": "duobao"},
        {"provider": "gitea", "owner": "octo/repo", "name": "duobao"},
        {"provider": "gitea", "owner": "octo", "name": ""},
    ):
        response = client.post("/api/v1/repo-links", headers=headers, json=payload)
        assert response.status_code == 400
