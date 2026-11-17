# 合契同产品不可变集成核心

工单 #1466；request_id `native-product-integration-20261118`。
所有路径以本仓库根为基准。本模块是现有司南工单接入的 Python host_tool，
复用 NativeCandidates、NativeWorkspace、NativeCheckRunner、NativeRelease 和
NativeWorkflow 域事务，不产生 Agent/Skill 定义，也不调用 Git 作为产品运行时。

## 安装与输入

安装者构造 `NativeIntegration(workflow, candidates, installed_plan, installed_resolver=None, review_receipt=None)`。
四个 native 端口必须连接同一权威数据库。安装者提供原有 workflow.principals
角色端口，包含 integrator/checker/reviewer/publisher，使用 resolver 时还须提供
resolver 身份。所有身份来自安装端；HTTP 不接受 actor、命令、贡献列表或成功事实。

任务授权增加 `delivery_mode="contribution"`。其原始终态必须由已验收生产者入口写入，
具有 produced、candidate、intake；有变化时 intake 是 NativeCandidates 的完整原件。
无变化时须保留 intake=null、no_changes=true、成功过程退出和原 transcript/来源，
候选必须精确等于原 selected；仍执行原检查，不构造虚假收件。
原件须绑定 native-source:source 摘要、native-worker:任务执行 ID、原 tenant/issue。
原始 base、写入边界、完整候选、生产者与当前原需求权限在消费时回读。
`check_contribution(actor, task)` 执行实际安装检查，保存贡献检查记录；不发布、不关单。
普通任务 review/complete 拒绝直接消费 contribution。已有单任务 finish 会转入贡献检查。

`installed_plan(actor, group)` 返回且仅返回 tasks、product、channel、base、expected、
checks、request_id、issue_url，可选 repins。它是组织授权的完整冻结成员集合。
authorize 保存每个任务的完整原合同、来源、原终态摘要、收件摘要、检查回执与固定
产品基线；计划 ID 是完整内容摘要。更换产品基线/expected 需要新的安装计划。
checks 必须覆盖全部原任务检查，且至少一个检查 reads=None 覆盖整个最终产品。

## 执行与验收

execute 按每个原贡献自己的 base 与固定产品 base 逐对象比较，包含删除和同值编辑。
不同值写入、删除/更新、原 base 前置条件不一致均形成明确冲突，不采用最后写入者。
文件大小写与文件/目录别名沿 NativeWorkspace 校验。原精确依赖发生变化则阻止集成。安装端新计划可显式给出
`repins={consumer:{dependency:"@integrated"}}`，将消费者重建到最终依赖，
使用 NativeCandidates 拓扑收件；无授权不自动改 pin，循环和缺失依赖拒绝。
删除依赖和原贡献自行改变依赖关系仍须额外设计决议，当前失败关闭。
内容通过 NativeCandidates 收件并 compose；不更新 native_heads，不改原终态。
每个最终候选增加 `integration-<plan>/integration.json`，含全部原需求、验收文本、
任务和收件引用；这是实际检查输入，最终检查证据绑定该完整候选及既有检查上下文。
每个计划的 manifest 均唯一，联合证据不借用缺失原需求覆盖的旧候选。

resolve 调用安装端 resolver，参数为 actor、原计划、确切冲突对象、稳定请求键。
安装端返回其自己身份写入的真实 NativeCandidates 收件。输出必须仅覆盖完整冲突
路径集合，保持产品基线及依赖；合并结果落入新计划，旧计划和贡献不变。
resolver、integrator 和所有原生产者均写入 native 事务内的权威作者集合，禁止自审。
检查、resolver 和独立审查调用均在域/native 锁之外。

finish 执行实际联合检查、安装端独立审查、NativeRelease approve/publish。
发布请求键固定，NativeRelease CAS 保持 expected。发布 guard 与 fan-in 采用
native 写锁在前、域写锁在后；全部来源、任务活跃版本、权限、停止状态与精确检查
策略重新核对。fan-in 在一个域事务中更新所有任务、managed issue、状态、进度和
outbox，故障全部回滚。发布后域失败，重试按原发布请求读取已验证历史发布，即使
同产品 head 已推进，也不重发/重跑原生产者。CAS 失败可以授权新计划复用原件。

HTTP `POST /api/v1/native/workflow/integration-{authorize,status,execute,resolve,reconcile,finish}`
分别仅接受 `{group}` 或 `{key}`。认证沿已有会话，未安装返回明确失败。
status 会重新检查当前权限与来源；它不提供绕过撤权的历史读取入口。

## 实际验证与保留范围

test_native_integration.py 使用真实 NativeCandidates、文件对象、SQLite 事务、
NativeCheckRunner 子进程、NativeRelease 与认证 HTTP。原终态通过测试适配器安装，
**不证明 #1461 的物理生产者或 Node 派发已接入**。独立 review/resolver 是安装端
测试端口，未调用生产模型，不宣称模型质量或真实模型验收。

