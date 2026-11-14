<!-- gonggong-request:ai-chat-intake-execution-1086-20261114 -->
父需求 #1086，实施父项 #1211。用户已明确授权本会话接管 #1086 全部实现与交付。此子项拆分 AIChat 工单向导与点火器的无 GUI 执行状态、实际进程和回执处理；最终由同一 #1086 集成候选交付。

范围：将 ai_chat_gonggong.cpp 的 issue guide / igniter Run/Poll/Cancel 与相关模型子进程调用迁入 AIChatIntakeExecution；保留来源身份、权限、确认、重复提交和恢复边界。主工作者负责旧入口接线及非 GUI 后台 owner，禁止增加只转调 Dock 的壳。

验收：
- [ ] 领域执行器拥有实际状态和副作用，保持原回执及来源绑定语义。
- [ ] 无 Dock 的本机受控进程、取消、晚到/未知回执及身份隔离测试通过。
- [ ] 主工作者接线、独立审查、原生/Windows CI 和 main 随 #1086 交付。

需求文档：`design-docs/ai-chat-intake-execution-1086-20261114.md`
执行授权来源：codex-user-explicit-1086-handoff-20261114
<!-- gonggong-host-git:Sail-Li -->

## 收尾决定
用户随后明确要求立即收尾、不再展开新内容。本项尚未派发、未开始实现，保留为 #1211/#1086 未完成范围；当前会话不再推进。本次不以完成关闭。
