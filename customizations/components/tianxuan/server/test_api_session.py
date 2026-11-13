"""会话 token 认证测试：登录签发、Bearer 访问、无效 token 与 X-Actor 兼容。"""

from __future__ import annotations

from typing import Any

from api import create_app
from fastapi.testclient import TestClient
from tianxuan_core import Tianxuan

EMAIL = "session@example.com"
PASSWORD = "secret-pass"


def _setup() -> tuple[TestClient, dict[str, Any]]:
    store = Tianxuan(":memory:")
    client = TestClient(create_app(store))
    registered = client.post(
        "/api/v1/auth/register",
        json={"tenant_name": "会话工坊", "email": EMAIL, "password": PASSWORD, "name": "Owner"},
    ).json()
    return client, registered


def _token(client: TestClient) -> str:
    login = client.post("/api/v1/auth/session", json={"email": EMAIL, "password": PASSWORD})
    assert login.status_code == 200, login.text
    return login.json()["token"]  # type: ignore[no-any-return]


def test_login_issues_token_and_bearer_authorizes() -> None:
    client, registered = _setup()
    token = _token(client)
    assert token.startswith("txs_")

    created = client.post(
        "/api/v1/docs",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "会话文档", "body_md": "# 会话\n"},
    )
    assert created.status_code == 200, created.text
    assert created.json()["title"] == "会话文档"

    listed = client.get("/api/v1/docs", headers={"Authorization": f"Bearer {token}"})
    assert listed.status_code == 200
    assert [doc["id"] for doc in listed.json()["docs"]] == [created.json()["id"]]

    x_actor = client.get("/api/v1/docs", headers={"X-Actor": registered["user_id"]})
    assert x_actor.status_code == 200


def test_invalid_bearer_and_missing_identity() -> None:
    client, _ = _setup()
    invalid = client.get("/api/v1/docs", headers={"Authorization": "Bearer txs_missing"})
    assert invalid.status_code == 400

    missing = client.get("/api/v1/docs")
    assert missing.status_code == 400


def test_login_rejects_bad_password() -> None:
    client, _ = _setup()
    assert client.post("/api/v1/auth/login", json={"email": EMAIL, "password": "wrong"}).status_code == 401
