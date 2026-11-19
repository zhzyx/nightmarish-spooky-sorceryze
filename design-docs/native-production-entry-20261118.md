# 原生工作流普通入口与自动推进

需求 ID：native-production-entry-20261118；父 #1444，原始用户目标 #1382。路径以实施仓库根解析。当前用户已授权继续实施；最高优先级仍是完整 AI 链路效率，不以各机制测试成功代替正常产品交付。

已有原生存储、任务、贡献接收、远程节点和模型提案机制；#1486 的源码交付、#1488 持续合入与 #1495 观测仍在各自交付流程中。普通服务器启动、用户注册并创建需求后，是否能够通过实际安装的司南策略自动拆单、选择模型/节点、生产、独立检查和审查、发布及回写进度，尚须逐入口核实。私有试验脚本手建 fixture、授权对象、产品安装和驱动调用不等于产品已提供这些入口。

1. 对当前可信 main 的实际服务器启动路径、API、安装配置、浏览器/Godot入口和事件消费建立源码证据图；与已独立审查的1486/1488候选对照，明确哪些是运行能力、哪些仍依赖私有测试配置。只核对本任务，保留 #951/#1343 原责任。
2. 设计一个可安装且可回退的正常产品接入，复用现有司南/偃师/合契/阎罗和原生状态机；不另建模型客户端、任务数据库或协调 Agent。登录和组织边界仍由现有服务器负责。注册不把未经授权的模型或执行程序开放给组织；平台运营者安装执行能力，组织用户选择已准入能力并在其需求范围内自动运行。
3. 需求修订、拆单、模型路由、工作者领取、检查、独立验收与完成事件须经实际现有契约绑定；过程持久可恢复、未知外部执行不重放。只处理真实事件，不新增定时扫描。模型调用按任务复杂度和能力证据选择已安装 CLI/API，不能绕过评测或从用户文本执行任意程序。
4. 首先给出可复现的普通入口缺口证据与最小实施分解，由根责任者核对后实施隔离代码；再从正常注册/需求 API 运行两名用户的相互独立任务及相关协作任务到交付，额外再测撤权、未知执行、重启与失败恢复。模型可用确定性测试安装验证状态机，真实模型、实际服务器沙盒和正常用户操作另行留证，不能混淆。
5. 不要求一次完成整个文档/表格/视觉产品，但正常 API/CLI 入口应可供浏览器与 Godot 共用，未覆盖的人机交互明确留在父项。原始需求和工单都在原生平台权威存储；Git只用于本实现留底及可选导出。
6. 宿主工具/运行包的实际构建输入、安装身份、停用和回退随实现登记；不改渲染能力，不重编译无关宿主脚本，不使用未验证安装替换服务器生产。

首阶段为事实核对与设计，不修改任何产品源码，不运行模型或生产部署；普通需求无需新的框架定义或治理批准。根责任者保留整体验收与正式交付。

## 2026-11-18 普通入口审计与实施边界（#1499）

审计基线为 `8da2ba2ef656cc352e69f286ed4f648eb25f2242`。本节仅事实核对及待实施设计，不表示普通用户链路已交付。逐文件 SHA-256 和实际探针见 `D:/GongGong/data-collection/receipts/duobao-1382/native-production-entry-audit.json`；该绝对路径以本机宿主解析。

已召回 `editor-dependency-handoff`：`bind-consumer-release`、`await-terminal-observers` 为 verified；`verify-normal-product-entry` 的原记录是 propose，不能称为已验证经验。本次应用前两项核对真实字节、接受回执与进程终态；第三项只作为本工单可证伪试验建议。

### 源码事实

以下位置均以本工作树根解析，另标 producer/continuous 的位置分别在其独立候选树。

