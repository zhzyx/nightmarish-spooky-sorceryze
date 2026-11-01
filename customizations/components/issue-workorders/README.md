# GitHub Issue 工单适配

适用 Olympus 工程层；共工共同框架、Ariadne 源状态和准入不变。工作区配置为 `work-items.json`，标签定义为 `.github/labels.json`。每个类别有独立 Issue 表单并携带一个默认标签。后续人工修改须保持恰好一个 `type:*`，当前没有后台强制标签服务。

Git 本身不提供 Issue，本工程采用现有 GitHub 远程仓库的 Issue。Issue 状态是权威；本地文档、创建计划和数据索引不是另一套工单账本。所有远程操作需要实际 GitHub 权限；目前工作区没有 `gh` 命令，GitHub 插件未连接，未发布远程配置。

```powershell
# 预览标签，不进行远程写入
python customizations/components/issue-workorders/work_items.py labels
# 在安装并登录 gh 后创建缺失的标签，不覆盖现有标签
python customizations/components/issue-workorders/work_items.py labels --apply
# 预览首张实际需求工单
python customizations/components/issue-workorders/work_items.py issue --document design-docs/issue-workflow-20261102.md --title "工单 Issue 化与需求及采集目录" --type development --request-id issue-workflow-20261102
# 同一命令添加 --apply 后执行创建；收到真实 URL 后回填文档
# 对已有真实事件生成谛听来源索引
python customizations/components/issue-workorders/work_items.py collect --request-id issue-workflow-20261102
```

`issue --apply` 创建前分页检查所有开放/关闭 Issue 中的稳定需求标记，已有单张则返回其 URL，多张则拒绝。该检查避免串行重试重复创建；GitHub 不提供此客户端操作的事务锁，禁止并发创建同一需求。网络超时后先重新查询，不直接假定失败。创建不会自动派工、修改权限、关闭其他 Issue 或修改原文档。

发布顺序：准备并审查本地配置 → 连接 GitHub → 创建缺失类别标签 → 将模板发布到默认分支 → 创建 Issue 并回填链接 → 记录真实回执。远程发布仍按任务授权执行；不会因为本地脚本或模板存在而声称已上线。

采集前调用现有 Hermes 验证工具；无实际事件、校验失败则拒绝生成成功索引。来源记录身份保持不变，采集索引只包含路径与摘要，不把历史记录重新上报为谛听自产事件。

回退：停止调用该适配器，保留既有 Issue、文档、事件和采集索引；不要删除远程标签或历史数据。恢复旧入口不能消除已经创建的 Issue。

接口依据：[GitHub Issue 表单](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms)、[gh issue create](https://cli.github.com/manual/gh_issue_create)、[gh label create](https://cli.github.com/manual/gh_label_create)。
