# 共工统一工作区

唯一当前框架由 CURRENT_FRAMEWORK.json 定位到 framework/；生成 Agent／Skill 定义时读取 framework/AGENTS.md 与 gonggong-check；普通需求不触发共工审查与元衡评价。冻结纲领和元衡原件不可修改，所有 Agent 受元衡治理。准入绑定精确候选，迁移不自动授权。

本仓库已接入 Git，任务通过 work-items.json 关联真实 Issue，需求在 design-docs/。开发前执行 customizations/components/issue-workorders/issue_gate.py 的 intake-only 回读；提交前执行正式门禁，提交后核验 git-check --require-committed。Git 约定属于接入层，不是共工核心的通用前提。

Windows 工单门禁使用 tools/run_issue_gate.ps1 探测可执行 Python，见接入层 README；PR 证据预检绑定已回读目标分支与完整候选 index。新任务从当前主线隔离，保留其他工作树；按 commit/push/CI/main 回读分别记录失败，发布回执未知先回读，不重复发布。

接到用户明确需求后，按 customizations/components/issue-workorders/execution-policy.md 连续执行；本地必要验证通过即在同次任务中自动开始提交、推送与 main 合入推进，不等待用户再次说“提交”“合入”或“继续”。远端 main 回读及全部已验收关联工单关闭属于交付；已有授权不重复询问。用户明确限定本地或草稿范围时遵循其限制。只在真实必要决定、权限/准入缺失或范围变化时挂起受影响步骤；保留必要独立审查和精确候选准入。

当前 Git 交付由阎罗承担提交前校验、全部适用核查通过后的 main 交付、状态记录和目标 Issue 关闭；入口见 customizations/components/issue-workorders/yanluo.md，定义批准见 data-collection/yanluo-user-approval.json。合契负责候选整合与冲突处理，司南负责派发、依赖与跨工单协调；现有在途发布须明确交接，不抢占其他工作副本。main 合入后，阎罗按完整验收项复核进度；大部分完成或仅少模块未支持时创建/复用关联剩余 Issue，保留未知与未完成范围，原单未满足整体验收不得标为完成；尾项承接核实后的结转关闭按 issue-lifecycle.md 执行。由真实事件触发，不新增定时扫描。
偃师在设计内拆分父 Issue 与可独立交付的 sub-issue；提交、关闭和阎罗尾项结转遵循 customizations/components/issue-workorders/issue-lifecycle.md，需求文档保留全部溯源映射。

Git/Godot 接入在 customizations/components/；当前框架不再有 Olympus 派生或同步关系。现行采集写入 gonggong-diting-data/，来源与回执在 data-collection/；历史 olympus-hermes-data/ 只读，纠正追加记录。采集配置不等于送达或消费，不记录凭据和估算用量。

司南只在需求、进度、依赖、决策、交接或完成事件时协调，不设定时扫描。局部阻塞只挂起受影响操作；合契按实际工作者与变更集处理差异，不能代操作其他工作副本。执行范围遵循 customizations/components/issue-workorders/execution-policy.md；交付遵循 framework/specs/delivery.md。

archive/、历史发布及批准记录只作证据，不自动启用；不继续已停止草稿。持久化路径注明解析基准。Godot 源码及现有接入保持在仓库根，不改外部引擎目录。未经验证不切换有效发布。