| 位置 | 实际行为与缺口 |
| --- | --- |
| `customizations/components/tianxuan/server/main.py:53,83` | native 模式构造 NativeStore 并传入 create_app，未传 native_workflow；没有生产安装、需求规划、调度消费生命周期。 |
| `customizations/components/tianxuan/server/api.py:299,315,566,579` | 工作流仅显式对象注入才挂载；需求 POST 只写需求，tickets POST 由调用者提交拆单结果。 |
| `customizations/components/tianxuan/server/tianxuan_core.py:1097,1543` | create_requirement 创建文档；plan_tickets 是现成拆单落库端口，非模型规划器。应复用，不能再造工单库。 |
| `customizations/components/tianxuan/server/access_control.py:43,72,114` | 非严格模式可注册/会话；严格部署以个人访问密钥及租户准入认证，禁止自行注册。两者不可混称正常生产注册。 |
| `customizations/components/tianxuan/server/native_remote_host.py:23,35,40` | 专用启动器需要外部 trusted factory(config)，仅接受 RemoteNativeWorker；提供组装接口，不是仓库已交付的产品安装策略。 |
| `customizations/components/tianxuan/sinan-workorders/native_workflow.py:30,553,609,616,665,798` | installed_plan、next_issues、principals、review_candidate、installed_target 均需可信安装；已有独立检查/审查/发布/验收、任务修订与完成 outbox。advance 缺 next_issues 时为空，不会自动拆单。 |
| `customizations/components/tianxuan/sinan-workorders/native_dispatch.mjs:40,94,155` | driveNative 调用现有司南 dispatchEvent，并在自身运行期间消费终态；CLI 需手动启动，pending 耗尽即返回，没有需求创建触发或新需求唤醒契约。 |
| `customizations/platforms/process-management/yuanheng-local/sinan/dispatch.mjs:31` | selectModel 使用 capabilities/targets/available/preference；复杂度须由可信规划策略转成能力要求和已评测目录，不得臆造性能排序。 |
| `customizations/components/tianxuan/sinan-workorders/native_remote_worker.py:25,32,53,122` | 节点来自可信安装 nodes 字典；有租户、token digest、profiles、容量及 package；绑定独占协调器。不是用户自由注册执行程序的入口。 |
| producer `customizations/components/tianxuan/sinan-workorders/native_model_producer.py:25,41,83,118` | source_digest/prepare_inputs/register/launch 绑定现有签名 host-http runtime grant；授权后、execute 前必须由宿主准备精确输入与不可变注册。没有用户需求到 grant 的产品适配器。 |
| continuous `customizations/components/tianxuan/sinan-workorders/native_continuous.py:74` | ContinuousIntegration 复用 integration，持久 lane/queue/batch/drive，需 installed policy。应直接安装，不另建发布队列。 |
| continuous `customizations/components/tianxuan/sinan-workorders/native_continuous_acceptance.py:24,29,35` | 验收脚本手建 fixture、principals 和 runner，证明机制边界，不证明普通用户操作。 |

实际探针直接导入普通 main，隔离 SQLite，ASGI TestClient 使用正常注册和 session bearer，不注入 workflow 或 fixture。两个独立租户均注册 200、需求创建 200、工单列表为空、workflow/inspect 404，domain DB 无 native_tasks。未启动网络监听、模型、节点或生产服务。系统 py 首次因缺 fastapi 退出 1；借用已存在 tx-venv 后退出 0。探针不能证明严格生产部署认证或真实模型链路。

### 待根责任者派发的最小实现

