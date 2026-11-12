# 跨模型运行与能力准入

本规范落实冻结纲领，不修改元衡上游。所有模型驱动的Agent实例仍受元衡控制；模型名称、输出和能力声明不产生权限。共享运行代码在runtime，未新增常设Agent或skill。

## 当前实现

customizations/platforms/ai-access/host-http/runtime/runner.py提供本地受控执行。single仅一步，workflow按宿主给定步骤顺序执行，autonomous允许在授权步骤内多轮读取指定资源。三者都必须通过定义准入、真实操作员签发的任务委托、能力评测证据与同一提交校验。输出为候选，completed不等于业务验收。

模型协议支持chat-completions、ollama-chat和gonggong-json。接口地址由宿主提供，前两者分别遵循[Chat Completions](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)、[Ollama Chat](https://docs.ollama.com/api/chat)官方协议（2026-11-01核对）。通用协议请求含model/messages/stream=false/max_output_tokens，响应含text/finish_reason/usage；第三方桥接可实现该接口，不依赖OpenAI SDK。当前仅文本、非流式；多模态、原生工具调用、引擎写操作需独立扩展验收，不冒充已支持。

模型统一输出JSON信封：`{"action":"final","value":...}`，或`{"action":"tool","name":"lookup_resource","arguments":{"key":"..."}}`。后者仅在autonomous及该步骤明确授权时读取宿主已提供的资源，不执行shell、不任意访问文件、不发布产物。没有原生工具调用能力的模型也可使用同一信封；不能稳定生成信封的模型不通过相应任务准入。

输出JSON约束只支持type/properties/required/items/enum/additionalProperties=false，不支持的语法拒绝。模型语义正确性仍由原质量责任链验证，夸父不代签，谛听不自批。

## 上下文、能力和路由

保留元衡核心、模板、完整冻结纲领、当前Agent及真实委托。每步可按需选择一个登记skill和相关Markdown引用，运行层加载内容；其他资料不默认全量注入。不复制模型专属Agent/skill。资料超出模型声明的max_context_bytes时换用其他已评测候选或转人工，不截断纲领；字节上限不是token估算，也不是供应商上下文窗口保证。

模型profile包含id/protocol/endpoint/model/max_context_bytes、可选system_role/api_key_env/timeout_seconds/output_parameter。system_role=false时转换为带角色标签的单条文本输入，不声称保留原生角色隔离。凭据只在适配器从环境读取，不进入模型上下文。

调用回执保留 `requested_model`、`observed_model` 和由宿主选择的 `protocol`。三个现有协议均只从响应顶层 `model` 读取供应商声明，`observed_model_source=response.model`；gonggong-json 可选提供此字段。模型名必须是非空、无首尾空白、可打印且不超过 512 UTF-8 字节的字符串，保持原值，不强转、截断或归一化。请求模型不合法时在发出网络请求前拒绝；响应的可选模型字段缺失/null 时 `observed_model_status=unavailable`，畸形时为 `invalid`，两者的 observed_model/source 均为 null，不影响原本有效的文本和用量。有效声明为 `provider_reported`，`model_identity_verified` 始终 false；别名、快照型号或与请求不同的声明都按原样保留，不自动拒绝或授予新模型准入。供应商回传的同名 provenance 字段不可信，也不用于覆盖宿主判断。

`evaluate.results[].response` 与 `runtime.sqlite` 的 `call_end.data` 保存完整回执。重放与恢复保留原调用记录；传输/结果格式未知或调用被中断时 observed_model 保持 null，不从请求型号推断。当前冻结谛听 schema 的 `usage.model` 仍是请求配置；其 `usage.metering_ref=runtime.sqlite#<task-id>/<event-seq>` 在同一私有 state 目录解析，用记录的 tenant_id 与引用的 task-id 经 runner.jid_for 得到 events.job，再联合 seq 回读调用身份。单独导出的谛听记录不包含 observed_model，需连同原宿主 journal 才能核查。历史回执缺少新字段时仍属未知，不能回填为请求型号。此证据不是供应商账号、实际权重或路由的独立身份验证。

customizations/platforms/ai-access/host-http/runtime/evaluate.py执行宿主提供的代表性用例，输出profile_digest、任务类型通过项、原始结果、样本集指纹、synthetic或live范围。profile的evaluation引用证据文件及SHA256，并复制profile_digest/scope/passed_task_types，运行前核对。变更模型、地址、配置或证据即需重新评测/准入。操作员负责证据真实性与代表性，测试脚本本身不认证供应商身份，也不证明开放任务能力。synthetic只能执行validation_only任务。

宿主按profiles排列路由优先级；仅选择该任务类型通过且当前上下文可容纳的模型。无效输出可转下一候选，消耗同一总调用预算；没有可用模型则needs_attention，不放宽验收要求、不强制依赖更强模型。能力不足可由宿主另行拆分任务或转人工，模型不能自行扩权。

## 权限、状态与恢复

部署者在模型不可读的宿主环境预置GONGGONG_HOST_KEY。authorize签发HMAC委托，绑定完整任务、模型配置/评测、限额、有效期、框架清单SHA256及状态库位置。密钥不能交给模型进程或不可信调用方；当前为单机可信操作员边界，不是企业IAM、多人审批或沙箱。框架文件和本地状态目录同样需要操作系统访问控制。

run前及每次模型调用/工具执行/结果采用前重验委托。状态SQLite按tenant+task ID去重，任务或委托内容变化拒绝复用ID，完成任务重放不再调用模型。OS锁串行保护同一状态目录；不同目录必须由宿主另行配置预算，不宣称已实现全局配额或ToB高并发。max_calls为持久硬限额；max_output_tokens是发送给供应商的单次输出请求上限，不是可证明的总token/货币预算。

HTTP错误、超时、畸形供应商响应都可能已产生消费，进入needs_reconciliation，不自动重试或切换模型。进程中断保留running，须操作员核对外部结果后使用recover retry/cancel，原预算不清零。锁保证活跃worker不能同时恢复。不能确认无副作用的写工具尚未纳入；将来扩展必须有独立幂等/结果对账契约。

已持久完成或取消的终态只能补交回执和最终状态，不能反向取消或恢复执行。过期委托可由同一可信操作员用renew签发仅延长有效期、明确绑定旧委托的后继记录，再recover；任务、框架、模型、权限及预算必须不变。框架变更不在此续期范围内，需另行审查和迁移。

运行journal保存调用前事件、响应及验证结论、工具结果引用、路由与恢复决定。请求内容、响应可能包含业务数据，必须使用客户授权的本地目录和保留政策；供应商私有思考字段不采集。日志不是身份安全根。

## 谛听与使用

runtime/diting.py自动将本运行器中的需求、内部消息、调用耗时与用量、输出契约失败及后续返工、正常结束投影到原谛听SQLite，复用outbox与真实回执。skill步骤按skill归属、实际执行Agent快照记录，一次调用仅计一次。缺失用量保留unavailable，跨供应商token不作通用价值换算。

coverage明确仅覆盖本运行器；外部聊天、语义方向纠正、业务质量工单不自动推断。现有ledger/reporting接口继续接收由真实宿主提交的这些事件。当前不会自动监听所有Codex或引擎会话。框架/元衡反馈仍只作reference。

安装依赖：Python标准库、Node；无需模型SDK。先准备模型profile和测试suite，再执行：

```text
python customizations/platforms/ai-access/host-http/runtime/evaluate.py --profile profile.json --suite suite.json --scope live --out evaluation.json
python customizations/platforms/ai-access/host-http/runtime/runner.py authorize --plan plan.json --state /absolute/private/state --authority-ref actual-delegation --out grant.json
python customizations/platforms/ai-access/host-http/runtime/runner.py run --grant grant.json --state /absolute/private/state
python customizations/platforms/ai-access/host-http/runtime/runner.py recover --grant grant.json --state /absolute/private/state --action retry
```

plan含task/profiles/limits；task含id/tenant_id/project_id/agent_id/outcome/authority_ref/retention/mode/work_items/steps及可选input/resources/validation_only。步骤含id/kind/instruction/output，可选schema/skill/references/tools。evaluation结果通过独立治理接纳后才可签发实际任务；authorize不代替业务审批。示例见templates/model-plan.json，未配置项不作为真实授权。

验收区分协议模拟、真实模型代表任务和生产部署。跨模型迁移必须在同一任务集比较有效交付、纠偏、返工、恢复、耗时和实际成本，不能仅以接口返回或JSON合规认定适配完成。

## 在途计划交接

已签发的计划继续由原受信安装核验与结清。迁移时保留原安装、状态目录与回执，先回读在途调用。确需切换时，由有权方核实旧计划终态与剩余工作，再按新运行时摘要重新签发；回执未知不得重复调用。
