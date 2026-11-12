# 启动前阻断后的显式、有界恢复

需求 ID `editor-blocked-dispatch-retry-20261112`，工单 [#877](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/877)，父需求 [#773](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/773)。路径均以仓库根解析。

正常生产中，runner 明确未启动的结果被编辑器映射成 waiting，结束后的 deferred dispatch 会立即再次启动。恢复批次又会被另一个 interrupted 兄弟任务整体挡住。修复限定在已有原生调度状态机，不新增模块、服务或供应商调用。

## 行为与边界

- runner 结束时，`blocked`、`blocked_model`、`blocked_dependency` 保留原回执并进入 interrupted。未知、缺失和对账状态也保持不可自动运行。
- 用户在父会话明确点击“继续落地”，仅对上述三个精确状态重新核对原始文件、运行标记、批次、需求、工单、设计和 worker 身份；新记录还核对文件摘要。旧版记录无摘要时必须与原文件中的唯一 worker 回执完整一致。取消回执、`blocked_unknown` 等前缀近似状态不能重试。
- 一次恢复仅排队一次尝试。运行中重复点击不能重复启动。新尝试沿现有实现生成新 batch/output，并清空子会话缓存的旧回执和旧摘要；原文件不修改。若新尝试无输出，旧 blocked 回执不能再授权下一次。
- 冷启动把包括旧 waiting+blocked 在内的 waiting/running/pending_host 统一停在 interrupted；仍须显式恢复，使用相同的回执核对逻辑。
- 未知 interrupted 兄弟项加入批次作为阻断项，保留原文件引用，不接受、不释放占用、不加入 runner workers。明确可重试项可独立推进。依赖仍由现有实际验收检查放行，受阻下游保持等待。

## 方法召回与验证

已从本租户召回 `editor-dependency-handoff`：`bind-consumer-release` revision 10 适用于下游释放，原回执不是验收；`await-terminal-observers` revision 5 适用于进程结束但文件缺失，未知不能重试。`review-context-and-source-evidence` 的独立审查证据边界保持不变，本单不扩大其验收权限。

`tests/editor/run_design_batch.py` 的原生 headless 夹具新增 `parallel-blocked`、`parallel-blocked-model`、`parallel-blocked-dependency`、`parallel-blocked-unknown`、`parallel-blocked-stale`、`parallel-blocked-tampered`、`parallel-blocked-live`、`parallel-blocked-cold`、`parallel-blocked-prefix`。实际启动独立 Node runner，并记录每次 batch；由真实按钮验证 idle 不增量、同轮及运行中重复点击不增量、显式恢复仅一次、未知兄弟不派发、旧回执不能覆盖新未知、篡改/活跃标记拒绝，以及旧版 waiting 历史重启恢复。原始回执字节不变也是断言。

正常独立生产及实际验收后的依赖接续沿已有 `tests/editor/run_native_acceptance.py` 组合夹具复验，不能用 blocked 模拟结果代替业务验收。Python 语法、Node 现有调度回归与 diff 检查由实现者执行；原生构建、上述新增运行场景、独立审查及正式交付由根会话接续，结果未出前不宣称验收完成。供应商正常入口和最终有效安装仍归父项 #773。

实现阶段检查（2026-11-12）：`python -m py_compile tests/editor/run_design_batch.py`、提取内嵌 runner 后 `node --check`、`git diff --check` 均通过；`node --test tests/editor/test_parallel_work_orders.mjs` 49/49 通过（71.8 秒）。这些检查不代替新增原生场景执行。

集成验收的原生场景、独立审查、纠偏及保留边界集中记录于 [#773 续作候选回执](../data-collection/editor-production-followups-773.json)。路径以仓库根解析；正式交付及有效安装状态另行回读。