本次范围包含联合内容、一次发布、冲突后继计划、原件/head 保持、原子回滚、
历史发布恢复、CAS 后继复用、来源换版、生产者撤权、读者 ACL、遗漏原检查、
联合语义失败、resolver 禁止自审，以及认证 HTTP 输入限制。

恢复支持真实 resolver 收件和已批准 NativeRelease review 的稳定请求键回读。
审查进程结果未知但尚无 NativeRelease review 时，只调用安装端 review_receipt
读取其权威执行账本；必须返回非空 id、精确 plan、candidate、reviewer 与 accepted
decision。该端口必须验证真实宿主收据，不允许从 HTTP 或模型自述构造。
没有实际收据仍保持未知，不重跑 resolver/审查。

尚未支持：依赖删除/生产者自行改变依赖图的语义决议、跨进程撤权竞态压力验证、
生产者/Node自动集成事件推进。#1461 接入、Linux、构建边界、独立
审查、正式发布和原父工单完整验收由上级继续；本模块不关闭 Issue。

持久化：native DB 增加作者表；域 DB 增加贡献、计划和阶段意图表。卸载模块后
保留这些历史行；不得回滚为可逐任务发布的 contribution。回退保持 contribution
停止交付，原候选与已发布产品仍可由既有 NativeRelease 查询。

缓存纠偏：原单任务 review 曾将 cached 检查结果当作含 outcome 的进程结果，
真实缓存命中导致 KeyError。共用 check_passed 对 cached 重新调用 EvidenceCache.lookup，
校验实际证据 ID/当前绑定和有效期；未补写或伪造 outcome。复现前回执存于
`data-collection/receipts/native-integration-1466/cache-review-before.json`。


## Installed group event continuation (#1466)

This section supersedes the earlier producer/Node integration limitation above.
`NativeIntegration(..., installed_groups=...)` optionally enumerates group IDs for the current actor.
Only `installed_plan(actor, group)` supplies plans. Discovery durably freezes the complete spec in
`native_integration_groups` (actor/name); changing the same group fails closed. A CAS successor uses
a new installed group and can reuse unchanged contributions. Standalone installs without enumeration
retain explicit group operation compatibility.

Authenticated workflow inspect separates contributions from independently published products and
returns ready fixed groups plus isolated group errors. The new integration-contribution operation
accepts only `{key}`. Clients cannot supply plans, programs, principals or review decisions.
The existing Sinan dispatchEvent/model router remains authoritative. Completion events trigger
contribution checks, ready group discovery, deterministic merge, installed resolution only on genuine
conflicts, joint checks, independent review, one release and atomic original-task fan-in. Original
acceptance outbox events authorize actual downstream production. There is no polling timer, global
producer barrier or Git/main chasing. Restart consumes durable contributions and integration results;
unknown resolver/reviewer outcomes require actual receipts and never authorize duplicate effects.

`test_native_joint_workflow.py` runs two overlapping OS producers, distinct execution principals,
authenticated HTTP and actual Node. The joint subprocess reads integration.json original source and
criteria plus the union of L/R outputs. A downstream producer reads that same release and emits L|R.
Both fresh dispatch and restart from a persisted integrated candidate reach one joint release,
original Issue fan-in, downstream completion and requirement progress 100%; another driver launch
performs no producer/reviewer work. Real original process terminals additionally exercise identical
edits, different-edit conflicts and no-op; those merge-shape probes do not claim business acceptance.
The installed test reviewer reads actual candidate bytes but is not a production model invocation.
Linux, independent review, build boundary, actual model benchmark and delivery remain parent-owned.


### Coordinator terminal events (#1466)

The installed `NativeWorkflow` owns completion futures for executions it actually
starts. Authenticated `await-terminal` subscribes under the same lock as ownership
registration, waits asynchronously, then reconciles durable state with current
source authority. Completed registrations are removed; late subscriptions read
durable terminals. Observer cancellation does not cancel execution. The deadline
is the worker profile timeout plus 60 seconds for persistence; expiry reports
unknown without transferring ownership or restarting production.

Node uses this port after ambiguous execute or running responses, then continues
contribution, integration, release and outbox in the same drive. One immediate
observer reconnect handles one lost reply. `executeTimeoutMs` configures transport
tests; production defaults to 120000 ms. Reconnecting drivers also observe visible
active executions. There is no idle polling or global completion barrier.

Live notifications require the exact installed coordinator instance owning the
execution: the current single-coordinator HTTP host. This is not a distributed
broker. Another process/restarted coordinator can reconcile a durable worker
terminal; unowned active execution explicitly returns unknown and holds occupancy.
Remote completion brokers, disconnected-client auto-restart and broker failover
remain unsupported; no PID takeover, lease expiry or producer replay is used.
