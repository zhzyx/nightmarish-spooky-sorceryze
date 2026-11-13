"""天璇闭环端到端测试：注册 → 需求落库 → 工单树 → 状态推进 → 进度同步 → AI 索引。"""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

SERVER = Path(__file__).resolve().parent
WENQU = SERVER.parent / "wenqu"
sys.path.insert(0, str(SERVER))
sys.path.insert(0, str(WENQU))

from api import create_app  # noqa: E402
from tianxuan_core import Tianxuan  # noqa: E402
from wenqu import build_ai_index  # noqa: E402


def test_closed_loop() -> None:
    store = Tianxuan(":memory:")
    client = TestClient(create_app(store))

    registered = client.post(
        "/api/v1/auth/register",
        json={
            "tenant_name": "天璇工坊",
            "email": "owner@example.com",
            "password": "secret-pass",
            "name": "Owner",
        },
    )
    assert registered.status_code == 200, registered.text
    actor = registered.json()["user_id"]
    headers = {"X-Actor": actor}

    requirement = client.post(
        "/api/v1/requirements",
        headers=headers,
        json={
            "request_id": "tianxuan-e2e",
            "title": "天璇首切片",
            "outcome": "注册后能创建文档并建工单",
            "scope": "单组织首版",
            "acceptance": "文档可读、工单可推进、进度同步",
        },
    )
    assert requirement.status_code == 200, requirement.text
    doc_id = requirement.json()["id"]

    planned = client.post(
        f"/api/v1/requirements/{doc_id}/tickets",
        headers=headers,
        json={
            "tickets": [
                {"title": "注册登录", "acceptance": "邮箱注册与登录通过"},
                {"title": "文档创建", "acceptance": "Markdown 文档可创建与更新"},
            ]
        },
    )
    assert planned.status_code == 200, planned.text
    issues = planned.json()["issues"]
    assert len(issues) == 3
    assert {issue["type"] for issue in issues} == {"requirement", "task"}

    child = next(issue for issue in issues if issue["type"] == "task")
    for status in ("planned", "in-progress", "in-review", "done"):
        moved = client.patch(f"/api/v1/issues/{child['id']}", headers=headers, json={"to_status": status})
        assert moved.status_code == 200, moved.text
        assert moved.json()["status"] == status

    document = client.get(f"/api/v1/docs/{doc_id}", headers=headers).json()
    assert document["progress"] == {"total": 3, "done": 1, "percent": 33}

    index = build_ai_index(document["body_md"])
    assert [heading["text"] for heading in index["headings"]] == ["天璇首切片", "目标", "范围", "验收"]
    assert index["language"] == "zh"
    assert index["content_hash"]

    events = client.get("/api/v1/events", headers=headers).json()["events"]
    types = {event["type"] for event in events}
    assert {
        "user.registered",
        "doc.created",
        "issue.created",
        "issue.transitioned",
        "requirement.planned",
    } <= types

    # A completed ticket cannot move backwards through the same API.
    rejected = client.patch(f"/api/v1/issues/{child['id']}", headers=headers, json={"to_status": "in-progress"})
    assert rejected.status_code == 409, rejected.text
