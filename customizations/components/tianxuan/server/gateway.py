"""天璇 BYOK 模型网关：用量计量、预算约束与审计事件。

职责边界：

- BYOK：每次调用由调用方传入 ``api_key``，只用于当次上游请求的
  ``Authorization`` 头；本模块不落库、不写日志、不把凭据放进审计事件。
- 计量：上游成功后写入 ``usage`` 表；存在预算记录时同步累加
  ``budgets.used_micros``。
- 预算：上游调用前检查本次预算与租户预算，已耗尽则直接拒绝。
- 成本：只按调用方提供的价目表计算（micros / 1M tokens），价目表未覆盖的
  模型成本为 0，不推测价格。
"""

from __future__ import annotations

import os
import sqlite3
import threading
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal
from urllib.parse import urlparse

import httpx
from access_control import COOKIE
from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, ValidationError

SCHEMA = """
CREATE TABLE IF NOT EXISTS usage (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  actor TEXT NOT NULL,
  model TEXT NOT NULL,
  prompt_tokens INTEGER NOT NULL,
  completion_tokens INTEGER NOT NULL,
  total_tokens INTEGER NOT NULL,
  cost_micros INTEGER NOT NULL,
  at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS budgets (
  tenant_id TEXT PRIMARY KEY,
  limit_micros INTEGER NOT NULL,
  used_micros INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_usage_tenant ON usage(tenant_id, at);
"""

MICROS_PER_MILLION = 1_000_000

# model -> {"prompt": micros/1M tokens, "completion": micros/1M tokens}
PriceTable = Mapping[str, Mapping[str, int]]
EventSink = Callable[[dict[str, Any]], None]


class GatewayError(Exception):
    """模型网关的基类错误。"""


class MissingCredential(GatewayError):
    """本次调用缺少可用的 BYOK 凭据。"""


class InvalidRequest(GatewayError, ValueError):
    """调用参数无法被网关安全执行。"""


class BudgetExceeded(GatewayError):
    """本次调用预算或租户预算已耗尽。"""


class UpstreamError(GatewayError):
    """上游模型服务请求失败。"""


class UpstreamContractError(UpstreamError):
    """上游响应缺少必需字段，或不是可解析的 JSON。"""


@dataclass(frozen=True)
class Budget:
    """租户预算快照，金额单位为 micros。"""

    tenant_id: str
    limit_micros: int
    used_micros: int

    @property
    def remaining_micros(self) -> int:
        return self.limit_micros - self.used_micros


class ChatRequestBody(BaseModel):
    """``POST /api/v1/models/chat`` 的请求体。"""

    model: str = Field(min_length=1)
    messages: list[dict[str, Any]] = Field(min_length=1)
    base_url: str = Field(min_length=1)
    max_tokens: int | None = Field(default=None, gt=0)
    budget_micros: int | None = Field(default=None, ge=0)


class WorkspaceMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=16000)


class WorkspaceChat(BaseModel):
    messages: list[WorkspaceMessage] = Field(min_length=1, max_length=25)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _normalize_prices(prices: PriceTable) -> dict[str, dict[str, int]]:
    """校验价目表并补齐缺省费率；未知字段视为配置错误而不是静默按 0 计。"""

    normalized: dict[str, dict[str, int]] = {}
    for model, rates in prices.items():
        unknown = set(rates) - {"prompt", "completion"}
        if unknown:
            raise ValueError(f"unknown price fields for model {model!r}: {sorted(unknown)}")
        prompt = rates.get("prompt", 0)
        completion = rates.get("completion", 0)
        if prompt < 0 or completion < 0:
            raise ValueError(f"price for model {model!r} must be non-negative micros per 1M tokens")
        normalized[model] = {"prompt": prompt, "completion": completion}
    return normalized


def _line_cost(tokens: int, micros_per_million: int) -> int:
    """按 1M tokens 单价折算 micros，向上取整以不低估成本。"""

    return (tokens * micros_per_million + MICROS_PER_MILLION - 1) // MICROS_PER_MILLION


