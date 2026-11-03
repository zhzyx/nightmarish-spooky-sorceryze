# 当前宿主的赫尔墨斯采集与调查入口

路径以工作区根为基准，命令可传 catalog 的绝对路径，不依赖进程 cwd。工具为 `framework/tools/hermes-host.py`，目录为 `data-collection/catalog.json`。复用赫尔墨斯 iris、原 reporter、outbox 和 v2 台账；没有新的 Agent 身份、授权、计费或质量账本。

当前实际接入为当前授权宿主的显式调用：用户消息、任务开始、工具执行、失败、质量/返工、Agent 交接、实际 GitHub 回读及任务结束分别在事件发生时提交。旧来源只读加入目录；历史遗漏以有来源摘要的 feedback 观察补录，标明补录时间、原始时间未知，不能伪造历史 message/step/handoff 或用量。原始敏感内容留在授权文件，事件保存最少引用。无事件不运行，不设定时、后台监听或轮询。

## 单次入口

```text
python framework/tools/hermes-host.py --catalog data-collection/catalog.json init
python framework/tools/hermes-host.py --catalog data-collection/catalog.json submit --envelope path/to/actual-envelope.json
python framework/tools/hermes-host.py --catalog data-collection/catalog.json run --session path/to/actual-session.json --key unique-actual-operation -- command arg
python framework/tools/hermes-host.py --catalog data-collection/catalog.json query --tenant local-olympus --work zhzyx/nightmarish-spooky-sorceryze#9 --receipt data-collection/receipts/issue9-read.json
```

envelope 必含 tenant_id、稳定 batch_key、source_ref、agent_snapshot_ref、request_ref、authority_ref 与 records。records 遵循 `framework/agents/hermes/references/data-contract.md`；source、真实 agent_snapshot、request 先送达，之后事件引用已落库身份。事件ID由来源或宿主实际实例提供；同一事件重放必须使用原 envelope，变更内容须新版本并沿用 supersedes。示例为 `work/hermes-gap-9/begin.envelope.json`，它是已执行事实，不可冒用为新需求。

session 含上述绑定字段（除 batch_key/records）、source_key 和真实 context。run 仅观察宿主明确传入的 argv，无 shell、无提权、无后台执行；运行前须真实授权。先记录开始，结束后以 supersedes 记录状态、退出码和实测时长。不同实际执行用不同 key；同一 key 无论成功、失败或回执不明都不重复执行。它不是通用沙箱，不因存在 session 就授予新命令权限。采集器不递归记录自己的执行。

需要单独提交的 message、direction_error、correction、quality_issue、rework、handoff 与 coverage 使用 submit；数据契约关联实际事件，handoff 同时引用真实双方快照。结束时提交 request_end 和按类别的 coverage；只有源序列可对账才写 complete，否则 partial/unavailable。模型供应商未暴露用量时保持 unavailable，不用零、估算或命令耗时充当 token。

## 恢复与读取

原始 envelope 先持久写入 inbox，随后排队并取得共享赫尔墨斯回执。同批次内容冲突拒绝；投递失败返回 pending_recovery，原 envelope 保留。后续真实事件重放相同 envelope 可恢复，不因采集故障重复业务命令。run 的 command 回执在 receipts 保留 terminal_record；若结束回执未送达，重放 inbox 中结束 envelope，不能重跑命令。若中断仅留下 claimed，先调查真实进程/副作用，不能自动删标记重跑。

退出码 0 表示所请求动作成功，2 表示部分读取或待采集恢复，1 表示输入/命令错误。检查 outcome、recorded、queued、delivered 和命令 status；这些状态不能相互替代。存储不可写时只能保留工具错误并向宿主交接，不能声称已持久化。

query 对登记来源只读，按 tenant、可选 work/kind 过滤，按原始记录身份/摘要去重；在合并证据关系上计算 superseded/stale。冲突证据及受影响引用不计 current；缺失来源不妨碍其他可读来源。输出记录、源快照摘要、筛选条件、覆盖说明、生成时间，可写独立消费回执。不自动复制历史台账，也不把记录数当需求量或失败率。

全局聊天捕获和供应商用量流仍需宿主平台提供真实事件源。当前接入以明确实际调用为边界；GitHub snapshot 观察不是 webhook，也不等于登记进阿里阿德涅原宙斯账本适配器。阿里阿德涅仍在真实事件到达时单次刷新；未覆盖部分要显式记录，不能用配置开关宣称全接通。
