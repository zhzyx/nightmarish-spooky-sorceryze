"""司南工单评论 API 测试：编辑者添加与列出、viewer 只读、参数校验与租户隔离。"""

from __future__ import annotations

from pathlib import Path
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


def test_reply_requires_a_parent_in_the_same_issue() -> None:
    store = Tianxuan(":memory:")
    client = TestClient(create_app(store))
    owner = _register(client, "Thread scope", "thread-scope@example.invalid")
    headers = {"X-Actor": owner}
    first = store.create_issue(owner, "first")
    second = store.create_issue(owner, "second")
    parent = store.add_issue_comment(owner, first["id"], "original")
    route = f"/api/v1/issues/{second['id']}/comments"
    for parent_id in [parent["id"], "icmt_absent"]:
        response = client.post(route, headers=headers, json={"body": "reply", "parent_id": parent_id})
        assert response.status_code == 404, response.text
    assert client.get(route, headers=headers).json()["comments"] == []
    assert store.list_issue_comments(owner, first["id"]) == [parent]


def test_existing_issue_comments_survive_store_upgrade(tmp_path: Path) -> None:
    database = str(tmp_path / "upgrade.db")
    old = Tianxuan(database)
    account = old.register("Previous schema", "upgrade@example.invalid", "test-password", name="原作者")
    actor = account["user_id"]
    issue = old.create_issue(actor, "Old thread")
    comment = old.add_issue_comment(actor, issue["id"], "保留原始内容")
    with old.db:
        old.db.execute("DROP TABLE issue_comment_replies")
    old.db.close()

    upgraded = Tianxuan(database)
    try:
        assert upgraded.list_issue_comments(actor, issue["id"]) == [comment]
        reply = upgraded.add_issue_comment(actor, issue["id"], "回复历史评论", comment["id"])
        assert reply["parent_id"] == comment["id"]
        assert upgraded.list_issue_comments(actor, issue["id"]) == [comment, reply]
    finally:
        upgraded.db.close()


def test_reply_retry_returns_one_persisted_comment() -> None:
    client, headers, issue = _setup()
    route = f"/api/v1/issues/{issue['id']}/comments"
    parent = client.post(route, headers=headers, json={"body": "original"}).json()
    payload = {"body": "reply", "parent_id": parent["id"], "call_id": "one-draft"}
    reply = client.post(route, headers=headers, json=payload)
    replay = client.post(route, headers=headers, json=payload)
    assert reply.status_code == replay.status_code == 200
    assert reply.json() == replay.json()
    conflict = client.post(route, headers=headers, json=payload | {"body": "different"})
    assert conflict.status_code == 409
    assert client.get(route, headers=headers).json()["comments"] == [parent, reply.json()]
