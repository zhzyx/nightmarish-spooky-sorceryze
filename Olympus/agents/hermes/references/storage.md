# 存储、查询与迁移

Python 标准库 SQLite v2 台账，不联网。从框架根执行，先创建批准的 work 目录。JSONL 按来源、Agent 快照、需求、事件、分析的依赖顺序提交。

```powershell
python agents/hermes/scripts/ledger.py --db work/data.sqlite init
python agents/hermes/scripts/ledger.py --db work/data.sqlite import --tenant demo --input work/batch.jsonl
python agents/hermes/scripts/ledger.py --db work/data.sqlite list --tenant demo --agent-id athena --agent-version 0.2.0 --work feature-1
python agents/hermes/scripts/ledger.py --db work/data.sqlite stats --tenant demo --request req-1 --group-by step
python agents/hermes/scripts/ledger.py --db work/data.sqlite stats --tenant demo --group-by request
```

records 保存版本事实，evidence 保存证据；agent_catalog、dimensions、agent_links、work_links、labels 为可重建关系投影，logical_keys 防止重复逻辑事件和计费单元。与原记录同事务写入，复合主键／外键及索引以 tenant 为首维度。list 保留历史和有效性，stats 读取一致性快照并只统计适用版本。current 不是真实性、权限、质量或采纳证明。

v1 数据不能冒充 v2 完整数据。迁移只复制到新文件，原库不改：

```powershell
python agents/hermes/scripts/ledger.py --db work/data-v2.sqlite migrate --source-v1 work/data-v1.sqlite
```

原文指纹不变，历史标为 legacy_unmapped，可查而不进 v2 统计。补充真实快照、需求、关联后以新记录 supersedes 原记录；不伪造缺失时间、消息和用量。对账迁移前后数量及指纹，失败目标不采用，换新目标重试。实际生产切换由宿主协调。

--tenant 是一致性过滤，不认证文件操作者。生产需客户数据库权限／租户隔离、队列游标、备份恢复、保留删除与撤回失效、访问审计及容量验证。SQLite 的 WAL 与事务不是高并发业务承诺。部署前验证对账覆盖，使用现有权威数据服务，不能另建竞争质量账本。

共工可按框架根 sync/POLICY.md 只读使用赫尔墨斯数据优化；用户已持续授权有效共工更新的完整同步。此前“单独指令”要求仍适用于自行提出和实施框架修改，不阻断已批准上游同步。数据读取工具为 sync/read_hermes.py，历史快照不改写。

用户明确豁免：无数据库时使用独立 extensions/hermes-files 模块，在目标 Git 仓库的 olympus-hermes-data 记录需求产出并随需求合入。该模块和数据不受共工同步覆盖；赫尔墨斯与共工使用同一文件分析入口。尚无目标仓库时只交付规则与工具，不创建生产数据。文件状态不冒充 SQLite 回执。
