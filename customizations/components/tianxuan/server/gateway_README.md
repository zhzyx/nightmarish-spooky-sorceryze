# 天璇模型网关（BYOK + 计量 + 预算）

`gateway.py` 是模型调用的唯一边界：凭据只随当次请求进入上游，成功后落用量、按租户预算拦截超额调用。
不访问网络以外的存储，不内置任何厂商价格，也不把提示词或凭据写入数据库、日志或审计事件。

## 快速使用

```python
import httpx
from gateway import ModelGateway, create_model_router

gateway = ModelGateway(
    "tianxuan.db",  # 或 ":memory:"
    transport=None,  # 生产用默认 httpx.Client；测试注入 httpx.MockTransport
    prices={  # micros / 1M tokens；不传则所有模型成本按 0 计
        # 仅为说明单位而设的示例费率，生产请按实际合同配置
        "example-model": {"prompt": 100_000, "completion": 400_000},
        "*": {"prompt": 0, "completion": 0},  # 可选兜底
    },
)
gateway.set_budget("tenant-1", 5_000_000)  # 5,000,000 micros（货币单位的百万分之一）

result = gateway.chat(
    "tenant-1",
    "user-1",
    "example-model",
    [{"role": "user", "content": "你好"}],
    api_key="sk-...",  # 仅本次调用使用
    base_url="https://api.example.com/v1",
    budget_micros=None,  # 可选的本次调用预算余量
)
# {"id": ..., "model": ..., "content": ..., "usage": {...}, "cost_micros": ...}
```

FastAPI 接入：

```python
from fastapi import FastAPI

app = FastAPI()
app.include_router(create_model_router(gateway))
```

## BYOK 边界

- `api_key` 每次调用显式传入，只写入当次上游请求的 `Authorization: Bearer <key>`。
- 不持久化、不写日志、不进入 `event_sink` 的审计字典；`usage` 表没有凭据列。
- `event_sink(event)` 只收到计量元数据（`type`、`usage_id`、`tenant_id`、`actor`、`model`、
  `usage`、`cost_micros`、`at`），不含 API Key、消息正文或 `base_url`；默认不回调。
- 上游地址由调用方给出，仅接受绝对 `http(s)` URL；`base_url` 末尾 `/` 会被归一化后拼接
  `/chat/completions`。

## 计量与成本

成功响应写入 `usage(id, tenant_id, actor, model, prompt_tokens, completion_tokens,
total_tokens, cost_micros, at)`，按 `at` 倒序保留最近 100 条；`usage_totals()` 聚合全部记录。

- 上游 2xx 但缺少 `usage`（或 token 字段非法）时抛 `UpstreamContractError`，不写任何用量。
- 上游 4xx/5xx、网络错误、非 JSON 响应统一抛 `UpstreamError` 子类，不写用量。
- 成本 = `prompt_tokens * prompt 单价 + completion_tokens * completion 单价`，单价单位为
  micros / 1M tokens，向上取整；价目表未覆盖的模型（且无 `"*"` 兜底）成本为 0，不猜测价格。
- 价目表字段只允许 `prompt` / `completion`；未知字段在构造时直接报错，避免拼写错误静默按 0 计。

## 预算

`budgets(tenant_id, limit_micros, used_micros)` 由 `set_budget(tenant_id, limit_micros)` 创建或调整；
已有 `used_micros` 不会因调整限额而重置。

- `chat(..., budget_micros=N)`：本次调用的预算余量，`N <= 0` 视为已耗尽。
- 租户预算：`used_micros >= limit_micros` 视为已耗尽。
- 任一预算耗尽都在上游调用前抛 `BudgetExceeded`（HTTP 429），不会产生上游请求或用量记录。
- 只有成功响应才累加 `used_micros`；失败、契约错误、传输错误都不扣预算。

## HTTP 接口

| 方法与路径 | 说明 |
| --- | --- |
| `POST /api/v1/models/chat` | 请求体 `{model, messages, base_url, max_tokens?, budget_micros?}`；`X-Model-Key` 必填，`X-Tenant` 必填，`X-Actor` 缺省为 `unknown` |
| `GET /api/v1/models/usage?tenant_id=` | 返回 `{"usage": [...], "totals": {calls, prompt_tokens, completion_tokens, total_tokens, cost_micros}}` |

错误映射：`MissingCredential` / 参数校验 / 非法 JSON → 400；`BudgetExceeded` → 429；
`UpstreamContractError` / `UpstreamError` / 传输错误 → 502。

## 验证

```sh
D:\GongGong-work\tx-venv\Scripts\python.exe -m pytest customizations/components/tianxuan/server/test_gateway.py -q
D:\GongGong-work\tx-venv\Scripts\mypy.exe --ignore-missing-imports --scripts-are-modules \
  customizations/components/tianxuan/server/gateway.py customizations/components/tianxuan/server/test_gateway.py
```

测试全部使用 `httpx.MockTransport`，不访问网络，也不依赖真实凭据。
