# 接通 GitHub Issue 事件协调与 Hermes 数据交接，核销陈旧状态

工单：https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/9

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
