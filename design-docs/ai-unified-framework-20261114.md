<!-- gonggong-request:ai-unified-framework-20261114 -->

# AI 公共运行框架与 M/C/V 分离

## 当前结论

用户于 2026-11-14 授权落地 AIChat、马良、天枢共用的 AI 框架，并要求完成提交、推送、main 合入，将公共契约纳入 AGENTS.md 的按需加载流程。用户已于本会话明确交接全部实现与交付；当前接收者 Sail-Li，Issue #1086，工作树基线 7acdf07ca4c89251527a392c754a536af2094b6a。当前实现进行中，未完成整体验收。

需求 ID 为 ai-unified-framework-20261114，类别为 type:development。原始需求为统一 AICore、UI 行为和 UI 表现，使后续 AINative 工作流通过公共框架接入。

## 范围与实现

公共核心管理版本化运行身份、模型与来源快照、运行状态、序号和终态；宿主适配器管理 Godot 数据映射及事件。核心使用引擎无关的 C++ 数据类型。既有 Provider、资产执行器、工单存储及权限实现通过适配器接入。

AIChat 抽出传输与运行 Controller。马良抽出进程、轮询、取消和恢复 Controller。天枢抽出会话绑定、路由回执和执行事件 Controller。各 View 负责控件、输入采集、状态呈现和预览。现有入口保留兼容转发，业务状态只有一个责任者。

公共运行接口由 AIWorkflowRuntime 提供 begin_run、publish、cancel、snapshot。事件包含 schema_version、workflow、scope、run_id、request_id、generation、sequence、kind、state、model、binding、payload。begin_run 冻结模型和绑定，同请求同内容幂等，异内容拒绝。publish 核对 run_id 与 generation，终态单调，晚到结果拒绝。模型与绑定只含可公开元数据，凭据留在传输适配器。

首批事件为 run_started、progress、text_delta、tool_requested、artifact_ready、completed、failed、cancelled。运行状态为 running、waiting_tool、waiting_confirmation、reconciling、succeeded、failed、cancelled。领域执行器保留自己的详细状态，通过适配器映射到公共运行状态。

公共契约正文进入 ai_core/README.md，仓库 AGENTS.md 路由至该正文。外层工作区的模块导航在现有 EngineCore 模块登记入口。后续新增 AI 工作流先读取该契约，复用运行框架并提供自己的领域适配器。

## 兼容与验证

目标为 Windows x64 / MSVC 当前编辑器。保留 HTTP/Responses、CLI、独立会话和节点模型选择、旧历史及 Provider 快照、权限确认、任务幂等和取消恢复语义。验证只使用隔离配置、临时项目与本机测试服务。

验收覆盖公共核心独立编译和状态机、并行运行隔离、取消后迟到事件、终态去重、模型快照冻结、原入口真实调用新 Controller、UI 重建后的运行查询，以及相关 AIChat/马良/天枢回归。原生和嵌入脚本均执行实际候选构建。Provider 生成质量和供应商账号可用性由既有业务验收负责，本次验证重构前后的接口行为。

## 工作拆分

公共核心、AIChat、马良、天枢四项按互不重叠的文件由不同工作者实施。共享契约和同一原生候选的跨入口验收构成一条集成链，使用本工单一个集成 PR，分别记录各项证据和独立审查。编译/注册/公共文档由当前责任者整合。

## 验收清单

- [ ] 引擎无关核心与统一版本化事件生效，成功、失败、取消、幂等和隔离检查通过。
- [ ] AIChat 正常发送、停止及响应经独立 Controller 和公共核心。
- [ ] 马良正常启动、轮询、取消、重试及恢复经独立 Controller 和公共核心。
- [ ] 天枢路由/执行状态经独立 Controller 和公共核心，聊天挂载仅属于 View。
- [ ] 旧入口和存量数据通过相关回归，候选 Windows 编辑器构建与 headless 验证通过。
- [ ] 公共契约通过 AGENTS.md 按需可达，单一正文与链接检查通过。
- [ ] 独立审查、正式门禁、PR/CI/main 回读和本工单收尾完成。

## 实际证据

待执行后追加原始命令、结果、候选和交付引用。

## 2026-11-14 接收后的实施边界

引擎无关核心和薄 Godot 适配器由原生工作者实施。Controller 采用已固定的 begin_run/publish/cancel/snapshot Dictionary 合同，公开元数据与凭据分离；共享构建、注册及跨入口验证由当前责任者整合。三个 View 的业务状态实际迁出，不用增加转发壳替代重构。独立子任务保留原父项验收并汇入同一集成候选。

## 本次收尾（用户要求不再展开）

用户要求立即收尾，停止扩展实现。当前是可恢复的阶段候选，#1086 未完成，不能据此关闭整单。

- 已实现统一核心、Godot 适配器、天枢与马良 Controller，以及 AIChat 的传输、会话、权限、工具和引擎/交付执行器迁移。
- 本机原生构建通过；最终 36 个 C++ 用例、801 个断言通过，无错误输出；实际原生编辑器的天枢 27 项与马良 8 项检查通过。马良独立审查所发现四项缺陷已修复，45 项回归通过，修复后独立复核尚待执行。
- AIChat 隐藏 Dock 和部分后台所有权尚未迁出，#1211/#1086 的完整 M/C/V 分离不成立。#1227 工单向导/点火器未派发、未实现，保留待办。
- 未完成：最终独立审查、完整旧入口回归、Windows/MSVC 精确候选 CI、main 合入与整体验收。保留已发现的 #1219/#1220 跟踪，不以本机测试替代交付。
- 未切换有效编辑器安装，未调用供应商或生产发布；保留本工作树、冻结源和原始验证证据，未删除其他任务未交付资源。
