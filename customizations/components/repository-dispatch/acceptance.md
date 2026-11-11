# 宿主独立验收适配（#776）

所有源码路径按仓库根解析。本入口为现有 Python/Node 宿主工具扩展，不是新签发服务；需要 Node、Git、Python 3.11+、操作者已有 gh 登录、可信安装和真实工单。生产模型不能用此文档授予自己验收身份。

## 私有编辑器接口

`python tools/gonggong_bridge.py acceptance-capture|acceptance-verify|acceptance-current --workspace ABS_CANDIDATE_ROOT --request PRIVATE_JSON --out PRIVATE_RESULT`

capture 输入为 `{request_nonce,issue_number,request_id}`，返回 `{ok,request_nonce,operator,candidate}`。candidate 为 `{root,branch,head,files_sha256,files:[{path,sha256}]}`；删除的已跟踪文件 sha256 为 null。清单包含 Git tracked 及 untracked nonignored 文件，排除 `.yuanheng/**` 账本和 Git 忽略的宿主瞬态文件；回执与日志放私有目录或已忽略的 bin，不能把生产资产藏进忽略路径。文件或父目录的 symlink/junction 拒绝。清单摘要为紧凑 JSON files 数组的 UTF-8 SHA256。

verify 输入额外包含 decision_json（完整字符串，最多 16 MiB）、host_liveness_path 与可选 host_dispatch_config。配置只能从宿主已有设置读取，不能来自模型结论；并行执行器使用实际 jobs/registry 配置，仓库派发使用 dependencyRegistry.path/tickets 和原授权 requests，二者按下文分别消费。decision 为 `{candidate,producer:{worker_id,conversation_id,receipt:{path,sha256}},reviewer:{worker_id,conversation_id,receipt:{path,sha256}},criteria:[{id,evidence:[{path,sha256}]}],verdict:'pass',reason,design_sha256}`，外部 producer 可用实际 execution_id 替代 conversation_id。receipt.sha256 是原始文件字节摘要，不是 envelope payload 摘要。返回 `{ok,request_nonce,decision_sha256,operator,candidate_sha256,current_candidate,projection}`；decision_sha256 绑定输入字符串的原始 UTF-8 字节。稳定 wrapper 的这三个操作始终从自身可信安装加载验证器，候选仅提供数据。

原生宿主必须先匹配真实派发、独立只读 reviewer、会话、generation、全部原验收项、成功读取的证据和当前未取消状态，再构造 decision。桥接本身只核对当前账号/写权限/intake、候选、逐项证据和终态文件；磁盘 JSON 不能证明真实完成事件。冷启动不能重建活来源时保持挂起。私有路径与 nonce 不是签名，也不声称防御同账号任意进程写入。

未配置 ledger 时 projection.state 为 not_configured，仅供编辑器消费者；Node 依赖不会因此通过。配置了错误映射则失败，不能降级 accepted。候选根必须与 registry 的实际账本根相同，producer.worker_id 必须等于账本实际 owner，criteria.id 按顺序对应原 acceptance，且任务启用了 independentReview；没有这样的既有映射保持阻塞，不自动造账或改 owner。

## 账本与完成事件

current 是原生宿主后台重核已验收候选的纯读入口，输入 `{request_nonce,candidate}`，返回 `{ok,request_nonce,candidate_sha256,current_candidate}`。它不查询账号、不签发验收、不写账本、不派发；只能与原生宿主已验证且仍存活的验收上下文一起消费。返回值是同一次文件核验的快照，严格绑定候选实际根、分支、HEAD 和全部文件，根目录被 junction 指向同内容副本也拒绝。原生消费者按本次请求和 generation 匹配结果，在真实生产开始后用尽该次证明；后续消费者重新后台核验，避免 UI 线程执行 Git 或全仓哈希。

projectAcceptance 由可信完成宿主调用，必须提供当前授权重核与事件续办回调。Production.review 在 writer.lock 内执行同步前置检查，拒绝普通 review JSON 注入 host_acceptance。写后由 board 推导 acceptanceValid，再调用原 runEvent/dispatchEvent 的 ticket.changed；原验收任务从后续 requests 排除。每轮补位重新 intake，原预留协议防止重复启动与释放未知工作者。

