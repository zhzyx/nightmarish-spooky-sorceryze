# 接通 GitHub Issue 事件协调与 Hermes 数据交接，核销陈旧状态

工单：https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/9

## 2026-11-03 本轮范围与验证

用户明确本轮不向对应宿主提交，先分析 blocked 原因并修复工单框架；后续 Issue 标明宿主 GitHub 账号，并让并发更新在工单事件记录中有可认定的修订标记。本轮改动限定 Olympus 的 Issue 创建适配器、表单和显式事件采集，不改上游 Ariadne 分发包、共工工作区或已部署宿主。使用内置 Python 在 Windows 验证 Issue 组件隔离测试与 `git diff --check`；停止条件是身份字段、冲突拒绝及事件修订证据可本地验证。真实 GitHub 并发写入的原子仲裁、共工司南接入与 Agent 启用仍需其所属来源及独立准入，不能由此轮本地记录宣称完成。

<!-- olympus-request:issue-event-data-loop-20261102 -->

缺口证据：work-items.json 的 ariadne_source_registered=false；Olympus/modules/ariadne/runtime/registry.json 的 sources 为空；data-collection/sources.json 只索引 #1/#2 且 ingestion_confirmed=false；部分工作区/组件元数据仍写候选待审，与后续精确准入及发布证据不同步。

目标：Issue 新建、状态、依赖、决策与执行回执到达时，通过实际宿主入口协调进度和文档；所有模块复用 Hermes，交付与消费状态有真实回执。GitHub 仍为工单状态权威，不伪造元衡账本以适配只支持文件账本的旧协调器。

验收：
- [ ] 选定并显式绑定实际 GitHub 事件来源与当前宿主，按 repository+issue+事件 ID 幂等；无事件不调用，无 cron/轮询/延时唤醒。
- [ ] 类别、状态、负责人、依赖、需决策项及真实执行回执有明确映射；在途任务只关联不重复派发。
- [ ] 代表任务从 Issue 事件到本地文档/执行回执、GitHub 回读贯通；父单不因子单完成自动关闭。
- [ ] 修订当前状态元数据并保留历史；配置、排队、文件记录、提交、谛听消费分别证明。
- [ ] 使用同一 Hermes 分析入口进行一次授权范围真实读取，覆盖范围与未知用量如实记录；不重复导入冒充自产。

状态：待判断。实际长驻 webhook 接收宿主/权限尚未绑定；不以本单建立常驻服务或新增时间自动化。可先推进单次显式宿主调用与数据核查。

## 已完成的数据核查

已通过同一 Hermes analyze 入口真实读取本次clone中的 olympus-workspace 数据，回执见 `data-collection/issue-event-read-receipt-20261102.json`。记录包含旧发布32条及本次4张工单登记，共36条；范围为已有文件，不代表实时事件全覆盖。执行消费者为当前Codex根任务，未冒充谛听Agent消费。

修订当前元数据语义，保留历史证据与 ariadne_source_registered=false；GitHub仍为权威，Ariadne实际源为空。待接入的是实际宿主GitHub事件来源、幂等收件及协调适配，并非恢复已废止的定时扫描。远程事件需实际可用的GitHub权限（插件读可用、写403，本次用已有CLI）。

## 2026-11-03 单次 Olympus 宿主入口

新增 `customizations/components/issue-workorders/issue_events.py`，只在显式调用时读取指定 Issue 的真实 GitHub event ID，再回读当前 Issue。验证来源仓库、Issue 身份、唯一需求 ID、唯一类别/状态和 `workspace:olympus` 后，按 repository + issue number + event ID 生成稳定幂等键，保存原始观察 envelope，并调用已有 Hermes `record` 取得真实文件回执。重放保持原始观察不变，不把当前状态冒充历史事件发生时的状态。

```powershell
$env:OLYMPUS_GH = '<本机 gh 可执行文件>'
./project/runtime/python/python.exe customizations/components/issue-workorders/issue_events.py --repo . --issue 9 --event-id <真实GitHub事件ID> --host-id codex-root --tenant olympus-workspace --request-id issue-event-data-loop-20261102 --host-definition AGENTS.md
```

类别、状态、GitHub assignees 和需决策状态直接映射；依赖仅解析显式 `<!-- olympus-depends-on:#编号 -->` 标记，普通正文 #链接不自动推断依赖。输出仅关联在途工作，不派发、关闭父单或修改远程 Issue。双工作区标签的 Issue 只处理 Olympus 侧；没有 Olympus 标签时拒绝。共工侧仍需所属框架的独立来源绑定。

