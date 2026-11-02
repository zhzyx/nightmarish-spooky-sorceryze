# Olympus 工作区约定


工程工单使用 `work-items.json` 指定仓库的 GitHub Issue；任务类别使用唯一 `type:*` 标签，定义见 `.github/labels.json`。需求文档以 Markdown 放入 `design-docs/` 并与 Issue 互链。谛听采集交接放入 `data-collection/`，保留原始来源；真实事件继续写入 `olympus-hermes-data/`。未发布草稿不当作远程工单，采集索引不当作谛听已消费回执。此工程定制不改写共工共同框架或绕过准入。

本 Git 仓库是奥林匹斯工作区；框架根是 `Olympus/`。按 `Olympus/AGENTS.md` 和实际职责加载规则，不全量灌入框架上下文。框架更新时全量核对有效共工上游；运行时校验已安装本地包及精确候选准入，不依赖外部共工目录。没有准入或真实宿主权限时，不声称 Agent 已启用。

需求产出包括代码/文档及 `olympus-hermes-data/` 内的真实文件事件。独立文件模式的入口是 `Olympus/extensions/hermes-files/hermes_files.py`，记录与分析无需数据库或上游在线。根据实际授权与事件记录，不将模板、测试数据或估算用量写成生产事实。

宿主开始开发前必须创建或复用同仓库真实 Issue，并回读校验仓库、租户、稳定需求 ID、唯一类别、有效执行状态及 Olympus 工作区标签；未绑定或查询失败则阻止模型及工具执行。聊天快照 ID、框架准入及文件回执均不能代替 Issue。人工、IDE、CLI 与生产工具遵循同一入口契约。

宿主使用框架产生的真实采集来源、验证证据、回执（`data-collection/`）和文件事件（`olympus-hermes-data/`）都是对应需求的 Git 交付内容，必须审查脱敏并与实现一起暂存、提交；不能留在本机或忽略后宣称交付。保留历史原件，纠正追加记录；缓存和凭据不进入采集目录。提交前执行真实 Issue 门禁，提交后执行 `git-check --require-committed`；远程推送和默认分支合入分别留证。

用户明确豁免 `Olympus/extensions/hermes-files/` 及根目录 `olympus-hermes-data/`，共工同步不能覆盖或清理它们。所有其他框架内容遵循确定性名称映射和全量同步。同步应从当前 Olympus 同步工具开始，在新目录重建和校验后交付 Git 变更。

需求合入前校验文件事件并纳入 Git，提交后使用 `git-check --require-committed` 检查记录与 HEAD；远程推送/合并按实际任务授权和仓库流程执行。凭据、本机绝对源路径、临时缓存不提交。没有真实权限或来源时保留未知，不绕过准入。

所有在此仓库创建或修改内容的人工、Agent、外部贡献者均先关联同仓库真实 Issue，再遵循 Olympus/AGENTS.md 按职责执行；适用于代码、引擎、文档、测试与资产等全部任务。协作入口与事件状态规则见 `.github/CONTRIBUTING.md`；提交候选执行 Issue 门禁，PR 关联不代替正式框架校验、实际采集及必要独立验收。新需求、状态、依赖、决策及回执事件到达时更新对应 Issue 与文档；无事件不调用，不使用定时扫描。
