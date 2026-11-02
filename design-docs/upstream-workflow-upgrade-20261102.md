# Olympus 同步共工交付与司南文档同步优化，保持既有发布可用

工单：https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/7

<!-- olympus-request:upstream-workflow-upgrade-20261102 -->

来自用户要求的 Olympus 优化缺口。当前 Olympus 固定已批准来源快照，Ariadne 0.4.0；共工新增交付检查及司南 0.4.1 文档同步。旧发布可用不代表已包含新上游。

状态：计划中；需先固定完整上游、隔离生成候选，再检查受影响定义及独立准入。沿用 Olympus/sync/POLICY.md 全量同步，不能挑文件复制或改旧批准摘要。

验收：
- [ ] 固定有效上游全部文件及来源证据；新目录完整重建，保留 Hermes 豁免模块/数据。
- [ ] 包含 delivery 规范、check_delivery 工具及 Ariadne 文档状态事件更新；核对相对路径和名称映射兼容。
- [ ] 验证精确候选和必要行为，审批需求由真实差异决定；未知批准保留阻塞。
- [ ] 新候选未通过前保持当前发布和绑定有效；通过后显式切换并回写版本/依赖/Issue。

证据：当前 Olympus/sync/POLICY.md、Olympus/source-evidence.json；共工 framework/specs/delivery.md、framework/reviews/sinan/workflow-optimization-review.json。不存在迁移即自动批准。

## 已完成的隔离推进

已修复同步器两类实证缺陷：Skill reporting应使用Skill版本而非模块版本；新refresh测试夹具需保留原.yuanheng账本路径，且旧源没有该测试时仍可重建。当前/旧批准源完整构建分别148/135、140/128；9项协调、14项交付检查通过，最终复用依据为相关文件逐字一致。

最小补丁见 `design-docs/patches/issue-7-upstream-sync-compatibility.patch`，摘要和独立复查见 `data-collection/issue-7-candidate-review-20261102.json`。新候选全部批准为空，未替换生产框架、绑定或旧批准。实际正式启用需对最终候选作相应准入与明确切换决策。