review 把 decision 摘要、operator、ticket、ledger key、完整候选写入原账本。派发失败后相同 decision 只重做续办；允许验收提交之后的纯 `.yuanheng/` 提交，所有其他 HEAD 或文件清单变化仍失效。不直接赋值 acceptanceValid。没有新真实事件不运行，不设后台定时器。

## 验证与回退边界

acceptance.test.mjs 使用真实临时 Git 账本、原 submit/review 和一次真实 Node 子进程；身份、权限和业务判断是受控夹具。test_acceptance.py 检验权限/intake 拒绝，不能代替真实 gh/独立 reviewer 证据。2026-11-11 的真实 capture 成功只证明当前 Sail-Li 权限、#776 intake 与候选读取，不是业务验收。

回退为停止从真实完成回调调用本入口，保留已有账本 review/证据；不能倒写历史。旧任务仍按既有人工规则工作，自动记录在检查器不可用时保持不通过。工具代码更新不要求重编译；原生宿主接线另需新二进制及完整 A→独立验收→B 的端到端验收。本适配器测试不能宣称原生集成、安装交付或 Issue 整体完成。

## 取消与本次宿主审计追加

verify 还必须带 host_liveness_path，指向原生宿主私有 request 对应的 .live 文件。内容为 `{request_nonce,active:true}`，缺失、nonce 不匹配或 active 非 true 即失败。停止、关闭、超时先移除该文件再结束桥接；读取完成结果后才清理。Node 在 writer.lock 内重核、提交后续办前及每次 worker 实际启动前检查。取消发生在已提交 review 后不倒写账本，保留待恢复且不启动依赖。Python 上限为两次 gh 各45秒、intake120秒、Node300秒；原生总预算600秒，超时先撤销存活标记。

捕获由可信桥接从本次 intake 衍生 candidate.audit_policy 的 tenant_id、request_id、source_ref。重核仅容许其精确 `gonggong-diting-data/events/<tenant>/<request>/` 下新增的未跟踪 host-context/godot-event 文件，且要求标准 envelope 字段、种类、时间、agent快照、摘要、source/request以及宿主 payload 绑定一致。所有捕获时已存在文件（包括未跟踪旧事件）仍逐字节绑定；新增代码、其他请求、无效事件或新跟踪事件均失败；新增审计事件不可作为本次业务验收证据。必需审计照常发送，不全局排除谛听目录。

## 实际并行执行器兼容

parallel_work_orders_config 的实际结构是 jobs/registry，不是 repository-dispatch 的 workers/requests/dependencyRegistry。入口按实际形状区分：并行配置必须唯一匹配 producer candidate 的 job.worktree，再匹配同根、owner 相等且被 jobs.dependsOn 引用的真实账本任务；job.acceptanceTicket 可显式消除歧义。没有映射不造账。没有 registry 仅在全部 job.dependsOn 显式为空时返回 not_configured。成功投影返回 dispatch.state=native_continuation_required，由原生匹配完成事件调用原执行器补位；不能仅收到配置便自动运行。

producer.execution_id 可替代 conversation_id，表示真实宿主执行引用；reviewer 仍须真实独立 conversation_id。外部 producer.receipt 是 #785 不可变 terminal_receipt：额外验证执行/worker身份、真实PID、退出/取消/上报结果、registration原始摘要、工单/需求/设计和产出候选；不能只凭哈希信任任意JSON。verify成功另返回current_candidate供原生消费者检查最新实际字节，不改变decision原候选和摘要。

已登记运行账本可由真实终态和独立验收在同一个writer.lock/提交中调用原submitEvidence后review，无须人工先点submit。没有伪造先前submitted历史；新增submitted与reviewed是本次真实事件。board同时复查终态原始回执，回执变化不放行。自动回调使用requireHostAcceptance，旧人工记录保留原语义但不升级为新自动消费者凭据。
