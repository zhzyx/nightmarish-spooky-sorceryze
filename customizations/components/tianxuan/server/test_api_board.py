"""司南工单列表与看板 API 测试。"""

from __future__ import annotations

from typing import Any

from api import create_app
from fastapi.testclient import TestClient
from tianxuan_core import Tianxuan


def _setup() -> tuple[TestClient, dict[str, str]]:
    store = Tianxuan(":memory:")
    client = TestClient(create_app(store))
    registered = client.post(
        "/api/v1/auth/register",
        json={
            "tenant_name": "看板工坊",
            "email": "board@example.com",
            "password": "secret-pass",
            "name": "Owner",
        },
    ).json()
    return client, {"X-Actor": registered["user_id"]}


def _requirement(client: TestClient, headers: dict[str, str], request_id: str) -> dict[str, Any]:
    return client.post(  # type: ignore[no-any-return]
        "/api/v1/requirements",
        headers=headers,
        json={
            "request_id": request_id,
            "title": f"需求 {request_id}",
            "outcome": "看板验证",
            "scope": "工单",
            "acceptance": "看板可见",
        },
    ).json()


def _tickets(
    client: TestClient, headers: dict[str, str], requirement: dict[str, Any], titles: list[str]
) -> list[dict[str, Any]]:
    tickets = client.post(
        f"/api/v1/requirements/{requirement['id']}/tickets",
        headers=headers,
        json={"tickets": [{"title": title} for title in titles]},
    ).json()["issues"]
    return tickets[1:]  # type: ignore[no-any-return]


def test_board_groups_issues_by_status() -> None:
    client, headers = _setup()
    requirement = _requirement(client, headers, "board-1")
    first, second = _tickets(client, headers, requirement, ["待规划", "进行中"])
    client.patch(f"/api/v1/issues/{second['id']}", headers=headers, json={"to_status": "planned"})

    board = client.get("/api/v1/board", headers=headers).json()["columns"]
    assert first["id"] in {issue["id"] for issue in board["backlog"]}
    assert [issue["id"] for issue in board["planned"]] == [second["id"]]
    assert "done" not in board


def test_issue_list_filters_by_status() -> None:
    client, headers = _setup()
    requirement = _requirement(client, headers, "board-2")
    first, second = _tickets(client, headers, requirement, ["待规划", "进行中"])
    client.patch(f"/api/v1/issues/{second['id']}", headers=headers, json={"to_status": "planned"})

    backlog = client.get("/api/v1/issues?status=backlog", headers=headers).json()["issues"]
    backlog_ids = {issue["id"] for issue in backlog}
    assert first["id"] in backlog_ids
    assert second["id"] not in backlog_ids

    planned = client.get("/api/v1/issues?status=planned", headers=headers).json()["issues"]
    assert [issue["id"] for issue in planned] == [second["id"]]

    assert client.get("/api/v1/issues?status=done", headers=headers).json()["issues"] == []


def test_issue_list_filters_by_requirement() -> None:
    client, headers = _setup()
    first_requirement = _requirement(client, headers, "board-3")
    second_requirement = _requirement(client, headers, "board-4")
    first_ticket = _tickets(client, headers, first_requirement, ["关联工单"])[0]
    second_ticket = _tickets(client, headers, second_requirement, ["无关工单"])[0]

    filtered = client.get(f"/api/v1/issues?requirement_id={first_requirement['id']}", headers=headers).json()["issues"]
    filtered_ids = {issue["id"] for issue in filtered}
    assert first_ticket["id"] in filtered_ids
    assert second_ticket["id"] not in filtered_ids
