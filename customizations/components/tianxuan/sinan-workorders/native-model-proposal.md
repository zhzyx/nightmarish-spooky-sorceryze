# 原生模型提案宿主接口（#1480）

路径解析基准为仓库根。组件属于现有 sinan-workorders 的 host_tool；没有写 proposal 文件、执行模型命令或改变 NativeWorker usage=None 的入口。输入为可信宿主提供的有界任务、上下文、验收和允许提案路径。下一集成层负责消费提案与文件落地。

可信 Python 宿主加载同目录 `native_model_host.NativeModelHost(installed, verify_installation, process_helper_path)`，调用 `.run(request, cancel=threading.Event())`。`installed` 必须由宿主配置提供，字段严格为 `node`、`entry`（已安装 Codex CLI JS/可执行文件）、`python`、`model`、`reasoning_effort`、`env`、`timeout`。三个程序路径必须绝对；`env` 为固定环境；timeout 为 0–600 秒。验安装回调必须返回 True，正式准入、凭据和模型授权由调用宿主负责。不要把请求内容传入这些配置字段；不要持久化账户配置。process_helper_path 指向已安装 `tools/ainative/owned_process.py`。运行前后核对配置与实现摘要。

request 的严格字段为 `request_id`、`task`、`context`、`write_allowlist`、`acceptance`，均为文本，只有 write_allowlist 为相对路径列表。完整 JSON 最多 128 KiB；上下文最多 64 KiB；任务最多 32 KiB；验收最多 16 KiB；路径最多 64 条。宿主规范化固定字段顺序并摘要，Node 做独立边界检查。request 不含环境、命令参数、主目录或凭据。模型收到不可变快照和摘要，无原生工具/MCP/web/approval。既有 subscription_session.start/turn 独立保留其身份、工具禁用、上下文重建策略。

提案仅包含 request_id、input_digest、summary、files[{path,content}]。输出最多 256 KiB，每文件最多 128 KiB，无重复路径，只能选择 allowlist 中的路径。私有响应同时绑定输入、输出、配置摘要及实际 thread/turn 标识。`execution_authority` 恒为 false。宿主必须独立验收模型文本，不能把其声明当作物理证明。

观察器包装 rpc.call 与 rpc.notify，同时原样调用既有 notify，绑定实际 thread/start 与 turn/start 回执，缓存最多32条早到用量事件，单回合最多32个原始快照、最多16个回合。成功提案后等待50毫秒接收迟到事件，然后关闭；窗口外缺失更新不推断。重复、错 thread/turn、负数、非安全整数或字段类型错误使用量 unknown/invalid，raw=null。有效更新保留原始 last/total（含可选 cacheWriteInputTokens），从不累加、不推导 token 归一化含义。`requested_model` 与 thread/start 实际回读的 `observed_model` 分开。模型调用失败/断线及不合法提案不回放、不重试，保留 unknown 终态。公开回执不含 account/read、账户身份、凭据、原始推理或stderr。

Python 外层将 Node 及其 app-server 后代交给现有 owned_process 所有权工具；只有该工具验证整树关闭后才返回成功，不能以 JS rpc.close 的 child.kill 作为关闭证据。本地取消不证明远端服务停止，remote_cancellation 恒为 unknown。取消或超时后不自动再发模型请求。临时输入/输出使用关闭即删除的私有临时文件，不留工作区生产文件。POSIX 继承 owned_process 的普通进程组限制，非 OS 沙箱。

验证入口：`node --test customizations/components/tianxuan/sinan-workorders/test_native_model_proposal.cjs`；`py -X utf8 -m unittest discover -s customizations/components/tianxuan/sinan-workorders -p test_native_model_host.py -v`。JS 使用真实 Subscription 与确定性假 RPC；Python 使用显式测试安装探针生成真实后代，验证成功、故障、超时和取消都阻止延迟写入。这些均不是实际模型收益或生产准入证明。真实试验及独立审查由根责任者记录。停用新宿主入口即可回退，保留已发生请求回执，不重发 unknown 请求。

失败提案与用量证据分开判断：已确认 thread/turn 的有效原始用量在格式错误或已绑定回合失败时保留，提案仍为 unknown、无内容、无执行权限；turn/start 未确认的早到通知不得推断绑定。强制终止、超时或取消而未返回有效私有回执时，用量仍可能未知。50ms 观察窗口仅保留最后有效快照，完整性未知；不是完整计费账本或最终计费证明。

## 可选阶段观测（#1495）

私有回执可带 `timing`：版本 1、`monotonic` 时钟、有界 `marks` 与 `rpc` 计数。阶段为 `session_ready`、`thread_start_sent/received`、`turn_start_sent/received`、`first_response`、`first_text`、`last_text`、`turn_completed`、`proposal_validated`、`receipt_ready`；值为从本次观察器创建开始的整数毫秒，未知为 null，最大 86400000。首个响应可能只是 turn/started，不表示模型已经输出文本。早到事件按收到时刻记录，只有真实回执确认 thread/turn 后采用，因此事件可能早于 turn/start 回复。

观察器只保留最多 256 个早到事件描述及 256 个完成消息 ID，不保留文本。重复完成消息不能推进末次文本时间，相同内容的合法增量仍分别计时；未知身份、其他回合、已结束后的通知被忽略，追踪溢出保留未知。原始协议回调仍完整接收通知。每类启动调用最多允许一次，额外调用用无效计数 2 显示并由宿主拒绝，观察器自身不新增请求。

Python 校验字段、范围、调用绑定及因果顺序，缺失文本不能放宽首次响应与结束时序。旧的不含 timing 的回执仍可验证。宿主独立产生 `host_timing`，其时钟起点是安装验证完成之后：`owned_process_closed_ms` 来自 owned-process 返回，`receipt_validated_ms` 来自成功验证，`protocol_elapsed_ms` 保留旧协议计时，`total_ms` 为宿主总耗时；JS 不能自报这些字段。两个时钟起点不同，不可直接相减冒充某一网络或推理阶段。强制终止未返回有效回执时协议阶段可全部未知，宿主仍记录自身观察。

计时不授予内容执行、验收、模型切换或自动重试权限；首文本不能代替回合及进程终态。实施改变安装摘要，旧评测或 grant 不能授权新实现。真实试验只支持其固定安装与任务，不将服务返回的 token 数当作完整计费或等待根因。
