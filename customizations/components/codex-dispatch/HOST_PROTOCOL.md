# 当前操作者原生工具桥

路径以仓库根为基准。一次真实需求／完成事件运行一次 `node customizations/components/codex-dispatch/session.mjs ABS_CONFIG ABS_RESULT`；没有事件不执行，不设定时任务。配置、请求、issued、原始工具回执、预留和日志保存在宿主私有 `data-collection/receipts/`，不发布凭据或原始本机路径。

配置绑定 `workspace`（实际 Git 工作副本根）、`python`、`repository`、已登录 `operator`、`authorityRef`、`bindings:[{number,requestId}]`、宿主实际 `catalog`、`capacity`、`defaultChatModel`、`event:{type,reference}` 和 `requests`。request 沿用 adapter README 的完整契约。模型目录由当前工具能力及实测提供；不能由子 Agent 的自评建立。`chatCreationAuthorized` 只有实际用户已要求建聊才为 true，`threadTarget` 必须来自实际宿主发现；仅 `explicitChatModels` 内用户明确指定的型号可覆盖默认模型。

当宿主要求 Agent 继承当前模型时，在会话配置中把 `inheritedAgentModel` 设为当前宿主核实的继承型号，并在 `catalog` 中登记它的实际能力及 agent 目标。司南仅在该型号满足请求时派发，原生调用省略 model 参数。宿主无法核实继承型号或模型能力时保留待派发。仅在宿主允许显式选模时使用原有精确型号模式（省略此配置项）。

会话输出 `nativeRoot` 后，真实 Codex 宿主处理文件事件：

1. 在 `NativeToolBridge.take(id)` 排他落盘 issued 后，按 request.tool 执行一次实际 `spawn_agent` 或 `create_thread`，参数只取 request.args；context 只用于工单与预留关联，不传给原生工具。请求必须仍匹配 task、授权、tool 及 argsDigest。
2. 工具返回后，以真实工具调用引用调用 `respond(id, parsedToolResult, toolEvidenceRef)`。没有回执时保留 issued 和预留，先查询原工作者，不重新 take、删除或重发请求。响应文件只是宿主回执载体，不是身份、权限或真实调用的自证；本接口未声称提供对任意编辑器的操作系统隔离。
3. queued chat 保持 setupPending，不当作 threadId 或实际运行。实际 setup 完成事件设置 `action:setup`、`reservationKey` 和最终 `workerReceipt`，event 类型为 ticket.changed。`verify_setup` 请求要求宿主通过真实 setup 回调核对原 clientThreadId 与最终 threadId，返回 `{clientThreadId,threadId,reference:event.reference}` 后才调用来源 ack；不能从无关聊天或文字猜测映射。
4. 收到真实工作者完成／失败事件后，在同一配置设置 `action:reconcile`、`reservationKey`、完整原 `workerReceipt`，event 绑定实际终态引用。桥的 `verify_worker` 是宿主核验请求，**不是新增模型工具**：Agent 用实际原生状态／完成回调核对原 workerId，chat 用实际 thread 状态与 setup 映射核对。宿主仅在核对后回传 `{workerId,state:completed|failed|interrupted,reference:event.reference}`，附真实工具／完成事件引用；模型的完成文字不够。驱动先 reconcile 再在同一事件中对剩余 requests 补位。
5. 仅确定未产生任何 launch-intent/native 请求时，真实失败事件可用 `action:release-unstarted`；与 beforeLaunch 共用来源锁，存在 intent、worker 或未知回执时拒绝释放。

`openSession(config, ports)` 也可由原生宿主直接注入 `verifyWorker(receipt,event,assignment)`、`acceptedDependency(ticket)` 和既有共享 `report(record)`；无依赖验收端口时，有依赖任务保持阻塞。验收回执必须来自原来源的实际证据，Issue 关闭本身不等于依赖验收。持久来源认领和 native receipt 是执行事实，业务验收、远端合入及工单关闭另行核对。

`OperatorRuntime` 的唯一认领根从真实 Git common directory 的父目录解析，所有受绑定操作者必须共用该安装。ticket 锁内回读真实来源修订并排他创建 claim，启动前再回读并写 launch-intent。原子性限定本安装中遵守同一入口的操作者，**不提供 GitHub 任意远程编辑的全局 CAS**；不同安装必须先选择同一认领服务，不能各建一个本地根后声称互斥。崩溃锁不按时间抢占；失联工作者不释放容量。回退时停用新入口并保留认领与回执供人工核验。

本入口使用当前已准入框架、真实 GitHub 登录及同仓库工单。候选定义准入只批准该定义，不授权未来任务。CLI 代表任务使用独立上下文和精确请求型号，实际路由未回传时 observedModel 仍为 null。
