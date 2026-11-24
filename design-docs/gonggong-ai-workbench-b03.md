# B03　天枢与司南的本机执行契约

对应 [B03 #1874](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1874)，源码基线为 [b60ae96914cd25b0856f4be09b6b0b6a710cc717](https://github.com/zhzyx/nightmarish-spooky-sorceryze/commit/b60ae96914cd25b0856f4be09b6b0b6a710cc717)。以下源码链接相对于本文所在的 `design-docs/`。本卡追踪天枢中一张已绑定 GitHub Issue 的操作。司南的需求判断回执允许进入开工步骤，聊天执行回执归属本轮请求，工单交付另有独立验收。[方案一 B03](gonggong-ai-workbench-plan1.md#b03)

## 从普通聊天入口走一张工单

**复现入口。** 打开定制 Godot 编辑器的“天枢”停靠面板，使用已核实访问权限的仓库、账号和已配置的 Codex 后端，进入一张天枢直接创建的工单。在画布聊天中输入该单已授权的具体操作并发送。已有账号实测可以按 Windows 候选 `b0368b91a0931d3587577e62794df024e8ca1615cb662f11bf08be4c20185d81` 的 #210 核对：画布发出操作、该单出现命令批准、批准后在该单候选中回读到 `scout.json`，本轮为 `completed`。该记录使用隔离 Issue 和真实 Codex 订阅，未计入本次版本的双平台实测。[停靠面板注册](../editor/docks/daqian_dock.cpp#L295) · [#758 的 live_canvas、live_effects](../data-collection/tianshu-production-parallel-758.json)

| 步骤 | 生产者 → 接收者 | 核对字段与动作 |
| --- | --- | --- |
| 1. 画布发送 | 天枢 `_send_canvas_message` → 只读意图判断 → 绑定工单 | 固定提交时的项目、账号、工单 URL/编号/request、修订和所选模型，回读权限。普通询问的 `answer` 回到聊天；`execute` 重新核对原工单，再交执行入口；需要新工单的 `requirement` 打开需求确认表。[画布提交与回调](../editor/docks/daqian/workspace.gd#L694) |
| 2. 尚在计划的直接工单 | 天枢司南卡 → Python `issue-route` → 当前准入的司南 | “确认需求并建单”通过 `issue-direct` 建立或对账 `planned` 绑定。发送操作若遇到待判断的工单，会引导完成需求判断。路由根据 `issue_number, request_id, expected_user, expected_revision` 回读原文。司南在禁用生产工具的模型轮次判定是否就绪，要求分析时才交偃师。结果带有 `route, reason, scope, acceptance, questions, ready`。UI 只接收与原单、原修订相符的结果。[按钮](../editor/docks/daqian/workspace.gd#L3763) · [宿主协议](../customizations/components/godot-host/HOST_PROTOCOL.md#天枢已建工单的推进判断) · [司南判断](../customizations/components/godot-host/issue_route.py#L352) · [回执校验](../editor/docks/daqian/workflow_controller.gd#L289) |
| 3. 开工并投递 | 用户选择“开始推进” → `issue-start` → 天枢推进对话 | 对同一账号、原始需求和就绪判断开工，收到有效状态才保存开工回执。来源或判断改变时先刷新。后续 `chat_context` 复核权威工单及本地开工记录。已开工的同一单可直接续聊。直接工单日志位于 Git common directory 的父目录下 `data-collection/receipts/daqian-direct/<request_id>/`。[开工及投递](../editor/docks/daqian/workspace.gd#L4128) · [上下文读取](../customizations/components/godot-host/issue_route.py#L436) · [日志根解析](../customizations/components/godot-host/direct_issue.py#L245) |
| 4. 到本机 | `submit_execution` → `AIChatDock::_open_daqian_chat` → 共工 `chat` → `_start_codex` | 执行 token 绑定项目、账号与工单。原生层传入工单号、需求 ID、Agent、当前工具许可以及文件/命令批准设置。桥回执成功后，原生层用有效配置中的 Node 启动 Codex 桥，通过管道收发。普通 AI Chat 未绑定的新需求走 `issue-agent` 识别和绑定；画布只读分类、司南需求判断和实际生产是三个独立动作。[投递与 token](../editor/docks/daqian/workflow_controller.gd#L144) · [原生会话](../editor/docks/ai_chat_dock.cpp#L5142) · [宿主参数](../editor/docks/ai_chat_gonggong.cpp#L512) · [Codex 调用](../editor/docks/ai_chat_dock.cpp#L6708) · [管道和 PID](../editor/docks/AIChatCliTransport.cpp#L109) |
| 5. 回到原单 | 原生会话 → `finish_execution(receipt, error, past_preflight)` → 天枢运行记录 | 只接收仍在途的 token；项目或账号变化触发 `scope_changed`。按 error 写 `failed` 或 `completed`；预检前的错误在卡上保留“预检失败”。后续阶段依据工单和产物验收证据推进。[执行回调](../editor/docks/daqian/workflow_controller.gd#L173) · [原生控件开工失败再恢复的历史回执](../data-collection/tianshu-issue-actions-452.json) |

**从执行会话派发本机独立工作者。** 设计已定稿并选择“按工单落地”、本机工作树写入已授权时，原生层另启 `tools/godot_parallel/runner.mjs`。执行器复用司南 `selectModel`，检查能力、依赖验收、独立工作树和可用槽位，先持久化准备回执与 `execution_id` 登记，再启动本地 CLI。实际 PID、所请求的模型与工作树属于这项执行。CLI 结束后还须等待标准输入交接、子进程 close 和日志流关闭；候选、终态上报和登记绑定均能回读，才产生运输完成的 `review`。终态中的 `business_accepted` 仍为 `null`。历史 #90 的原生按钮实测记录了两项 CLI 工作的 PID、退出码 0 和 `review`，同时保留了调试器清理诊断。[原生派发与回读](../editor/docks/ai_chat_sub_agents.cpp#L2266) · [选择与预留](../tools/godot_parallel/runner.mjs#L149) · [进程与终态](../tools/godot_parallel/runner.mjs#L245) · [#90 历史回执](../data-collection/sinan-parallel-godot-live-20261105.json)

## 可复现的失败回执

在下方第三条验证命令中，`failed process retains a false transport result and original execution receipt` 让临时工单的实际子进程以 7 退出。测试从 `worker.terminal_receipt.path` 重新打开磁盘上的 JSON，并分别核对工作者状态及原终态字段。观察到 `worker.state = "reconcile_required"`、`worker.transport_completed = false`、`terminal.exit_code = 7`、`terminal.transport_completed = false`。终态保存原执行和候选关联，已尝试启动的未知执行保留占用，后续先读原登记、候选和终态。夹具控制了授权与上报，未调用真实模型。[失败用例](../tests/editor/test_parallel_work_orders.mjs#L213) · [原终态持久化与释放条件](../tools/godot_parallel/runner.mjs#L309)

路由失败发生在更早的阶段。模型判断没有有效结论时，`run_turn` 将本次尝试及原因写回原路由日志，再次收到同一请求会提示“上次模型调用未取得可用结论，请核实后显式重试本工单”。本次测试确认普通重复调用没有再次请求模型，开工要求刷新判断，显式重试取得 `ready` 后原单仍为 `planned`。[路由日志](../customizations/components/godot-host/issue_route.py#L225) · [测试](../customizations/components/godot-host/test_direct_issue.py#L394)

## 本机生命周期差异

| 消费者及阶段 | Windows 当前实现 | macOS 当前实现 | 可核实的边界 |
| --- | --- | --- | --- |
| 普通 Codex 对话启动 | 桥目录包含 `subscription_session.js` 且配置了 workflow Python 时选择可复用的 `session`，否则逐轮 `chat --progress`。Codex 桥建立 kill-on-close Job。 | `native_session=false`，通过 Node 逐轮 `chat --progress` 启动 CLI。 | 原生传输保存管道和桥 PID。取消会话调用 `OS.kill` 处理保存的桥 PID。macOS 普通聊天传递的是 `--progress`，不能从其他使用 `--host-process-group` 的分支推断该路径已经核实全树退出。[启动](../editor/docks/ai_chat_dock.cpp#L6708) · [桥](../tools/codex_cli/godot_bridge.js#L212) · [取消](../editor/docks/AIChatCliTransport.cpp#L349) |
| “按工单落地”执行、停止 | 独立 Node 入口须成功建立 kill-on-close Job；单项取消对该工作者调用 `taskkill /PID … /T /F`。 | 同一 runner 启动子进程；单项取消向直接子进程发 `SIGTERM`。该分支没有逐组停止并核验孙进程的步骤。 | 两平台均以 `execution_id`、候选、退出码和日志关闭来判定工作者阶段；失去观察时记待对账。当前编辑器退出分支直接停止并行 runner 的 PID。[取消与终态](../tools/godot_parallel/runner.mjs#L279) · [入口 Job](../tools/godot_parallel/runner.mjs#L380) · [原生退出](../editor/docks/ai_chat_dock.cpp#L8139) |
| 父任务交付适配器持有的命令 | `OwnedCommand` 挂起创建，分配到专用 Job 后恢复执行。清理时停止 Job、等活跃进程数归零并收齐输出。 | 独立会话启动，保持直接子进程身份直至向进程组发 `SIGKILL`；Darwin 在信号权限异常时通过 libproc 核对剩余成员，再回收子进程和输出。 | 此保证仅适用于进入该适配器的命令，显式取消可撤销 live request。本次 Windows 测试确认取消后孙进程未发生延迟写入。[父任务宿主](../customizations/components/godot-host/README.md) · [启动与清理](../tools/ainative/owned_process.py#L179) · [取消测试](../customizations/components/godot-host/test_parent_completion.py#L348) |
| 编辑器退出与再次打开 | 天枢退出结束板会话、停止观察与调试并保存视图；聊天退出刷新历史、撤销活动请求和停止后台任务。历史 Windows `direct` 用例在第二个编辑器进程中读到了开工回执。 | 使用同一套天枢及聊天退出回调；历史 macOS arm64 隔离编辑器验证覆盖 `entry/direct`、批准和标签重启。 | 历史 UI 回执各有自己的二进制摘要。本基线尚缺同一候选在两台真实编辑器中执行“关闭运行中任务 → 核实本任务子进程全部退出 → 重开续至原阶段”的整链回执。[天枢退出](../editor/docks/daqian/workspace.gd#L1880) · [聊天退出](../editor/docks/ai_chat_dock.cpp#L8139) · [Windows 实录](../data-collection/tianshu-issue-actions-452.json) · [macOS 实录](../data-collection/tianshu-macos-local-editor-validation-20261108.json) |

## 本次定向验证与交接

从上述基线仓库根，在 Windows PowerShell、Python 3.14.3、Node v24.22.1 下运行。两个 Python 命令均使用下列环境设置。按命令顺序分别通过 3、3、3、16 项，退出码均为 0。前两组覆盖原单开工、缺回执拒绝、模型失败恢复、终态等待、冷启动权限和真实后代取消；第三组使用临时工作树与真实替身 CLI 检查成功、退出 7 和日志关闭失败；最后一组检查司南容量、能力、去重与未知占用。此次没有安装新的编辑器或运行真实账号任务。

```powershell
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
py customizations/components/godot-host/test_direct_issue.py -v DirectIssueTests.test_only_start_can_activate_exact_planned_issue DirectIssueTests.test_active_label_without_local_start_receipt_cannot_execute DirectIssueTests.test_model_failure_and_missing_model_leave_verified_issue_recoverable
py customizations/components/godot-host/test_parent_completion.py -v ParentCompletionTests.test_owned_process_cancellation_prevents_late_descendant_write ParentCompletionTests.test_cold_binding_without_live_owner_is_not_restored ParentCompletionTests.test_waiting_real_execution_requires_event_not_retry
node --test --test-name-pattern='real worker registration and immutable terminal|failed process retains a false transport result|late transcript flush failure' tests/editor/test_parallel_work_orders.mjs
node --test customizations/platforms/process-management/yuanheng-local/sinan/test/dispatch.test.mjs
```

[B06](gonggong-ai-workbench-plan1.md#b06) 取本表中的原生控制器、UI 脚本与宿主桥核定构建边界。[B07](gonggong-ai-workbench-plan1.md#b07) 取实际的 GitHub 来源与阶段回执映射关停策略。[D01](gonggong-ai-workbench-plan1.md#d01) 取只读意图判断和显式执行的分界。完整退出、检查点与恢复由 [R01–R04](gonggong-ai-workbench-plan1.md#r01)、[Windows Q04](gonggong-ai-workbench-plan1.md#q04)、[macOS Q05](gonggong-ai-workbench-plan1.md#q05) 验收。
