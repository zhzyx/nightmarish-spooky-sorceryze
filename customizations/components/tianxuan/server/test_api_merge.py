"""离线草稿三方合并 API 测试：同版本应用、无冲突合并、冲突 409 与 404。"""

from __future__ import annotations

from typing import Any

from api import create_app
from fastapi.testclient import TestClient
from tianxuan_core import Tianxuan

BASE = "# 标题\n\nA\n\nB\n"
REMOTE = "# 标题\n\nA-remote\n\nB\n"
LOCAL = "# 标题\n\nA\n\nB-local\n"
LOCAL_CONFLICT = "# 标题\n\nA-local\n\nB\n"


def _setup() -> tuple[TestClient, dict[str, str], dict[str, Any]]:
    store = Tianxuan(":memory:")
    client = TestClient(create_app(store))
    registered = client.post(
        "/api/v1/auth/register",
        json={
            "tenant_name": "离线工坊",
            "email": "offline@example.com",
            "password": "secret-pass",
            "name": "Owner",
        },
    ).json()
    headers = {"X-Actor": registered["user_id"]}
    document = client.post(
        "/api/v1/docs",
        headers=headers,
        json={"title": "离线合并", "body_md": BASE},
    ).json()
    return client, headers, document


def test_merge_applies_local_when_version_matches() -> None:
    client, headers, document = _setup()
    local = BASE + "\nC\n"
    response = client.post(
        f"/api/v1/docs/{document['id']}/merge",
        headers=headers,
        json={"base_md": BASE, "local_md": local, "expected_version": 1},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "applied"
    assert body["doc"]["body_md"] == local
    assert body["doc"]["version"] == 2


def test_merge_combines_non_overlapping_edits() -> None:
    client, headers, document = _setup()
    updated = client.patch(
        f"/api/v1/docs/{document['id']}",
        headers=headers,
        json={"body_md": REMOTE, "expected_version": 1},
    )
    assert updated.status_code == 200, updated.text

    response = client.post(
        f"/api/v1/docs/{document['id']}/merge",
        headers=headers,
        json={"base_md": BASE, "local_md": LOCAL, "expected_version": 1},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "merged"
    assert body["remote_version"] == 2
    assert body["doc"]["body_md"] == "# 标题\n\nA-remote\n\nB-local\n"
    assert body["doc"]["version"] == 3


def test_merge_reports_conflict_without_writing() -> None:
    client, headers, document = _setup()
    client.patch(
        f"/api/v1/docs/{document['id']}",
        headers=headers,
        json={"body_md": REMOTE, "expected_version": 1},
    )

    response = client.post(
        f"/api/v1/docs/{document['id']}/merge",
        headers=headers,
        json={"base_md": BASE, "local_md": LOCAL_CONFLICT, "expected_version": 1},
    )
    assert response.status_code == 409, response.text
    body = response.json()
    assert body["status"] == "conflict"
    assert body["conflicts"]
    assert body["remote_version"] == 2
    current = client.get(f"/api/v1/docs/{document['id']}", headers=headers).json()
    assert current["version"] == 2
    assert current["body_md"] == REMOTE


def test_merge_unknown_document() -> None:
    client, headers, _ = _setup()
    response = client.post(
        "/api/v1/docs/doc_missing/merge",
        headers=headers,
        json={"base_md": BASE, "local_md": LOCAL, "expected_version": 1},
    )
    assert response.status_code == 404
