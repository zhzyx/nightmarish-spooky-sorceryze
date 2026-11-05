# 司南并行派发核心候选独立审查

审查者：当前会话独立子 Agent `/root/dispatch_review`，2026-11-05；不是批准人。
范围：司南 0.1.2 的 AGENT.md、agent.json、reporting.json、references/parallel-dispatch.md，支撑模块 0.6.0 的 module.json、dispatch.mjs 及派发回归。路径相对框架根。两个宿主实现不在此结论内。

发现并修复：预留异常中断整批、ack/记录失败丢失真实执行回执、复核拒绝后未在事件内补位、延后任务字段未提前校验导致预留后异常中断。独立复核 15/15 派发测试通过，无新增必要修改项。

元衡评价：purpose 通过，直接服务明确的多任务并行与能力选模；truth 通过，候选、启动、回执及验收分离，未知保留；economy 通过，复用原司南、来源与共享谛听，无定时调用；authority 契约层通过，真实权限、准入与容量由宿主复核；adaptation 通过，动态目录、事件补位、保留在途记录的回退；continuity 通过，原 prepare/refresh 与业务承诺保持，冻结来源未修改。

精简性通过：入口统一换行后由 869 字符增至 1071 字符（新增 202 字符），细节置于按需文档。不是 token 或成本统计。reporting 入口摘要为 65c18a21a076c79e1e2c66840f12b51035cd9a22c4b13079a93568eae935e1a0，配置校验通过。

未决：精确候选批准、两个宿主独立审查、真实模型目录与权限、来源 start/ack、跨聊天持久锁/崩溃恢复、实际派发及谛听送达回执。保持 runtime_connected=false。结论：核心候选共工边界、元衡六原则及精简性通过，生产启用待验证，本结论不是批准通行证。

后续增量复核：同一独立审查者核对了 queued chat 返回 delegated_pending_host、持久化异常保留 error.receipt 两处修改与 Codex 适配器；实际 26/26 测试通过（核心派发 16、Codex 10），无新增必要修改。Codex 使用原生回调模拟，不能证明生产工具桥或真实来源 CAS/谛听送达。Godot 仍另行审查。

queued chat 的追加复核通过：setupPending=true 时不调用来源 ack，只保留待宿主状态，测试明确断言 acks=0；真实 threadId 到达后才由宿主继续核对和 ack。核心及 Codex 26/26 测试通过。
