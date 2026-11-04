# Issue 颗粒度与尾项结转

<!-- gonggong-request:issue-granularity-20261105 -->

用户原意：偃师设计完成后在设计中拆分任务，一个父 Issue 包含多个 sub-issue；子项提交后独立关闭，全部完成后关闭父项；阎罗发现少量尾项时按交付规则新建承接 Issue 并关闭旧 Issue。文档是溯源主线。

范围：本仓库 Issue 接入层规则、设计拆分模板、偃师与阎罗的宿主交接入口。不修改冻结纲领、元衡原件、历史准入和共享 Agent 定义；阎罗候选由 Issue #79 管理，本任务只衔接其规则。目标为 Windows/Git 文档契约，无引擎编译。所有相对路径以仓库根为基准。

验收：任务按可独立验证交付单元拆分；子项关闭有提交、检查、远端及文档证据；父级关闭逐项核对；尾项结转完整承接而不冒充完成；失败或并发变更保持旧单开放并可幂等恢复。文档引用、代表场景审查和既有门禁通过后交付；真实远端执行与本地规则分别记录。

实现与验证记录将在本档案追加。生产启用仍遵循当前有效框架和精确候选准入。

## 实现与职责衔接

工单：[Issue #84](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/84)，已实际完成 intake-only。规则见 [Issue 生命周期](../customizations/components/issue-workorders/issue-lifecycle.md)，模板见 [设计拆分记录](templates/issue-breakdown.md)，入口接入根 AGENTS、贡献指南、适配器 README 与需求模板。

本次为同一文档契约的小修订，规则与入口必须一起交付，保留单 Issue；未来产品设计中的多个独立交付单元按新规则建立原生 sub-issue。本次不批量重排已有 Issue，也未操作其他任务工作树。

阎罗 #79 工作树的 `customizations/components/issue-workorders/yanluo.md` 已有“多数完成或至多两个剩余模块”的判断。本次保留其触发依据，新增用户明确要求的结转关闭语义：done/completed 仅用于完成，cancelled/not_planned 用于容器已结转，用户目标由承接链持续跟踪。#79 尚在途，其旧条款“创建 follow-up 后旧单保持开放”需在整合时区分迁移进行中与承接已核实；此任务没有修改该工作副本或宣称其自动适配器已支持新语义。

验收采用文档场景审查：独立子项可关闭；本地提交不提前关闭；子项全 closed 但有 cancelled 不误关父单；所有验收和集成通过可关闭父单；少量尾项承接完整可结转；关系失败/未知/并发变更保留旧单；重试复用原编号。规则明确覆盖以上场景，属于契约审查，不是自动执行器行为测试。实际减少积压效果仍待后续交付观察。