def _token_count(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise UpstreamContractError(f"upstream usage field {field!r} must be a non-negative integer")
    return value


class ModelGateway:
    """BYOK 模型网关：上游调用、计量、预算与审计。

    ``prices`` 是调用方提供的价目表（micros / 1M tokens）。未覆盖的模型成本为
    0；网关不会内置或猜测任何厂商价格。
    """

    def __init__(
        self,
        db_path: str = ":memory:",
        *,
        transport: httpx.BaseTransport | None = None,
        prices: PriceTable | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.db = sqlite3.connect(db_path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        self.db.commit()
        self._lock = threading.Lock()
        self._prices = _normalize_prices(prices or {})
        self._client = httpx.Client(transport=transport, timeout=timeout)

    def close(self) -> None:
        self._client.close()
        with self._lock:
            self.db.close()

    # ---------- 计量与预算 ----------

    def set_budget(self, tenant_id: str, limit_micros: int) -> Budget:
        """设置或调整租户预算；已有 ``used_micros`` 保持不变。"""

        if not tenant_id.strip():
            raise ValueError("tenant_id is required")
        if limit_micros < 0:
            raise ValueError("limit_micros must be non-negative")
        with self._lock:
            self.db.execute(
                "INSERT INTO budgets (tenant_id, limit_micros, used_micros) VALUES (?, ?, 0) "
                "ON CONFLICT(tenant_id) DO UPDATE SET limit_micros = excluded.limit_micros",
                (tenant_id, limit_micros),
            )
            self.db.commit()
        budget = self.get_budget(tenant_id)
        if budget is None:  # pragma: no cover - 刚写入的记录必然存在
            raise RuntimeError("budget row was not persisted")
        return budget

    def get_budget(self, tenant_id: str) -> Budget | None:
        with self._lock:
            row = self.db.execute(
                "SELECT tenant_id, limit_micros, used_micros FROM budgets WHERE tenant_id = ?",
                (tenant_id,),
            ).fetchone()
        if row is None:
            return None
        return Budget(
            tenant_id=str(row["tenant_id"]),
            limit_micros=int(row["limit_micros"]),
            used_micros=int(row["used_micros"]),
        )

    def usage_rows(self, tenant_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        with self._lock:
            rows = self.db.execute(
                "SELECT id, tenant_id, actor, model, prompt_tokens, completion_tokens, "
                "total_tokens, cost_micros, at FROM usage WHERE tenant_id = ? "
                "ORDER BY at DESC, id DESC LIMIT ?",
                (tenant_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def usage_totals(self, tenant_id: str) -> dict[str, int]:
        with self._lock:
            row = self.db.execute(
                "SELECT COUNT(*) AS calls, COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens, "
                "COALESCE(SUM(completion_tokens), 0) AS completion_tokens, "
                "COALESCE(SUM(total_tokens), 0) AS total_tokens, "
                "COALESCE(SUM(cost_micros), 0) AS cost_micros FROM usage WHERE tenant_id = ?",
                (tenant_id,),
            ).fetchone()
        if row is None:  # pragma: no cover - 聚合查询总会返回一行
            return {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cost_micros": 0}
        return {
            "calls": int(row["calls"]),
            "prompt_tokens": int(row["prompt_tokens"]),
            "completion_tokens": int(row["completion_tokens"]),
            "total_tokens": int(row["total_tokens"]),
            "cost_micros": int(row["cost_micros"]),
        }

    def _check_budget(self, tenant_id: str, budget_micros: int | None) -> None:
        if budget_micros is not None and budget_micros <= 0:
            raise BudgetExceeded(f"call budget exhausted for tenant {tenant_id}")
        budget = self.get_budget(tenant_id)
        if budget is not None and budget.used_micros >= budget.limit_micros:
            raise BudgetExceeded(f"tenant budget exhausted for tenant {tenant_id}")

    def _record_usage(
        self,
        tenant_id: str,
        actor: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        cost_micros: int,
    ) -> str:
        usage_id = _new_id("use")
        at = _now()
        with self._lock:
            try:
                self.db.execute(
                    "INSERT INTO usage (id, tenant_id, actor, model, prompt_tokens, completion_tokens, "
                    "total_tokens, cost_micros, at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        usage_id,
                        tenant_id,
                        actor,
                        model,
                        prompt_tokens,
                        completion_tokens,
                        total_tokens,
                        cost_micros,
                        at,
                    ),
                )
                self.db.execute(
                    "UPDATE budgets SET used_micros = used_micros + ? WHERE tenant_id = ?",
                    (cost_micros, tenant_id),
                )
                self.db.commit()
            except sqlite3.Error:
                self.db.rollback()
                raise
        return usage_id

    # ---------- 上游调用 ----------

    def chat(
        self,
        tenant_id: str,
        actor: str,
        model: str,
        messages: list[dict[str, Any]],
        *,
        api_key: str,
        base_url: str,
        max_tokens: int | None = None,
        budget_micros: int | None = None,
        event_sink: EventSink | None = None,
    ) -> dict[str, Any]:
        """调用上游 ``POST {base_url}/chat/completions`` 并返回归一化结果。

        成功响应才会写入用量；上游缺少 ``usage`` 或内容时抛
        :class:`UpstreamContractError` 且不留用量记录。
        """

        if not tenant_id.strip():
            raise InvalidRequest("tenant_id is required")
        if not actor.strip():
            raise InvalidRequest("actor is required")
        if not model.strip():
            raise InvalidRequest("model is required")
        if not messages:
            raise InvalidRequest("messages must not be empty")
        if max_tokens is not None and max_tokens <= 0:
            raise InvalidRequest("max_tokens must be positive")
        if budget_micros is not None and budget_micros < 0:
            raise InvalidRequest("budget_micros must be non-negative")
        if not api_key or not api_key.strip():
            raise MissingCredential("api_key is required for BYOK calls")

        base = base_url.rstrip("/")
        parsed = urlparse(base)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise InvalidRequest("base_url must be an absolute http(s) URL")

        self._check_budget(tenant_id, budget_micros)

        body: dict[str, Any] = {"model": model, "messages": messages}
        if max_tokens is not None:
            body["max_tokens"] = max_tokens

        try:
            response = self._client.post(
                f"{base}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json=body,
            )
        except httpx.HTTPError as exc:
            raise UpstreamError("upstream model request failed") from exc

        if response.status_code >= 400:
            raise UpstreamError(f"upstream model returned HTTP {response.status_code}")

        try:
            payload = response.json()
        except ValueError as exc:
            raise UpstreamContractError("upstream response is not valid JSON") from exc
        if not isinstance(payload, dict):
            raise UpstreamContractError("upstream response must be a JSON object")

        usage = payload.get("usage")
        if not isinstance(usage, dict):
            raise UpstreamContractError("upstream response omitted usage")
        prompt_tokens = _token_count(usage.get("prompt_tokens"), "prompt_tokens")
        completion_tokens = _token_count(usage.get("completion_tokens"), "completion_tokens")
        total_tokens = usage.get("total_tokens")
        if total_tokens is None:
            total_tokens = prompt_tokens + completion_tokens
        else:
            total_tokens = _token_count(total_tokens, "total_tokens")

        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise UpstreamContractError("upstream response omitted choices")
        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise UpstreamContractError("upstream response choice must be a JSON object")
        message = first_choice.get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            raise UpstreamContractError("upstream response omitted message content")
        content = message["content"]

        response_id = payload.get("id")
        if not isinstance(response_id, str) or not response_id:
            response_id = _new_id("chatcmpl")
        response_model = payload.get("model")
        if not isinstance(response_model, str) or not response_model:
            response_model = model

        rates = self._prices.get(model) or self._prices.get("*") or {"prompt": 0, "completion": 0}
        cost_micros = _line_cost(prompt_tokens, rates["prompt"]) + _line_cost(completion_tokens, rates["completion"])
        usage_id = self._record_usage(
            tenant_id, actor, model, prompt_tokens, completion_tokens, total_tokens, cost_micros
        )

        normalized_usage = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        }
        if event_sink is not None:
            event_sink({
                "type": "model.chat.completed",
                "usage_id": usage_id,
                "tenant_id": tenant_id,
                "actor": actor,
                "model": model,
                "usage": dict(normalized_usage),
                "cost_micros": cost_micros,
                "at": _now(),
            })

        return {
            "id": response_id,
            "model": response_model,
            "content": content,
            "usage": normalized_usage,
            "cost_micros": cost_micros,
        }


# ---------- FastAPI 路由 ----------

_HEADER_TENANT = "X-Tenant"
_HEADER_ACTOR = "X-Actor"
_HEADER_KEY = "X-Model-Key"


def _header(request: Request, name: str) -> str:
    return (request.headers.get(name) or "").strip()


def create_model_router(gateway: ModelGateway) -> APIRouter:
    """创建模型网关路由；调用方自行 ``app.include_router(...)``。"""

    router = APIRouter(prefix="/api/v1", tags=["tianxuan-models"])

    def identity(request: Request) -> tuple[str, str]:
        store = request.app.state.store
        actor = getattr(request.state, "verified_actor", None)
        if not actor:
            scheme, _, token = request.headers.get("authorization", "").partition(" ")
            actor = store.user_for_token(token.strip()) if scheme.lower() == "bearer" else None
        if not actor:
            raise HTTPException(401, "valid authenticated identity required")
        context = store.actor_context(actor)
        if request.method != "GET" and context["role"] == "viewer":
            raise HTTPException(403, "read-only account")
        tenant = context["tenant"]
        if _header(request, _HEADER_TENANT) not in ("", tenant) or _header(request, _HEADER_ACTOR) not in ("", actor):
            raise HTTPException(403, "identity mismatch")
        return tenant, str(actor)

    @router.post("/models/chat")
    async def chat(request: Request) -> dict[str, Any]:
        tenant_id, actor = await run_in_threadpool(identity, request)
        api_key = _header(request, _HEADER_KEY)
        if not api_key:
            raise HTTPException(status_code=400, detail=f"{_HEADER_KEY} header is required")

        try:
            payload = await request.json()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="request body must be valid JSON") from exc
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="request body must be a JSON object")
        try:
            body = ChatRequestBody.model_validate(payload)
        except ValidationError as exc:
            raise HTTPException(status_code=400, detail="invalid request body") from exc

        try:
            return await run_in_threadpool(  # type: ignore[no-any-return]
                lambda: gateway.chat(
                    tenant_id,
                    actor,
                    body.model,
                    body.messages,
                    api_key=api_key,
                    base_url=body.base_url,
                    max_tokens=body.max_tokens,
                    budget_micros=body.budget_micros,
                )
            )
        except (MissingCredential, InvalidRequest) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except BudgetExceeded as exc:
            raise HTTPException(status_code=429, detail=str(exc)) from exc
        except UpstreamError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail="upstream model request failed") from exc

    @router.post("/workspace/chat")
    async def workspace_chat(body: WorkspaceChat, request: Request) -> dict[str, str]:
        if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
            raise HTTPException(415, "application/json required")
        store = request.app.state.store
        actor = getattr(request.state, "verified_actor", None)
        if not actor:
            scheme, _, token = request.headers.get("authorization", "").partition(" ")
            key = token.strip() if scheme.lower() == "bearer" else request.cookies.get(COOKIE, "")
            actor = await run_in_threadpool(store.user_for_access_key, key) if key else None
        if not actor:
            raise HTTPException(401, "personal access key required")
        context = await run_in_threadpool(store.actor_context, actor)
        if context["role"] == "viewer":
            raise HTTPException(403, "read-only account")

        model = os.environ.get("TIANXUAN_CHAT_MODEL")
        base_url = os.environ.get("TIANXUAN_CHAT_BASE_URL")
        model_key = os.environ.get("TIANXUAN_CHAT_MODEL_KEY")
        if not model or not base_url or not model_key:
            raise HTTPException(503, "workspace chat is not configured")

        messages = body.messages
        if messages[-1].role != "user" or any(
            message.role != ("assistant" if index % 2 else "user")
            or not message.content.strip()
            or (message.role == "user" and len(message.content) > 8000)
            for index, message in enumerate(messages)
        ):
            raise HTTPException(400, "messages must alternate and end with a user message")

        try:
            result = await run_in_threadpool(
                gateway.chat,
                context["tenant"],
                actor,
                model,
                [message.model_dump() for message in messages],
                api_key=model_key,
                base_url=base_url,
                max_tokens=2048,
            )
        except BudgetExceeded as exc:
            raise HTTPException(429, "workspace model budget exhausted") from exc
        except (MissingCredential, InvalidRequest, UpstreamError, httpx.HTTPError) as exc:
            raise HTTPException(502, "workspace model did not return a reply") from exc
        return {"model": result["model"], "content": result["content"]}

    @router.get("/models/usage")
    def usage(request: Request) -> dict[str, Any]:
        tenant_id, _ = identity(request)
        requested = request.query_params.get("tenant_id")
        if requested is not None and requested != tenant_id:
            raise HTTPException(403, "tenant mismatch")
        return {"usage": gateway.usage_rows(tenant_id), "totals": gateway.usage_totals(tenant_id)}

    return router
