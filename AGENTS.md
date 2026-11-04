# 共工统一工作区

唯一当前框架由 CURRENT_FRAMEWORK.json 定位到 framework/；框架生产前读取 framework/AGENTS.md 与 gonggong-check。冻结纲领和元衡原件不可修改，所有 Agent 受元衡治理。准入绑定精确候选，迁移不自动授权。

本仓库已接入 Git，任务通过 work-items.json 关联真实 Issue，需求在 design-docs/。开发前执行 customizations/components/issue-workorders/issue_gate.py 的 intake-only 回读；提交前执行正式门禁，提交后核验 git-check --require-committed。Git 约定属于接入层，不是共工核心的通用前提。

偃师在设计内拆分父 Issue 与可独立交付的 sub-issue；提交、关闭和阎罗尾项结转遵循 customizations/components/issue-workorders/issue-lifecycle.md，需求文档保留全部溯源映射。

Git/Godot 接入在 customizations/components/；当前框架不再有 Olympus 派生或同步关系。现行采集写入 gonggong-diting-data/，来源与回执在 data-collection/；历史 olympus-hermes-data/ 只读，纠正追加记录。采集配置不等于送达或消费，不记录凭据和估算用量。

司南只在需求、进度、依赖、决策、交接或完成事件时协调，不设定时扫描。局部阻塞只挂起受影响操作；合契按实际工作者与变更集处理差异，不能代操作其他工作副本。执行范围遵循 customizations/components/issue-workorders/execution-policy.md；交付遵循 framework/specs/delivery.md。

archive/、历史发布及批准记录只作证据，不自动启用；不继续已停止草稿。持久化路径注明解析基准。Godot 源码及现有接入保持在仓库根，不改外部引擎目录。未经验证不切换有效发布。
