# 天璇产品 Agent 候选 · 审查与整改进度

本目录定义三个产品级 Agent 候选与三个 Skill 候选，均**未准入、未启用**。本文件记录独立审查结论与本轮整改，不构成批准。

## 独立审查结果（2026-11-14）

审查方式：独立子 Agent 只读审查，候选 commit `b7353f0a`，对照 `framework/FOUNDATION.md`、`gonggong-check`、`specs/governance-review.md`、元衡上游与现有核心 Agent。

结论：**6 项全部 `needs_changes`，无 pass**。

| 对象 | 结论 |
| --- | --- |
| 文曲 Agent | needs_changes |
| 多宝 Agent | needs_changes |
| 司南·工单 Agent | needs_changes |
| wenqu-doc-authoring | needs_changes |
| duobao-repo-review | needs_changes |
| sinan-work-order-management | needs_changes |

完整记录见 `data-collection/tianxuan-agents-review-20261114.json`。

## 本轮整改

1. **reporting 合同**：每个 Agent 与 Skill 新增 `component.json`、`reporting.json` 与 `reporting-binding.template.json`；policy/reporter 改为框架根相对路径，补齐 10 个事件、`entry_sha256` 与 7 项依赖指纹。已用 `framework/tools/reporting.mjs --component` 逐项校验，**6/6 通过**。
2. **注册与准入形状**：新增 `component.json`、`candidate_digest`、`admission.json`（`approved: false`），并在 `customizations/host-agents.json` 登记三条 candidate 条目，`approval: null`。
3. **合入与准入矛盾**：候选仅作为 candidate 合入 main；`admission.json` 与 host 登记均声明未批准，不追溯授权。准入需新候选摘要与授权批准人签署。
4. **司南·工单边界**：改为只负责工单模型、合法迁移与事件进度聚合；来源工单创建/关闭、派发、跨工单依赖与验收决定交还核心司南、宿主来源与有权验收者；移除不受支持的 `extends`。
5. **定义级证据**：补充测试与失败/取消/恢复覆盖（见下）；不再只引用单个测试文件。
6. **文曲 Skill**：frontmatter 约定补入 `request_id`，与 `wenqu.py` 和领域核心一致。

## 验证证据

- 领域核心 + HTTP：`pytest customizations/components/tianxuan/server` -> 34 passed
- 文曲：23 passed；多宝：8 passed；Gitea 客户端：25 passed（本地全量 143 passed + 25 subtests）
- 代表性任务：`server/test_e2e.py` 注册 → 需求落库 → 工单树 → 状态推进 → 进度 33% → AI 索引
- 失败/取消/恢复：
  - 文档版本冲突拒绝（409）
  - 非法工单状态迁移拒绝（409）
  - 冲突合并干净中止并保留仓库状态（多宝测试）
  - 回执未知不重发、保留占用（司南/派发契约）
- reporting：6/6 profile 通过 `framework/tools/reporting.mjs --component`

## 仍未完成

- 需对本轮修正后的 `candidate_digest` 做新的独立审查，并由授权批准人签署 review pass。
- 在此之前 `approval: null`、`review_pass: null`，任何文档或登记都不得被解读为已准入。
- 真实宿主身份、工具权限、模型凭据与生产执行授权仍由宿主核验。

## 审查入口

按 `framework/skills/gonggong-check/SKILL.md`，读取冻结纲领、元衡上游与 `specs/governance-review.md`；用 `framework/templates/review-pass.json` 记录 review pass，绑定精确候选摘要与范围。自评不是批准。
