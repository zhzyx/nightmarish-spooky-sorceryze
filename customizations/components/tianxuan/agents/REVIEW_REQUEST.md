# 天璇产品 Agent 候选 · 审查与整改记录

本目录定义三个产品级 Agent 候选与三个 Skill 候选，均**未准入、未启用**。本文件记录两轮独立审查与整改，不构成批准。

## 审查记录

| 轮次 | 审查对象 | 结论 | 记录 |
| --- | --- | --- | --- |
| 第 1 轮 | `b7353f0a` | 6 项 `needs_changes` | `data-collection/tianxuan-agents-review-20261114.json` |
| 第 2 轮 | `526ae131` | 6 项 `needs_changes` | `data-collection/tianxuan-agents-review2-20261114.json` |

两轮均由独立子 Agent 只读审查，对照 `framework/FOUNDATION.md`、`gonggong-check`、`specs/governance-review.md`、元衡上游与现有核心 Agent。

## 整改 2（本轮）

1. **候选摘要可复现**：按 `framework/tools/admission.mjs` 的算法（按路径 ordinal 排序、`path + NUL + 文件 SHA256 + LF`、显式 `candidate_files`）重算摘要：
   - 文曲 `f5a3c422149a6ba9a6ceca8ef5dd10e4f51bce8077d5c6a2d88789ec2abb7c86`
   - 多宝 `83a0455896f4ec821ea2674f7845c7a38c1dc4f4577692277bc40511dc49c4c2`
   - 司南·工单 `e77011ad30006fb4f0537f3881786e40f1e1d2c157a3e4b4b644ee5e9b76d71a`
2. **注册不污染签名宿主登记**：撤回对 `customizations/host-agents.json` 的修改（其哈希被 `yanluo_host.py` 的 `host_registry_sha256` 固定，改动会使在途签名授权漂移），改为产品级 `agents/host-registry.json`，并说明原因。
3. **证据纠偏**：
   - 服务端 33 passed；文曲 23；多宝 8 tests + 25 subtests；Gitea 83；全量 147 + 25 subtests
   - 本轮**未新增测试**，只引用现有测试；不把“补充测试”写成事实
   - 取消：当前切片没有取消流程与取消测试，**未覆盖**
   - 未知回执不重发：只有契约与现有派发测试，不是本候选的测试
   - `plan_tickets` 属于核心 `tianxuan_core`，不属于本候选；候选只验证状态迁移与进度聚合
4. **司南边界**：`agent.json` 的 scope 移除 `dependencies`；来源创建、派发、依赖与验收仍归核心司南与有权验收者。
5. **Skill 准入记录**：三个 Skill 各新增 `admission.json`，标明 `parent_scoped_pending`。
6. **组件契约**：六个 `component.json` 补 `binding_template`，与 `create-component.py` 输出一致。

## 当前状态

- reporting：6/6 profile 通过 `framework/tools/reporting.mjs --component`
- 注册：`agents/host-registry.json` 三条 candidate 条目，`approval: null`
- `admission.json`：`approved: false`、`approver: null`
- `review_pass: null`，不存在任何批准记录

## 仍未完成

- 需对整改 2 的新摘要做第 3 轮独立审查，并由授权批准人签署精确候选的 review pass。
- 历史 `b7353f0a` 未经准入即合入 main，需所有者决定如何记录或回退；不追溯授权。
- 取消流程与取消测试尚未实现。
- 真实宿主身份、工具权限、模型凭据与生产执行授权仍由宿主核验。

## 审查入口

按 `framework/skills/gonggong-check/SKILL.md`，读取冻结纲领、元衡上游与 `specs/governance-review.md`；用 `framework/templates/review-pass.json` 记录 review pass，绑定精确候选摘要与范围。自评不是批准。
