# AI 对话子 Agent：父窗口内嵌、按设计定稿工单自动落地

<!-- gonggong-request:sub-agents-20261104 -->

- 需求 ID：`sub-agents-20261104`
- Issue：https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/48
- 类别：`type:development`
- 责任人：待实际指定

## 原始需求与目标

用户原话（2026-11-04）：

1. 增加“子agent”概念，子agent窗口寄生在父agent窗口内。只有父agent可以用户手动或者自动建立子agent。子agent可以主动获取父agent的上下文。
2. 当会话交付设计定稿之后，根据结果创建若干子agent。通过子agent进行落地。

背景（已核实）：引擎内会话在设计定版后只把生产工单标为“待派发”，没有任何执行入口承接，导致设计无法在编辑器内落地（见 Issue #47 会话）。编辑器已有平级 Agent 标签、定时任务隐藏 Agent（`ai_chat_scheduler.cpp`）及单执行器串行调度，可复用。

目标：在 Godot 编辑器 AI 对话中提供父子 Agent；设计定稿后由父 Agent 按“生产工单”自动派生子 Agent，并在编辑器内按工单顺序执行落地。

## 范围与非目标

范围：

- 父子关系：子 Agent 只能由顶层（普通、非定时、非子）Agent 创建；子 Agent 不能再创建子 Agent。每个父 Agent 最多 16 个子 Agent，全部子 Agent 最多 128 个。
- 窗口内嵌：子 Agent 不在顶层标签栏单独出现；选中父 Agent 或其子 Agent 时，在父窗口内显示“子 Agent”标签条（父会话 + 各子 Agent + 状态），切换后在同一窗口区域显示子会话。
- 手动创建：子 Agent 标签条上的“新建子 Agent”按钮。
- 自动创建：父 Agent 一轮完成后，若当前绑定需求文档 `design-docs/<request_id>.md` 含“设计定版确认”小节和“生产工单”编号列表，且该父 Agent 尚未为该需求派生过子 Agent，则每张工单创建一个子 Agent，首条消息为工单内容。另提供“按工单创建”按钮立即执行同一检测。
- 获取父上下文：子 Agent 可调用只读工具 `get_parent_context`（API 后端为函数工具；CodeBuddy CLI 后端为保留命令 `godot-host-action get_parent_context`），返回父 Agent 标题、会话 ID、最近可见对话（脱敏、有上限）及兄弟子 Agent 状态。首条工单消息同时注明父 Agent、Issue、需求文档和此工具。
- 落地执行：自动创建的子 Agent 共享单执行器，按工单顺序串行执行；前一张未完成（失败/停止/中断）则后续停住并提示，不跳过依赖。手动子 Agent 由用户自行发送。
- 持久化：父子关系、工单序号、状态随 `ai_chat_history.json` 保存；重启后执行中/等待中的子 Agent 标为“中断”，不自动重放。
- 关闭父 Agent 时一并关闭其子 Agent（确认框说明）。

非目标：

- 不新增或注册共工框架 Agent；子 Agent 与现有 Agent 标签同属 Godot 宿主 UI 会话，GongGong 上下文仍为既有 Yanshi 装配，入口门禁、准入、谛听回执不放宽。
- 子 Agent 不运行 issue-agent 需求整理、不新建 Issue：沿用父 Agent 当前绑定的真实 Issue/需求 ID（与定时 Agent 相同的跳过规则），每轮仍经 `gonggong_bridge.py chat` 正式回读。
- 不并行执行多个模型请求（编辑器仍为单执行器）。
- 工具权限、文件自动应用、命令自动执行沿用用户当前开关，不为子 Agent 自动提权。
- 不实现子 Agent 之间直接通信；兄弟状态只读。

## 设计方案

数据模型（`editor/docks/ai_chat_dock.h`）：

- `HashMap<int, Dictionary> sub_agents`：键为子 Agent 的稳定 ID，值 `{parent, work_order, source(manual|design), request_id, state(manual|waiting|running|completed|failed|interrupted)}`。
- 子 Agent 标签在 `agent_tabs` 中隐藏（与定时 Agent 相同），复用 `AgentSession` 切换、保存与关闭逻辑；`_manual_agent_count()` 不计入子 Agent。

界面（新文件 `editor/docks/ai_chat_sub_agents.cpp`）：

- 父窗口内 `SubAgentBar`：标签条（父会话 + 子 Agent，提示框显示状态）、“新建子 Agent”、“按工单创建”。仅当前 Agent 是父 Agent 或子 Agent 时显示；子 Agent 中新建按钮禁用。

工单解析（`AIChatSubAgents::parse_work_orders`，纯函数，可单测）：

- 文档须含标题包含“设计定版确认”的小节；读取标题以“## 生产工单”开头的小节，顶层编号行 `N. 标题` 及其缩进子行构成一张工单；最多 16 张，单张不超过 8 KiB。

调度：

- `_sub_agent_dispatch()` 在空闲时（与 `_scheduler_dispatch` 相同的空闲条件）选择下一个父 Agent 中最小序号、状态为 waiting 的设计子 Agent；若更小序号存在未完成的子 Agent 则不派发。`_set_busy` 结束时更新子 Agent 状态并延迟调用调度；定时任务优先级不变。

父上下文工具：

- `get_parent_context` 仅对子 Agent 有效；从 `agent_sessions[parent].transcript` 取 user/assistant/editor 记录，最近 40 条、总计不超过 48 KiB，`_redact` 脱敏，附 `untrusted:true`。CLI 端在 `godot_terminal.js`、`godot_acp.js`、`godot_bridge.js` 白名单中增加该保留动作。

## 依赖及风险

- 依赖现有单执行器：子 Agent 执行期间无法切换 Agent（与现状一致），用户可切页查看。
- 设计文档格式依赖“设计定版确认”和“## 生产工单”约定；不符合时不自动创建，提示可手动新建。
- 自动执行受用户当前审批开关控制；开关关闭时子 Agent 会在每个写入/命令处等待确认。
- 历史文件增加 `sub_agent` 字段；旧版本编辑器读取时忽略该字段，子 Agent 显示为普通 Agent（向后兼容，不丢数据）。

## 验收标准

- [ ] 顶层 Agent 可手动新建子 Agent；子 Agent 中无法再新建；子 Agent 不出现在顶层标签栏，只在父窗口的子 Agent 标签条中出现。
- [ ] 子 Agent 调用 `get_parent_context` 返回父 Agent 最近可见对话（脱敏、有上限）；非子 Agent 调用返回错误。
- [ ] 父 Agent 一轮完成后，绑定需求文档含设计定版与生产工单时，自动按工单创建子 Agent，且同一父 Agent/需求不重复创建；“按工单创建”按钮效果相同。
- [ ] 自动子 Agent 按工单顺序串行执行；前序失败时后续停住并提示。
- [ ] 子 Agent 不触发 issue-agent/建单，仍经 GongGong chat 正式入口校验。
- [ ] 父子关系与状态重启后恢复，执行中/等待中标为中断且不自动重放；关闭父 Agent 一并关闭子 Agent。
- [ ] 原生单测覆盖工单解析与父上下文截取；CLI 保留动作单测通过；编辑器可编译。

## 验证与采集证据

实施后补充：引用实际提交、测试输出及 `gonggong-diting-data/` 真实事件；未知用量保持 null。
