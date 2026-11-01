---
name: mnemosyne
description: Store versioned Hermes evidence and request telemetry with indexed work links, idempotency and explicit completeness.
---

按 ../../references/data-contract.md 与 ../../references/storage.md 复用权威数据服务；本地使用 ../../scripts/ledger.py。批次事务、来源幂等、租户与外键一致性先校验，拒绝冲突不得静默覆盖。JSONL 原始记录、结构化索引和统计使用同一事实源。

全量需求关联必须可查，缺值写明原因及 coverage。更正创建版本，派生事实重评；统计保留查询条件、快照、口径、未知量，实测与估算不混加。宙斯／奥林匹斯只存 reference，子 Agent 优化保持 proposed。保留、删除、权限和备份由宿主执行，数据写入不是修改批准。

按随附 reporting.json 使用奥林匹斯共享赫尔墨斯上报入口；运行须由宿主绑定实际需求与数据源，排队不等于落库成功。
