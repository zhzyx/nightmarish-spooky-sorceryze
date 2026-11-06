# GitHub Issue 工单适配

夸父按 framework/specs/quality-responsibilities.md 在开发阻塞、用户报告、重复停滞或关键问题事件中即时登记工单。此类 Issue 统一使用唯一 `type:bug`；用稳定阻塞标识查重并保留原任务链接，同一问题追加原单，非 bug 父单保留原类别。首次创建回读前记录待关联状态，失败/回执不明先对账后重试。类别约定不等于已接通自动事件监听或授予工具权限。

Windows 推荐从任务隔离工作树执行 `./tools/run_issue_gate.ps1 -Issue N -RequestId ID`；开发入口加 `-IntakeOnly`。入口探测 Python 3.11+，排除 WindowsApps 别名，复用该仓库或 Git common-dir 所属仓库的运行时，也支持 `-Python` / `GONGGONG_PYTHON` 指定已验证解释器。`-ProbeOnly` 只读输出实际解释器与仓库；不安装运行时、不修改 PATH 或权限。相对 `-Repo` 以调用 cwd 解析，默认仓库以脚本目录解析。

提交门禁先按 `--base-ref`（默认已 fetch 的 `origin/main`）与 HEAD 的 merge-base 到 index 核对整个 PR 的新增/变更证据，包含此前已经提交的修改。有本需求 Diting 事件时，PR 中必须同时包含 JSON 采集证据，顶层 `request_id` 与 `issue`/`issue_url`/整数 `issue_number` 明确匹配；仅 source_ref 或已在 base 的旧证据不能满足 CI。使用 PR 的实际目标分支，不以 HEAD 伪造目标来缩小差异。CI 仍使用可信 base 脚本；本地通过不代替远端回读。

`work_items.py collect --request-id ID` 从同租户 request 事件的精确本仓库 Issue 来源生成 `issue_url`/`issue_number`，多 Issue 歧义拒绝写入；不改旧记录，也不把来源索引当作远端状态认证。缺少可绑定来源时仍保留未知，不能靠填一个不相关编号满足交付。

`WORKTREE_UNSTAGED` 表示工作文件与 index 不同，尚未执行框架准入；在基于已回读主线的独立工作树组装当前任务，不为通过门禁暂存别人的文件。`GIT_PERMISSION`、`GIT_LOCK`、`GITHUB_NETWORK`、`GITHUB_HTTP_*`、`*_TIMEOUT` 分别处理权限、占用、网络、API 权限及未知超时。错误不回显子进程原始输出或凭据；不能将网络不可用或工具缺失报成批准拒绝。

交付分别记录 commit SHA、push 回执、精确候选 CI、main 接收和回读、Issue 状态。每条命令失败立即保留该阶段，不让后续成功覆盖退出码。push 成功但 fetch/readback 失败标记 `published_readback_pending`，恢复先按 SHA 回读远端，不重复提交/推送。已有阎罗 journal 按相同原则续接；不改写批准定义，不新增后台发布器。

偃师定版后的父子工单拆分、按子项提交关闭、阎罗少量尾项结转及文档追溯，统一遵循 [Issue 生命周期](issue-lifecycle.md)。设计内使用 [拆分模板](../../../design-docs/templates/issue-breakdown.md)；原生子项关系和远端状态必须实际写入并回读。

宿主执行约束见 [执行范围与验证成本](execution-policy.md)：任务入口固定边界，交付阶段按变更选择验证，等待阶段合并真实状态事件，效果沿用 Diting 记录。它是本组件的流程约定，不改变共享 Agent 定义或声称已实现自动预算控制。


宿主开发入口使用同一脚本的 `--intake-only --tenant <配置租户>` 模式，仍需提供 `--repo`、`--issue`、`--request-id`。此模式只回读真实工单并验证仓库 origin、稳定 ID、类别、有效状态、租户及 workspace:gonggong，不执行模型、不代替正式框架准入。没有 Issue 时先经已授权需求入口创建/复用；聊天入口拒绝绕过，不以本地预览替代发布。

