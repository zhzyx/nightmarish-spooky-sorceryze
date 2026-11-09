# 天枢的多 CLI 工程链路

需求 tianshu-cli-host-pipeline，对应 #659、父单 #592。Godot 负责工单、当前操作者、候选工作树、逐项权限、文件读取与结果回执。适配器负责启动和停止供应商进程、识别本次登录、读取协议消息，并将结果交还对应的原始调用。用户在同一工单内操作，CLI 取用各自获准的本机登录。

## 一次工具回合

1. 将供应商提案转成宿主已有的 assistant/tool_calls 格式。每项包含唯一 id、function.name 和 JSON 参数。只公布此轮允许的工具。供应商提供原生文件回调时，保存回调到宿主 id 的映射。
2. 宿主验证工单与候选。相邻的同步 read_file 最多 16 项共用一次开始和一次结果校验，每项保留实际结果与成功标记。遇到写入、命令、构建或其他类型时结束这一组，按原执行序列和审批处理。咨询模式及中断命令恢复继续走各自原路径。
3. 逐项按 tool_call_id 归还结果。原生文件回调依据显式成功标记取得原文或拒绝，正文可能以 Error: 开头。宿主未签收整批结果前，适配器不能让模型继续。停止或改口会影响尚未执行的动作，迟到的旧会话事件需检查代次。
4. 会话复用还需要账号、工作区、能力与已接受历史相符。文本预览和终态分开处理。只有完整、合法的终态动作能进入工具执行器。

| 接入 | 供应商边界 | 验证 |
| --- | --- | --- |
| Codex | 保留原订阅 app-server 或兼容 exec 路径，结构化动作交由 Godot 执行 | 随机文件及追问已有 #650 的真实订阅样本，隔离环境验证回执拒绝、停止与改口 |
| CodeBuddy | 保留 ACP session 与文件回调；最多挂起 32 项独立读取，每个宿主信封最多 8 项。混合写入沿用原来的 8 项容量和审批 | 原生 SDK 对端并发读 9 个文件分成 8+1；真实编辑器配合受控 ACP 对端核对成功、缺失、原调用 ID 与 Error: 正文 |
| 后续 Claude Code 或其他 CLI | 对接自己的认证、会话句柄、流事件、终态和原始调用；受管工程工具须交回同一 Godot 宿主。只有原生工具能被限制或路由回宿主时才启用开发操作 | 在隔离工程重跑相同验收，再由供应商真实登录补足首答、续聊与取消证据 |

Claude Code 的程序化入口支持非交互运行、会话延续与结构化输出；SDK 另有工具权限回调。接入时需要验证所用版本与认证方式，特别是官方说明 bare 模式不读取订阅 OAuth。工程工具注册、账号和候选能力均验证后，才提供可选择的 Claude 后端。[官方程序化接口](https://code.claude.com/docs/en/headless) · [权限与工具回调](https://code.claude.com/docs/en/agent-sdk/permissions)

## 复测同一条工程链路

在工作树根执行；用实际编辑器可执行文件替换路径。Windows 终端回归需要 CODEBUDDY_GIT_BASH_PATH 指向可信 Git Bash；CodeBuddy SDK 依赖取 tools/codebuddy_cli/package-lock.json。

```text
node --test tests/editor/test_codebuddy_acp.js tests/editor/test_codebuddy_terminal.js tests/editor/test_codebuddy_bridge.js tests/editor/test_codex_subscription.js
python tests/editor/run_codebuddy_read_batch.py --godot <editor> --modules <codebuddy_node_modules>
python tests/editor/run_ai_chat_read_batch.py --godot <editor> --case receipt
python tools/tianshu_trace_timings.py <worktree>/gonggong-diting-data/events/<tenant>/<request>
```

计时工具直接读取已有宿主记录，核对摘要并通过 supersedes 配对同一进程的单调时钟。只输出阶段、状态、耗时和未配对数量。模型阶段可能含桥接与传输等待；真实网络模型时延、首次可读正文和用户点击数需要另用编辑器实测。外部账号未登录时，受控对端验证的范围止于编辑器和协议链路。
