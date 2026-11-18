# 原生工作者上下文按需与增量消费

需求 ID：native-context-consumption-20261118；父 #1444，原始目标 #1382。沿用用户完整 AI 工作链路效率优先、开始执行及继续授权。路径以本工单仓库根解析。

已交付的 #1414 提供普通文件快照与有界上下文差异，不代表模型生产者实际按需消费。当前 NativeModelProducer 把所选 UTF-8 文件整体放入提案输入，单文件与总输入有明确上限，超限拒绝；不得悄悄截断或误称有交互工具。#1499 正在接普通用户需求自动链路，保留其文件占用。#951 的共享 Subscription/controller 仍由原责任者维护。

本项首先按当前源码核查实际消费链：用户原话与需求修订、司南计划、NativeWorkspace 读取集/增量、producer prepare_inputs、模型提案协议、现有 CLI/API 运行时工具能力和回执。区分可复用工具与尚未提供的能力。沿真实工具/对象读取，绑定组织、任务、原始修订、读取权限及来源，重复读取使用内容摘要；未知必须显式反馈，不能让不完整摘要代替原始事实。

实施验收：

1. 给出小型目录/符号/对象清单及任务相关来源，允许经既有受信运行时按需读取原始对象和精确范围。接口有返回大小上限、续读身份、来源摘要和完整性标志；上限不能导致无声裁剪或伪装完整。固定任务版本不追赶全局 main。
2. 模型实际读工具记录真实读取对象/范围和权限，构造可核验依赖；仅扫描目录/提供摘要不足以证明读取。写入及发布仍经现有不可变贡献、合契检查和阎罗独立批准，不让模型自证可合入。
3. 已知对象与变化增量可复用，恢复只回读已持久回执，未知模型/工具操作不重放。当前撤权、跨组织、路径/符号链接替换、超限、工具失败及错误来源均须处理。
4. 保留现有完整小任务提案通路及多 CLI/API 适配；不能另建模型客户端、调度器或绕过司南判断。与 #1499 接口明确，避免修改其在途副本及 #951 占用源码。
5. 确定性真实协议测试验证多步按需获取、上下文增量、失败/恢复、读取来源与产物一致；独立审查后才做预登记少量真实模型调用，固定任务和质量标准，记录实际发送/返回字节与原始用量。合成样本只证明机制，不声称普遍 token/时间收益。

先产出源码绑定的具体接入方案和验收矩阵；根责任者确认读写边界后同工单继续实施，无需再问用户是否继续。构建类别 host_tool，原生渲染逐帧路径不变。实现后通过实际 SCons 消费者、门禁、独立审查、CI/main 留底及服务器隔离验收。完整平台/AA/生产切换仍由父目标负责，不以本子项代替。

## 2026-11-18 当前源码审计和待实施契约

本节为待实施设计，不能作为实现或业务完成回执。审计工作树 `D:/GongGong-work/native-context-consumption-20261118`，HEAD `604fd44d64fc96cb2c110ecb26b3a36aacdff002`；逐文件摘要及五项无模型探针在 `D:/GongGong/data-collection/receipts/duobao-1382/native-context-consumption-audit.json`。未访问 #1499 工作树。其 planner “固定完整需求＋selected scopes/complexity、没有新读工具”来自根责任者转交，尚不是本候选源码事实。root 已回读 intake-only exit 0，来源事件 `gonggong-diting-data/events/gonggong-workspace/native-context-consumption-20261118/codex-intake-1501-20261117.json`，SHA256 `819ae0291be9992cbe661ac5dea48fcf214577c30b3509403b1925bdf78c75c0`。

召回 `editor-dependency-handoff` 的已验证 `bind-consumer-release` r21 和 `await-terminal-observers` r6：下一阶段必须绑定真实接收者、候选字节、进程关闭与回执持久化；候选改变、仅运输成功、日志未闭合均不放行。此审计只证明当前事实和方案，不能释放生产验收依赖；未把其他候选方法当已验证经验。

### 当前事实与最小选择

