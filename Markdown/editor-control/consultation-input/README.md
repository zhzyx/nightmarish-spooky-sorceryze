# 仅咨询会话的受信文字输入

这是官方受信 Desktop 宿主的专用 UDS 入口，不是通用 HTTP/editor 写权限，也不能用于生产任务提交。

## 使用边界

- 仅对当前用户已选择的顶层仅咨询会话发送普通文字；生产发送仍需原 owner、真实 Issue 和 snapshot。
- `consultation_only=true` 只用于单条请求降权，不切换或保存全局模式；不得传 `false`、数字或字符串代替。
- 保留原 owner、上下文、PID／实例、请求幂等、防重放、空闲、空草稿、队列及自动执行 opt-in 等保护。
- 关闭本地工具时纯文字可发送，但恶意工具请求仍须拒绝；普通 HTTP/editor 的仅咨询写入禁令不变。
- accepted / instruction_submitted 只表示进入正常聊天，不表示模型回答或业务完成。

## 原始命令示例

以下命令来自 macOS 原生验证记录，其他平台不能直接照抄解释器路径：

```text
/usr/bin/python3 tools/editor_instruction_client.py --project /path/to/project --instance PID context --consultation-only --wait 10
/usr/bin/python3 tools/editor_instruction_client.py --project /path/to/project --instance PID submit --consultation-only --text-file message.txt --expected fresh-context.json --request-id UNIQUE_ID
```

先保存该次真实 context 的完整结果，再将其作为 `--expected`；上下文变化后重新获取，拒绝旧请求。

完整设计和验证范围见 [仅咨询会话的受信文字输入](../../../design-docs/consultation-command-input-20261109.md)。
