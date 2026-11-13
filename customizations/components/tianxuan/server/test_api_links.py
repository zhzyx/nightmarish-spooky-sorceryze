"""文曲文档链接与反向链接 API 测试。"""

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
            "tenant_name": "链接工坊",
            "email": "links@example.com",
            "password": "secret-pass",
            "name": "Owner",
        },
    ).json()
    return client, {"X-Actor": registered["user_id"]}


def _doc(client: TestClient, headers: dict[str, str], title: str, body: str) -> dict[str, Any]:
    return client.post(  # type: ignore[no-any-return]
        "/api/v1/docs",
        headers=headers,
        json={"title": title, "body_md": body},
    ).json()


def test_links_resolve_by_title_and_report_backlinks() -> None:
    client, headers = _setup()
    alpha = _doc(client, headers, "Alpha", "# Alpha\n")
    beta = _doc(client, headers, "Beta", "# Beta\n\n参见 [[Alpha]] 与 [[Missing]]\n")

    beta_links = client.get(f"/api/v1/docs/{beta['id']}/links", headers=headers).json()
    assert beta_links["outgoing"] == [
        {"target": "Alpha", "doc_id": alpha["id"], "resolved": True},
        {"target": "Missing", "doc_id": None, "resolved": False},
    ]

    alpha_links = client.get(f"/api/v1/docs/{alpha['id']}/links", headers=headers).json()
    assert alpha_links["outgoing"] == []
    assert alpha_links["backlinks"] == [{"doc_id": beta["id"], "title": "Beta"}]


def test_links_resolve_by_document_id() -> None:
    client, headers = _setup()
    alpha = _doc(client, headers, "Alpha", "# Alpha\n")
    gamma = _doc(client, headers, "Gamma", f"# Gamma\n\n[[{alpha['id']}]]\n")

    gamma_links = client.get(f"/api/v1/docs/{gamma['id']}/links", headers=headers).json()
    assert gamma_links["outgoing"][0]["resolved"] is True
    assert gamma_links["outgoing"][0]["doc_id"] == alpha["id"]

    alpha_links = client.get(f"/api/v1/docs/{alpha['id']}/links", headers=headers).json()
    assert {item["title"] for item in alpha_links["backlinks"]} == {"Gamma"}


def test_links_unknown_document() -> None:
    client, headers = _setup()
    assert client.get("/api/v1/docs/doc_missing/links", headers=headers).status_code == 404
