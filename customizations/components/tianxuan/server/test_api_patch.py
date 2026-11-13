"""文曲 AI 结构化补丁 API 测试：唯一替换、版本冲突、缺失/歧义目标与多步补丁。"""

from __future__ import annotations

from typing import Any

from api import create_app
from fastapi.testclient import TestClient
from tianxuan_core import Tianxuan

BASE = "# 标题\n\nA\n\nB\n"


def _setup() -> tuple[TestClient, dict[str, str], dict[str, Any]]:
    store = Tianxuan(":memory:")
    client = TestClient(create_app(store))
    registered = client.post(
        "/api/v1/auth/register",
        json={
            "tenant_name": "补丁工坊",
            "email": "patch@example.com",
            "password": "secret-pass",
            "name": "Owner",
        },
    ).json()
    headers = {"X-Actor": registered["user_id"]}
    document = client.post(
        "/api/v1/docs",
        headers=headers,
        json={"title": "补丁测试", "body_md": BASE},
    ).json()
    return client, headers, document


def test_patch_applies_unique_replacements() -> None:
    client, headers, document = _setup()
    response = client.post(
        f"/api/v1/docs/{document['id']}/patch",
        headers=headers,
        json={
            "expected_version": 1,
            "patches": [
                {"find": "A", "replace": "A2"},
                {"find": "B", "replace": "B2"},
            ],
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["version"] == 2
    assert body["body_md"] == "# 标题\n\nA2\n\nB2\n"


def test_patch_rejects_stale_version() -> None:
    client, headers, document = _setup()
    client.patch(
        f"/api/v1/docs/{document['id']}",
        headers=headers,
        json={"body_md": BASE + "\nC\n", "expected_version": 1},
    )
    response = client.post(
        f"/api/v1/docs/{document['id']}/patch",
        headers=headers,
        json={"expected_version": 1, "patches": [{"find": "A", "replace": "A2"}]},
    )
    assert response.status_code == 409, response.text


def test_patch_rejects_missing_and_ambiguous_targets() -> None:
    client, headers, document = _setup()
    missing = client.post(
        f"/api/v1/docs/{document['id']}/patch",
        headers=headers,
        json={"expected_version": 1, "patches": [{"find": "不存在", "replace": "x"}]},
    )
    assert missing.status_code == 400
    assert "not found" in missing.json()["detail"]

    ambiguous = client.post(
        f"/api/v1/docs/{document['id']}/patch",
        headers=headers,
        json={"expected_version": 1, "patches": [{"find": "\n\n", "replace": "\n"}]},
    )
    assert ambiguous.status_code == 400
    assert "ambiguous" in ambiguous.json()["detail"]


def test_patch_rejects_empty_find_and_unknown_document() -> None:
    client, headers, document = _setup()
    empty = client.post(
        f"/api/v1/docs/{document['id']}/patch",
        headers=headers,
        json={"expected_version": 1, "patches": [{"find": "", "replace": "x"}]},
    )
    assert empty.status_code == 400

    assert (
        client.post(
            "/api/v1/docs/doc_missing/patch",
            headers=headers,
            json={"expected_version": 1, "patches": [{"find": "A", "replace": "x"}]},
        ).status_code
        == 404
    )