* `NativeWorkflow.authorize_task` 固定 source/selected/writes/producer/installation；`NativeWorker.run` 物化完整模块闭包，传 definition 文件，通过实际进程关闭和日志摘要才收集候选。
* #1414 的 `NativeWorkspace.sources/materialize/collect/delta` 是文件宿主视图；`sources` 校验读过原始 blob 也不等于模型读过。`collect` 写入 `reads=None`，保守拒绝同模块漂移。`delta` 固定两个修订及租户分页，可能 `content_omitted=true,truncated=true,next_cursor=null`；现有 `NativeStore.read` 只能补读整对象，没有模型范围读接口。原 API 没有身份认证，必须在可信宿主授权外壳内使用。
* `native_model_producer.prepare_inputs` 将整个 UTF-8 文件图放入 request 和 private binding；`snapshot` 每文件 131072、整 JSON 100000 字节，但 host/JS 的 context 上限 65536，还需容纳 adapter 追加治理文本。这是明确拒绝，不是截断或真实按需读取。
* `runner.validate_plan/_run` 已有自主模式 `lookup_resource`，仅返回已签任务内静态 resources[key]；single 禁工具。事件只记 key，不记正文摘要、范围与交付状态。`verify_grant` 验签/版本/期限，不查询当前业务读权。
* 原生 adapter `build_request` 假设每个 user message 都含唯一 native_request；真实工具结果会 KeyError。CLI helper 强制 `available_tools:[]`、固定 proposal schema，`call_native` 总包装 action=final。必须修改真实适配，不能把新 prompt 清单称为工具。
* #951 的 `Subscription.turn(input,scope,schema,prompt,progress)` 可承载严格 JSON；增量复用需 `accepted()`、精确前缀和身份，compaction/权限或绑定变化会重建。当前 native helper 每次 start/close，未复用其多轮 session。此次不改 `tools/codex_cli/subscription_session.js`、`godot_bridge.js`、controller。第一版使用既有 runner 多次有界调用，承认 CLI 每次新 session、历史重发，不预先声称 token/时延节省。

最小实现：保留一个现有 runner 循环、现有 adapters、原 small-full proposal；添加宿主 context 能力、允许现有原生通道返回受限 action。没有第二模型客户端、调度器、直接 shell 或 provider 工具。初版保留文件物化和候选冲突的 `reads=None`，新增可信实际读取账本，不将局部读范围误用为可以合并漂移头的证明。

### 文件及函数边界（待 root 接收后派发）

| 文件（仓库相对路径） | 待实现内容 |
| --- | --- |
| `customizations/components/tianxuan/sinan-workorders/native_context.py`（新） | `NativeContext(store, authorize, binding, ledger)`；`manifest(cursor=None)`、`read_object(args)`、`delta(args)`、`receipt()`。仅可信对象解析和授权，不运行模型。绑定摘要纳入 producer source_digest/runtime_digest。 |
| `customizations/components/tianxuan/sinan-workorders/native_model_producer.py` | 保留 prepare_inputs/snapshot v1；新增 `prepare_context_inputs(contract,execution,workspace,manifest,write_allowlist,acceptance,installed_context)`；launch 按显式 schema=2 分支，校验 immutable 物化来源和安装，创建受信 resolver 传既有 runner。输出前再次核对权限、范围与工作目录身份。 |
| `customizations/platforms/ai-access/host-http/runtime/runner.py` | `run(..., context_resolver=None)` 显式注入宿主能力；自主模式白名单新增 `native_context`；单循环分派 manifest/read/delta。journal 持久化请求、解析、确切响应、调用输入关联、交付/未知状态；重建 history 只消费持久确知结果，不再起模型或工具来弥补未知。 |
| `customizations/platforms/ai-access/host-http/runtime/native_proposal_adapter.py` | v1 原样；v2 从唯一初始 native_request 加合法 assistant/tool-result history 构造固定 action request；不把 private binding/数据库路径/授权来源凭据送模型。保留原始/有效输入摘要及每次 raw usage。 |
| `customizations/components/tianxuan/sinan-workorders/native_model_host.py`、`native_model_proposal.cjs` | v2 严格 action schema：tool(native_context,arguments) 或 final(value=旧 proposal)，外层 original_request_digest、round/input_digest、context_receipt_digest。工具意图不在 JS 执行，交还 runner 后由可信 resolver 执行。无自动 fallback/retry；旧 schema 和校验仍保留。 |
| `customizations/components/tianxuan/sinan-workorders/native_worker.py` | 可选、可信安装注入的 `context_receipt_reader(task,execution)`；进程关闭后回读宿主账本，核对 execution/source/terminal，将读取证据绑定候选 terminal。任意 CLI 没有该能力仍 reads=None；禁止从工作目录模型文件接收读取集。 |
| 同目录 `test_native_context.py`、`test_native_model_producer.py`、`test_native_model_host.py`、`test_native_model_proposal.cjs`，runtime 现有测试 | 下述真实进程与拒绝矩阵；专属新测试不依赖 live/provider。更新既有文档、宿主分发输入和实际 SCons 消费者测试。 |

