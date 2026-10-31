# Olympus 工作区约定

本 Git 仓库是奥林匹斯工作区；框架根是 `Olympus/`。按 `Olympus/AGENTS.md` 和实际职责加载规则，不全量灌入框架上下文。框架生产验证先核对有效共工上游；没有上游或准入时，不声称 Agent 已启用。

需求产出包括代码/文档及 `olympus-hermes-data/` 内的真实文件事件。独立文件模式的入口是 `Olympus/extensions/hermes-files/hermes_files.py`，记录与分析无需数据库或上游在线。根据实际授权与事件记录，不将模板、测试数据或估算用量写成生产事实。

用户明确豁免 `Olympus/extensions/hermes-files/` 及根目录 `olympus-hermes-data/`，共工同步不能覆盖或清理它们。所有其他框架内容遵循确定性名称映射和全量同步。同步应从当前 Olympus 同步工具开始，在新目录重建和校验后交付 Git 变更。

需求合入前校验文件事件并纳入 Git，提交后使用 `git-check --require-committed` 检查记录与 HEAD；远程推送/合并按实际任务授权和仓库流程执行。凭据、本机绝对源路径、临时缓存不提交。没有真实权限或来源时保留未知，不绕过准入。
