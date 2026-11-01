# 设计与需求文档

所有需求正文以 UTF-8 Markdown（`.md`）保存于此目录。命名采用稳定需求 ID，例如 `issue-workflow-20261102.md`。使用 `templates/requirement.md` 起草；模板不是实际需求或验收证据。

每份实际文档写明需求 ID、关联 Issue 完整 URL、任务类别标签、原始需求、范围、方案、验收标准、依赖及证据。Issue 尚未创建时明确写“待创建”，不得伪造编号。创建后将 URL 补回文档；Issue 正文引用仓库相对文档路径，PR/提交引用 `owner/repo#number`。

工单状态以 GitHub Issue 为准，文档描述设计和验收标准，不维护另一份竞争状态。Issue 关闭不自动证明验收或 Agent 准入。旧本地工单迁移时保留源 ID 和证据，逐条确认对应 Issue，禁止自动批量关闭旧工单。
