# 奥林匹斯组件默认上报

本次按用户明确指令扩展创建和准入流程，不修改冻结纲领或宙斯原件。奥林匹斯工作流创建、更新、派生及合入的 skill 和 Agent 均必须携带赫尔墨斯上报配置；既有三个 Agent、八个框架内 skill 以及宙斯组织 skill 的外部适配配置均纳入校验。上游原件保持不变。

## 创建与审查

使用 tools/create-component.py，或生成满足同一契约的组件。入口只保留一条上报要求，reporting.json 绑定组件类型、ID、版本、入口指纹及共享实现指纹。方法不复制到各组件，Agent 与 skill 都复用 tools/hermes-report.py。

```powershell
python tools/create-component.py --kind skill --id example-skill --purpose "处理明确范围的任务" --out work/example-skill
python tools/create-component.py --kind agent --id example-agent --purpose "承担明确的独立结果" --out work/example-agent
node tools/reporting.mjs --component . work/example-skill
```

产物是 candidate_pending_review，自动携带 reporting.json 和未填的 reporting-binding.template.json。生成或静态校验通过不等于准入、运行授权或数据已接通。完成实现后入口变化要刷新版本和配置，再做原奥林匹斯／宙斯审查。不要手动标 runtime_connected=true；定义文件不证明运行事实。

候选实现完成后可用 `python tools/create-component.py --refresh work/example-skill --version 0.1.1` 绑定新入口；这仍是待审候选，不更新任何批准。旧排队批次不能因此静默变成新版本。

框架登记时将组件报告路径写入 framework-manifest.json；Agent 元数据使用同一路径。tools/verify_framework.py 和上下文加载器检查缺配置、少事件、错误归属与旧指纹，失败不得声明定义已准入。外部组件也经过相同检查。按原流程独立评价及审批后更新通行证，框架不因创建工具而自批新 Agent。

## 运行与回执

宿主在执行前绑定实际租户、来源、执行 Agent 快照、需求、持久 outbox、目标库和授权引用；模板不能充当绑定。调用每个 skill 时它仍属于实际 Agent 的步骤，不另造 Agent 身份。一个实际调用的 usage_key 只计一次；同一步骤由 Agent 和 skill 同时重复记账会被拒绝，应由主上报方提交，其他方引用。

Agent 本体上报的快照必须匹配组件 ID、版本及入口 SHA256；skill 的上报组件与实际执行 Agent 分别记录。完整候选依赖指纹仍由准入通行证保存，不能用入口指纹替代准入验证。

宿主负责在需求开始／结束、步骤开始／结束／失败／取消、消息、纠偏、质量返工和交接时调用 reporter 或等价连接器。运行中的步骤先报 running，结束时以 supersedes 报同逻辑步骤新版本。相关覆盖、缺失和用量沿用赫尔墨斯 v2 契约；供应商未给用量时保留 null+reason。上报代码本身不递归作为新业务步骤上报，也不重复创建赫尔墨斯反馈任务。

```powershell
python tools/hermes-report.py --outbox work/outbox.sqlite enqueue --tenant demo --registered agent:athena --binding work/actual-binding.json --batch-key stable-batch-1 --input work/events.jsonl
python tools/hermes-report.py --outbox work/outbox.sqlite flush --db work/data.sqlite
python tools/hermes-report.py --outbox work/outbox.sqlite status --tenant demo
```

目标 v2 台账先用 ledger.py init 创建；binding 的 sink_ref 与 outbox_path 使用实际绝对路径。生成组件的本地试验使用 --component-dir DIR 替代 --registered，绑定仍必须真实填写；这不授予候选生产运行权。

enqueue 只表示持久 pending。flush 校验组件、绑定、校验和并事务落库后记录 sent 与实际回执；失败保留 pending/error，限定批次重试。落库成功但回执写入前中断时，重试依赖 ledger 幂等，不重复统计。同批次 key 不同内容拒绝；更正内容须新批次及记录版本。组件变更后旧队列禁止静默换版本，需明确重映射并保留原证据。空队列不是成功上报证据。

outbox v2 持久保存尝试顺序：未尝试、最久未尝试的批次优先，失败批次保留并轮转，避免队首坏数据长期阻塞后续批次。读取旧 v1 队列时事务增加调度字段，原 payload、绑定及回执不变；共享实现变化导致的旧配置仍按上段拒绝静默升级。此本地机制不是企业高并发调度的验收结果。

步骤记录附 reporting_component，可用 --label component_id=ID、component_kind=skill 或 component_version=VERSION 查询；各字段基于上报归属，不把一个真实调用重复分摊相加。事件、原文和采样范围继续受实际数据权限约束，不默认发送外部网络。

## 启用判定与限制

created/configured、queued、delivered 是不同事实。生产启用需宿主验证真实身份、绑定及代表任务真实回执；还须通过失败重试和来源覆盖对账。缺绑定或不可持久排队时，宿主不得声称已开启受完整观测的奥林匹斯生产；未接通时保持候选／待接入，保留已有有效任务的恢复记录。

当前交付可运行的本地 outbox→SQLite 链路、创建模板与文件校验，没有接管 Codex／引擎的所有运行事件，也未部署企业连接器、后台发送服务或身份验证。纯提示词不能强制所有运行环境埋点；宿主必须调用此共享接口。奥林匹斯／宙斯采集内容仍仅作 reference，实际修改需要用户单独指令。

共工可按框架根 sync/POLICY.md 只读使用赫尔墨斯数据优化；用户已持续授权有效共工更新的完整同步。此前“单独指令”要求仍适用于自行提出和实施框架修改，不阻断已批准上游同步。数据读取工具为 sync/read_hermes.py，历史快照不改写。

用户明确豁免：无数据库时使用独立 extensions/hermes-files 模块，在目标 Git 仓库的 olympus-hermes-data 记录需求产出并随需求合入。该模块和数据不受共工同步覆盖；赫尔墨斯与共工使用同一文件分析入口。尚无目标仓库时只交付规则与工具，不创建生产数据。文件状态不冒充 SQLite 回执。
