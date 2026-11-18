# 司南 · 工单扩展

在现有司南能力之上扩展工单管理，不新建平行协调器；派发、依赖、进度仍由司南承担。

## 已实现（领域核心）

- 工单创建、父子关系、编号、类型、优先级、验收字段。
- 最小状态机：`backlog → planned → in-progress → in-review → done`，支持 `blocked` 与 `cancelled`。
- 需求文档 → 计划拆单（父单 + 子单）→ 状态推进 → 进度回写。

## 约定

- 最小可自定义：固定核心字段 + 有限自定义字段；状态机由项目模板决定。
- 每次状态迁移写事件；需求页进度由事件聚合，不手工维护。
- 文档 ↔ 工单双向链接（`requirement_id` / `[[doc-id]]`）。
- 自动推进的“提议/执行”边界按平台 AI 自主策略；破坏性动作需门禁与回滚。

## 原生本地工作链路（#1444）

`native_workflow.py` 为已有司南提供宿主状态；`native_dispatch.mjs` 调用原有
`dispatchEvent`/`selectModel`，没有第二套模型选择算法。`native_worker.py` 使用已安装
`owned_process` 执行有界本地命令，在独立普通文件目录生产，`reads=None` 收集并校验
授权对象范围。它是可信本地工具，不是恶意代码沙盒。

安装者构造 `NativeWorkflow(domain, worker, runner, release, authorize, ...)`，通过
`create_app(..., native_workflow=workflow)` 挂载认证 HTTP 入口。`installed_plan` 从真实
授权解析固定输入、验收、profile 和 mandate；HTTP 的 authorize 只接受 Issue ID，不能
提交命令、路径、actor 或批准内容。`principals` 将登录操作者绑定到已准入的独立执行
身份，`review_candidate` 必须实际审查精确候选并严格返回 True。单一操作者可以委托
独立生产、检查、审查和发布执行；模型文本本身不构成可信身份或审查回执。
安装校验必须核对完整 argv 引用的脚本/库和凭据来源，不能以无条件 True 配置生产。

命令入口：`node customizations/components/tianxuan/sinan-workorders/native_dispatch.mjs`。
安装者在独立进程环境提供 `NATIVE_SERVICE_URL` 和 `NATIVE_SERVICE_TOKEN`；它们不进入
任务合同或工作者上下文。服务地址只支持 TLS 或回环 HTTP，不跟随重定向，响应有界。
HTTP 操作包括 authorize、advance、inspect、reserve、execute、status、reconcile、check、
review、publish、complete、finish。普通工具/API 的 issue done 不能绕过托管完成门禁。
CLI 在实际生产终态后调用 finish，由已安装的 `installed_target` 选择频道和预期发布版本，
目标首次落库后重放保持不变。内容检查失败不会启动独立审查。精确发布、完成与进度落库后，
继续消费 outbox 并派发新就绪任务，直到当前事件无可推进任务；不依靠定时扫描。
单项发布冲突或失败保留候选和错误，继续其余任务；不会自动改换预期版本或重跑生产。
实际终态逐项释放生产容量和触发补位，不等待同一批的其他进程结束；当前 CLI 的交付并行
上限沿用安装容量。不同 CLI 的全局生产预约由领域库仲裁，交付执行节点容量还须由安装者
统一配置。`advance` HTTP 返回逐事件成功/失败，失败项留待下一真实事件恢复，不阻断
其他已验收分支；单次驱动不重复尝试同一个失败事件。

定义摘要包含当前工单原始诉求/验收及直接和祖先需求内容；排除 status、progress、
updated_at。合同固定选定模块、允许写入对象、实际安装摘要、检查上下文及精确依赖
发布回执。新要求或 mandate 改变会拒绝旧合同。认证 HTTP `workflow/revise` 接收
`issue` 与精确旧任务 `expected`，只从 `installed_plan` 取得新合同；当前授权与 active
绑定在短事务内 CAS。相同合同重放返回原任务，不重新激活已替换版本。旧合同、验收、
任务历史不变，替换时清空当前工单验收并重新计算需求进度。旧 reserved/running/held
继续计入真实占用；只有可信 worker 终态可结清，晚到终态不能覆盖新版本状态。

依赖固定原验收 selection ID。`NativeRelease.historical` 回读原始记录和原子事件，
核对当前读取/原发布者权限、原审查授权、撤回、有效期、检查政策与内容完整性；不要求
频道指针保持原值。上游 active 定义前进不会改变已验收内容的固定引用，新定义完成仍须
新任务独立验收。客户端不能提交任意发布回执替代此回读。

旧 issue UNIQUE 表、active 映射和前驱历史在同一短事务迁移，保留全部实际 worker 状态。
重启幂等；失败回滚全部 DDL。版本化任务写入触发器要求连接注册 v2 能力函数，旧安装
可只读历史，修改明确失败；不支持旧代码继续写多版本数据。回退先停用工作流入口，
保留新数据，恢复兼容安装后再启用，不降级表或丢弃旧产物。

