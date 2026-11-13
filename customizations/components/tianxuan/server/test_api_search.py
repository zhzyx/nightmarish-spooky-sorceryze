"""文曲 HTTP 能力测试：检索、导出、AI 视图与自动归类。"""

from __future__ import annotations

from api import create_app
from fastapi.testclient import TestClient
from tianxuan_core import Tianxuan


def _client() -> tuple[TestClient, dict[str, str]]:
    store = Tianxuan(":memory:")
    client = TestClient(create_app(store))
    registered = client.post(
        "/api/v1/auth/register",
        json={
            "tenant_name": "检索工坊",
            "email": "search@example.com",
            "password": "secret-pass",
            "name": "Owner",
        },
    )
    return client, {"X-Actor": registered.json()["user_id"]}


def test_search_export_ai_view_and_classify() -> None:
    client, headers = _client()
    doc = client.post(
        "/api/v1/docs",
        headers=headers,
        json={"title": "天璇检索", "body_md": "# 天璇检索\n\n需求与验收说明。\n"},
    ).json()
    client.post(
        "/api/v1/docs",
        headers=headers,
        json={"title": "无关文档", "body_md": "# 其他\n\n没有关键字。\n"},
    )

    results = client.get("/api/v1/search", headers=headers, params={"q": "天璇"}).json()["results"]
    assert [item["id"] for item in results] == [doc["id"]]

    export = client.get(f"/api/v1/docs/{doc['id']}/export", headers=headers).json()
    assert export["filename"] == f"{doc['id']}.md"
    assert export["markdown"].startswith("---")
    assert "天璇检索" in export["markdown"]

    view = client.get(f"/api/v1/docs/{doc['id']}/ai-view", headers=headers).json()
    assert view["machine"]["headings"][0]["text"] == "天璇检索"
    assert "requirement" in view["tags"]

    tags = client.post(f"/api/v1/docs/{doc['id']}/classify", headers=headers).json()["tags"]
    assert "requirement" in tags and "zh" in tags

    empty = client.get("/api/v1/search", headers=headers, params={"q": "不存在的词"}).json()["results"]
    assert empty == []

    assert client.get("/api/v1/docs/doc_missing/export", headers=headers).status_code == 404
