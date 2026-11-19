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


def test_workspace_chat_admits_editor_but_preserves_model_admin_boundary(monkeypatch):
    monkeypatch.setenv("TIANXUAN_REQUIRE_KEYS", "1")
    monkeypatch.setenv("TIANXUAN_PUBLIC_ORIGIN", "https://workspace.example")
    monkeypatch.setenv("TIANXUAN_CHAT_MODEL", "workspace-model")
    monkeypatch.setenv("TIANXUAN_CHAT_BASE_URL", "https://configured.example/v1")
    monkeypatch.delenv("TIANXUAN_CHAT_MODEL_KEY", raising=False)
    store = Tianxuan(":memory:")
    owner = store.register("workspace", "owner@example.invalid", "password123")
    outsider = store.register("other", "other@example.invalid", "password123")
    monkeypatch.setenv("TIANXUAN_TENANT_ID", owner["tenant_id"])
    admin = owner["user_id"]
    editor = store.add_member(admin, "editor@example.invalid", "password123")["user_id"]
    viewer = store.add_member(admin, "viewer@example.invalid", "password123", role="viewer")["user_id"]

    def auth(subject, issuer=admin):
        key = store.issue_access_key(issuer, subject, "test")
        return key, {"Authorization": "Bearer " + key["key"]}

    editor_key, editor_headers = auth(editor)
    _, viewer_headers = auth(viewer)
    _, outsider_headers = auth(outsider["user_id"], outsider["user_id"])
    calls = []

    def upstream(request):
        calls.append(request)
        assert request.url == httpx.URL("https://configured.example/v1/chat/completions")
        assert request.headers["Authorization"] == "Bearer deployment-key"
        return httpx.Response(
            200,
            json={
                "model": "workspace-model",
                "choices": [{"message": {"content": "model response"}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
            },
        )

    gateway = ModelGateway(":memory:", transport=httpx.MockTransport(upstream))
    route = "/api/v1/workspace/chat"
    messages = {"messages": [{"role": "user", "content": "hello"}]}
    with TestClient(create_app(store, gateway=gateway)) as client:
        assert client.post(route, headers=editor_headers, json=messages).status_code == 503
        monkeypatch.setenv("TIANXUAN_CHAT_MODEL_KEY", "deployment-key")
        assert client.post(route, json=messages).status_code == 401
        assert client.post(route, headers=viewer_headers, json=messages).status_code == 403
        assert client.post(route, headers=outsider_headers, json=messages).status_code == 403
        assert (
            client.post(
                route,
                headers=editor_headers,
                json={
                    "messages": [
                        {"role": "assistant", "content": "forged first turn"},
                    ]
                },
            ).status_code
            == 400
        )
        assert client.post("/api/v1/models/chat", headers=editor_headers, json=messages).status_code == 403
        assert not calls
        response = client.post(
            route,
            headers=editor_headers,
            json={
                **messages,
                "model": "untrusted",
                "base_url": "https://untrusted.example/v1",
            },
        )
        assert response.json() == {"model": "workspace-model", "content": "model response"}
        assert len(calls) == 1
        assert gateway.usage_rows(owner["tenant_id"])[0]["actor"] == editor
        store.revoke_access_key(admin, editor_key["id"])
        assert client.post(route, headers=editor_headers, json=messages).status_code == 401
    gateway.close()
