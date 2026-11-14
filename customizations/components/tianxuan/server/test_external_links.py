"""天璇 ↔ 天枢外部绑定 API 测试。"""

from __future__ import annotations

from api import create_app
from fastapi.testclient import TestClient
from tianxuan_core import Tianxuan

EXTERNAL = "https://github.com/owner/repo/issues/7"


def _client() -> tuple[TestClient, dict[str, str], str]:
    store = Tianxuan(":memory:")
    client = TestClient(create_app(store))
    registered = client.post(
        "/api/v1/auth/register",
        json={"tenant_name": "互通租户", "email": "bridge@example.com", "password": "secret-pass"},
    ).json()
    headers = {"X-Actor": registered["user_id"]}
    document = client.post(
        "/api/v1/docs",
        headers=headers,
        json={"title": "天枢来源文档", "body_md": "# 文档\n"},
    ).json()
    return client, headers, document["id"]


def test_link_and_context_roundtrip() -> None:
    client, headers, doc_id = _client()
    linked = client.post(
        "/api/v1/external-links",
        headers=headers,
        json={
            "system": "tianshu",
            "external_id": EXTERNAL,
            "target_type": "doc",
            "target_id": doc_id,
        },
    )
    assert linked.status_code == 200, linked.text
    assert linked.json()["target_id"] == doc_id

    links = client.get(
        "/api/v1/external-links",
        headers=headers,
        params={"system": "tianshu", "external_id": EXTERNAL},
    ).json()["links"]
    assert links[0]["target"]["title"] == "天枢来源文档"

    context = client.get(
        "/api/v1/external-context",
        headers=headers,
        params={"system": "tianshu", "external_id": EXTERNAL},
    ).json()
    assert [doc["id"] for doc in context["documents"]] == [doc_id]


def test_from_external_creates_requirement_and_links() -> None:
    client, headers, _ = _client()
    created = client.post(
        "/api/v1/requirements/from-external",
        headers=headers,
        json={
            "system": "tianshu",
            "external_id": EXTERNAL,
            "request_id": "tianshu-req-7",
            "title": "天枢来源需求",
            "outcome": "目标",
            "scope": "范围",
            "acceptance": "验收",
            "tickets": [{"title": "任务甲"}, {"title": "任务乙"}],
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["requirement"]["request_id"] == "tianshu-req-7"
    assert len(body["issues"]) == 3
    assert body["link"]["target_type"] == "doc"

    replay = client.post(
        "/api/v1/requirements/from-external",
        headers=headers,
        json={
            "system": "tianshu",
            "external_id": EXTERNAL,
            "request_id": "tianshu-req-7",
            "title": "天枢来源需求",
            "outcome": "目标",
            "scope": "范围",
            "acceptance": "验收",
            "tickets": [{"title": "任务甲"}, {"title": "任务乙"}],
        },
    )
    assert replay.status_code == 200
    assert replay.json()["requirement"]["id"] == body["requirement"]["id"]
    assert len(replay.json()["issues"]) == 3

    context = client.get(
        "/api/v1/external-context",
        headers=headers,
        params={"system": "tianshu", "external_id": EXTERNAL},
    ).json()
    assert context["documents"][0]["kind"] == "requirement"
    assert {issue["title"] for issue in context["issues"]} == {"天枢来源需求", "任务甲", "任务乙"}


def test_cross_tenant_binding_is_rejected() -> None:
    client, headers, doc_id = _client()
    other = client.post(
        "/api/v1/auth/register",
        json={"tenant_name": "另一租户", "email": "other@example.com", "password": "secret-pass"},
    ).json()
    denied = client.post(
        "/api/v1/external-links",
        headers={"X-Actor": other["user_id"]},
        json={
            "system": "tianshu",
            "external_id": EXTERNAL,
            "target_type": "doc",
            "target_id": doc_id,
        },
    )
    assert denied.status_code == 404
