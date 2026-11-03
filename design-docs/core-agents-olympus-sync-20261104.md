# 同步共工通用司南与合契 Agent 到 Olympus

工单：https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/35
稳定需求 ID：`core-agents-olympus-sync-20261104`。

共工后续固定源为 `core-agents-generalization-20261103/frozen-v1/framework`，清单树摘要 `57a71cb09424a9cf124608d2f320fb40d37c1695a0b7e7262bb56e1b5f78cf93`。来源声明合契 0.3.0、独立司南 Agent 0.1.0 与司南工具 0.5.0；Olympus 接收前仍须逐文件校验、核对原审查和精确准入。该需求在 #27 固定 0.2.1 的 PR #34 远端验收后串行开始，不能替换或混入其候选。

目标是用当前同步工具完整重建并确定性映射有效共工上游，保留 `extensions/hermes-files/` 和根 `olympus-hermes-data/` 豁免。通用司南与合契是框架 Agent，不作为 Git/Godot 子模块定义；Olympus 当前 Git Issue 接入应在实际宿主的协调 registry 中核对来源和 `issue_tracking` 授权绑定，历史 `issue_ref` 不等于启用回执。候选不自动启动 Agent、监听或远端写入。

本次产物为完整框架差异、必要映射/适配、来源与独立审查、准入、代表链路证据以及真实 Hermes 文件事件。平台先限当前 Windows 框架分发验证；按受影响模块选局部回归，再根据实际接口风险扩大。提交前执行本工单门禁，提交后 `git-check --require-committed`；远端 PR 和合入分别回读。停止条件为全量 parity、精确准入和相关行为验收通过；若 #27 未合入、源漂移、授权或审查不足，保持 planned，不以配置或候选校验声称启用。

## 固定来源与映射候选

#27 的 PR #34 已按候选 `fb51bd9b` 合入 main，合并提交 `cab56e6f`。本单从该提交起步；固定源 `frozen-v1` 的 216 项文件清单逐项 SHA256 相符，正式源校验返回 `approved_file_integrity`。同步工具在新目录完整重建，215 个框架源文件映射为 164 个分发文件，parity 通过。五个目标 Agent 为 Athena、Themis、Hermes、Harmonia 0.3.0 和独立 Ariadne 0.1.0；Ariadne 工具模块为 0.5.0。九份被替换或移除的本地准入与审查原件按字节归档在 `data-collection/issue35-previous-local-admission/`。原始来源与候选摘要见 `issue35-frozen-source.json`、`issue35-sync-candidate-20261104.json`；本次真实文件事件在 `olympus-hermes-data/` 追加。

同步适配器根据实际 Agent 集合生成模块说明，避免沿用“不新增 Agent”的旧叙述；同时保留源协调账本的 `.yuanheng` 文件格式，覆盖新增测试夹具。Ariadne Node 测试 16 项、框架 Python 测试 19 项通过，质量归属和 Python/Node 语法通过。候选验证为 `candidate`，当前尚待 Olympus 独立审查和五个映射后精确许可。没有发现当前宿主的 `issue_tracking` 协调 registry 绑定；历史 `issue_ref` 不视为启用，运行时仍为关闭。

## 独立审查与本地定义准入

独立只读审查核对 216 项冻结源、五个映射后精确摘要、Ariadne Agent 与 0.5.0 工具的不同许可路径、Harmonia 通用身份、reporting、豁免和九份旧原件，结论为定义候选通过，原件记录在 `Olympus/reviews/local-admission/issue35-independent-review.json`。依据用户要求验证后完成本工单合入的指令，仅为五个精确候选记录本地定义许可；决定与许可位于 `Olympus/reviews/`，其范围不包含宿主运行或 Git 交接。正式 `verify_framework.py` 返回 `approved_file_integrity`，全量 parity 与离线快照 164 项通过；详细证据见 `data-collection/issue35-admission-20261104.json` 与追加 Hermes 事件。Ariadne 工具模块仍为待分发审查且默认关闭，当前没有实际 `issue_tracking` 绑定或谛听消费回执。
