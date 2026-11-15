# DeepSeek Harness 派发接入候选

路径相对仓库根。本目录把 DeepSeek Harness（DSH）登记为共工派发宿主，复用
[共享派发契约](../../platforms/process-management/yuanheng-local/sinan/dispatch.mjs)、
谛听文件回执和既有 Issue 门禁，不新增第二套协调、准入或数据通道。

状态：`candidate_pending_host_binding_and_admission`，`runtime_connected: false`。
目录存在不等于已接通；候选、测试与本地回执都不产生生产准入或工具权限。

## 职责边界

- `adapter.mjs` 只做宿主绑定：校验调用方提供的权威 source 回调与原生 subagent 回调，
  在产生副作用前持久化预留，再把 plan 分配映射到原生工具。
- 身份、权限、模型选择、工具许可、真实 Issue 和用户确认仍由当前宿主控制。
- 不执行模型、不创建定时扫描、不代理 GitHub 写操作、不读取或写入凭据。
- 模型、工具与业务验收分离记录；`agent_execution_enabled:false` 不等于宿主被禁用。

## 原生工具映射

| DSH 原生能力 | 用途 | 约束 |
| --- | --- | --- |
| `subagent` / `subagent_fork`（`native.spawnAgent`） | 启动一个工单子 Agent | 交接只含目标、授权、验收、资源与引用 |
| `send_message` | 运行中继续、纠偏或补位 | 仍以原工单和授权范围为限 |
| `interrupt_agent` | 停止当前步骤 | 先撤销 live 请求，再排队终态 |
| `list_subagent_models` / `list_agents` | 宿主核实可用能力与在途状态 | 目录由宿主提供，不发明型号 |
| `workflow` | 多工单 fan-out 编排 | 不替代独立审查与验收 |

## 绑定与使用

```js
import {HarnessDispatchHost, harnessHostDescriptor} from './adapter.mjs';

const host = new HarnessDispatchHost({
  stateRoot: absolutePrivateStateRoot, // 例如 data-collection/receipts/harness-dispatch
  source,                              // inspect/revalidate/startSource/ack/report/verifyTerminal
  native,                              // host 实际提供的 subagent 回调
  policy: {operator: hostSessionId},
});
const batch = await host.run({type: 'request.created', reference: actualEventRef}, requests);
```

- `stateRoot` 必须是宿主提供的绝对私有路径；不得把本地路径、回执或凭据提交进仓库。
- 预留先于任何启动副作用；回执未知时保留占用，用真实终态 `reconcile` 释放。
- 同一来源修订只派发一次；跨会话共用同一 `stateRoot`。
- 没有原生 chat 线程入口，`chat` 目标会被延后，不回退为未受治理的对话。

## 验证

```sh
node --test customizations/components/harness-dispatch/adapter.test.mjs
```

测试使用模拟 source 与模拟原生回调，覆盖参数校验、预留幂等、原生回执映射、
终态核对与释放；不代表真实 DSH 生产派发回执。

## 回退

停用适配器调用，保留 `reservations`、`records`、`released` 与来源证据；在途任务
按原回执对账，不删除历史预留后重放。恢复前先取得权威终态读回。

## 相关

- [宿主协议](HOST_PROTOCOL.md)
- [Codex 派发候选](../codex-dispatch/README.md)
- [仓库派发入口](../repository-dispatch/README.md)
- [接入子模块边界](../../module-boundaries.md)
