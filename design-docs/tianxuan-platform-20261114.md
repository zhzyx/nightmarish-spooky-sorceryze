# 天璇：AI-native 在线管理平台（共工模块）

> 模板：复制并填写后才是实际需求，不作为生产事件。

## 当前结论

- 用户要达成的结果：在共工框架与元衡治理下新增“天璇”在线管理模块，把 AI-native 云文档（文曲）、工单（司南扩展）与自建代码仓库（多宝）整合为一套系统，支持注册、在线创建/编辑文档、偃师需求沉淀、工单自动推进与进度同步、模型调用。
- 已确认范围：单组织首版、≤10 人、文档量万级、自动归类、多语言、离线编辑（先 Web，后续进 Godot）；文档以 Markdown 为唯一权威、AI 阅读效率优先；仓库直接复用开源 Git 方案并做高并发优化；工单基于现有司南扩展，最小自定义、单独工单 Agent；扁平化中国风 + 毛玻璃；不专门做无障碍；验收沿用现有 Agent。
- 剩余验收与证据入口：**#1188**（单一 TODO 入口）；交付状态见下节。
- 下一步：按 #1188 完成部署、TLS、运行时接线与已知缺陷收口；核心实现已交付。
- 需求 ID：`tianxuan-platform-20261114`
- Issue：https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1085
- 类别：`type:requirement`
- 责任人：已由当前实现的协作会话承担；后续尾项见 #1188

## 交付状态（2026-11-14）

- 核心实现已合入 main（最新 `a39ae340`）：`customizations/components/tianxuan/`、`apps/tianxuan/`、`deploy/`。
- 验证：server **114 passed**、Gitea client **87 passed**、Web `next build` 通过、`demo.py` 端到端通过。
- 真实 Gitea 28.3.0：仓库状态/列表/创建/读取通过；需求 Git 落库与 commit 回读一致。
- 已准入：wenqu / duobao / sinan-workorders 及 3 个 parent-scoped Skill（PR #1186）；`runtime_connected` 仍为 false。
- 视觉证据：`D:\GongGong-work\tianxuan-visual\shots\`（本地验收资产，不随仓库提交）。
- 单一剩余工作入口：**#1188**。
- 已关闭/归并以保证单一入口：
  - #1085：父需求，核心交付完成关闭；
  - #1092：夸父 CI 跟踪，随父单关闭；
  - #1115 / #1116 / #1117 / #1118：未修复或部分满足的验收项已并入 #1188，原证据与验收措辞保留。

## 原始需求与目标

用户要求创建类似 Confluence / 飞书云文档的在线文档系统，AI native 且以 AI 效率优先、人类查看为辅；同时整合类似 Jira/Git 的工单与在线代码仓库，三者成为一套系统；模仿苹果视觉与交互（最终确认改为扁平化中国风 + 毛玻璃），需要则产出素材；允许用户在平台内用偃师创建需求并落库（线上保存 Markdown 设计文档），产生工单并自动推进、同步进度；支持模型调用。所有内容基于已有元衡审查与共工框架开发。

## 范围与非目标

**范围内**

- 天璇产品壳：注册/登录、工作台、全局搜索、通知、设置。
- 文曲：Markdown 文档创建/编辑/协同/版本/评论/导出/自动归类/语义检索。
- 司南扩展：项目、工单、状态机（最小可配置）、看板、依赖、事件驱动推进。
- 多宝：仓库创建/浏览/提交/分支/PR/评审，复用开源 Git 实现并做并发合入优化。
- 跨模块闭环：偃师需求 → Markdown 落库 → 工单树 → 事件推进 → 代码关联 → 验收。
- 模型调用：BYOK + 平台额度、计量、审计。
- 多语言（中/英）、离线编辑（Web 优先）。
- 扁平化中国风 + 毛玻璃设计系统与素材清单（AI 提示词交付给用户生成）。

**非目标（首版）**

- 多组织计费与复杂租户套餐。
- 移动端原生 App。
- 无障碍专项（用户明确不专门做）。
- 从零实现 Git 协议；复用开源实现。
- 首版不把天璇嵌入 Godot，仅预留接口。

## 设计方案

### 1. 模块结构

- 产品模块：`customizations/components/tianxuan/`（`module.json`、`README.md`、`build-impact.json`）
- 文档子模块：`customizations/components/tianxuan/wenqu/`
- 仓库子模块：`customizations/components/tianxuan/duobao/`
- 工单子模块：`customizations/components/tianxuan/sinan-workorders/`
- Web 前端：`apps/tianxuan/`（Next.js）
- 后端：`customizations/components/tianxuan/server/`（FastAPI）
- 新增 Agent 定义按共工框架生成，遵循 `framework/AGENTS.md` 与 `gonggong-check`。

### 2. 角色与 Agent

| 角色 | 来源 | 职责 |
| --- | --- | --- |
| 偃师 | 复用 | 需求澄清、设计文档、验收标准 |
| 文曲 | 新增 | 文档创建/编辑/归类/检索/版本与评审批次 |
| 多宝 | 新增 | 仓库、分支、PR、评审、并发合入编排 |
| 司南 | 扩展 | 工单派发、依赖、进度、自动推进 |
| 夸父 | 复用 | 质量事件与排障 |
| 谛听 | 复用 | 事件、回执、审计 |
| 合契 | 复用 | 多工作者/多分支整合 |

新增 Skill 命名沿用“文曲/多宝”风格；所有新增 Agent/Skill 必须先经 `skills/gonggong-check` 审查并取得精确候选准入，不得自行批准。

### 3. 文曲（文档）

- 唯一权威：Markdown（frontmatter + 正文 + 稳定标题锚点）。
- AI 阅读优先：结构化元数据、稳定 ID、摘要、块索引、向量检索。
- 自动归类：基于标题/正文/引用/工单关联的规则 + 模型分类，人工可纠正。
- 协同：Yjs/Hocuspocus 实时协同；版本快照与 diff；评论与建议模式。
- 导出：md / pdf / docx / html。
- 离线：本地草稿队列 + 冲突检测，联网后合并。
- 搜索：全文 + 语义（pgvector）。

### 4. 多宝（代码仓库）

- 复用开源 Git 服务（Gitea/Forgejo 或 go-git 封装），不重写协议。
- 高并发：仓库分片、读写分离、合入队列、锁粒度到分支/路径、批量评审。
- AI：代码检索、PR 摘要、审查建议、冲突辅助、工单自动关联。
- 权限：租户/仓库/分支/路径级；保护分支与合并策略。

### 5. 司南（工单）

- 在现有司南能力上扩展，不新建平行协调器。
- 最小自定义：固定核心字段 + 有限自定义字段；状态机由项目模板决定。
- 单独工单 Agent 身份，复用司南的派发/依赖/进度能力。
- 自动推进：事件（工单/文档/代码/CI）→ 状态迁移规则 → 提议或执行（按 AI 自主边界）。
- 文档 ↔ 工单双向链接。

### 6. 天璇（产品壳与 UI）

- 深色优先、扁平化中国风、毛玻璃材质、克制动效。
- 页面：认证、工作台、文档空间/编辑器、工单看板/详情、仓库/PR、搜索、通知、设置、AI 面板。
- 多语言：中/英；文案 token 化。

### 7. 数据与事件

- PostgreSQL：租户、用户、成员、空间、文档、版本、评论、项目、工单、仓库元数据、模型与用量、审计。
- 事件表 + SSE/Webhook；谛听回执。
- Git 对象由 Git 服务管理，平台存元数据与授权。

### 8. AI 工具面

`doc.search/read/create/update/comment/export`、`issue.search/create/update/transition/link/bulk_create`、`repo.tree/read/commit/branch/pr.create/pr.review`、`requirement.clarify/persist/plan_tickets`、`search.global/semantic`、`model.chat/embed`。全部幂等、范围化、可审计。

### 9. 多语言 / 离线 / Godot 集成

- 多语言：前端 i18n + 后端错误码；文档语言元数据。
- 离线：IndexedDB 草稿 + 冲突合并；首版仅 Web。
- Godot：预留桥接接口与只读视图，后续接入编辑器。

### 10. 治理与准入

- 所有新增 Agent/Skill 生成前与准入前回查 `skills/gonggong-check`；保存 review pass。
- 新模块按 `customizations/module-boundaries.md#新增模块的构建边界与验收` 记录 `build-impact.json` 并执行对应检查。
- 工单门禁：建单 → intake 回读 → 实现 → 正式门禁 → 提交/推送/合入。
- 验收沿用现有 Agent（司南协调、偃师设计、夸父质量、谛听证据）。

