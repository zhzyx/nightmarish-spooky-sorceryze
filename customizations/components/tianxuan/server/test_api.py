"""天璇 FastAPI 适配层测试。

每个测试使用全新的内存领域核心，验证 HTTP 映射而非重测领域规则：
状态码、actor 头、版本冲突与状态机拒绝的 409、未知对象的 404。
"""

from __future__ import annotations

from typing import Any

import pytest
from api import create_app
from fastapi.testclient import TestClient
from tianxuan_core import Tianxuan


@pytest.fixture()
def store() -> Tianxuan:
    return Tianxuan(":memory:")


@pytest.fixture()
def client(store: Tianxuan):
    with TestClient(create_app(store)) as test_client:
        yield test_client


@pytest.fixture()
def account(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "tenant_name": "天璇测试组织",
            "email": "owner@example.com",
            "password": "secret-pass",
            "name": "Owner",
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert isinstance(data, dict)
    return data


@pytest.fixture()
def auth(account: dict[str, str]) -> dict[str, str]:
    return {"X-Actor": account["user_id"]}


def create_requirement(
    client: TestClient, auth: dict[str, str], request_id: str = "tianxuan-http-slice"
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/requirements",
        headers=auth,
        json={
            "request_id": request_id,
            "title": "天璇 HTTP 切片",
            "outcome": "注册后能创建文档并建工单",
            "scope": "单组织首版",
            "acceptance": "文档可读、工单可推进、进度同步",
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert isinstance(data, dict)
    return data


def test_health(client: TestClient):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_register_and_login(client: TestClient, account: dict[str, str]):
    assert set(account) == {"tenant_id", "space_id", "user_id"}

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "secret-pass"},
    )
    assert response.status_code == 200
    user = response.json()
    assert user == {
        "user_id": account["user_id"],
        "tenant_id": account["tenant_id"],
        "email": "owner@example.com",
        "name": "Owner",
    }

    assert (
        client.post("/api/v1/auth/login", json={"email": "owner@example.com", "password": "wrong"}).status_code == 401
    )
    assert (
        client.post("/api/v1/auth/login", json={"email": "nobody@example.com", "password": "secret-pass"}).status_code
        == 401
    )

    # 同一邮箱重复注册由领域层拒绝，映射为 400。
    duplicate = client.post(
        "/api/v1/auth/register",
        json={"tenant_name": "另一个组织", "email": "owner@example.com", "password": "secret-pass"},
    )
    assert duplicate.status_code == 400


def test_document_create_get_and_version_conflict(client: TestClient, auth: dict[str, str]):
    created = client.post(
        "/api/v1/docs",
        headers=auth,
        json={"title": "上线检查", "body_md": "# 上线检查\n\n登录与文档创建必须通过。\n"},
    )
    assert created.status_code == 200
    doc = created.json()
    assert doc["version"] == 1
    assert doc["kind"] == "doc"
    assert doc["status"] == "draft"

    fetched = client.get(f"/api/v1/docs/{doc['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["body_md"] == doc["body_md"]

    updated = client.patch(
        f"/api/v1/docs/{doc['id']}",
        headers=auth,
        json={
            "body_md": doc["body_md"] + "\n补充：支持离线草稿。\n",
            "expected_version": 1,
            "title": "上线检查（修订）",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["version"] == 2
    assert updated.json()["title"] == "上线检查（修订）"

    stale = client.patch(
        f"/api/v1/docs/{doc['id']}",
        headers=auth,
        json={"body_md": "过期的正文", "expected_version": 1},
    )
    assert stale.status_code == 409
    assert "version" in stale.json()["detail"]
    # 冲突不会落库：版本与正文保持第二次更新的结果。
    assert client.get(f"/api/v1/docs/{doc['id']}").json()["version"] == 2


def test_docs_list_filters_by_kind(client: TestClient, auth: dict[str, str]):
    doc = client.post("/api/v1/docs", headers=auth, json={"title": "普通文档", "body_md": "正文"})
    assert doc.status_code == 200
    requirement = create_requirement(client, auth)

    response = client.get("/api/v1/docs", headers=auth, params={"kind": "requirement"})
    assert response.status_code == 200
    assert [item["id"] for item in response.json()["docs"]] == [requirement["id"]]

    all_docs = client.get("/api/v1/docs", headers=auth).json()["docs"]
    assert {item["id"] for item in all_docs} == {doc.json()["id"], requirement["id"]}


def test_requirement_tickets_transition_and_progress(client: TestClient, auth: dict[str, str]):
    requirement = create_requirement(client, auth)
    assert requirement["kind"] == "requirement"
    assert requirement["progress"] == {}

    planned = client.post(
        f"/api/v1/requirements/{requirement['id']}/tickets",
        headers=auth,
        json={
            "tickets": [
                {"title": "注册登录", "acceptance": "邮箱注册与登录通过"},
                {"title": "文档创建", "acceptance": "Markdown 文档可创建与更新", "priority": "high"},
            ]
        },
    )
    assert planned.status_code == 200
    issues = planned.json()["issues"]
    assert len(issues) == 3
    assert all(issue["requirement_id"] == requirement["id"] for issue in issues)
    parent = next(issue for issue in issues if issue["type"] == "requirement")
    assert all(issue["parent_id"] == parent["id"] for issue in issues if issue["id"] != parent["id"])

    listed = client.get("/api/v1/issues", headers=auth, params={"requirement_id": requirement["id"]})
    assert listed.status_code == 200
    assert {issue["id"] for issue in listed.json()["issues"]} == {issue["id"] for issue in issues}

    child = next(issue for issue in issues if issue["type"] == "task")
    for status in ("planned", "in-progress", "in-review", "done"):
        transitioned = client.patch(f"/api/v1/issues/{child['id']}", headers=auth, json={"to_status": status})
        assert transitioned.status_code == 200, transitioned.text
        child = transitioned.json()
    assert child["status"] == "done"

    # done 是终态，任何迁移都会被领域层拒绝并映射为 409。
    rejected = client.patch(f"/api/v1/issues/{child['id']}", headers=auth, json={"to_status": "in-progress"})
    assert rejected.status_code == 409

    progress = client.get(f"/api/v1/docs/{requirement['id']}").json()["progress"]
    assert progress == {"total": 3, "done": 1, "percent": 33}


def test_transition_from_backlog_is_rejected(client: TestClient, auth: dict[str, str]):
    issue = client.post("/api/v1/docs", headers=auth, json={"title": "临时文档"}).json()
    # 需求文档之外不能拆工单：领域层抛 TianxuanError，映射为 400。
    invalid_plan = client.post(
        f"/api/v1/requirements/{issue['id']}/tickets",
        headers=auth,
        json={"tickets": [{"title": "不应该创建的工单"}]},
    )
    assert invalid_plan.status_code == 400

    created = client.post(
        "/api/v1/requirements",
        headers=auth,
        json={
            "request_id": "tianxuan-http-transition",
            "title": "状态机",
            "outcome": "非法迁移被拒绝",
            "scope": "单工单",
            "acceptance": "backlog 不能直接 done",
        },
    ).json()
    issues = client.post(
        f"/api/v1/requirements/{created['id']}/tickets",
        headers=auth,
        json={"tickets": [{"title": "状态机工单"}]},
    ).json()["issues"]
    child = next(issue for issue in issues if issue["type"] == "task")
    rejected = client.patch(f"/api/v1/issues/{child['id']}", headers=auth, json={"to_status": "done"})
    assert rejected.status_code == 409


def test_unknown_objects_return_404(client: TestClient, auth: dict[str, str]):
    assert client.get("/api/v1/docs/doc_missing").status_code == 404
    assert (
        client.patch("/api/v1/docs/doc_missing", headers=auth, json={"body_md": "x", "expected_version": 1}).status_code
        == 404
    )
    assert client.patch("/api/v1/issues/iss_missing", headers=auth, json={"to_status": "planned"}).status_code == 404
    # 未知 actor 无法解析租户，同样按未知对象返回 404。
    assert client.get("/api/v1/events", headers={"X-Actor": "usr_missing"}).status_code == 404


def test_events_list(client: TestClient, auth: dict[str, str]):
    doc = client.post("/api/v1/docs", headers=auth, json={"title": "事件文档", "body_md": "正文"})
    assert doc.status_code == 200

    response = client.get("/api/v1/events", headers=auth)
    assert response.status_code == 200
    events = response.json()["events"]
    types = [event["type"] for event in events]
    assert "user.registered" in types
    assert "doc.created" in types
    registered = next(event for event in events if event["type"] == "user.registered")
    assert registered["payload"] == {"email": "owner@example.com"}
    assert all({"type", "actor", "target", "payload", "created_at"} <= set(event) for event in events)

    limited = client.get("/api/v1/events", headers=auth, params={"limit": 1})
    assert limited.status_code == 200
    assert len(limited.json()["events"]) == 1


def test_actor_header_is_required(client: TestClient, auth: dict[str, str]):
    assert client.get("/api/v1/docs").status_code == 400
    assert client.get("/api/v1/events", headers={"X-Actor": "  "}).status_code == 400
    assert client.post("/api/v1/docs", json={"title": "无 actor"}).status_code == 400

    # 单文档读取在当前切片不要求 actor，健康检查同样匿名。
    doc = client.post("/api/v1/docs", headers=auth, json={"title": "免 actor 读取"}).json()
    assert client.get(f"/api/v1/docs/{doc['id']}").status_code == 200
    assert client.get("/api/v1/health").status_code == 200