`native_store.py`、`native_workspace.py`、共享 Subscription/controller 先不修改；复用它们的精确修订、hash、路径校验和冲突规则。运行时安装/清单变动的实际文件由 root 结合 #1499 接收候选确认后列入写范围，不猜另一个工作者正在编辑的文件。

### 安装与普通消费者

#1499 接收后的可信 factory 是普通入口：用户提交需求→现有 planner 选任务模块/修订→NativeWorkflow authorize_task→factory 在小任务选择 v1，在显式 admitted `native-context-v2` profile 选择 v2→NativeWorker/producer→同一 runner 读工具→提案→不可变候选/合契/阎罗。用户无须输入对象 hash 或构造工具协议。第一版不改 planner 的完整需求输入；该优化只覆盖被授权生产者读取的模块对象，不能声称 planner 已实现增量需求消费。

factory 必须提供 `installed_context` 的宿主私有绑定（固定 store、业务 domain/身份适配器、安装摘要、execution→原始 contract 映射），供独立 producer 重建 **实时** `authorize(binding,module,revision,operation)`。该适配器由固定可信安装定位，模型不能指定 Python 模块/路径/数据库/租户。授权需要重新查询当前 actor/producer、原需求 doc 可读性、任务读取范围及 module rights；NativeCandidates 的 module read 检查与 NativeWorkflow 的 source/doc 检查均不能省略。存储/业务连接失效即拒绝，不以签名未过期继续。若 #1499 factory 还无此安装契约，root 应先派发此可隔离接口和授权实测，v2 不准上线；禁止临时改为 always-True 或 grant-only callback。

### 数据和工具合同

host binding v2：`schema,execution,tenant,actor,producer,issue,source_digest,definition_digest,selected,allowed_objects,allowed_delta_pairs,installation_digest,limits`；来源范围取已授权 contract，固定任务版本不读全局 main。manifest 项为 `module,revision,name,object_digest,byte_length,encoding_hint`，分页有 binding/cursor 和整体完整性。目录/符号线索只是可选索引，若尚无可信符号解析器就仅给路径清单；不得捏造符号或算作正文读取。

唯一工具名 `native_context`，严格 arguments 为以下之一：

* `{op:"manifest",cursor:null|string}`。
* `{op:"read",module,revision,name,object_digest,offset,length,cursor:null|string,known_receipt:null|string}`。range 为原始字节半开区间；UTF-8 中间边界以 base64 精确返回，不偷偷移动 offset。全对象 hash 始终返回。
* `{op:"delta",module,before,after,cursor:null|string}`；仅允许 binding 明列的一对原始修订，例如已验收上次任务→当前固定 selected。任意历史修订不是自动可读。

响应封套：`schema,execution,binding_digest,request_digest,result_id,status,source,range,content,encoding,response_sha256,complete,next_cursor,content_omitted,error`。source 含 tenant/module/revision/name/object_digest；range 含 offset/returned_bytes/total_bytes。页面完整、对象完整分开表达。建议默认总响应上限 16 KiB（含 JSON）、单片原始正文最多 8 KiB，100 个 manifest 项，初始 manifest 8 KiB；与 source 总量沿现有 Limits。单响应边界和 session 总预算签入 grant，不允许模型提高。正文不存在、二进制、权限撤销、超限、hash 错误都显式返回/终止；cursor 绑定 execution/tenant/source/权限范围/limits/offset，并在每次续读重新授权，cursor 不是凭据。