1. **可信安装层**：新增 `server/native_installation.py`，由 main 在显式运营配置开启后加载，普通用户请求不得指定 Python 工厂、argv、环境、签名密钥或 principal。安装清单采用绝对路径及摘要，区分 domain/native DB、worker root、模型评测目录、节点 package、checker、独立 reviewer、publisher、产品 channel 和容量预算。构造现有 NativeWorker/RemoteNativeWorker、NativeCheckRunner、NativeRelease、NativeWorkflow、NativeIntegration 及 #1488 continuous；沿现有模型运行时和 #1486 注册接口，不新建 LLM client。保留无安装时可读能力状态，配置错误明确失败，不能静默声称自动执行可用。
2. **偃师规划适配器**：新增 `sinan-workorders/native_requirement_plan.py`，以 actor、需求 ID、精确版本/摘要和已授予的任务范围为输入；调用已准入偃师角色及现有运行时生成封闭 schema 的 DAG 提案。验证父子映射、验收归属、依赖无环、有限模块写集合、已准入能力、权限及产物目标后，通过现有 plan_tickets 落库。将计划与来源修订绑定，向 NativeWorkflow.installed_plan/next_issues 提供合同；提案不是批准。确定性模型安装可测试 schema，真实规划能力单独评测与实测。复杂度映射到既有司南目录要求，由 selectModel 实际选择；没有匹配能力应保留可见阻塞。
3. **用户入口**：在现有需求 API 提供自动执行选项或单一 execute 操作，用户只提交需求、验收与本应由其决定的产品/授权选择。系统内部生成 task contract、grant、write allowlist、product plan；不得让用户手写这些对象。原有手动 tickets 模式可保留。需求创建/修订与请求自动执行应有一个幂等 call_id 和来源版本绑定；事务内保留待处理事件，提交后唤醒。浏览器/Godot 共用 HTTP 契约；本阶段不承诺 UI/render 改造。
4. **事件与进程桥接**：新增 `server/native_execution_host.py`，只负责已有 driveNative 的启动、通知、回读和终态监督。沿 domain DB 增加最小入口事件/消费游标与外部调用 intent 元数据，复用 native_tasks/native_outbox/continuous 驱动账本，不建第二套任务状态机。现有通用 events 有裁剪能力，不能直接以可裁剪审计历史替代不可丢的执行事件。每个租户/执行授权的事件绑定 actor、版本、授权引用；发布 outbox 与领域变化同事务。进程驱动使用可信安装身份及受限委托，不把用户密钥写命令行或数据库。driveNative 的薄 IPC/HTTP 适配器仍使用司南 dispatchEvent；机器节点凭证继续只访问 outer node mount。
5. **明确消费时机**：启动时获取既有单协调器所有权，先回读持久未消费入口事件、active reservations、worker terminals 和 outbox，然后只唤醒已有 driver；创建/修订、真实终态、验收、显式恢复/权限变更时通知。睡眠为有界条件/流等待，无周期扫描。驱动空闲退出与新事件提交通过短事务 claim/generation + 退出后二次回读防止丢唤醒；锁内只操作账本，不运行模型、检查或等待网络。进程退出必须确认 stdout/stderr/终态落库；驱动退出 0 本身不等于业务验收。
6. **未知与恢复**：外部 launch/model/review 的 intent 在副作用之前持久化。重启按已有 receipt、request/turn、process closure 回读，known-not-started 才可继续首次启动；unknown/held 不补发、不自动切模型、不释放占用。生产成功而发布回执未知时调用历史选择回读，不重新发布。缺少可信 review reconciliation 时保留明确未完成，不能清理 NULL review intent 后重跑。权限每次规划/领取/执行/检查/发布/消费重核，等待结束后重核，撤权期间不推送私有结果给原调用者。
7. **独立交付**：checker、reviewer、publisher 来自可信安装的现有权限模型；reviewer 必须与 producer 独立，审查 exact candidate + 原验收；不得以 callback 恒 True 或同一生产会话自批。合契负责贡献/冲突，阎罗沿当前 NativeRelease 精确发布与 complete 回写 Issue/progress；完成 outbox 只释放真实已验收依赖。

文件建议范围：上述三个新模块、main.py/api.py/native_api.py 的窄入口和 lifespan 接线、native_dispatch.mjs 的事件传输适配、相应 normal-entry 测试和 README/build-impact/host inputs 登记。只有确需原子持久入口事件时才在 tianxuan_core.py 增加领域端口；不得修改 #951 控制器或 #1343 渲染所有者内容。具体实现由根责任者另行授权；本审计未改产品源代码。

