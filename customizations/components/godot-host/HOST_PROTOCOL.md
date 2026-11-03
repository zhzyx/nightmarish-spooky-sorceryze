# Olympus 宿主协议 v1

Godot、IDE、命令行和其他生产工具共享 `tools/olympus_bridge.py`，使用同一 Olympus 框架和赫尔墨斯文件入口。组件历史目录名保留兼容；没有 IDE 白名单或 Agent 自批开关。

调用：`python tools/olympus_bridge.py chat --workspace <工作区> --request <请求JSON> --tenant <租户>`。参数路径由宿主提供，不提交本机绝对路径配置。进程以 JSON 返回上下文、真实文件回执及上报绑定；非零退出或 `ok:false` 时宿主必须停止模型/工具执行。

```json
{
  "protocol_version": 1,
  "host": {"id": "example-ide", "kind": "ide"},
  "agent_id": "athena",
  "request_id": "actual-user-request",
  "outcome": "用户的真实任务",
  "authority_ref": "host-authenticated-user-request",
  "project": "host-project-reference",
  "tools_enabled": false,
  "file_changes_require_approval": true,
  "execution_requires_approval": true
}
```

`host.kind` 支持 `engine`、`ide`、`cli`、`production-tool`。`host.id` 和 `agent_id` 使用小写字母、数字、下划线、点、连字符，最长 96 字符。Agent 必须在当前 manifest 唯一注册且持有匹配批准。没有协议版本和 host 字段的旧请求兼容 Godot/Athena 默认值；v1 必须明确宿主和 Agent。

宿主描述只用于绑定和归属，不能认证身份或赋予权限。实际身份、工具许可、用户确认由宿主控制。桥接器不执行模型，`context_ready:true` 只说明该次上下文及文件回执通过；`agent_execution_enabled:false` 和 `model_execution_started:false` 不表示 IDE 被禁用。宿主应注入返回的完整上下文，按 reporting 绑定记录实际开始、步骤、结果和取消，真实回执失败时停止下一轮。用量不可测时保留 null。

`doctor` 是只读诊断；`check` 只校验候选及源内容完整性，不能作为生产准入依据。每次 `chat` 仍重新执行正式加载器。`flush` 重试共享持久队列，只有真实文件回执成功才删除信封。

## 会话内工单引导

`issue_number`/`request_id` 未绑定（`Missing host request: request_id` 或 “Before development, create/reuse a real Issue…”）时，宿主可以在会话内引导绑定，不把本轮当作终止错误。引导期间的回复由宿主本地解析，不进入模型消息，也不执行工具；绑定后用原消息重新调用 `chat`，入口门禁不放宽。无人值守（定时）轮次与恢复轮次仍按拒绝处理。三个辅助动作都用 `--request <JSON>`，返回 `ok:false` 时宿主停留在引导中：

- `issue-draft`：`{request_id,title,category,outcome}`。写入 `design-docs/<request_id>.md`，已存在且内容不同则拒绝；返回 `work_items.py issue` 的预览，不产生远程副作用。
- `issue-create`：参数同上。经 `work_items.py issue --apply` 创建或复用同需求 ID 的 Issue，标签为唯一 `type:*`、`status:needs-decision`、`workspace:olympus`。找不到 gh 时返回 `error:"gh_unavailable"` 和可复制的创建命令。
- `issue-start`：`{issue_number,request_id}`。仅在用户于会话中明确回复开工时调用；校验仓库、开放状态、需求 ID 与 `workspace:olympus` 后，把 `status:needs-decision`/`status:planned` 改为 `status:in-progress`。其他状态需在 GitHub 上人工决定。

gh 查找顺序：`OLYMPUS_GH`，`PATH`，再依次是 `~/.local/bin/gh`、`/opt/homebrew/bin/gh`、`/usr/local/bin/gh`（GUI 启动的宿主通常没有用户 shell 的 PATH）。

找到 gh 后，三个动作都会先执行只读的 `gh auth status --hostname github.com`。`issue-draft` 返回 `gh_authenticated` 和 `gh_login_command`；`issue-create`/`issue-start` 在未登录时返回 `error:"gh_unauthenticated"` 和 `login_command`（`<gh> auth login --hostname github.com --git-protocol https --web`），不调用 API、不创建或修改 Issue。登录需要交互，宿主只展示命令，由用户在终端完成；登录后回复 `确认`/`开始` 重试。


## 常规会话需求入口（当前约定）

`issue-agent` 是普通用户轮次的默认入口；旧三个手工动作仅保留兼容用途，不作为正常会话绕过 Athena/Metis 的入口。请求含 outcome、conversation_id（会话+真实用户轮次）、已有 issue_number/request_id、当前HTTP endpoint/model或CodeBuddy CLI模型/入口；APIKey 必须通过私有 stdin JSON 行发送，不允许写到 --request 文件。

前置阶段只验证环境及仓库访问、装配已批准 Athena+Metis 上下文并生成结构化需求，不运行生产工具。Agent 输出 decision/title/category/goal/scope/acceptance/questions，宿主不相信输出自带的身份或权限。真正未知写 questions；工单可先以 needs-decision 跟踪，已具备行动条件的用户需求按本次自动流程授权转 in-progress。返回 ready 后仍须原正常 chat intake 回读仓库、租户、类别、状态、工作区标签和准入。

失败保留原需求和尝试；修复后明确重试。模型结果未知不自动重复付费调用；发布结果未知只查询原稳定ID，未发现唯一单据则保持待对账。取消不撤销已提交远端请求，只停止本地后续步骤和迟到绑定。需求阶段 journal 与正式Hermes回执分开，真实Issue创建后将真实需求调用/用量绑定并投递；夹具数据不得导入生产。
