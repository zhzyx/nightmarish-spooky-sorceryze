"""文曲评论 API 测试：创建、列出、解决、重新打开与错误映射。"""

from __future__ import annotations

from typing import Any

from api import create_app
from fastapi.testclient import TestClient
from tianxuan_core import Tianxuan


def _client() -> tuple[TestClient, dict[str, str], dict[str, Any]]:
    store = Tianxuan(":memory:")
    client = TestClient(create_app(store))
    registered = client.post(
        "/api/v1/auth/register",
        json={
            "tenant_name": "评论工坊",
            "email": "comments@example.com",
            "password": "secret-pass",
            "name": "Owner",
        },
    )
    headers = {"X-Actor": registered.json()["user_id"]}
    document = client.post(
        "/api/v1/docs",
        headers=headers,
        json={"title": "评论测试", "body_md": "# 评论测试\n\n正文。\n"},
    ).json()
    return client, headers, document


def test_comment_lifecycle() -> None:
    client, headers, document = _client()

    created = client.post(
        f"/api/v1/docs/{document['id']}/comments",
        headers=headers,
        json={"body": "请补充验收标准"},
    )
    assert created.status_code == 200, created.text
    comment = created.json()
    assert comment["resolved"] is False
    assert comment["doc_id"] == document["id"]

    listed = client.get(f"/api/v1/docs/{document['id']}/comments", headers=headers).json()["comments"]
    assert [item["id"] for item in listed] == [comment["id"]]

    resolved = client.patch(f"/api/v1/comments/{comment['id']}", headers=headers, json={"resolved": True}).json()
    assert resolved["resolved"] is True
    assert resolved["resolved_at"]

    reopened = client.patch(f"/api/v1/comments/{comment['id']}", headers=headers, json={"resolved": False}).json()
    assert reopened["resolved"] is False
    assert reopened["resolved_at"] is None


def test_comment_errors_are_mapped() -> None:
    client, headers, document = _client()

    assert (
        client.post(f"/api/v1/docs/{document['id']}/comments", headers=headers, json={"body": "   "}).status_code == 400
    )
    assert client.post("/api/v1/docs/doc_missing/comments", headers=headers, json={"body": "x"}).status_code == 404
    assert client.patch("/api/v1/comments/cmt_missing", headers=headers, json={"resolved": True}).status_code == 404
