# 共工统一工作区

仅 Godot 引擎任务遵循 [Godot 宿主的静默验证约定](customizations/components/godot-host/README.md#静默验证)。此约定适用于本仓库的 Godot 接入。

当前及今后取得本仓库有效写权限（WRITE、MAINTAIN、ADMIN）的每位协作者，都可以本人身份行使本仓库已准入的全部共工框架操作权限。宿主核对本人在目标仓库的有效权限，授权随授予生效、随撤销终止，包含团队继承的写权限。协作者可发起和授权工单、调用已准入的 Agent 与 Skill、委托司南多 Agent 派发、发起夸父排障、谛听采集、合契整合及阎罗签发交付，也可按治理规则担任审查、批准和验收负责人。每次操作遵循工单范围、独立审查、精确候选准入和实际分支保护。默认使用[协作者签发入口](customizations/components/issue-workorders/yanluo.md#协作者快速签发和自动提交)。模型、生产工具与第三方服务使用操作者有权使用的宿主凭据。

唯一当前框架由 CURRENT_FRAMEWORK.json 定位到 framework/；生成 Agent／Skill 定义时读取 framework/AGENTS.md 与 gonggong-check；普通需求不触发共工审查与元衡评价。冻结纲领和元衡原件不可修改，所有 Agent 受元衡治理。准入绑定精确候选，迁移不自动授权。

排查当前问题时，发现并复现的范围内缺陷直接进入修复、验证与交付，无需用户再说“优化”。用户明确要求仅解释或只读排查时，遵循该限制。

本仓库已接入 Git，任务通过 work-items.json 关联真实 Issue，需求在 design-docs/。开发前执行 customizations/components/issue-workorders/issue_gate.py 的 intake-only 回读；提交前执行正式门禁，提交后核验 git-check --require-committed。Git 约定属于接入层，不是共工核心的通用前提。

Windows 工单门禁使用 tools/run_issue_gate.ps1 探测可执行 Python，见接入层 README；PR 证据预检绑定已回读目标分支与完整候选 index。新任务从当前主线隔离，保留其他工作树；按 commit/push/CI/main 回读分别记录失败，发布回执未知先回读，不重复发布。

接到用户明确需求后，按 customizations/components/issue-workorders/execution-policy.md 连续执行；本地必要验证通过即在同次任务中自动开始提交、推送与 main 合入推进，不等待用户再次说“提交”“合入”或“继续”。远端 main 回读及全部已验收关联工单关闭属于交付；已有授权不重复询问。用户明确限定本地或草稿范围时遵循其限制。只在真实必要决定、权限/准入缺失或范围变化时挂起受影响步骤；保留必要独立审查和精确候选准入。

所有当前仓库协作人均为关键可提交角色；有实际合入权限的协作人可用本人账号按阎罗入口的 PR 路径完成交付，不需要所有者另行签发。当前 Git 交付由阎罗承担提交前校验、全部适用核查通过后的 main 交付、状态记录和目标 Issue 关闭；入口见 customizations/components/issue-workorders/yanluo.md，定义批准见 data-collection/yanluo-user-approval.json。合契负责候选整合与冲突处理，司南负责派发、依赖与跨工单协调；现有在途发布须明确交接，不抢占其他工作副本。main 合入后，阎罗按完整验收项复核进度；大部分完成或仅少模块未支持时创建/复用关联剩余 Issue，保留未知与未完成范围，原单未满足整体验收不得标为完成；尾项承接核实后的结转关闭按 issue-lifecycle.md 执行。由真实事件触发，不新增定时扫描。
偃师在设计内拆分父 Issue 与可独立交付的 sub-issue；提交、关闭和阎罗尾项结转遵循 customizations/components/issue-workorders/issue-lifecycle.md，需求文档保留全部溯源映射。

Git/Godot 接入在 customizations/components/；当前框架不再有 Olympus 派生或同步关系。现行采集写入 gonggong-diting-data/，来源与回执在 data-collection/；历史 olympus-hermes-data/ 只读，纠正追加记录。采集配置不等于送达或消费，不记录凭据和估算用量。

司南只在需求、进度、依赖、决策、交接或完成事件时协调，不设定时扫描。局部阻塞只挂起受影响操作；合契按实际工作者与变更集处理差异，不能代操作其他工作副本。执行范围遵循 customizations/components/issue-workorders/execution-policy.md；交付遵循 framework/specs/delivery.md。

archive/、历史发布及批准记录只作证据，不自动启用；不继续已停止草稿。持久化路径注明解析基准。Godot 源码及现有接入保持在仓库根，不改外部引擎目录。未经验证不切换有效发布。
## 从 main 取得自动推进与生产入口

协作者从可信 main 检出取得司南事件、工单回读、工作者启动、终态核验和依赖补位入口，见 [仓库派发说明](customizations/components/repository-dispatch/README.md)。从命令行可在专用测试工单运行框架核验，也可在真实授权下调用框架模型运行时。编辑器并行落地支持已授权的非 Codex 工作者。只有选择 Codex 原生 Agent／chat 时才使用下述原生宿主协议。各入口分别核对权限、在途占用和交接，不把他人的配置或凭据写入仓库。

## Codex 中已授权的 Issue

用户在 Codex 中要求完成明确 Issue 时，当前 Codex 会话负责接续至整体验收。先回读该 Issue、授权来源、已有 PR、已交付范围与剩余验收，并核对实际责任者及在途工作。部分 PR 合入或计划登记后，继续当前可执行的剩余项。只有用户指定或实际发布者确认接收时才移交执行。大千计划登记、打开 Godot、额外配置模型 API Key 均非 Codex 路径的前置步骤。

当前会话应调用司南组织多 Agent 派发：对已授权、依赖已验收且读写范围可隔离的任务，按真实可用槽位派发原生子 Agent；同一实现允许独立只读核查。按 [Codex 派发宿主协议](customizations/components/codex-dispatch/HOST_PROTOCOL.md) 绑定工单、占用及真实回执。只有一项可执行时由当前责任者继续；宿主缺少子 Agent 能力时记录受影响的派发步骤并推进可独立完成的工作。完成事件到达后核验结果、回读依赖并继续下一项。跨设备先核对在途认领和交接；无法确认已有工作者终态时保留其占用。

## 阻塞由夸父当次介入

用户反馈受阻，或需求、依赖、权限、工具、构建、验证、提交、推送、CI、合入、交接及回执核对任一动作无法继续时，发现者在同一事件中将原工单、动作、候选/来源修订、已尝试操作和实际失败证据交给夸父。依赖正常等待、已有工作者运行或槽位暂满可按原完成事件接续；有证据表明停滞或用户反馈受阻时立即进入排查。

当前宿主按 [夸父接单、上报和复验](customizations/components/issue-workorders/kuafu-routing.md) 执行。先查重或关联 bug，按实际授权加载夸父职责、确认接单、判断故障层级和影响、跟进唯一主责并向原工单上报。网络、身份或宿主不可用时保留待接单及恢复条件。源头修复、原候选复验和业务验收分别留证；涉及他人的在途任务时只做隔离验证和必要交接，等原发布者确认后再变更其候选。