## 依赖及风险

- 新增 Agent/Skill 的准入是硬前置，不能用本地测试替代。
- 多宝高并发合入与 Git 服务选型是最大工程风险。
- 离线冲突合并与实时协同的边界需实测。
- 多语言与文档自动归类的准确率需验收样本。
- 天璇为大型模块，需拆父 Issue 与可独立交付的 sub-issue。

## 验收标准

- [x] 新用户注册并进入单组织工作台。
- [x] 创建/编辑 Markdown 文档，AI 可读、可检索、可自动归类。
- [x] 偃师生成需求文档并落库，自动创建工单树。
- [ ] 工单按事件自动推进，文档与工单双向链接。（状态机/评论/看板已实现；事件自动推进与双向链接尾项见 #1188）
- [ ] 多宝完成仓库创建、提交、分支、PR、评审，并支持并发合入。（仓库/分支/PR/合并已实现；评审与并发合入策略尾项见 #1188）
- [ ] 模型调用（BYOK + 额度）可用且计量/审计留证。（网关/预算/用量已实现；真实 provider 调用尾项见 #1188）
- [ ] 中英文切换可用；离线草稿可合并。（离线草稿与三方合并已实现；i18n 尚未实现，见 #1188）
- [x] 视觉符合扁平化中国风 + 毛玻璃，素材清单与提示词交付。
- [x] 全部新增 Agent/Skill 通过共工审查与精确候选准入。

## 验证与采集证据

引用实际文件、提交和事件，不填写估算用量。验收证据在实现后按工单逐项回填到 `data-collection/` 与 `gonggong-diting-data/`。
