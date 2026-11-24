# GongGong 仓库协作入口

已暂存本工单候选的仓库写入者，按[协作者快速签发和自动提交](../customizations/components/issue-workorders/yanluo.md#协作者快速签发和自动提交)用本人账号运行交付入口。由同一条命令完成门禁、提交、签发与 PR 创建。

设计中的独立交付单元按[生命周期](../customizations/components/issue-workorders/issue-lifecycle.md)拆分；不可分的小修复保留单 Issue。该规约统一定义验收关闭与尾项结转。

本约定适用于本仓库的所有贡献者：人工、IDE/CLI/引擎宿主、Agent、外部协作者；覆盖需求、设计、开发、缺陷、研究、测试、文档、维护及资产。技术细节遵循根目录 CONTRIBUTING.md 的项目贡献指南；本仓库分支及治理以本入口为准。

任务开始与范围变更遵循 [执行范围与验证成本](../customizations/components/issue-workorders/execution-policy.md)，在原需求文档记录最小验证计划、证据复用依据和完成条件；不另造状态账本。

授权、普通框架校验与新定义准入、独立审查与 GitHub approval 的含义见[术语与触发条件](../customizations/platforms/process-management/repository/execution-policy.md#术语与触发条件)。按原授权连续执行，保留用户范围限制，不逐阶段重复确认。

宿主开发必须在开发模型/生产工具执行前回读同仓库真实 Issue，校验稳定需求 ID、租户、类别、有效执行状态和 workspace:gonggong；查询失败仅阻止依赖该回读的生产步骤，按夸父入口处理；独立已授权项继续。Godot GongGong 页面填写 Issue 编号和稳定 ID，其他宿主使用 issue-workorders 的 intake-only 契约。data-collection 中的真实来源、证据和回执与 gonggong-diting-data 文件事件均为本次需求必须提交的产物；代码提交不能替代数据交付。普通引擎会话先由现有 Yanshi／ClarifyFeature 受限整理需求并自动建单或更新原单；该阶段只允许需求文档与 Issue 跟踪，不开放开发或生产工具，恢复开发仍须真实工单回读。见 [当前需求入口协议](../customizations/components/godot-host/HOST_PROTOCOL.md)。提交前检查 index，提交后检查 HEAD；禁止删除原始采集历史，纠正追加记录。

1. 先查本仓库已有 Issue；复用同一需求，关联在途工作，禁止重复派发。新内容先创建 Issue，明确原始需求、目标、范围、验收、依赖、责任人和稳定需求 ID。缺授权或目标待判断，不把建议/Issue 本身当执行授权。
2. 按职责加载当前规则；普通任务执行已安装框架的正式校验。只有生成、更新或接入 Agent/Skill/框架候选时，读取其 AGENTS 与 GonggongCheck/Yuanheng 治理入口，按精确对象准入；不改旧批准。冻结框架和 Diting 原件保持不变。
3. 开始实际工作时将工单置为 `status:in-progress` 并写执行责任及范围。独立任务并发，冲突文件单一写入，必要审查独立；不用额外完整历史或重复审查。开始、状态、依赖、决策、执行回执等真实事件触发一次跟进，不新增 cron 或定时唤醒；原运行的等待按执行策略处理。
4. 需求文档放 `design-docs/` 并与 Issue 互链；实际事件调用已有 Diting 文件入口写入 `gonggong-diting-data/`，来源/验证证据放 `data-collection/`。提交前执行组件 README 中的 Issue 门禁及适用业务测试。把记录、Git 提交、远程发布、谛听消费分别记账；未测用量留 null。
5. 本地必要验证通过后，在同次任务中自动开始正式门禁、提交、提交后核验、推送及 main 合入推进，无需用户再次催促；具体执行与真实阻塞处理见执行策略“本地验证通过即推进 main”。PR 面向 main，填写 `.github/PULL_REQUEST_TEMPLATE.md`，关联同仓库 Issue。提交精确候选、实际检查结果及所需独立审查；仍未验收时用 `Refs`，不要写自动关闭关键字。候选有修改时仅重验受影响部分。合入后取得远端回读再收尾。
6. 只有验收与约定交付完成后才设置 `status:done` 并以 completed 关闭；取消用 `status:cancelled` 和 not_planned，不能冒充通过。父单逐项核对自己的验收，子单完成不自动关闭父单。失败保留原因、证据和下一事件，不添加定时重试。

标签使用唯一 `type:*`（`.github/labels.json`）和唯一 `status:*`（`.github/status-labels.json`）。待判断 needs-decision、计划 planned、处理中 in-progress、阻塞 blocked、待验收 in-review、完成 done、取消 cancelled。GitHub open/closed 是生命周期，status 表示执行状态；bug 属于 type。状态变更保留其他类别/业务标签，不覆盖并行编辑。

Issue 是状态权威；本地快照注明读取时间与范围。当前 GitHub 来源绑定、真实 start/ack/terminal 与消费分别见[来源与执行接入](../customizations/components/issue-workorders/README.md#当前来源与执行接入9-最终对账)；旧 registry 标志不表示当前宿主未接通，配置和 PR 检查也不证明已派发。

`gonggong-issue-gate.yml` 只做真实工单关联检查，不执行 PR 代码，也不证明框架或业务验收；其他模块 CI 会按各自契约执行候选检查。所有贡献者必须执行上述本地框架与采集步骤。普通 PR 只运行注册表选择的模块测试，审查人必须核对选择 artifact 与真实结果，详见[模块化 CI 与状态检查](../Markdown/testing/ci-modules.md)。服务器强制保障由有权维护者配置，实际状态以远端回读为准；日常交付不据此新增修改保护配置的前置步骤。AGENTS.md/文档本身不是操作系统访问控制，不能阻止任意编辑器直接写盘。