data-collection 内公开的业务来源与交付回执也是交付内容：本地提交门禁逐文件比较 index 当前字节，拒绝未跟踪、被忽略、未暂存或删除的采集原件。宿主私有 inbox/、outbox/、receipts/ 及采集根目录 *.local.json、SQLite 和标准旁文件必须保持忽略且未跟踪，强制暂存会被拒绝；公开交付证据放在其他明确路径。任意业务证据不因被忽略而豁免。缓存、凭据和本机绝对源路径不得发布；纠正追加记录。Diting 仍按既有规则校验并在提交后核对 HEAD。服务器 required check、分支保护及 Sinan 事件来源仍需各自真实启用，入口校验不冒充这些能力。
Git 工作流接入子模块见 [git-workflow.md](git-workflow.md)。新建工单记录当前认证的 GitHub login；显式事件记录事件操作者与 Issue 修订标记，供并发更新核对。共工后续需在自身框架中实现相应来源适配和回读，本组件不修改 Sinan 分发包。

适用 GongGong 工程层；共工共同框架、Sinan 源状态和准入不变。本文路径均相对仓库根。工作区配置为 `work-items.json`，类别定义为 `.github/labels.json`，七种状态另列 `.github/status-labels.json`。每个类别表单携带唯一 `type:*` 和默认 `status:needs-decision`；开始生产前明确范围、授权及依赖并转为 `status:in-progress`，待验收时为 `status:in-review`。

Git 本身不提供 Issue，本工程采用现有 GitHub 远程仓库的 Issue。Issue 状态是权威；本地文档、创建计划和数据索引不是另一套工单账本。所有远程操作需要实际 GitHub 权限；已验证本机现有 GitHub CLI 登录及仓库写权限；若 `gh` 不在 PATH，将实际 CLI 的 bin 目录加入本机会话 PATH。账号凭据不进入仓库。GitHub 插件状态不影响已验证的本机 CLI 通道。

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

对用户已明确要求执行且范围齐备的需求，调用者核实授权后附加 `--execution-authority-ref "原需求中的用户指令/宿主授权引用"`，新单直接以 `status:in-progress` 创建并记录引用，随后执行 intake-only。该参数只是溯源，不认证身份、不签发治理准入；无授权引用时保持 needs-decision。已有匹配单原样返回，不修改其状态或关闭原因。普通表单及第三方来源仍先核实授权。后续依 [自主推进规则](execution-policy.md) 连续处理，必要发布职责沿用 [阎罗入口](yanluo.md)。

发布顺序：准备并审查本地配置 → 连接 GitHub → 创建缺失类别标签 → 将模板发布到默认分支 → 创建 Issue 并回填链接 → 记录真实回执。远程发布仍按任务授权执行；不会因为本地脚本或模板存在而声称已上线。

采集前调用现有 Diting 验证工具；无实际事件、校验失败则拒绝生成成功索引。来源记录身份保持不变，采集索引只包含路径与摘要，不把历史记录重新上报为谛听自产事件。

提交前使用已审查、受信任的工程入口；不得执行未知 PR 提供的脚本：

```powershell
# gh 不在 PATH 时，GONGGONG_GH 可指向宿主已登录的 gh.exe；不存储令牌。
# 暂存本次交付和真实 Diting 事件，再运行（仓库根路径按实际环境传入）：
python customizations/components/issue-workorders/issue_gate.py --repo . --issue 6 --request-id issue-governance-20261102
```

本地门禁查询 `work-items.json` 对应仓库的真实开放 Issue，要求 origin 同仓库、唯一已知类别、唯一 `in-progress` 或 `in-review` 状态，稳定需求 ID 支持 `<!-- gonggong-request:ID -->` 或 Issue 表单的 `### 稳定需求 ID` 字段，歧义拒绝。它直接执行 `framework/tools/verify_framework.py` 正式模式（无 `--candidate`）与包含结构/摘要/关联验证的 Diting 提交前 `git-check`（不再重复运行 `validate`），拒绝历史事件删除或改写，并检查该需求已有真实文件事件且已被 Git 跟踪。`work-items.json` 必须显式绑定 `tenant_id`；只选取该租户和需求的事件，且至少一个 `kind=request` 事件的 `source_ref` 必须精确等于 Issue URL 或 `github:owner/repo:issue:N`。正式框架校验使用已安装包内完整性清单和精确准入，不访问外部共工。无外部框架同步来源；正式校验和实际采集缺失仍阻断。