### 验收矩阵与交付边界

* 安装验收：只从文档化 main/CLI 安装进入；可信管理员预装评测合格 profile、角色授权、检查/审查程序和节点，关闭后回退到只读/手动能力。普通用户零 Python fixture、零 grant/task contract 编写。host_tool 按实际脚本/运行时输入哈希登记；同一运行包更新/停用/回退并拒绝旧摘要，保留未知执行和必要回退版本。
* 两用户独立链路：两名已认证用户提交各自私有需求，各自从父子工单、自动司南分配、真实 worker terminal、内容检查、独立审查、发布选择到 progress/Issue 完成；验证互不可见。非严格注册模式与严格管理员准入模式各自单测，严格模式不虚构自注册。
* 两用户协作链路：同组织通过现有分享/成员权限共同授权产品，两人贡献可并行，已有 continuous 队列按精确候选联合检查并保留旧验收；冲突由已安装合契解决，不能任意覆盖。一人的失败不阻塞无依赖私有任务。
* 崩溃矩阵：入口事务提交后通知前；reserve 后 launch 前；外部已启动但返回丢失；process closed 但流/terminal 未落库；review 已发出但无回执；release 成功但 complete 前。逐格验证重启只回读/继续可证明的步骤，未知项不重放，队列不丢事件；进程关闭及日志 flush 留证。
* 撤权/修订：等待中撤销 session、组织写权限、能力安装或节点；拒绝后续副作用并保持占用直到真实终态。需求版本/候选变化拒绝旧授权；显式新修订另有幂等来源，旧证据保留。
* 分层证据：确定性安装先验证上述状态机；独立审查精确候选后，再正常部署沙盒、真实已评测模型、两用户 HTTP/CLI 操作全链路留证。机制测试、ASGI 探针和固定模拟模型均不能替代真实模型/实际服务器验收。浏览器/Godot UX 与未覆盖产品能力留父 #1444/#1382。

尚未知：可信生产安装清单及真实主体准入；实际模型能力评测与可用预算；#1486/#1488 最终 main 候选；严格生产部署现状；完整独立审查安装；UI normal-entry 操作路径。本审计未调用远端/provider，因此不能补写这些事实。没有发布、合入或关闭任何工单。

临时资源：保留本次 probe.py、SQLite 和 normal-main-result.json，供根责任者接受审计后归档/清理；不存在模型/监听进程。未创建分支/worktree，未删除他人资源。当前子任务终态为审计设计完成，原始整体验收仍未完成。

## 2026-11-18 #1499 实施与确定性普通入口验收

当前实施复用已接受 main `88a401d8a8498af36063eedbed3abc5657c52d90` 的原生
producer/continuous 接口；不在实施期间追新 main。入口、安装 schema 与边界详见
`customizations/components/tianxuan/server/native-entry-interface.md`。

已接 normal main、ASGI API 与 lifespan，安装者只需固定配置及摘要，不要求普通用户
编写 Python factory、plan、grant 或 command。用户创建需求后选择已安装有限 scope
并调用 execute；真实 Node driveNative/司南调度原生任务，现有 NativeWorker、检查、
独立角色审查、ContinuousIntegration、发布回读与原需求/父子工单进度完成收口。
模块按租户和需求命名空间隔离；同需求已授权贡献沿同一 continuous lane 发布。
会话/访问密钥、来源修订、安装及需求权限在副作用和等待后重核；生产和检查等待支持
真实撤权取消。只凭精确物理关闭回执沿既有接口结算撤权占用，不释放未知外部执行。
独立入口可在另一入口等待时继续，产品内事件串行且不持有 SQLite 锁执行外部程序。