持久 ledger 每项含 task/source/tenant/actor、request id、调用序号、operation、精确对象/范围、当前授权决策摘要、正文 hash、确切序列化响应 hash、结果状态及父 call id。`resolved` 表示宿主读取成功；`included_in_call` 表示确实组入下一模型请求；`transport_received`/unknown 由真实传输回执决定。只能称为“已交给模型的字节”，不能声称证明模型理解。manifest 和 metadata/delta 摘要单列；delta 实际带出的正文也记真实读取。请求失败/读取失败不进入已交付正文集。恢复只重放已持久响应，所有缺口保持 unknown、阻止候选准入；不能自动重试未知 provider 调用。

重复内容仅在同 execution 内已有确切已交付 receipt 且仍在当前有效历史中时返回 unchanged/ref；新 session、丢失历史、compaction、跨租户、权限变更不凭一个模型自报 hash 省略内容。保留原 CLI raw last/total/source/thread/turn 和 HTTP 原始 usage，另记实际 input/output/tool-response 字节；不把累积 total 相加，不估算缺失用量。

### 验收矩阵与阶段闸门

1. 确定性实际进程：现有安装 probe 的假协议端驱动 `manifest→范围1→范围2→delta→final`，穿过真实 NativeWorker→producer→runner→NativeModelHost→Node wrapper；匹配准确输入/响应 digest、候选内容、进程关闭、最终 ledger。fixture 验证标志不得冒充生产准入。
2. 权限：两 tenant 同名对象；grant 仍有效时撤回 doc/module 读取权；工具读取前和响应发送前撤权；依赖闭包未授权；cursor 搬到另一任务。均不能泄漏正文或接受候选。auth callback 本身失败保持 unknown/denied。
3. 范围/来源：大于旧 context cap 的对象只读选段；UTF-8 分界、空对象、二进制、超限、路径穿越、symlink/junction 替换、blob 篡改、旧 revision、错误 delta pair、游标换 limits，显式拒绝或精确内容，绝不默截断。
4. 恢复：在 tool start/result commit/发送模型前后/process close/transcript flush 间杀真实进程；只回读持久事实，不双发 provider；未知读取不混进可信读取集；冻结全任务调用/字节预算不重置。
5. 集成：小任务 v1 回归、HTTP 通道自主工具回归、CLI 多轮 raw usage 不重复累计；v2 退出到 v1 仅在新授权之前选路，不能失败后偷偷重跑。无需修改 #951 接口。root 接收 #1499 候选后再跑实际 factory 普通用户入口，用真实 domain 的权限回调，不用 always-True 替身证明撤权。
6. 独立审查通过后才预登记 live：固定一个需求和质量标准，small-full 基准一次＋v2 一次，v2 最多 6 次模型调用；预登记安装、模型、source/selected、每次字节和时间预算。记录原始协议用量/unknown、产物相同验收与工具字节。未通过不扩量；该对照只支持这项任务，不宣称普遍收益。预算实际值由 root 在 live 准入记录中签定，当前审计不调用模型。
7. 新 host_tool 输入、安装摘要、SCons 包装/拷贝消费者，以及同一二进制上的能力更新/撤回实测；回退停用 v2 profile、新任务走 v1，保留原账本/未知调用/必要旧安装。完成后正式门禁、独立审查、CI/main、普通用户验收和 Issue 回读均仍待 root 推进。

本阶段输出仅可让 root 审查接口并派发实现；#1501、父 #1444/#1382 整体验收未完成。

### root 复核补充：实际闭环、负向依赖

不依赖共享 Subscription 增加动态工具，也不声称原生 app-server 工具已启用。沿现有 host-http 约定，模型生成严格 JSON 工具意图，runner 真实执行宿主工具，再把工具响应作为下一模型输入。v2 Node helper 使用现有 `session.turn` 的 schema 参数改为 action 联合结构；`available_tools` 可以仍为空（没有 app-server native tools），system 明确只允许返回宿主 action JSON。私有 v2 host terminal 区分 `tool_requested/final/unknown`，含 action/output_digest 和当前 turn 的 UsageObserver 原始回执；只有 final 验证旧 files/proposal，tool_requested 只验证指定 native_context 参数结构，不应用产物。adapter 将验证过的 action 原样交 runner，不再强行改为 final。

