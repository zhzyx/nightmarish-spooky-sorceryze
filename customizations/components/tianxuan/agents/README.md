# 天璇产品 Agent 候选

本目录定义天璇平台的产品级 Agent 候选，**不是**已准入的核心 Agent，也不修改 `framework/agents/` 或框架 manifest。

| Agent | 职责 | 与核心关系 |
| --- | --- | --- |
| 文曲（`wenqu`） | Markdown 权威文档、版本、归类、检索、导出、离线合并 | 复用谛听；新增定义待审查 |
| 多宝（`duobao`） | 仓库、分支、PR、评审、并发合入编排 | 复用开源 Git；新增定义待审查 |
| 司南·工单（`sinan-workorders`） | 工单模型、状态机、事件推进 | 基于现有司南扩展；不新建平行协调器 |

## 状态

全部为 `candidate_pending_review`，`runtime_connected: false`。

## 准入前置

1. 按 `framework/skills/gonggong-check/SKILL.md` 对每个 Agent/Skill 定义做生成前与准入前回查。
2. 用 `framework/templates/review-pass.json` 记录范围匹配的 review pass；自评不是批准。
3. 取得精确候选摘要与真实宿主授权后才可启用。
4. 本目录不产生工具权限、模型凭据或生产准入。

## 命名

新增 Agent/Skill 沿用“文曲/多宝/司南”风格；Skill 名称使用 `<agent>-<capability>`，例如 `wenqu-doc-authoring`。
