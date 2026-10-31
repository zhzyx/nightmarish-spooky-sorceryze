# 独立豁免：赫尔墨斯文件数据源

[规则与命令](extensions/hermes-files/README.md)：无数据库记录需求数据，目标 Git 仓库内独立命名为 olympus-hermes-data，作为需求产出合入。模块与数据均不被共工同步覆盖；待合入目标仓库后再创建真实数据目录。

# 奥林匹斯：共工的同步分发框架

共工为唯一上游；除名称映射及明确的分发接入外，不允许框架行为偏差。赫尔墨斯数据可由共工只读用于优化。详见 [同步与数据共享规则](sync/POLICY.md)。

本包为同步后候选，尚需独立准入；原批准原件见 source-history.zip。不存在后台自动部署服务。运行数据须存放在包外。

# 奥林匹斯框架

版本 0.8.1；冻结纲领 1.0；宙斯 0.4.1。所有 Agent，包括临时、派生和外部接入实例，均受宙斯统一控制，无例外。本索引用于发现，按任务加载相关规范。

## 当前组成

| 层级 | 当前内容与入口 |
| --- | --- |
| 冻结纲领 | [FOUNDATION.md](FOUNDATION.md)，不可修改 |
| 宙斯共同基础 | upstream/zeus：原则、Agent 模板、组织方法及契约，原件保持不变 |
| 治理与准入 | [GOVERNANCE.md](GOVERNANCE.md)、[奥林匹斯回查](skills/dike/SKILL.md)、[审查规范](specs/governance-review.md) |
| 3 个正式独立 Agent | [雅典娜](agents/athena/AGENT.md)：需求理解与文档设计；[忒弥斯](agents/themis/AGENT.md)：升级质量事件监察；[赫尔墨斯](agents/hermes/AGENT.md)：数据记录、分析与优化参考 |
| 9 项 skill | dike、metis、themis、iris、mnemosyne、cadmus、demeter、apollo、上游 hestia |
| 临时审查职能 | 阿斯特赖亚·框架审查：独立评价当前候选；不是第四个常设 Agent，不因命名获得权限 |
| 15 项专项规范 | 模块、客户方案、组织、项目状态、并发、代码、场景、质量、引擎适配、企业运行、治理审查、文档设计、质量职责、数据反馈、上报；路径与加载条件见 framework-manifest.json |
| 共享实现与记录 | tools、contracts、templates；雅典娜兼容代码在 integrations/athena-legacy；本版审查证据在 reviews |

组件版本以 framework-manifest.json 和各 Agent 元数据为准。所有组件路径相对本框架根。旧版本保留为历史来源，不把其中的 Agent、规范或批准自动并入当前清单。

## 使用与职责

先按客户目标、团队能力和约束选择模块，再按任务分工。雅典娜负责设计，业务主责负责实现，验证者签发质量结论，忒弥斯处理升级监察，赫尔墨斯记录和分析；[质量职责](specs/quality-responsibilities.md)保持单一主责。

奥林匹斯生产、组件创建变更和外部合入均执行奥林匹斯回查及宙斯评价。通行证绑定对象、版本、指纹、阶段、范围、独立证据与真实批准；模板不是批准，本地定义通过不授予未来任务或生产运行权限。

新组件通过 tools/create-component.py 或等价契约自带赫尔墨斯配置；共 12 份配置覆盖 3 个 Agent 和 9 项 skill。创建、配置、排队与取得落库回执分别记录，详见 [上报规范](specs/reporting.md)。赫尔墨斯对奥林匹斯／宙斯只保留 reference，调整须用户另行明确下令；其他子 Agent 优化候选仍走原授权和审查。

## 已验证与待接入

本地工具提供文件与准入一致性校验、上下文装配、组件创建、质量职责检查、SQLite 数据台账、持久 outbox 与落库回执。Python、Node 为运行依赖；雅典娜兼容工单工具另需 Git。

`python tools/verify_framework.py` 检查当前定义；`node tools/agent-context.mjs AGENT-ID HOST-MANDATE.json` 仅装配上下文。文件锁、JSON 通行证与绑定文本本身不是身份或权限安全根。

真实宿主自动采集、认证、预算和状态强制控制、企业数据连接器、生产容量及数据保留／恢复仍待部署验收。当前没有自动捕获全部 Codex 或引擎事件的后台服务。设计规范不代表 Godot、自研引擎或高并发生产系统已经实现；精简入口也不代表已经证明理解效率或 token 成本改善。
