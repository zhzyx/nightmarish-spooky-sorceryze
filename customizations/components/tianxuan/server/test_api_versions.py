"""文曲版本历史与差异 API 测试。"""

from __future__ import annotations

from typing import Any

from api import create_app
from fastapi.testclient import TestClient
from tianxuan_core import Tianxuan

BASE = "# 标题\n\nA\n"
UPDATED = "# 标题\n\nB\n"


def _setup() -> tuple[TestClient, dict[str, str], dict[str, Any]]:
    store = Tianxuan(":memory:")
    client = TestClient(create_app(store))
    registered = client.post(
        "/api/v1/auth/register",
        json={
            "tenant_name": "版本工坊",
            "email": "versions@example.com",
            "password": "secret-pass",
            "name": "Owner",
        },
    ).json()
    headers = {"X-Actor": registered["user_id"]}
    document = client.post(
        "/api/v1/docs",
        headers=headers,
        json={"title": "版本测试", "body_md": BASE},
    ).json()
    client.patch(
        f"/api/v1/docs/{document['id']}",
        headers=headers,
        json={"body_md": UPDATED, "expected_version": 1},
    )
    return client, headers, document


def test_versions_list_and_get() -> None:
    client, headers, document = _setup()
    versions = client.get(f"/api/v1/docs/{document['id']}/versions", headers=headers).json()["versions"]
    assert [item["version"] for item in versions] == [1, 2]

    first = client.get(f"/api/v1/docs/{document['id']}/versions/1", headers=headers).json()
    assert first["body_md"] == BASE
    assert first["version"] == 1


def test_diff_between_versions() -> None:
    client, headers, document = _setup()
    diff = client.get(f"/api/v1/docs/{document['id']}/diff?from_version=1&to_version=2", headers=headers).json()["diff"]
    assert "--- v1" in diff
    assert "+++ v2" in diff
    assert "-A" in diff
    assert "+B" in diff


def test_version_and_document_not_found() -> None:
    client, headers, document = _setup()
    assert client.get(f"/api/v1/docs/{document['id']}/versions/99", headers=headers).status_code == 404
    assert client.get("/api/v1/docs/doc_missing/versions", headers=headers).status_code == 404
