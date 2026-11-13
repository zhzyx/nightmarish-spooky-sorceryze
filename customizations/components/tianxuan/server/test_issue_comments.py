"""司南工单评论 API 测试：编辑者添加与列出、viewer 只读、参数校验与租户隔离。"""

from __future__ import annotations

from typing import Any

from api import create_app
from fastapi.testclient import TestClient
from tianxuan_core import Tianxuan


def _register(client: TestClient, tenant_name: str, email: str) -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "tenant_name": tenant_name,
            "email": email,
            "password": "secret-pass",
            "name": email.split("@")[0],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["user_id"]  # type: ignore[no-any-return]


def _setup() -> tuple[TestClient, dict[str, str], dict[str, Any]]:
    store = Tianxuan(":memory:")
    client = TestClient(create_app(store))
    owner = _register(client, "工单评论工坊", "issue-comments@example.com")
    headers = {"X-Actor": owner}
    issue = store.create_issue(owner, "补充工单评论")
    return client, headers, issue


def test_editor_adds_and_lists_comments() -> None:
    client, headers, issue = _setup()

    created = client.post(
        f"/api/v1/issues/{issue['id']}/comments",
        headers=headers,
        json={"body": "请补充验收标准"},
    )
    assert created.status_code == 200, created.text
    comment = created.json()
    assert comment["issue_id"] == issue["id"]
    assert comment["author"] == headers["X-Actor"]
    assert comment["body"] == "请补充验收标准"
    assert comment["created_at"]

    second = client.post(
        f"/api/v1/issues/{issue['id']}/comments",
        headers=headers,
        json={"body": "第二条评论"},
    )
    assert second.status_code == 200, second.text

    listed = client.get(f"/api/v1/issues/{issue['id']}/comments", headers=headers)
    assert listed.status_code == 200, listed.text
    assert [item["id"] for item in listed.json()["comments"]] == [comment["id"], second.json()["id"]]

    events = client.get("/api/v1/events", headers=headers).json()["events"]
    assert "issue.comment_added" in {event["type"] for event in events}


def test_viewer_cannot_comment_but_can_read() -> None:
    client, admin, issue = _setup()
    added = client.post(
        f"/api/v1/issues/{issue['id']}/comments",
        headers=admin,
        json={"body": "编辑者的评论"},
    )
    assert added.status_code == 200, added.text

    member = client.post(
        "/api/v1/users",
        headers=admin,
        json={"email": "viewer@example.com", "password": "member-pass", "name": "Viewer", "role": "viewer"},
    )
    assert member.status_code == 200, member.text
    token = client.post(
        "/api/v1/auth/session",
        json={"email": "viewer@example.com", "password": "member-pass"},
    ).json()["token"]
    viewer = {"Authorization": f"Bearer {token}"}

    denied = client.post(
        f"/api/v1/issues/{issue['id']}/comments",
        headers=viewer,
        json={"body": "只读用户不能评论"},
    )
    assert denied.status_code == 403, denied.text

    listed = client.get(f"/api/v1/issues/{issue['id']}/comments", headers=viewer)
    assert listed.status_code == 200, listed.text
    assert [item["body"] for item in listed.json()["comments"]] == ["编辑者的评论"]


def test_empty_body_is_rejected() -> None:
    client, headers, issue = _setup()

    blank = client.post(f"/api/v1/issues/{issue['id']}/comments", headers=headers, json={"body": "   "})
    assert blank.status_code == 400, blank.text
    empty = client.post(f"/api/v1/issues/{issue['id']}/comments", headers=headers, json={"body": ""})
    assert empty.status_code == 400, empty.text


def test_unknown_issue_is_not_found() -> None:
    client, headers, _issue = _setup()

    assert client.post("/api/v1/issues/iss_missing/comments", headers=headers, json={"body": "x"}).status_code == 404
    assert client.get("/api/v1/issues/iss_missing/comments", headers=headers).status_code == 404


def test_second_tenant_cannot_read_or_comment() -> None:
    client, headers, issue = _setup()
    outsider = _register(client, "另一个工坊", "outsider@example.com")
    other = {"X-Actor": outsider}

    assert client.get(f"/api/v1/issues/{issue['id']}/comments", headers=other).status_code == 404
    assert (
        client.post(f"/api/v1/issues/{issue['id']}/comments", headers=other, json={"body": "越权"}).status_code == 404
    )
    assert client.get(f"/api/v1/issues/{issue['id']}/comments", headers=headers).json() == {"comments": []}