主 ASGI 确定性试验覆盖两独立租户、同组织成员分享后的继续贡献、实际生产与检查进程、
独立内容审查、连续发布、需求100%、等待中logout撤权、重启不重放，以及管理员预置
key的严格入口拒绝自注册并完成新需求。审查原始贡献逐项重核，完整序列化快照超
100000字节时明确未审查；不截断，不称为全链路token优化。只读broker恢复验证原签名
绑定并读取已完成runtime回执；未知结果不重发。最终测试数量及源码摘要以
`data-collection/native-production-entry-implementation-1499.json` 的同次回执为准。

该 normal factory 当前为 **local-only**，即在安装服务器运行固定的本地命令。
已有远端执行机制不是当前 normal main 已接通的证据；可信构造器仅保留现有
NativeWorker/RemoteNativeWorker注入点。#1501 context_factory仅留可信宿主接点，
v1报告context_tools=false，未提前启用v2，也未更改#951/#1343消费者。
真实远端设备接入、正常沙盒监听服务器、实际已评测模型与独立业务审查仍由根责任者
推进；测试安装明确标为deterministic-test，不替代这些验收。没有生产模型、网络监听、
提交、推送或部署行为。

构建类别为host_tool：输入为安装清单、固定角色程序、上述入口/原生工作流源码、
既有host-http及owned-process运行时。改变固定文件或配置摘要会拒绝继续；停用环境
配置后回到native手动存储入口，必须保留未知runtime状态与必要旧安装。实际整包
更新/回退与正式build-impact/host inventory由根责任者核对，本子任务不改全局登记。

### 原目标未完成项（根责任者要求先冻结审查）
product_locks目前覆盖同requirement的consume_product全链路，两个成员的不同entry不能重叠生产；只有单entry DAG内部仍可并行。第二entry要求与首份modules aliases完全一致，不同scope会拒绝；依赖只在本entry mapping内解析，next_issues仅枚举该actor的entry。上述普通共享需求试验是顺序贡献，不能算同产品多Agent并行达标。根责任者要求停止扩大该调度修改并先独立审查，完整原需求保持未完成。签名bridge专项已实际验证并修复中央预算tasks/jid路径及Diting结构化work_items，使用synthetic测试安装，不代表真实模型准入。


## R1–R4 parallel repair candidate

The repair uses one finite installed module catalog per shared requirement, stable
scope provenance, short atomic seed/identity reservations, and task-specific inputs.
All role/process waits run outside product locks. Existing NativeWorkflow, Sinan,
NativeIntegration and ContinuousIntegration remain the execution/delivery owners.
The ordinary API binds optional existing-task dependencies to immutable contracts
and sources, wakes on durable acceptance/credential/source events, and keeps unknown
physical effects occupied. Each unfinished original retains its exact entry grant.
Explicit coordinator handoff performs old-policy CAS and physical acceptance readback;
active unknown publication cannot transfer. Entry settlement is independent of the
shared requirement aggregate; the shared parent closes only after all mapped tasks.
The interface and evidence index document catalog migration and handoff limits.

Validation uses isolated finite deterministic installed programs through actual normal
main/ASGI, real Python and Node subprocesses, with original failed probes preserved.
Physical intervals, old logout/new credential behavior, cross-member dependency wake,
slow-peer entry settlement, conflict isolation and coordinator handoff are checked.
These receipts do not accept live model quality, listener/device delivery, package
update/rollback, remote adapters or #1501 context integration; those remain root scope.

## #1499/#1501 ordinary runtime integration (2026-11-18)

`main` accepts an operator-pinned `TIANXUAN_NATIVE_RUNTIME` absolute JSON path and `TIANXUAN_NATIVE_RUNTIME_SHA256`. Its closed v1 schema is `{version, installation, remote, context}`; `installation` is the exact ordinary installation manifest digest. `remote` is null for local execution or `{profiles,nodes}` using the existing RemoteNativeWorker public descriptors. `context` is `{local_token_sha256,full_bytes,limits}`; limits remain NativeContext's bounded response/chunk/total/read limits. This is installation data, never an ordinary request field. Runtime policy bytes are checked again on authority and context operations. The main process creates the existing RemoteNativeWorker and mounts the existing outbound-node API when configured. Sinan remains the dispatcher; model routing, checks, independent review, integration and publication retain their existing owners.

