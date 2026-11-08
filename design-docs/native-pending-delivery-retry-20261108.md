# 已关闭工单的激活待完成重试

Issue: #572 · request_id: native-pending-delivery-retry-20261108

## 真实来源

原用户要求验证聊天、拆解、实现、编译、子验收和 main 全链路，遇阻修复。#483 的真实 fixed host action 已完成 PR567/C28cc/Sf58/main6d67 与 closed completed done 回读，但复制到私有入口后 strict signature 失败，返回 completion_verified=true / ok=false / activation_pending。外层只读确认原入口与旧63产物保留。无专用恢复 action；不能让闭单再次普通生产 intake，也不能将外部 activation JSON 手改为 native 成功。#569 单独修复制元数据。

## 最小合同

1. 仅 Mac trusted Desktop UDS 的 retry-delivery 命令。先读取真实 live context，提交同上下文和独立 request_id；工具许可、自动执行、顶层原父、空闲、无草稿/IME/并行更新等都由实际宿主核对。
2. 只从已验证绑定 common-dir 的 finalization journal 选择唯一同 owner、snapshot、source、Issue/request 的 completion_verified=true / activation_pending 事务；限定 C/S/PR、接受声明和原 receipt SHA。旧 scope/nonce/generation 不变；本次 live owner/snapshot/generation/nonce/request_id 独立记录。
3. 新受信安装 fixed worker 重新验证 private binding、source C、签发 PR/CI/main、闭单 completed/done、现操作者写权限和原声明摘要。只重做 activation，无模型、无新的验收声明、无 Issue 写、无普通 intake。新 helper 可验证旧 source，不复制到旧 SourceInputs。
4. 原事务与失败 last_receipt 保留。独立 retry journal/attempt 和宿主 route receipt 记录 started/unknown/actual result；同 request 幂等、不同并发受同事务锁保护。未知先读回，不盲重放。不能从 history、可写 activation JSON 或 caller 指定路径获得准入。
5. 新 worker 结果经 provenance 和本次 live 身份检查后本地 delivery_completed；非 LLM tool_call，记录为真实 host action。冷历史本身不恢复权限；需要 fresh trusted Desktop action。普通已关闭工单聊天仍拒绝。
6. complete_delivery state schema 明确 enum(done,remaining,unknown)，仅 done 可最终完成；passed 不映射，错误定位 item。

## 验证与交付

隔离真实 Git fixture + fixed worker / native typed loop：正常、跨重启新 generation、旧记录只读、权限/owner/snapshot/child/consultation/busy/歧义/unknown/并发/幂等拒绝。所有账户、_sc_、central config、源项目和 bridge 均私有；不连接生产引擎或原483。非作者独审、正式 gate/writer、exact CI、main 与本单权威终态回读。原483恢复另由 Root 的公开维护宿主实际验收，不能把本单fixture当成其成功。

## 已验证的实现与恢复入口

本机后台候选已完成23项跨重启与26项已登记 managed native entry 组合验证，恢复阶段没有模型轮或 Issue 写入。初始合成模型仅用于创建真实原生 pending 事务，单独计1轮。非作者审查通过并实核保留的源清单、三份严格签名、不可变 payload、原 journal 与独立 retry receipt；原生产 #483 尚由维护宿主接管恢复，未将本单夹具当成生产成功。

新的 live context 带真实 engine_pid 和每个 Dock 实例随机 host_instance_id。重启可能让 generation 变小，原交易 generation/nonce 仍保留；旧进程 context 不能再次授权。worker 固定从正在运行的可信安装加载，目标始终是原绑定源，不复制新代码进已签旧 source_inputs。

Mac 官方 Codex 桌面进程树内使用 Apple Python（不是引擎子进程），先对明确观察到的编辑器实例读取 context，然后调用 retry-delivery；不提供 owner、候选、验收声明、源路径或模式参数。示例中的路径和 PID 由维护宿主读取，不由模型猜测：

```text
/usr/bin/python3 TRUSTED/tools/editor_instruction_client.py --project PROJECT --instance OBSERVED_PID context
/usr/bin/python3 TRUSTED/tools/editor_instruction_client.py --project PROJECT --instance OBSERVED_PID retry-delivery --expected FRESH_CONTEXT_JSON --request-id NEW_REQUEST_ID
/usr/bin/python3 TRUSTED/tools/editor_instruction_client.py --project PROJECT --instance OBSERVED_PID status NEW_REQUEST_ID
```

首条请求回执仅 delivery_retry_started/running，不能当完成。只有新固定 worker 的真实回读经 provenance/本次 owner/snapshot/generation/nonce/pid/instance 验证，并且 host-action 回执持久化成功，才本地结束为 delivery_completed。unknown 或 pending 保留原结果；旧请求只查询，不盲重放。已经运行的动作中 Stop 会终止子进程并保留不确定性，冷恢复的 running 路由只变为 unknown，不自动调度。

#569 管理入口首次登记须由真实维护宿主经其正式 CLI 显式选择 managed_native_app_link；本 API 不替用户猜模式。已有受信登记之后，retry 默认严格复用。未登记的旧 copy pending 不会自动获得链接授权。

验收 state schema 现仅 done/remaining/unknown，只有 done 可以完成；passed 会指出具体 item 并拒绝，不做映射。普通关闭工单的新聊天仍受原 intake 门禁。
