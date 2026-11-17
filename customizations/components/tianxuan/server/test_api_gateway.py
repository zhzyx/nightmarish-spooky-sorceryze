"""模型网关挂载到 HTTP 应用的集成测试（MockTransport，无网络）。"""

from __future__ import annotations

import httpx
from api import create_app
from fastapi.testclient import TestClient
from gateway import ModelGateway
from tianxuan_core import Tianxuan


def authenticated_client(gateway):
    store = Tianxuan(":memory:")
    user = store.register("org", "model@example.invalid", "password123")
    client = TestClient(create_app(store, gateway=gateway))
    client.headers["Authorization"] = "Bearer " + store.issue_session(user["user_id"])
    return client


HEADERS = {"X-Model-Key": "secret-key"}


def _transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer secret-key"
        return httpx.Response(
            200,
            json={
                "id": "cmpl_1",
                "model": "deepseek-v4-pro",
                "choices": [{"message": {"content": "pong"}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
            },
        )

    return httpx.MockTransport(handler)


def test_model_router_is_mounted_and_meters_usage() -> None:
    gateway = ModelGateway(":memory:", transport=_transport())
    client = authenticated_client(gateway)

    response = client.post(
        "/api/v1/models/chat",
        headers=HEADERS,
        json={
            "model": "deepseek-v4-pro",
            "messages": [{"role": "user", "content": "ping"}],
            "base_url": "https://model.example/v1",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["content"] == "pong"
    assert body["usage"]["total_tokens"] == 5
    assert "secret-key" not in response.text

    usage = client.get(
        "/api/v1/models/usage",
    )
    assert usage.status_code == 200, usage.text
    totals = usage.json()["totals"]
    assert totals["calls"] == 1
    assert totals["total_tokens"] == 5


def test_model_router_rejects_missing_key() -> None:
    gateway = ModelGateway(":memory:", transport=_transport())
    client = authenticated_client(gateway)
    response = client.post(
        "/api/v1/models/chat",
        headers={},
        json={"model": "m", "messages": [{"role": "user", "content": "x"}], "base_url": "https://model.example/v1"},
    )
    assert response.status_code == 400, response.text


def test_model_router_absent_without_gateway() -> None:
    client = TestClient(create_app(Tianxuan(":memory:")))
    assert (
        client.get(
            "/api/v1/models/usage",
        ).status_code
        == 404
    )
