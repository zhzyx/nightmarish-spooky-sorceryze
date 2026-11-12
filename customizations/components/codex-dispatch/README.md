# Codex 派发接入候选

路径相对仓库根。`adapter.mjs` 调用本地过程适配器 `customizations/platforms/process-management/yuanheng-local/sinan/dispatch.mjs`。当前操作者通过 `operator.mjs` 和 [宿主协议](HOST_PROTOCOL.md) 绑定真实 GitHub 来源、共享认领、原生工具请求／回执、终态对账与事件补位。普通 Node 不直接访问 Codex 内部工具，由真实当前宿主处理 `native-bridge.mjs` 请求；配置、源码准入和代表任务回执分别核对，不创建定时扫描。

```js
const host = new CodexDispatchHost({stateRoot, source, native, policy});
const result = await host.run({type: 'request.created', reference: actualEventRef}, requests);
// 收到真实完成或失败回执时，先核验并释放，再在同一事件中补位。
await host.reconcile(actualTerminalEvent, reservationKey, actualWorkerReceipt);
await host.run(actualTerminalEvent, remainingRequests);
```

`stateRoot` 是宿主提供的绝对私有路径，例如以仓库根为解析基准的 `data-collection/receipts/codex-dispatch`；不得把本地路径、回执或凭据纳入发布。`reservations` 持久化先于任何启动副作用；`records` 保留实际启动回执、错误及上报输入；`released` 仅在权威终态回读后写入。单条写入采用排他创建与 fsync。损坏/部分文件读取失败时拒绝派发，不按空状态恢复。跨聊天必须共用相同 stateRoot。协调锁不按时间抢占，崩溃后的锁需实际确认旧工作者终止后人工恢复。

source 必须实现 inspect、revalidate、startSource、ack、report、verifyTerminal：inspect 返回最新 board 和宿主模型目录/容量/所有在途任务；revalidate 校验当前准入、来源版本、权限、资源与预算；startSource/ack 通过原来源 CLI 执行并使用版本条件串行写入；report 调既有共享谛听并保留真实送达状态；verifyTerminal 必须确认 reservation、worker、来源修订和实际终态。单纯完成文字或 event.type 不足以释放。所有回调均不可用本地自评替代授权。

native 回调接受原生工具参数，返回工具的解析后对象（或 structuredContent）。Agent 调用使用 `fork_turns: none` 和精确 model，交接只含目标、权限、验收、资源和引用。chat 使用 policy.threadTarget（由实际宿主发现的项目/目标配置）和明确的 chatCreationAuthorized；默认使用 policy.defaultChatModel，不传 model 覆盖。只有 policy.explicitChatModels[ticket] 保存用户明确指定的具体型号时，才传 model。默认模型不满足能力时延后，不暗中换型。建聊的目标、工作副本选择等仍受原生工具约束。

当宿主要求 Agent 继承模型时，设置 `policy.inheritedAgentModel`（会话配置同名字段）为宿主核实的当前型号。派发只考虑该型号的真实能力，保留任务的精确型号要求；不匹配的任务延后。原生 spawn_agent 省略 model，此时回执 `model` 表示规划型号，`requestedModel` 为 null，未回传型号时 `modelEvidence` 为 `host_inheritance_not_observed`。省略此选项沿用原显式选模协议。

回执的 `observedModel` 仅在宿主实际回传型号时填写。queued clientThreadId 以 setupPending 保存，不能作为已就绪 threadId 交给其他工具；由宿主 setup 完成事件继续对账。实际启动的线程/Agent 标识立即落盘，ack 或上报失败保留占用，禁止重派。完成不自动关闭父工单或替代验收。

同一来源快照的 key 仅派发一次，包括已终止记录；明确重试必须由权威来源形成新修订，不能删除历史预留后重放。变更来源版本也不能重复启动仍在途的同一工单。失联实例保留容量直到终态核验。回退时停用适配器、处理在途对账并保留证据。

验证：`node --test customizations/components/codex-dispatch/adapter.test.mjs`。测试使用明确的模拟原生回调，覆盖并发、模型参数、跨进程状态重载、重复派发、回执失联、完成补位、锁和 chat 权限；不能作为真实 Codex 生产派发回执。

模型配置参考 [OpenAI 官方子 Agent 文档](https://learn.chatgpt.com/docs/agent-configuration/subagents)。具体可用工具、型号覆盖及建聊约束以当前宿主实际暴露的接口为准，本适配器不固定供应商型号。

GitHub 连接由已安装的 `issue-workorders/github_runtime.mjs` 经当前配置 `python` 调用同目录 Python 解析／传输实现。优先级为显式 `config.gh`、显式环境 `GONGGONG_GH`，然后沿共享运行时的安装目录、PATH、固定位置规则；显式空值、null、缺失或不可执行路径拒绝，不回退。裸命令只在传入 PATH 按原名查找。一次会话固定绝对 CLI，并用于权限／工单回读、intake 和上报的子进程环境；新会话重新读取配置，父进程环境与账号不变。GitHub 请求最多等待 120 秒，桥接有额外 5 秒退出期限；错误不回显 CLI stderr，未知写入结果必须先回读远端再重试。工具依赖从安装文件位置加载，目标工作区只提供数据；打包或回退须同时保留 JS 桥接、Python 桥接与 `github_runtime.py`。
