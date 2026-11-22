# R04　macOS 已登记任务进程组退出

macOS 编辑器退出时清理已登记的并行 runner 与普通 CLI 对话的专属进程组，直属子进程保持可等待，直至内核确认组内只剩已退出的组长。超时保留身份以便重试，丢失所有权后停止发信号。真实编辑器的活动 runner、先退组长及 Codex 桥三条路径分别核对三个、三个和四个 PID 全部消失，三个独立对照持续存活。真实 runner 登记与工作者 PID 和文件摘要匹配。

父任务交付沿用已有的 OwnedCommand 撤销协议。组状态未知时留存本地核对记录，重开后按原工单核对。两个较早的模拟父任务回执用例在修复前后均未返回预期消息，回执列出了两次的对照结果。

[方案一 R04](gonggong-ai-workbench-plan1.md#r04) · [候选与实机验收](../data-collection/gonggong-ai-workbench-plan1-r04-rechecked.json)
