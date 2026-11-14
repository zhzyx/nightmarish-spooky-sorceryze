# AIChat 运行与传输 Controller 重构

父 #1086，授权来源 codex-user-explicit-1086-handoff-20261114：用户明确将统一核心、三个 Controller 和全部交付移交本会话。当前操作者 Sail-Li，从 main 7acdf07ca4c89251527a392c754a536af2094b6a 的独立工作树实施，保留其他工作副本。路径以仓库根为基准。当前未实现/验收，不代替父单关闭。

公共 Godot 合同已由核心实现者与整合者确认：AIWorkflowRuntime singleton，begin_run(Dictionary request)、publish(Dictionary event)、cancel(run_id,generation,event_id)、snapshot(run_id)，返回 ok/code/reason/changed/snapshot，run_event(snapshot) 仅有效变更触发。request 包含 workflow/scope/request_id/model/binding/input；事件绑定 run_id/generation/event_id/expected_sequence/kind/state/payload；模型与绑定只用公开元数据，运行开始冻结。接口集成验证等待核心实际实现，Controller 的现有职责迁移可先独立实施。

## 实施与验收

将 AIChatDock 中会话运行、HTTP/Responses 和 CLI 请求生命周期、工具继续轮、取消/迟到响应及后台工单工作者的执行职责迁至独立 AIChatController。Controller 通过公共核心拥有运行身份/状态；View 仅输入、控件、状态显示和预览。保留现有模型目录、凭据目标绑定、会话模型/强度选择、历史恢复与权限实现，禁止重写供应商协议或用另一个隐藏 Dock 作为后台执行器。

- [ ] 正常发送/停止/HTTP与CLI响应从原入口进入 Controller 与公共核心。
- [ ] 后台工单工作者不依赖创建 UI Dock 执行；旧公共入口保留必要兼容转发。
- [ ] 会话隔离、模型冻结、工具许可、迟到结果及恢复回归通过。
- [ ] UI 重建可查询既有运行，无重新提交副作用。
- [ ] 精确候选独立审查、父集成原生构建/CI/main 及回读完成。
