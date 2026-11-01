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