adapter v2 `build_context_request(messages)` 明确只从第一个结构化 user 输入提取 native_request，后续只接 runner 生成、具有 request/result id 的工具响应及已持久 assistant action；初始请求 hash 恒定，每轮另算 exact messages/input hash。不能使用当前 v1 的“解析所有 user message 为 input.native_request”，也不能将历史当作新授权。每轮 host process 继续通过相同安装和 owned_process；每个 turn 单独保留 usage.raw 和线程/轮次标识，现有 source_digest/configuration/runtime_digest 加入新 helper/context 源码。无效输出、传输未知或安装改变均停止；不会重启 session 自动补发该请求。runner 恢复持久 tool result 的确切 payload/history 时，不重新解析任意 mutable workspace 文件，也不重新执行已完成工具。resolved 未 included 不算已交付，provider call_start 无已知终态保留 unknown 并挂起受影响执行。

目录枚举、对象不存在、删除项、依赖表及符号索引均可能影响模型决策，账本另记 `dependency_kind=namespace|absence|object|revision_metadata`，绑定查询范围、原始 revision/map digest 与查询结果。缺失对象是有意义的负向事实，不能简单丢弃。初版不将该账本转换为 NativeStore 的正向 object-name reads 列表；继续 `reads=None`、全部原依赖固定 revision，因此没有凭不完整正向读取集放宽并发接收。若将来要精确放行漂移，需独立设计 namespace/absence 冲突谓词并验证，非本次最小实现。

root 已将五项探针关联夸父 #1445，incident `e0b11d9b28c10cda5ef16bb7e2f8be802b8fdb986e19315473a8bdcf23cb3d15` assessed；这是排障接单状态，不是修复回执。


### 根责任者实施决定：实际增量会话优先

审计契约接受；实现继续使用现有 runner 和 Subscription，不修改 #951 共享源码。每次工具返回都新建 CLI 会话并重发历史只可作为明确的保守兼容/测试通路，不能作为目标效率方案或默认“已优化”结论。v2 应在一次受控生产执行内复用现有 Subscription 多轮会话及 accepted()/精确历史前缀，利用真实 inputTextBytes 与 bootstrap/incremental 回执证明只发送增量。工具仍由宿主 runner 执行，模型不获得原生 shell 权限。

会话须绑定原任务/租户/身份/安装摘要和实际权限。每次工具读取及下一轮模型发送前重新授权，未知调用不重发；session丢失或compaction应保留明确恢复事实，不能声称仍增量或自动重播已未知执行。关闭等待真实进程终态，预算覆盖全部轮次且不因重建清零。不要为达到会话复用创建第二套模型客户端或绕过已有权限/治理。若复用接口存在必须先实现；仅在真实不可兼容限制有证据时，向根责任者报告精确阻塞并继续独立项。此次决定不新增真实调用次数，实际模型验证仍由根责任者在独立审查后预登记。


### 实施回读（2026-11-18，待独立审查与安装联调）

实现入口为 `NativeContext.resolve(arguments, call)`，统一分派 manifest/read/delta；固定 binding 包含 execution、tenant、actor、producer、source_digest、installation_digest、selected、limits。`source_digest` 是原始 `contract["source"]` 的 canonical sorted JSON SHA256。宿主传入 live `authorize(binding,module,revision,operation)`；每次请求、读取、响应和模型发送重新核对。账本路径须为可信安装持有的绝对路径，禁止工作目录模型文件；构造后复核文件身份与不可变 binding。

`prepare_context_inputs(..., installed_context, materialized_files=...)` 接受宿主 staging 的 `snapshot(staging, large=True)` 摘要图，以绑定尚未创建的最终 worker workspace。`launch(registry, context_factory=...)` 只接受可信安装注入的 factory，默认 CLI 不提供 v2 factory。factory 接收 `(native_binding, execution, workspace)` 并返回绑定真实 store、domain/doc/module 当前权限和 ledger 的 NativeContext。普通安装入口由 #1499/root 接续；测试 factory 不能代替生产准入。

runner 显式注入 resolver 后复用现有循环；CLI v2 只启动一个由既有 OwnedCommand 监管的 Node helper。每轮通过任务绑定、序号、input digest 和独占目录身份的原子有界信箱往返；Node 复用既有 Subscription.turn/accepted，provider 的 available_tools 保持空。首轮 bootstrap、后续精确历史前缀 incremental；compaction、历史或安装变化、未知执行均停止，不自动新建 session 补发。同 execution 已存在 model_call_start 时禁止重启会话。stdout/stderr、信箱、总轮次和总输入有上限，deadline 跨轮累计；final 等待物理退出和完整输出排空。