The installed producer broker optionally accepts `context_transport:{server,token_file}` in its already digest-pinned configuration. The token file is private to the installed broker/node. HTTPS is required except explicit loopback HTTP; redirects and URL user-info are rejected. No token, signing key, argv or principal enters the signed model input. The server receives only the existing node token hash/public installation identity, not node model credentials. NativeNode's trusted configuration accepts `contract_registry`; NativeWorker writes the immutable exact execution contract there before the existing broker signs its grant. No ordinary API accepts a grant or executable configuration.

For small selected materializations, the broker retains the bounded full-context path. Above the installed byte threshold it calls prepare_context_inputs and launches with a concrete HTTP resolver factory. The runtime template must already admit autonomous native_context tools and the intended cumulative call budget; the bridge never rewrites role/model authority. Source, selected revisions, execution and installation identities are checked against the original contract. The server owns NativeContext storage and its durable ledger, reconstructs the original entry from task.mandate rather than an ambient HTTP ContextVar, and rechecks current workflow, actor/tenant, assignment node/package/profile, cancellation and selected-revision authority before every RPC and after its effect. Historical delta pairs are not admitted by this sidecar; the existing general NativeContext callbacks and historical-revocation tests remain intact.

The resolver implements the existing NativeContext interface (including durable events and identity); it is a transport adapter, not an LLM client. Model-host closure is recorded separately from worker closure. Only the worker receipt reader, after checking the actual immutable process/output records, appends the final physical process closure. A closed worker rejects later context RPCs. Unknown read/model intents remain durable and cannot be replayed. Context reads remain `reads:null`, not merge read-sets.

Validation uses deterministic admitted fixture programs, actual ASGI main, loopback HTTP, the existing Node runtime and separate node storage. Ordinary remote execution reaches delivered/100%; signed local and remote broker tests run actual multi-turn context tooling and retain final context receipts. This does not establish production activation, model quality, organization identity resolution or WAN deployment readiness. No model/provider request was made. The earlier small trial (tools 157s versus full 127s) remains a counterexample to universal context savings; threshold policy is boundedness/fit policy, not a performance claim. Root retains installation packaging closure, independent review, production admission and Git delivery responsibility.


## 2026-11-19 已完成源码分片提交与保留验收

用户要求提交已完成的部分，高并发实测继续延期。联合候选 PR #1564 的普通 Docker112项通过，但完整模块套件1236通过、3项合契普通入口停在planned/67%，故该联合候选未准入main。原提交与失败记录保留，合契v3源码和验收由 #1526 / #1499 原责任者继续持有。

本分片从可信main ac8d1376d0a03678b625cbe4bd9b09ea18120475 独立提取已审查的上下文HTTP惰性TLS、每次已知未启动重试的新Request、受测镜像导出和摘要清单。传输适配仍连接已交付v1/v2普通入口与原生上下文，不依赖未接收的v3 resolver；不新增或替换模型、调度、工单存储或渲染层。有效服务器安装未变，回退保留原安装、授权、未知执行与原始回执。

两份常规工作流显式排除 test_250_local_tool_burst，原测试保留在部署构建的手动布尔输入 run_context_burst（默认false）。普通功能、安全、撤权、恢复仍为必需检查；归档明确记录not_run_user_deferred，不宣称高并发容量或token收益。该决定不把历史失败改写为成功。

#1529正常归档下载/身份核验/服务器安装及同包更新回退、#1501完整生产集成、#1526合契失步原因与剩余恢复场景、整个多组织平台及AA渲染目标继续未验收。此分片main交付后各原发布者按自己的候选复验，不能提前释放依赖resolver的整体验收。
