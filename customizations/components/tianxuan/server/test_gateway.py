"""模型网关的离线测试：MockTransport + FastAPI TestClient，不访问网络。"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from gateway import (
    BudgetExceeded,
    MissingCredential,
    ModelGateway,
    UpstreamContractError,
    create_model_router,
)

PRICES = {"test-model": {"prompt": 1_000_000, "completion": 2_000_000}}
USAGE = {"prompt_tokens": 12, "completion_tokens": 4, "total_tokens": 16}


def completion_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": "chatcmpl-test",
        "model": "test-model",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "你好，天璇"},
                "finish_reason": "stop",
            }
        ],
        "usage": dict(USAGE),
    }
    payload.update(overrides)
    return payload


class Upstream:
    """记录调用次数并返回固定响应（或固定异常）的 MockTransport 处理器。"""

    def __init__(self, payload: dict[str, Any] | None = None, *, error: Exception | None = None) -> None:
        self.calls: list[httpx.Request] = []
        self.payload = payload if payload is not None else completion_payload()
        self.error = error

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        if self.error is not None:
            raise self.error
        return httpx.Response(200, json=self.payload)


def make_gateway(upstream: Upstream, *, prices: dict[str, dict[str, int]] | None = None) -> ModelGateway:
    return ModelGateway(
        ":memory:",
        transport=httpx.MockTransport(upstream),
        prices=PRICES if prices is None else prices,
    )


def make_client(gateway: ModelGateway) -> TestClient:
    app = FastAPI()
    app.include_router(create_model_router(gateway))
    return TestClient(app)


def headers(**overrides: str) -> dict[str, str]:
    values = {"X-Model-Key": "sk-live-secret", "X-Tenant": "ten-1", "X-Actor": "usr-1"}
    values.update(overrides)
    return values


def chat_body(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": "test-model",
        "messages": [{"role": "user", "content": "机密提示词"}],
        "base_url": "https://llm.example/v1",
    }
    body.update(overrides)
    return body


def test_chat_records_usage_and_returns_content() -> None:
    upstream = Upstream()
    gateway = make_gateway(upstream)
    gateway.set_budget("ten-1", 1_000_000)
    events: list[dict[str, Any]] = []

    result = gateway.chat(
        "ten-1",
        "usr-1",
        "test-model",
        [{"role": "user", "content": "机密提示词"}],
        api_key="sk-live-secret",
        base_url="https://llm.example/v1/",
        event_sink=events.append,
    )

    assert result["content"] == "你好，天璇"
    assert result["usage"] == USAGE
    assert result["cost_micros"] == 20  # 12 * 1M/1M + 4 * 2M/1M
    assert upstream.calls[0].url == httpx.URL("https://llm.example/v1/chat/completions")
    assert upstream.calls[0].headers["Authorization"] == "Bearer sk-live-secret"

    rows = gateway.usage_rows("ten-1")
    assert len(rows) == 1
    assert rows[0]["actor"] == "usr-1"
    assert rows[0]["model"] == "test-model"
    assert rows[0]["prompt_tokens"] == 12
    assert rows[0]["completion_tokens"] == 4
    assert rows[0]["total_tokens"] == 16
    assert rows[0]["cost_micros"] == 20

    budget = gateway.get_budget("ten-1")
    assert budget is not None
    assert budget.used_micros == 20
    assert budget.remaining_micros == 1_000_000 - 20

    assert len(events) == 1
    assert events[0]["type"] == "model.chat.completed"
    assert events[0]["tenant_id"] == "ten-1"
    assert events[0]["actor"] == "usr-1"
    assert events[0]["usage"] == USAGE
    assert "api_key" not in events[0]
    assert "messages" not in events[0]
    assert "sk-live-secret" not in repr(events)
    assert "机密提示词" not in repr(events)
    assert "sk-live-secret" not in repr(rows)


def test_default_price_table_charges_zero() -> None:
    upstream = Upstream()
    gateway = make_gateway(upstream, prices={})

    result = gateway.chat(
        "ten-1",
        "usr-1",
        "unpriced-model",
        [{"role": "user", "content": "hi"}],
        api_key="sk-live-secret",
        base_url="https://llm.example/v1",
    )

    assert result["cost_micros"] == 0
    assert gateway.usage_totals("ten-1")["cost_micros"] == 0


def test_missing_key_is_rejected_without_upstream_call() -> None:
    upstream = Upstream()
    gateway = make_gateway(upstream)

    with pytest.raises(MissingCredential):
        gateway.chat(
            "ten-1",
            "usr-1",
            "test-model",
            [{"role": "user", "content": "hi"}],
            api_key="   ",
            base_url="https://llm.example/v1",
        )

    assert upstream.calls == []
    assert gateway.usage_rows("ten-1") == []


def test_router_rejects_missing_key_header_without_upstream_call() -> None:
    upstream = Upstream()
    gateway = make_gateway(upstream)
    client = make_client(gateway)

    response = client.post("/api/v1/models/chat", json=chat_body(), headers={"X-Tenant": "ten-1", "X-Actor": "usr-1"})

    assert response.status_code == 400
    assert upstream.calls == []


def test_upstream_missing_usage_raises_and_records_nothing() -> None:
    payload = completion_payload()
    payload.pop("usage")
    upstream = Upstream(payload)
    gateway = make_gateway(upstream)
    gateway.set_budget("ten-1", 1_000)

    with pytest.raises(UpstreamContractError):
        gateway.chat(
            "ten-1",
            "usr-1",
            "test-model",
            [{"role": "user", "content": "hi"}],
            api_key="sk-live-secret",
            base_url="https://llm.example/v1",
        )

    assert gateway.usage_rows("ten-1") == []
    assert gateway.usage_totals("ten-1")["calls"] == 0
    budget = gateway.get_budget("ten-1")
    assert budget is not None
    assert budget.used_micros == 0


def test_upstream_contract_error_maps_to_502() -> None:
    payload = completion_payload()
    payload.pop("usage")
    upstream = Upstream(payload)
    client = make_client(make_gateway(upstream))

    response = client.post("/api/v1/models/chat", json=chat_body(), headers=headers())

    assert response.status_code == 502
    assert len(upstream.calls) == 1


def test_transport_error_maps_to_502() -> None:
    upstream = Upstream(error=httpx.ConnectError("upstream down"))
    gateway = make_gateway(upstream)
    client = make_client(gateway)

    response = client.post("/api/v1/models/chat", json=chat_body(), headers=headers())

    assert response.status_code == 502
    assert gateway.usage_rows("ten-1") == []


def test_budget_exceeded_returns_429_without_upstream_call() -> None:
    upstream = Upstream()
    gateway = make_gateway(upstream)
    gateway.set_budget("ten-1", 0)
    client = make_client(gateway)

    response = client.post("/api/v1/models/chat", json=chat_body(), headers=headers())

    assert response.status_code == 429
    assert upstream.calls == []
    assert gateway.usage_rows("ten-1") == []


def test_per_call_budget_exhausted_without_upstream_call() -> None:
    upstream = Upstream()
    gateway = make_gateway(upstream)

    with pytest.raises(BudgetExceeded):
        gateway.chat(
            "ten-1",
            "usr-1",
            "test-model",
            [{"role": "user", "content": "hi"}],
            api_key="sk-live-secret",
            base_url="https://llm.example/v1",
            budget_micros=0,
        )

    assert upstream.calls == []


def test_tenant_budget_exhausted_by_recorded_usage() -> None:
    upstream = Upstream()
    gateway = make_gateway(upstream)
    gateway.set_budget("ten-1", 20)
    gateway.chat(
        "ten-1",
        "usr-1",
        "test-model",
        [{"role": "user", "content": "hi"}],
        api_key="sk-live-secret",
        base_url="https://llm.example/v1",
    )
    assert len(upstream.calls) == 1

    with pytest.raises(BudgetExceeded):
        gateway.chat(
            "ten-1",
            "usr-1",
            "test-model",
            [{"role": "user", "content": "hi again"}],
            api_key="sk-live-secret",
            base_url="https://llm.example/v1",
        )

    assert len(upstream.calls) == 1
    assert len(gateway.usage_rows("ten-1")) == 1


def test_invalid_base_url_maps_to_400_without_upstream_call() -> None:
    upstream = Upstream()
    gateway = make_gateway(upstream)
    client = make_client(gateway)

    response = client.post(
        "/api/v1/models/chat",
        json=chat_body(base_url="file:///etc/passwd"),
        headers=headers(),
    )

    assert response.status_code == 400
    assert upstream.calls == []


def test_usage_endpoint_returns_rows_and_totals() -> None:
    upstream = Upstream()
    gateway = make_gateway(upstream)
    client = make_client(gateway)

    for _ in range(2):
        response = client.post("/api/v1/models/chat", json=chat_body(), headers=headers())
        assert response.status_code == 200
        assert response.json()["content"] == "你好，天璇"
        assert response.json()["usage"] == USAGE

    listing = client.get("/api/v1/models/usage", params={"tenant_id": "ten-1"})
    assert listing.status_code == 200
    data = listing.json()
    assert len(data["usage"]) == 2
    assert {row["tenant_id"] for row in data["usage"]} == {"ten-1"}
    assert {row["actor"] for row in data["usage"]} == {"usr-1"}
    assert data["totals"] == {
        "calls": 2,
        "prompt_tokens": 24,
        "completion_tokens": 8,
        "total_tokens": 32,
        "cost_micros": 40,
    }

    empty = client.get("/api/v1/models/usage", params={"tenant_id": "other"})
    assert empty.json() == {
        "usage": [],
        "totals": {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cost_micros": 0},
    }

    assert upstream.calls[0].headers["Authorization"] == "Bearer sk-live-secret"