账本分别记录 namespace、absence、object、revision_metadata；resolved 不能当作已交付。included_in_call/transport_received 含实际引用的 result_id；另存确切模型历史、wire_input SHA256/inputTextBytes、每轮 raw last/total、时序与进程关闭。只在全部 started 已 resolved、发送已收到、最终模型 final、无 unknown 且物理 exit 0 时 receipt.terminal=final。NativeWorker 的可信 context_receipt_reader 回读 execution/tenant/source/terminal 后绑定候选；reads 仍为 None，原依赖修订不放宽。

manifest/delta 的 complete 表示当前分页链已结束，正文完整性另列 object_complete；metadata 响应 content_omitted=true，原对象需 read。UTF-8 分界和二进制统一以 base64 精确字节返回。known_receipt 内容省略目前明确拒绝，不信任模型自报 hash；已知上下文复用由真实 Subscription 增量承担。delta 只提供固定显式 revision pair 的元数据，不伪装已读取正文。未知执行仅允许读取持久事实，不自动恢复模型发送。

确定性验证包含五轮 manifest→范围1→范围2→delta→final、一次 thread/start、四次 incremental、真实 NativeWorker→producer→runner→NativeModelHost→Node/Subscription→不可变候选与可信账本、真实 Tianxuan 文档撤权（读取后响应前）、crash/flood 物理关闭和无重播、v1与计时回归。最终命令、原始输出与实际账本导出见 `data-collection/native-context-consumption-implementation-1501.json` 及其指向的宿主收据。合成协议只证明机制；无真实模型调用、效率收益结论或生产切换。独立审查、#1499真实factory联调、完整新增模块打包/更新回退、live预登记与CI/main仍由根责任者推进。

回归编排曾误将导入即执行的 `test_runtime.py` 与 pytest 套件合跑，产生临时 loopback 假HTTP服务及全局测试密钥环境污染，触发10项正确的凭据隔离拒绝；该脚本 finally 已关闭服务。随后在干净子进程排除该模块，重新验证无服务器测试。保留失败原因，不作为产品安全检查的豁免。没有外部 provider/业务服务调用。


## #1501 独立审查 R1/R2 修订（2026-11-18）

原 implementation 和 independent-review 报告保留历史效力；本修订待新独立审查，不能释放 factory、live、CI/main 或父工单验收。

权限采用有意保守的并集：原 selected 加全部明确 admitted delta before/after endpoint。每次 launch、tool_request、tool_response、model_turn、apply_proposal 都查询同一实时 authority；因此即使历史对象已经进入模型历史，撤销其旧修订权限也阻止下一轮与提案应用。不根据是否再次显式读取来缩小检查；namespace/absence/delta 同样适用。factory 仍须提供当前 actor/producer、原需求与模块的真实权限回读。

`native_store.py::NativeContextStorage` 是现有存储的宿主内部读取能力，已纳入 producer source_digest；没有新增 scheduler/client。每个 resolver 独立索引，key 包含 tenant（实例）、module/revision/name、精确 object SHA256，且绑定原 database inode 与 execution binding；不持久化或跨 execution 复用 verified cache。原 revision JSON 先查询字节长度、再在预算内载入并验证 revision SHA256。对象长度取 SQLite BLOB 元数据，不读取正文。manifest 索引只构造一次，后续 cursor 绑定原 binding/query，在不可变索引分页；delta 仅保留最近一对的有界索引。不同 delta pair 切换允许重建元数据索引，不重新读正文。

明确硬上限：全部 selected/delta endpoints 合计最多 128 个修订、4096 个对象引用、1 MiB revision payload、8 MiB 正文长度总和；单对象 2 MiB。相同对象在不同 endpoint 的引用保守重复计数。先查长度/计数再分配正文；旧 endpoint 也受限。launch/model/tool check 在启动模型或 started 工具记录之前完成 source admission；初始私有 ledger 的 binding 记录不是模型/工具执行。宿主 schema/授权范围不因此扩大。

