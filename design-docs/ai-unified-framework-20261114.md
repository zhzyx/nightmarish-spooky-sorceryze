# AI 公共运行框架与 M/C/V 分离

## 当前结论

用户于 2026-11-14 授权落地 AIChat、马良、天枢共用的 AI 框架，并要求完成提交、推送、main 合入，将公共契约纳入 AGENTS.md 的按需加载流程。当前责任者为本次 Codex 会话，使用独立工作树，基线为 d3177311f67720fc5ef32a399f2398ce2ab0fb67。关联工单为 [#1086](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1086)。实现、Windows 原生构建和三模块集成回归已完成。验收结果由本文末尾的候选证据及工单交付回执共同追踪。

需求 ID 为 ai-unified-framework-20261114，类别为 type:development。原始需求为统一 AICore、UI 行为和 UI 表现，使后续 AINative 工作流通过公共框架接入。

## 范围与实现

公共核心管理版本化运行身份、模型与来源快照、运行状态、序号和终态。宿主适配器管理 Godot 数据映射及事件。核心使用引擎无关的 C++ 数据类型。既有 Provider、资产执行器、工单存储及权限实现通过适配器接入。

AIChat 抽出传输与运行 Controller。马良抽出进程、轮询、取消和恢复 Controller。天枢抽出会话绑定、路由回执和执行事件 Controller。各 View 负责控件、输入采集、状态呈现和预览。现有入口保留兼容转发，业务状态只有一个责任者。

公共运行接口由 AIWorkflowRuntime 提供 begin_run、publish、cancel、snapshot。事件包含 schema_version、workflow、scope、run_id、request_id、generation、sequence、kind、state、model、binding、payload。begin_run 冻结模型和绑定，同请求同内容幂等，异内容拒绝。publish 核对 run_id 与 generation，终态单调，晚到结果拒绝。模型与绑定只含可公开元数据，凭据留在传输适配器。

首批事件为 run_started、progress、text_delta、tool_requested、artifact_ready、completed、failed、cancelled。运行状态为 running、waiting_tool、waiting_confirmation、reconciling、succeeded、failed、cancelled。领域执行器保留自己的详细状态，通过适配器映射到公共运行状态。

公共契约正文进入 ai_core/README.md，仓库 AGENTS.md 通过现有 Markdown/engine-core/README.md 模块索引路由至该正文，Markdown/sources/README.md 登记权威来源。后续新增 AI 工作流先读取该契约，复用运行框架并提供自己的领域适配器。

2026-11-14 先后整合主线 bb6236c7、627d49f1 、f83f680a 和 99a8e8cb。接收模块化 AGENTS 导航，保留马良已下线 GPT 网格模式的主线行为，并整合天选独立变更。后续保留主线分片交付、操作者绑定和节点模型选择修复，对重叠文件完成独立复核及定向重验。公共契约沿现行导航加载。

## 兼容与验证

目标为 Windows x64 / MSVC 当前编辑器。保留 HTTP/Responses、CLI、独立会话和节点模型选择、旧历史及 Provider 快照、权限确认、任务幂等和取消恢复语义。验证只使用隔离配置、临时项目与本机测试服务。

验收覆盖公共核心独立编译和状态机、并行运行隔离、取消后迟到事件、终态去重、模型快照冻结、原入口真实调用新 Controller、UI 重建后的运行查询，以及相关 AIChat/马良/天枢回归。原生和嵌入脚本均执行实际候选构建。Provider 生成质量和供应商账号可用性由既有业务验收负责，本次验证重构前后的接口行为。

## 工作拆分

公共核心、AIChat、马良、天枢四项按互不重叠的文件由不同工作者实施。共享契约和同一原生候选的跨入口验收构成一条集成链，使用本工单一个集成 PR，分别记录各项证据和独立审查。编译/注册/公共文档由当前责任者整合。

## 验收清单

- 引擎无关核心与统一版本化事件生效，成功、失败、取消、幂等和隔离检查通过。
- AIChat 正常发送、停止及响应经独立 Controller 和公共核心。
- 马良正常启动、轮询、取消、重试及恢复经独立 Controller 和公共核心。
- 天枢路由/执行状态经独立 Controller 和公共核心，聊天挂载仅属于 View。
- 旧入口和存量数据通过相关回归，候选 Windows 编辑器构建与 headless 验证通过。
- 公共契约通过 AGENTS.md 按需可达，单一正文与链接检查通过。
- 独立审查、正式门禁、PR/CI/main 回读和本工单收尾完成。

## 实际证据

候选构建、原生与集成回归、已修复问题和验证边界记录在 [验证证据](../data-collection/ai-unified-framework-1086-verification.json)。独立审查及精确输入摘要记录在 [审查证据](../data-collection/ai-unified-framework-1086-review.json)，新增模块的独立编译和构建失效验证记录在 [构建证据](../data-collection/ai-unified-framework-1086-build-impact.json)。

最终 PR、精确候选 CI、main 合入提交与七项验收终态在 [工单 #1086](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1086) 登记和回读。原始失败、修复后的命令输出和本机环境诊断保留在本任务的私有验收归档。

严格编译修复后的最新候选记录在 [复验结果](../data-collection/ai-unified-framework-1086-ci-fixed-verification.json)、[独立复核](../data-collection/ai-unified-framework-1086-ci-fixed-review.json) 和 [构建复验](../data-collection/ai-unified-framework-1086-ci-fixed-build-impact.json)。原始验收记录保留供追溯。