预约以 SQLite 短事务记录全局容量和租户 FIFO 顺序，未知运行保留占用。
FIFO 只约束当前可调度的前项；服务端再次验证安装模型的可用性、目标和能力。
其他组织或当前不可读工单只以匿名槽位计入占用。固定输入完整闭包中的需求模块，在
授权、认领、执行和验收时回读当前 ACL。生产终态保存真实产物，但不会覆盖并发取消、
阻塞或已改变的授权/来源；停止的业务保留待处理，不自动重启生产。
生产、检查、模型/网络操作在领域锁外。宿主确认进程终态、日志完成、候选落库后才保存原生终态；
reconcile 只读取该持久终态，不能凭 PID、超时租约或客户端自报释放未知运行。
独立审查只执行一次；NativeRelease 已有精确审查记录可以重放，审查副作用未知且
没有发布库记录时保留待调查。实际工作者失败和范围外写入不会放行下游。

NativeRelease 的短写入防护覆盖最终领域验收事务，阻止撤回/策略/频道更新插入
验收读取与领域提交之间。发布也以 Native→domain 次序核验当前合同，并持有领域写入
防护直到 Native 发布提交完成，防止审查期间取消后仍切换内容。长审查调用不持锁。
没有跨数据库原子事务承诺。发布后领域写入失败时按稳定
操作键回读恢复。完成、需求进度与 outbox 在领域库内原子写入。`advance` 由真实事件
或用户调用，已安装 `next_issues` 图解析器选择下游，`installed_plan` 绑定已验收输出；
完成事件不直接相信 done 字符串，不创建定时扫描。

构建位置为 `host_tool`；实际输入是领域库、NativeStore、可信安装/角色配置、固定合同、
原有司南算法和进程宿主。普通 Python/Node 安装不进入 Godot 原生编译输入。测试在同一
解释器中停用并恢复可选 HTTP 入口，保留领域/发布库和候选。生产回退先停用入口，保留
未交付文件、终态、未知占用及已安装有效版本；此测试不代表实际生产部署或消费者安装。

当前验证为 Windows 本地生产与 HTTP 协调、A/B 独立产品输出经 C 集成、真实内容检查和
独立发布。尚未声称远程执行节点、真实 provider/用量收益、250 任务负载、同一产品并发
结果的合契语义整合、浏览器/Godot 消费或 Linux 生产验收完成。
API/CLI 只绑定本地可信生产安装；请求来自另一台节点不等于生产计算已迁到远端。


## Immutable worker intake (#1461)

The installed host must construct `NativeWorker(..., authorize=authority)` with a
short local `authority(db, tenant, producer, module, action)` callback returning
exactly `True` for current `read` and `receive` permission. There is no default
allow policy. Resolve current permissions from trusted installation state (use
`db` for transactional revocation); never accept the callback, actor, source,
profile or task contract from producer workspace files. `NativeWorkflow` supplies
the authorized full task; execution is its canonical digest, including tenant,
producer, original source, mandate, selected inputs and writes. These ordinary
local processes are trusted installed programs, not an OS isolation boundary.

Successful output is bounded and collected once after owned process closure and
transcript flush. A short transaction stores the full original task and immutable
closed-output spool in `native_worker_closed`. `NativeCandidates.receive` then
records the original baseline and native source/task/issue URI provenance without
moving shared module heads. The terminal retains the exact intake receipt and
composition; `produced` is not joint product acceptance or publication. Empty
changes retain provenance with `no_changes=true` and `intake=null`.

Restart reconciles only host database closure records, replaying the same intake
key and rechecking current authority. Failure between closure, receive,
composition and terminal can finish without relaunch or mutable workspace reads.
An existing execution directory without closure stays unknown; no PID or edited
workspace receipt establishes success. Terminals use `native_worker_terminals_v2`
so legacy submit-based terminals are not silently promoted to intake evidence.
Installations upgrading active legacy workers must preserve their original
owner/receipt and reconcile through that installed version before switching.
The host database, spool and installation must be inaccessible to untrusted
producers. Missing or corrupted records require owner investigation, not rerun.

The default worker collection budget is 2 MiB per file and 8 MiB total. An
installed host may pass `limits=Limits(...)` after evaluating its memory budget;
workspace collection and candidate intake share those limits. Hex spool encoding
and JSON parsing amplify memory use; this slice makes no throughput claim.
`process_closed(task, execution)` is a trusted coordinator-only physical fact
port. Its caller must authenticate its coordination role. It returns only a
boolean, without exposing output, receiving candidates or publishing content,
so producer withdrawal does not prevent an authorized coordinator releasing a
physically closed reservation. `reconcile` still requires current producer ACL.

Cancellation linearizes at the event check inside the closed-output transaction,
after collection and encoding and before any candidate intake. An observed cancel
persists `cancelled=true` with no changes; clearing the event or restarting cannot
turn that decision into produced. A later event does not revoke an already closed
output decision. The process helper may report a null exit for cancellation or
bounded termination; only its returned, fully cleaned-up observation is recorded.
Recovery validates both physical and output record digests/contracts, binds their
exit/transcript fields, reconstructs every terminal and compares all saved fields.
A physical non-success can reconstruct failure even if interrupted before output
spooling. A physical success without an output decision remains unknown; arbitrary
terminal rows cannot establish failure or success. Trusted-host database corruption
probes test integrity, not a public producer attack surface.

## Optional native model production

The fixed installed launcher and explicit CLI protocol are documented in
[native-model-producer.md](native-model-producer.md). The existing NativeWorker
process closure, candidate and NativeIntegration paths remain authoritative.
