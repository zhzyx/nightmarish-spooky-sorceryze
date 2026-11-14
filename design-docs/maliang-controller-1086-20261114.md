# 马良工作流运行 Controller 重构

父 #1086，授权来源 codex-user-explicit-1086-handoff-20261114：用户明确将统一核心、三个 Controller 和全部交付移交本会话。当前操作者 Sail-Li，从 main 7acdf07ca4c89251527a392c754a536af2094b6a 的独立工作树实施，保留其他工作副本。路径以仓库根为基准。当前未实现/验收，不代替父单关闭。

公共 Godot 合同已由核心实现者与整合者确认：AIWorkflowRuntime singleton，begin_run(Dictionary request)、publish(Dictionary event)、cancel(run_id,generation,event_id)、snapshot(run_id)，返回 ok/code/reason/changed/snapshot，run_event(snapshot) 仅有效变更触发。request 包含 workflow/scope/request_id/model/binding/input；事件绑定 run_id/generation/event_id/expected_sequence/kind/state/payload；模型与绑定只用公开元数据，运行开始冻结。接口集成验证等待核心实际实现，Controller 的现有职责迁移可先独立实施。

## 实施与验收

将 workbench.gd 中 jobs、run_id、auto_step、启动请求/进程、轮询、取消、重试及恢复职责迁至独立 workflow_controller.gd；View 保留控件、输入快照和资产预览。复用 tools/ainative 的 Executor/Provider/持久任务和进程所有权，保留 #1163 建模与雕刻独立模型、旧设置迁移及已有恢复语义。不得只加一个转发到 View 的空 Controller。

- [ ] 原启动、轮询、取消、重试及恢复入口实际调用独立 Controller。
- [ ] 运行身份与公共状态/事件接入统一核心；节点选中模型及供应商快照保持冻结。
- [ ] 领域执行器保留唯一任务事实，View 不再维护第二份可变运行状态。
- [ ] UI 重建/绑定后回读既有运行，旧 Provider、人工确认、取消迟到结果回归通过。
- [ ] 精确候选独立审查、父集成内嵌脚本/原生构建/CI/main 及回读完成。