输出摘要绑定当前 HEAD、index 与 tracked/nonignored 文件内容，检查前后内容和 Issue 状态须一致。修改后重新绑定候选并回查受影响证据；提交时复核 Git 内容，提交后另运行 Diting `git-check --require-committed`。此摘要不是签名、准入通行证、消费回执或可跨版本复用的成功证明；工具核验事件结构、摘要和关联；静态 tenant/source/actor 字段及 SHA256 不能认证操作者身份或证明事件叙述真实，也不替代宿主独立权限或业务验收。纠正已有事件时追加新事件及 supersedes，保留历史原件。

PR 正文必须有且仅有以下两行关联字段：

```text
GongGong-Issue: #6
GongGong-Request: issue-governance-20261102
```

`.github/workflows/gonggong-issue-gate.yml` 使用 PR 创建、编辑、同步等事件，无定时任务；`pull_request_target` 仅运行可信 base 工作流的固定 github-script，权限只读，绝不 checkout 或运行 PR 代码。CI 查询本仓库真实 Issue、类别/状态及需求 ID；无外部共工源时不冒称执行完整准入或业务验收。Issue 后续独立改标签/关闭不会自动刷新已有 PR 检查，合入前须重跑并复核最新状态。管理员需另将 `issue-association` 配置为分支保护必需检查；工作流存在不表示远程已强制，也无法约束仓库外直接修改 Godot。

回退：停止调用该适配器，保留既有 Issue、文档、事件和采集索引；不要删除远程标签或历史数据。恢复旧入口不能消除已经创建的 Issue。