并发同一事件由操作系统排他锁拒绝；进程退出由操作系统释放锁，锁文件保留以避免并发删除产生不同锁对象，无时间清理或轮询。文件先在忽略的 outbox 临时区完整写入并 fsync，再通过不覆盖目标的硬链接原子发布；进程中断不会留下半个最终 JSON。Hermes 失败保留 envelope，下一次用户/业务事件显式调用可以重试。观察文件与文件回执位于 `data-collection/issue-events/<幂等键>/`，Hermes 的实际事件位于既有数据集。`git_committed=false` 指生成回执时尚未提交，后续 Git 校验另行记录；文件回执不等于谛听消费或宿主权限认证。

此入口不注册 Ariadne 文件账本源，不启动 webhook 服务，不自造 GitHub 事件 ID，也不修改 Agent 准入。11 项隔离测试涵盖身份/工作区拒绝、依赖映射、重放顶层身份与宿主摘要篡改、已有回执摘要不符、未知类别与错租户、失败重试、并发锁、进程崩溃锁释放和原子发布失败；模拟测试文件不进入生产数据。真实 GitHub 事件演示与共享 `analyze` 读取须由主任务实际执行并另附回执，本段不将尚未执行的验证记为完成。

重放前将 envelope 顶层事件 ID、租户、需求、宿主和定义摘要与确定性身份核对；已有回执的 envelope SHA256 必须先匹配才允许调用 record。CLI 租户必须与 work-items.json 的 tenant_id 一致，类别必须属于 .github/labels.json；绑定冲突一律拒绝，不覆盖历史。

## 2026-11-03 实际事件验收

当前宿主已显式处理本工单的真实 GitHub 事件 `34930471933`（添加 `status:in-progress`），首次调用取得 `recorded_file` 回执，重复调用返回幂等成功。来源与回执在 `data-collection/issue-events/4e45ac85a254e7cf12b7d3cc7263500d5e1b5827c7fb065b6b7c284851e0ed53/`，已随 `b439d032` 提交。共享 Hermes analyze 实际读取当时的 46 条事件，读取证据见 `data-collection/issue-9-explicit-event-read-20261103.json`；消费者为当前 Codex 宿主，未知用量仍为 null。

因此 Olympus 单次事件记录、重放及共享分析路径已贯通。本父单仍为处理中：共工侧来源适配与代表任务未由本工作区完成，Ariadne GitHub 来源注册仍为 false；不将手工单次调用或来源索引当作自动派发、谛听 Agent 消费或双工作区全部完成。

## 本轮显式合入与状态核销

用户要求合入本地内容并推进全部开放工单。本轮范围为回读远程真实状态、交付 #15 策略、核销已有验收的 #8/#11/#15，以及保留 #9 的外部接入缺口。最小验证为现有精确CI/独立证据映射、真实Issue和正式框架/Hermes门禁及提交后HEAD检查；未改引擎，不重新构建。

PR #17 已合入，#8/#11/#15 已按现有证据 completed 关闭。旧PR #14 的缺失Issue继续执行路径与当前契约冲突，以PR #16替代并关闭，保留历史分支。#6 的宿主代码已合入，但新Windows候选检查与实际启用验收仍须按真实结果处理，不自动关闭。#9 仍缺双工作区真实来源/宿主绑定与共工侧代表回执；已向用户请求实际接收宿主信息，未注册假来源。原始远程快照见 data-collection/workspace-final-issues-20261103.json 与 workspace-final-prs-20261103.json。

## 2026-11-03 跨贡献者采集缺口

用户报告其他贡献者基于共工生产的内容未被当前仓库采集提交。本次范围限 Olympus 仓库 PR 交付入口：校验 `workspace:olympus`；PR 带有该需求的成功 Hermes 文件事件时，要求同时带有同一稳定需求 ID 和 Issue 身份的 `data-collection` JSON。没有成功记录时发出明确警告并允许提交，覆盖状态保持未知，不补造事件。目标平台为 GitHub Actions 的可信基础分支工作流，最小验证为脚本语法与缺失、错需求、匹配文件三个场景。此检查只核对 PR 文件的存在和绑定，不执行贡献者代码，也不证明事件内容真实、共工侧谛听已消费或直推已被服务器阻止。历史缺失事件保留未知，需原执行者提供真实来源后追加。完整强制执行仍依赖管理员把检查设为 required 并保护默认分支；共工工作区使用其自身采集入口，不将其数据伪装为 Olympus 事件。本地 `issue_gate.py` 在其他在途修改范围内，当前未调整其对首次无事件需求的阻断行为。