冷读以每块 8192 字节执行全对象 SHA256，成功才保留私有分块 SHA256 索引。随后实际返回范围所触及的块逐块重新读取并认证；热读同样必须验证触及块。不同租户/修订/execution 不共享缓存。长度变化、数据库身份替换、冷校验失败、热块损坏均拒绝；缓存损坏项被移除。热读不证明未请求块未被外部破坏，但每个返回字节均由原 whole-object SHA256 导出的可信块索引认证。元数据及私有内存/数据库 ACL 仍是可信宿主边界，未声称对进程内恶意改写防篡改。

每个范围请求最多 8192 返回字节、最多认证两块；冷请求最多 2 MiB + 16384 blob 字节，热请求最多 16384。每个 execution 冷校验累计至多 8 MiB，另加 max_reads × 16384（max_reads≤1024）；重建 resolver 会重新冷验证，不自动重放历史工具。正文工作缓冲为有限个 8192 字节块和≤8192 返回缓冲；块摘要数量受 admitted 8 MiB/4096引用约束。每连接 SQLite page-cache 目标 256 KiB、mmap=0；不是整个 Python 进程 RSS 上限，JSON/索引/运行时有独立开销，元数据输入≤1MiB/4096项。已有响应与历史预算保持。

同一 120×65536 字节实际 NativeStore 样本：旧两页读取 15728640 正文字节，新两页为 0，metadata payload 一次 9421 字节；2 字节范围冷读 73728、热读 8192（旧每次65536）。这是 SQLite API 逻辑正文读取量，不是物理磁盘 IO、网络或真实模型收益。冷读略增是认证索引成本，不隐瞒它。跨块、长度变化、损坏、数据库替换、不同 execution/tenant/revision、旧 endpoint 超预算与历史撤权均有新测试。

## 当前宿主验收回读（2026-11-18，#1501）

上述阶段性“待审查/live”描述保留为历史。当前12项源码已绑定独立审查 `4e7f442034d56544f0a753c126c58268232f63749fe79d6f22987733a963ad16`；`data-collection/native-context-live-protocol-1501.json` SHA256 `a6c0db9c51a238550750aa6557d8667605dc44241b791b2e64bc6e68535e29cb` 记录后续严格任务实测成功。该次工具方案比基线更慢、计费 token 更多，不能声称效率收益。本次宿主验收没有新增模型调用，前后12项源码摘要一致。

`data-collection/native-context-host-acceptance-1501.json` 记录当前 Windows 57项测试、15项子测试及 Node 33项测试通过，包含真实 NativeWorker→`launch(registry, context_factory)`→签名 runner→Node/既有 Subscription→候选链路、五轮增量会话、v1兼容、撤权、未知执行不重放与物理关闭。隔离的已签名测试安装在 probe 字节篡改后由实际 launcher 拒绝；恢复原字节后以不同 execution 执行 v1，产出正确不可变对象并关闭进程。此为测试安装恢复和兼容性证据，合成 authority/evaluation 不能代替普通 factory。

组件实际分类为 `host_tool`。现有接口提供固定 argv、私有不可变 registry、签名 runtime/source/installation 绑定和显式可信 factory；没有独立版本化 context 包的 manifest/ABI 切换、原子更新或回滚管理器。因此不能标记 `runtime_package`，也不能把恢复 probe 字节称为同一编辑器二进制上的包热更新/回退。明确 fallback 为保留 v1 安装能力，在原有效配置恢复后授权新任务；未知 execution 和账本不自动重放。

现有 Linux 可信镜像的无网络、192MiB、1CPU、只读临时容器通过30项 Python测试和15项子测试，含成功/失败/超时/取消/非法响应的真实 Python 子进程树关闭。镜像没有 Node，11项依赖 Node 的 context 测试未执行，Linux Node/Subscription/v2链路仍未验收；未下载运行时或变更生产服务。两次隔离打包缺失 configuration 所列依赖的失败保留，沿实际依赖闭包补齐后复验成功。

普通 #1499 factory 的安装及真实 actor/producer/doc/module 权限集成、生产启用和整体验收仍由 root 接续。Windows必要账本已归档，临时测试目录删除被自动审批以 blocked by policy 拒绝，目录仍保留待主责任者收尾；Linux临时目录和容器已删除并回读为空。私有日志与脚本保留供独立审查。本报告不代表CI/main交付或整个Issue完成。
