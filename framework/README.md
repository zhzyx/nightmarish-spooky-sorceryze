# 共工框架

版本 0.9.2（统一候选，待精确准入）；冻结纲领 1.0；元衡 0.4.1。所有 Agent，包括临时、派生和外部接入实例，均受元衡统一控制，无例外。本索引用于发现，按任务加载相关规范。

## 当前组成

| 层级 | 当前内容与入口 |
| --- | --- |
| 冻结纲领 | [FOUNDATION.md](FOUNDATION.md)，不可修改 |
| 元衡共同基础 | upstream/yuanheng：原则、Agent 模板、组织方法及契约，原件保持不变 |
| 治理与准入 | [GOVERNANCE.md](GOVERNANCE.md)、[共工回查](skills/gonggong-check/SKILL.md)、[审查规范](specs/governance-review.md) |
| 核心独立 Agent | [偃师](agents/yanshi/AGENT.md)：需求理解与文档设计；[夸父](agents/kuafu/AGENT.md)：阻塞优先处置与升级质量事件监察；[谛听](agents/diting/AGENT.md)：数据记录、分析与优化参考；[司南](agents/sinan/AGENT.md)：通用任务协调；[合契](agents/heqi/AGENT.md)：通用协作与成果整合。具体准入状态以登记表与当前候选为准 |
| 按需 skill | gonggong-check、clarify-feature、kuafu、data-collect、data-store、data-label、data-classify、data-analyze、上游 yuanheng-organize |
| 临时审查职能 | 獬豸·框架审查：独立评价当前候选；不因临时审查职能增加常设 Agent，不因命名获得权限 |
| 专项规范 | 模块、客户方案、组织、项目状态、并发、代码、场景、质量、引擎适配、企业运行、治理审查、文档设计、质量职责、数据反馈、上报、跨模型运行；路径与加载条件见 framework-manifest.json |
| 跨模型本地运行 | [运行规范](specs/model-runtime.md)、由已选择的宿主实现模型评测、传输、执行及采集 |
| 共享实现与记录 | tools、contracts、templates；偃师兼容代码在 文档平台兼容模块；本版审查证据在 reviews |

组件版本以 framework-manifest.json 和各 Agent 元数据为准。所有组件路径相对本框架根。旧版本保留为历史来源，不把其中的 Agent、规范或批准自动并入当前清单。

## 使用与职责

先按客户目标、团队能力和约束选择模块，再按任务分工。偃师负责设计，业务主责负责实现，验证者签发质量结论，夸父处理阻塞清障与升级监察，谛听记录和分析；[质量职责](specs/quality-responsibilities.md)保持单一主责。

仅生成 Agent／skill 定义及接入这些定义时执行共工回查及元衡评价；普通业务生产不触发该审查。通行证绑定对象、版本、指纹、阶段、范围、独立证据与真实批准；模板不是批准，本地定义通过不授予未来任务或生产运行权限。

新组件通过 tools/create-component.py 或等价契约自带谛听配置；配置覆盖已登记 Agent 和 skill，数量以当前登记表与实际检查为准。创建、配置、排队与取得落库回执分别记录，详见 [上报规范](specs/reporting.md)。谛听对共工／元衡只保留 reference，调整须用户另行明确下令；其他子 Agent 优化候选仍走原授权和审查。

## 已验证与待接入

本地工具提供文件与准入一致性校验、上下文装配、组件创建、质量职责检查、SQLite 数据台账、持久 outbox 与落库回执。Python、Node 为运行依赖；偃师兼容工单工具另需 Git。

`python tools/verify_framework.py` 检查当前定义；`node tools/agent-context.mjs AGENT-ID HOST-MANDATE.json` 仅装配上下文。文件锁、JSON 通行证与绑定文本本身不是身份或权限安全根。

0.9提供独立于Codex的本地Python运行器：三种文本协议、签名委托、能力路由、调用预算、持久状态、受限资源读取和自动投影谛听。配置真实模型、live代表任务证据及有效授权后，实际任务可经该入口运行，不要求GPT或OpenAI SDK；协议模拟通过不等于真实模型认证。

当前没有自动捕获全部Codex或引擎事件的后台服务。运行器之外的身份认证、全局预算、企业连接器、生产并发及数据保留／恢复仍待部署验收。设计规范不代表Godot、自研引擎或高并发生产系统已实现；精简入口也不代表已证明理解效率或token成本改善。
