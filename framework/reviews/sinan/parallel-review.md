# 司南并发调度独立增量验证

日期：2026-11-02。评价者：`/root/parallel_dispatch_validation`，独立于实现者 `/root`。范围限定本次调度器与分工约束修订；只修改测试文件及 work 证据，不修改实现、真实账本、自动化或共享框架。此评价不是批准。

结论：本次覆盖通过，未发现遗留阻断项。实际执行 `node --test outputs/gonggong-workorders/test/dispatch.test.mjs`，12/12 通过；保留原 6 项覆盖，新增 6 项行为测试。没有重跑无关上报链路或整套框架。

验证到的行为：

- 两个互不冲突执行任务与一个独立审查任务可在同一批次进入候选，审查路由到 independent_validator。
- 三个同对象只读任务可并行；host_worker_slots 为 1 或 0 时分别限制为 1 或 0。
- 已运行审查占用 review 槽，仍保留两个 worker 槽；其他审查等待。
- 先读后写、先写后读均阻断真实冲突；不同输出目录但读取对方写入对象也阻断。
- 硬依赖未满足者不进入候选，无关执行和审查继续。
- 非整数／负容量、矛盾只读写声明、非法 lane 或 scope 拒绝。
- 既有未知范围、blocked 占位、真实路径别名冲突、范围越界、用户待决定及禁用状态保持约束。

框架与元衡评价：复用当前 v0.9 治理上下文并读取适用审查规范；本次未创建新治理规则或正式 Agent。目的对应用户并发诉求；事实区分候选计划与实际运行；复用原工单与宿主；权限、独立验收和共享写入约束保留；适应限定读写范围与槽位计算；既有阻塞、依赖和授权条件连续。各项在本次覆盖范围内通过。

职责说明要求委托传递最小输入和实际读写范围；只读审查若需写报告／测试产物，须声明独立输出目录；稳定快照审查才可与新制作流水并行。只读规划没有验证实际宿主身份隔离、实际多 worker 启停或 token 降幅；这些不能仅凭本次测试宣称已实现或已测得。

最终内容 SHA256：

| 文件 | SHA256 |
| --- | --- |
| outputs/gonggong-workorders/dispatch.mjs | 2bd94d3b040ed3770fb364bf6da54d8d75dfd445f9cd9ea80ee6c8ae39dea4c9 |
| outputs/gonggong-workorders/test/dispatch.test.mjs | f1633a1a0d5756aaf937ff9dde9e6bf31c12024abc6e39a4ff342637bd74e85e |
| outputs/gonggong-workorders/调度与Agent职责.md | 1f54b4f5ad651b32113778f63070d62b9b4703c8b8236c2940ed143b54d467a8 |

测试夹具仅在 work/dispatch-* 中产生，无真实派发和源账本写入。正式启用、当前用户授权及实际扫描回执由主流程核验。