接口依据：[GitHub Issue 表单](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms)、[gh issue create](https://cli.github.com/manual/gh_issue_create)、[gh label create](https://cli.github.com/manual/gh_label_create)。

普通引擎会话复用现有 Yanshi／ClarifyFeature 自动整理需求并建单，受限需求阶段与开发门禁分开，见 [宿主协议](../godot-host/HOST_PROTOCOL.md)。工单适配器不因此授予模型、工具或设计定版权限。

## 核验复用与成本（Issue #85 候选）

门禁仍前后核对 HEAD、index 对象及工作区精确字节；index 对象已绑定内容，不重复生成 staged binary diff。工作区字节流式哈希，不用 mtime/size 代替内容验证。整仓前后读取仍保留，不能声称已经消除全部磁盘读取。

Git 跟踪、忽略和 blob 内容使用 NUL 分隔路径与批量对象读取；Git 异常、合并冲突、链接对象仍失败。Diting 一轮只加载一次当前与历史数据。框架完整性扫描的实时摘要供候选和报告检查共享；正式准入状态和有效期每次检查。

通常一次门禁调用即可。宿主确有连续显式请求时，可运行 `issue_gate.py --repo . --session`，逐行通过 stdin 提交 `{"issue":85,"request_id":"verification-efficiency-20261105"}`。每行返回一个成功/失败 JSON；EOF 退出，不扫描、不轮询、不设后台任务。宿主必须检查每行 `state`，不能以进程仍存活或最后退出码代替门禁结果。

session 仅在同一进程内复用成功事件的结构/摘要校验，精确字节改变会失效；仓库、Diting validator 字节或 Python 版本改变清空缓存，失败清空缓存。门禁自身或已加载 Git helper 字节改变时拒绝继续，必须重启会话。关联图、Git 当前状态、Issue 状态、框架准入和候选前后一致性始终重新核对；磁盘上的旧成功文件不被当作缓存。普通一次性 CLI 不跨进程复用证据。

此节描述隔离候选能力，精确准入完成前不代表有效发布已切换。回退为使用原已批准版本；保留历史事件、测试与实测证据。
## 当次操作者接收事件

#9 的用户决定采用“谁操作，谁接收”：当次操作者负责当前需求、进度、依赖、决策、交接和完成事件的显式接收；换人后由新操作者承接，不要求固定 webhook 宿主。GitHub event actor、Issue assignee、正文宿主账号和当前接收者是不同概念，不能互相推断。下述参数标识处理上下文，不认证身份或授予权限。

1. 当次操作者绑定真实 Issue、稳定 request ID、配置租户、实际宿主定义与接收上下文 ID；执行 `issue_gate.py --intake-only` 回读。业务仍 blocked 的 Issue 需先区分可执行工作与受阻动作，不能为过门禁虚报状态。
2. 从这次明确业务操作的 GitHub 回执或按需 API 回读中取得真实 event ID，再执行单次入口。没有新事件不调用；不扫描所有工单或启用时间任务。
3. 相同 repository / issue / event ID 在仓库中只有一个原始观察，已有接收绑定不得改归属。换人接续已接收事件时引用原 receipt，另记实际交接；不得把新 host ID 强写到原 envelope。只有新的真实事件才建立新的接收绑定。
4. `recorded_file` 仅证明原始观察与文件回执。当前操作者按事件更新需求和进度，明确 Git 提交、实际 analyze 消费与远程回读各自结果；旧 receipt 不改写。失败保留原 envelope，由后续用户请求或真实业务事件触发同绑定重放。

以下是本轮已经执行成功的精确调用示例，路径以仓库根解析，Python 使用当前环境已验证的解释器。示例参数不能用于冒充其他操作者：

```powershell
python customizations/components/issue-workorders/issue_gate.py --repo . --issue 9 --request-id issue-event-data-loop-20261102 --intake-only --tenant gonggong-workspace
python customizations/components/issue-workorders/issue_events.py --repo . --issue 9 --event-id 35158186727 --host-id codex-issue9-current-operator --tenant gonggong-workspace --request-id issue-event-data-loop-20261102 --host-definition AGENTS.md
python framework/extensions/diting-files/diting_files.py analyze --repo . --tenant gonggong-workspace
```

当前用户是本轮接收责任方，Codex 本聊天是授权执行上下文。首次实际调用为 idempotent=false，同绑定重放为 true。这落实单次来源接收契约，尚不表示司南 board 注册了 GitHub 来源、自动 start/ack 或全局事件覆盖。来源注册状态以实际 board 为准。

## 当前来源与执行接入（#9 最终对账）

上段是首次接收时的历史边界。已交付的 `github_source.mjs` 与 `../codex-dispatch/operator.mjs` 现可由当次操作者按 [宿主协议](../codex-dispatch/HOST_PROTOCOL.md) 显式绑定真实 GitHub 工单、共享安装认领和原生执行回执；#90 的真实 start/ack/terminal 与消费验收已合入 main。每次运行的 bindings 才是该次已注册来源集合，来源数、可读数和在途状态取自本次 inspect，不从配置文字推断已执行。

`work-items.json` 的兼容字段 `sinan_source_registered=false` 仅指通用框架旧 registry，不表示当次操作者宿主未接通；`sinan_source_binding` 显式记录当前接入入口、范围和证据。单次 `issue_events.py` 仍只接收与关联，不自行派发，因此它的布尔观测不代表整个执行宿主状态。两条入口共享真实 Issue 身份与谛听来源，不能用全局 true 替代实际绑定、准入或调用回执。

接收责任随当前操作者交接；事件 actor、assignee 与接收者分别保留。旧 envelope/receipt 不更改归属；实际读取、文件送达、Git/main 接收与指定记录消费各有独立证据。无新事件不调用，不新增全局监听、定时扫描或后台服务。历史 Olympus 来源只读沿用，当前新增记录统一写入 GongGong 数据集。

## 读取当前工单和复盘周转

从仓库根运行 `python customizations/components/issue-workorders/work_items.py brief --issue 58`。它仅在本次读取时汇集 GitHub 正文、完整偃师澄清、最新评论、原生前置与子单，并链接当前检出提交的设计结论。各项标明来源；历史澄清保留当时范围，工作者仍需核对后续用户决定。新建工单正文提供直接打开主线设计的链接。

复盘一个已发布版本时，运行 `python customizations/components/issue-workorders/work_items.py turnaround --baseline data-collection/diting-flow-20261107.json --released-at 2026-11-06T18:27:48Z`。替换为实际同仓基线索引和发布时间。按当前类别比较基线与发布后新建且已完成的工单，输出样本编号、中位数及 P90；另列同仓原单上的夸父公开复验回执。没有回执的人工阅读时长及实质并发返工保持未知。单个已签 PR 的基线移动、写入重叠及交付差异由 `writer_submit.py --inspect-pr <编号>` 回读。均由当次需求或事件触发。