## Git 接入子模块 PR 验收

子模块 PR #26 重放到 #35 合并后的 main，41 项 issue-workorders 测试、正式框架校验、真实 #9 门禁与提交后 Hermes 检查通过。首次静态 CI 提示两份 Python 文件需要 Ruff 格式化；已按仓库配置修复，追加证据见 `data-collection/issue9-git-workflow-ci-20261104.json` 和 Hermes 事件。此 PR 只交付宿主 Git 接入子模块，#9 的共工真实来源绑定与 Ariadne 自动消费继续等待实际后续交付。

## 2026-11-05 当前共工来源对账（取代上文当前状态判断，历史保留）

本轮产物为 #9 的来源证据与接入调查候选，以 `1b0a33fd5e3a579e70c46aedeb67dc3f179c2130` 为输入基线。范围限本需求文档、追加采集来源及谛听记录；Windows / Python 3.14，未改引擎，不需要编译器或引擎构建。验收是既有真实事件的 envelope / 文件回执 / 消费记录一致，以及明确当前来源缺口；停止于可审源码证据候选，不承诺已部署接收服务。本轮只负责 #9；其他聊天的代码和工作副本保持独立。

现行框架已统一为共工，当前入口是 `customizations/components/issue-workorders/issue_events.py`，共享记录与分析入口是 `framework/extensions/diting-files/diting_files.py`。上文 Olympus/Hermes/Ariadne 描述仅为历史，不构成恢复其运行链、双工作区部署或旧入口的指令。`work-items.json` 的 `sinan_source_registered=false` 与实际司南 board 的 0 注册、0 读取来源一致。

### 已有真实证据的复用

协调宿主已显式接收 #55 的真实 renamed 事件 `35149121962`，首次与重放报告 idempotent false/true。本候选原样复制其 envelope、receipt 和当前谛听记录，保留 #55 的原需求 ID、宿主身份、时间与摘要，不归因为 #9 自产事件。路径均以仓库根解析：`data-collection/issue-events/4b616abe9db4e0eba1c8e348fbee22ec71aaef4616ff2c85958714d738923984/`。本轮再次通过真实 GitHub API 核对事件 ID、类型及时间，并检查 envelope SHA256 等于回执绑定值。

`data-collection/issue9-source-reconciliation-20261105.json` 提取协调宿主既有 analyze 的消费摘要并绑定原输出字节 SHA256。原输出编码为 GB18030，解析后目标记录与本候选 canonical event JSON 完全相等；原输出读取 1459 条、当前 1049 条，包含只读历史来源。这是旧输入对应的实际消费证据，不是本候选重新执行 analyze 的计数。消费者是显式调用工具的 Codex 宿主，不能称为谛听 Agent 自动消费。用量保持 null，覆盖仍 unknown。receipt 内的 git_committed=false / diting_consumption_confirmed=false 是生成时事实，追加本次对账不覆盖旧回执；提交后的 Git 核验另行交接。

### 来源适配调查与缺失决定

现有单次入口已按 repository + issue + event ID 幂等，映射类别、状态、assignees、显式依赖标记和需决策状态，并保留当前快照与原事件的时间边界；只关联，不派发、不关闭父单。`framework/modules/sinan/coordinator.mjs` 的 board 读取 `state.json` 的 ledgerId/tasks；prepare 调用原来源 CLI。它尚无 GitHub 来源协议，不能将 GitHub 快照伪装成元衡账本或仅填写 sources 后宣称接通。已存在的单次映射可复用；真正的司南来源适配仍需明确只读快照接口、版本校验、followUps 的稳定外部键，以及实际 start/ack 回执接口，并针对独立候选完成治理审查。

解除外部阻塞需要宿主责任方给出：实际接收环境与维护责任；由哪条原生业务事件向入口传递 repository/issue/event ID；授权主体及仓库权限引用（不提交凭据）；持久化收件位置和失败后由何种真实事件触发重放；司南连接的批准候选与 start/ack 接收方。提供一个真实投递回执后，才能验证端到端代表任务与协调回读。在这些决定缺失时保留 open/blocked，不自建 webhook、不新增定时扫描，不将本次证据对账当作父单完成。下一事件是上述绑定决定及真实投递到达，或协调者合入本证据候选后回读提交。

本轮验证只需来源摘要、原消费记录一致性、真实 GitHub 事件回读、司南 board、`git diff --check`、提交前正式 Issue 门禁和提交后 `git-check --require-committed`。未改组件或冻结框架，无新增准入或启用声明；必要独立审查针对本次证据与表述边界。
