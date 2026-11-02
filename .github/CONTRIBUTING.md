# Olympus 仓库协作入口

本约定适用于本仓库的所有贡献者：人工、IDE/CLI/引擎宿主、Agent、外部协作者；覆盖需求、设计、开发、缺陷、研究、测试、文档、维护及资产。技术细节沿用根目录 CONTRIBUTING.md 的 Godot 指南；本仓库分支及治理以本入口为准。

1. 先查本仓库已有 Issue；复用同一需求，关联在途工作，禁止重复派发。新内容先创建 Issue，明确原始需求、目标、范围、验收、依赖、责任人和稳定需求 ID。缺授权或目标待判断，不把建议/Issue 本身当执行授权。
2. 加载 `Olympus/AGENTS.md` 与职责相关入口；框架审查复用 Dike/Zeus，实际身份权限由宿主决定。已有有效源保持绑定；上游升级另建候选并完整同步，禁止修改旧批准以跳过检查。冻结框架和 Hermes 原件规则继续生效。
3. 开始实际工作时将工单置为 `status:in-progress` 并写执行责任及范围。独立任务并发，冲突文件单一写入，必要审查独立；不用额外完整历史或重复审查。开始、状态、依赖、决策、执行回执等真实事件触发一次跟进，无 cron、轮询或延时唤醒。
4. 需求文档放 `design-docs/` 并与 Issue 互链；实际事件调用已有 Hermes 文件入口写入 `olympus-hermes-data/`，来源/验证证据放 `data-collection/`。提交前执行组件 README 中的 Issue 门禁及适用业务测试。把记录、Git 提交、远程发布、谛听消费分别记账；未测用量留 null。
5. PR 面向仓库实际默认分支，填写 `.github/PULL_REQUEST_TEMPLATE.md`，关联同仓库 Issue。提交精确候选、实际检查结果及所需独立审查；仍未验收时用 `Refs`，不要写自动关闭关键字。候选有修改时仅重验受影响部分。
6. 只有验收与约定交付完成后才设置 `status:done` 并以 completed 关闭；取消用 `status:cancelled` 和 not_planned，不能冒充通过。父单逐项核对自己的验收，子单完成不自动关闭父单。失败保留原因、证据和下一事件，不添加定时重试。

标签使用唯一 `type:*`（`.github/labels.json`）和唯一 `status:*`（`.github/status-labels.json`）。待判断 needs-decision、计划 planned、处理中 in-progress、阻塞 blocked、待验收 in-review、完成 done、取消 cancelled。GitHub open/closed 是生命周期，status 表示执行状态；bug 属于 type。状态变更保留其他类别/业务标签，不覆盖并行编辑。

Issue 是状态权威；本地快照只记录读取时间与覆盖范围。Ariadne 当前文件账本适配器尚无 GitHub 源绑定，不得把本次 PR 检查当作 Ariadne 已自动派发。GitHub 事件接入及数据消费见 Issue #9；新上游同步见 #7；引擎同步回执优化见 #8。

PR 工作流只做真实工单关联检查，不执行 PR 提供的代码，也不伪装为远程框架/业务验收。所有贡献者必须执行上述本地框架与采集步骤。服务器侧不可绕过的保障需要仓库管理员将检查设为 required、保护默认分支并限制绕过；当前账号没有 admin 权限，此项尚未启用。AGENTS.md/文档本身不是操作系统访问控制，不能阻止任意编辑器直接写盘。
