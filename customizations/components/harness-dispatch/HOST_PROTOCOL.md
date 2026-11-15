# DeepSeek Harness 宿主协议（候选）

协议版本 1，与 `customizations/components/godot-host/HOST_PROTOCOL.md` 共用宿主描述、
共享谛听与既有 Issue 门禁。本文件只规定 DSH 如何绑定为派发宿主，不改变核心协调语义。

## 宿主描述

```json
{
  "protocol_version": 1,
  "host": {"id": "deepseek-harness", "kind": "cli"},
  "agent_id": "sinan",
  "request_id": "actual-user-request",
  "outcome": "用户的真实任务",
  "authority_ref": "host-authenticated-user-request"
}
```

- `host.id` 固定为本集成标识，避免把其他宿主回执误记为 DSH。
- `agent_id` 必须是当前 manifest 唯一注册且持有匹配批准的 Agent。
- 宿主描述只用于绑定和归属，不认证身份，也不赋予权限。

## 调用方必须提供的回调

| 回调 | 责任 |
| --- | --- |
| `source.inspect(event)` | 返回最新 board、模型目录、容量与全部在途任务 |
| `source.revalidate(assignment)` | 核对当前准入、来源版本、权限、资源与预算 |
| `source.startSource(assignment)` | 通过原来源 CLI 启动，使用版本条件串行写入 |
| `source.ack(assignment, receipt)` | 回写原来源启动回执 |
| `source.report(value)` | 调用共享谛听并保留真实送达状态 |
| `source.verifyTerminal(assignment, event, receipt)` | 确认预留、工作者、来源修订与真实终态 |
| `native.spawnAgent(args, meta)` | 用宿主实际提供的 subagent 能力启动子 Agent |

缺任一权威回调时构造失败，不回退到本地自评或未受治理的模型调用。

## 生命周期

1. 真实业务事件到达，宿主提供 `event.reference`。
2. `inspect` → `revalidate` → `reserve`（先于副作用）→ `startSource` → `launch` → `ack` → `record`。
3. 终态 `execution.finished` / `execution.failed` 到达后调用 `reconcile`；
   `verifyTerminal` 通过才写入 `released`。
4. 回执未知时保留预留与占用，禁止重派；用原回执只读核对。

同一来源快照的 key 仅派发一次，包括已终止记录。明确重试必须由权威来源形成新修订。

## 状态目录

`stateRoot` 是宿主提供的绝对私有路径，包含：

- `reservations/`：先于任何启动副作用写入的意图与待核实终态；
- `records/`：实际启动回执、错误与上报输入；
- `released/`：仅权威终态回读后写入；
- `coordination.lock`：跨会话协调锁，不按时间抢占。

不得把本地路径、回执或凭据纳入发布。损坏或部分文件读取失败时拒绝派发，不按空状态恢复。

## 约束

- 开发前必须有真实 Issue；未建单不能先开发再补单。每次调用仍重新核对仓库、租户、
  唯一类别、状态、需求 ID 与 `workspace:gonggong`。
- 工具许可取自宿主实际开关；本协议文本不增加本地工具权限。
- 每次模型请求按共享规范调用 `framework/tools/agent-context.mjs` 并保留谛听回执；
  失败或离线时拒绝发送，没有跳过开关。
- Godot 相关变更遵循静默验证：只使用 `--headless`、隔离工程与几何断言，不驱动桌面。
- 不新增定时扫描；协调只由真实事件触发。取消、暂停、预算和用户保留决定继续有效。
- 事件进入 `gonggong-diting-data/` 后，随对应真实需求审查、暂存与提交；
  Git 提交不等于谛听已消费。

## 失败与未知

- 启动回执未知：保留预留，回读原来源后对账，不重复启动。
- 模型结果未知：不自动重复付费调用；发布结果未知只查询原稳定 ID。
- 相同失败无新证据时转排障，未知副作用先回读，不盲目重试。
- 缺环境、缺准入与从未接入分别报告，不把配置或本地测试称为已接通。
