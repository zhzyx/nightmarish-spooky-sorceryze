# AI 公共运行契约 v1

路径均以仓库根为基准。本模块是 AIChat、马良、天枢的公共运行状态拥有者；领域执行器仍拥有传输、工具、权限、持久化与实际进程。新工作流先读本契约，再实现领域 Controller 和宿主适配器。View 仅采集输入、订阅事件及展示，不创建第二份业务状态机。

## 边界与构建

`WorkflowRuntime.h/.cpp` 仅依赖 C++17 标准库，可使用 `-fno-exceptions -fno-rtti` 独立编译。它不包含 Godot、Provider、网络、文件、凭据、工单或 UI 实现。`editor/AIWorkflowRuntime.h/.cpp` 将 Godot Dictionary 映射为核心值并提供 `run_event` 信号；原生注册与 `editor/SCsub` 由编辑器集成负责。现有模型目录、连接、Provider、权限、GitHub 和领域存储继续复用。

核心接口为 `AICore::WorkflowRuntime::BeginRun/Publish/Cancel/Snapshot`。Godot 固定脚本 API 为 `begin_run/publish/cancel/snapshot`，可由 `AIWorkflowRuntime::get_singleton()` 或注册后的 `Engine.get_singleton("AIWorkflowRuntime")` 取得。编辑器创建并持有唯一服务，View 销毁不释放服务；退出先从 Engine 移除再释放。额外测试实例不替换已有 singleton。

## Godot API

所有调用返回 `{ok: bool, changed: bool, code: String, reason: String, snapshot: Dictionary}`。不存在运行或宿主输入验证失败时 snapshot 为空；核心拒绝已有运行的冲突、旧代次、旧序号和终态事件时保留当前 snapshot。不要把 `ok`、进程退出或事件发送等同领域验收。

```gdscript
var runtime = Engine.get_singleton("AIWorkflowRuntime")
var result = runtime.begin_run({
    "workflow": "chat", "scope": "session-id", "request_id": "stable-request-id",
    "model": {"backend": "http", "model": "selected-model", "connection_id": "public-id"},
    "binding": {"session_id": "session-id"},
    "input": {"input_digest": "normalized-effective-input-digest"}
})
var run = result.snapshot
runtime.publish({
    "run_id": run.run_id, "generation": run.generation,
    "event_id": "stable-source-event-id", "expected_sequence": run.sequence,
    "kind": "progress", "state": "waiting_confirmation", "payload": {"step": "approval"}
})
runtime.cancel(run.run_id, run.generation, "cancel")
var reattached = runtime.snapshot(run.run_id)
```

`begin_run` 必须提供非空 String `workflow/scope/request_id`；`model/binding/input` 为可省略 Dictionary。`initial_state` 默认 `running`，仅还允许 `reconciling`。三个身份字段构成元组，字符串中的分隔符不会造成串接碰撞。相同身份且相同规范化输入、模型、绑定、初始状态返回原运行（`idempotent`，包括原运行已终结）；异内容返回 `request_conflict`，不覆盖原状态。重试新执行必须由领域 Controller 明确分配新 request_id。

`publish` 必须提供 `run_id`、正整数 `generation`、非空 `event_id` 与 `kind`，可选 `state`、Dictionary `payload`、正整数 `expected_sequence`。核心创建 generation 和 sequence；调用方不得生成公共序号。event_id 标识一次真实来源事件，精确重放返回 `duplicate` 且不发送信号；相同 ID 不同内容返回 `event_conflict`。generation 不匹配返回 `stale_generation`。若来源事件可能乱序，Controller 必须提供其发起时 snapshot 的 `expected_sequence`，旧序号返回 `stale_sequence`，不得自动用最新序号重试旧结果。没有 expected_sequence 的独立进度事件按到达顺序接收。源序号不是公共序号。

所有运行和事件快照都有 `schema_version=1, workflow, scope, run_id, request_id, generation, sequence, kind, state, model, binding, payload`。开始时 sequence 为 1、kind 为 `run_started`、payload 为空对象；每次实际接收事件递增一次。snapshot 保存最新事件 payload，不是完整输出/历史日志；正文累积、产物目录、工具明细与恢复记录由领域模型提供。

| kind | state 约束 |
| --- | --- |
| run_started | 仅核心开始时产生，running 或 reconciling |
| progress、text_delta、artifact_ready | 保留当前活跃状态或显式指定 running/waiting_tool/waiting_confirmation/reconciling |
| tool_requested | waiting_tool |
| completed | succeeded |
| failed | failed |
| cancelled | cancelled |

终态为 succeeded/failed/cancelled，任何新的事件都不能逆转；精确已接收事件重放仍是无副作用 duplicate。kind/state 矛盾返回 invalid_state；未知 kind 返回 invalid_kind。工具权限确认可用 progress/waiting_confirmation，工具结束后领域回执用 progress/running。没有自动重试、计时器、后台轮询或状态推进。

`cancel(run_id, generation, event_id="cancel")` 仅终结公共运行并拒绝后续结果；实际 HTTP/CLI/子进程取消及未知远端副作用对账仍由领域 Controller 和执行器负责。它不证明进程已退出。`snapshot` 永不改变序号、不发送信号、不推进轮询。

## 冻结与公开信息

输入字典以递归键排序、完整浮点精度的 JSON 规范化，数组顺序保留；只接受 null/bool/int/有限 float/String/Array/字符串键 Dictionary，最大深度 32。对象、资源、非字符串键、循环、非有限数显式拒绝。已规范化 input 仅在核心内部用于幂等比对，不进入信号或 snapshot。Controller 应传有效输入的稳定摘要，避免持有不必要的原文。

model/binding 采用公开字段白名单，未知键显式拒绝而非静默删减。以下字段均可选；除 nodes/capabilities 外只接受 String/int/bool。字段语义由领域适配器负责，不能把密钥伪装成公开名称。

- model：id、model、model_id、name、label、provider、provider_id、backend、backend_id、connection_id、revision、catalog_revision、source、source_revision、capabilities、reasoning_effort、selection_revision、protocol、variant、connection_revision、source_id、effort、strength、nodes、node_id、image_model。`reasoning_effort` 为推荐通用键，effort/strength 为已有领域别名；核心不改写含义。
- model.nodes：节点字典数组，每项必须含非空 String node_id，仅允许上述公开模型键，禁止再次嵌套 nodes。保留每个节点的独立模型；不将多模型工作流压成单一默认模型。image_model 保留领域节点独立选择的辅助图像模型，仍为公开字符串元数据，不写入 capabilities。capabilities 为字符串数组。
- binding：id、workflow、scope、project_id、session_id、node_id、issue_number、request_id、repository、source、source_revision、plan_id、task_id、run_id、domain_run_id、revision、selection_epoch、controller、operation、route、workspace_id、parent_run_id、actor_id、tenant_id、binding_id。

不接收 endpoint、URL query、headers、credential、API key 或 token。递归 JSON 验证也拒绝已知凭据字段（password/secret/credential、api_key/apikey、access_token/refresh_token、authorization、headers），该检查不能识别伪装成普通字符串的秘密；Controller 仍须从现有安全连接层选择公开引用。禁止将整个 Provider、连接配置、HTTP 回执或用户配置复制到公共元数据/事件。payload 是经领域适配的公开内容，凭据仅留在传输层。

核心的 `Metadata` 使用 `std::map<std::string,std::string>`：值是宿主已经验证的 canonical JSON；input/payload 也是经边界验证的 canonical JSON 字节。核心检查公开顶层键并按值冻结，不重复实现 JSON parser。其他非 Godot 宿主必须实现与以上相同的类型、凭据和节点模型验证及规范化边界，不能直接把不可信原始 JSON 当成已验证数据。Godot 映射返回独立字典，修改输入、返回 snapshot 或信号参数均不能修改核心状态。

## 生命周期、线程和恢复

核心 mutex 保护身份、运行和去重映射，所有操作线性化并返回值副本；锁内没有外部回调。运行与已接收事件的幂等记录保留到 runtime 销毁，当前没有持久化、自动淘汰或跨进程查询。调用者必须在析构前结束自己的工作线程。

Godot API 包括 snapshot 都要求主线程；其他线程返回 `wrong_thread`，不变更核心、不发送信号。领域工作线程先通过其拥有者的主线程完成机制提交公开结果。`run_event` 仅在 changed=true 时主线程发送，重复、拒绝、查询均不发。重入发布先排队，当前事件投递完后才发送后续序号，避免回调重入使订阅顺序反转。

View 重建或重新挂载后，Controller 保存的 run_id 可查询同一编辑器服务中的原运行，信号订阅只影响展示，不重新发起执行。进程重启后内存运行不存在；run_id/generation 仅属于创建它们的 runtime 实例，不是可跨实例恢复的持久 ID。领域存储以 domain_run_id 及已有持久快照恢复，在新服务中使用新的请求绑定 `initial_state="reconciling"`，核实真实回执后才 publish；不得将旧进程 generation/晚到回调映射成新运行成功。未知远端副作用保持 reconciling；公共核心不替代领域幂等和恢复协议。

## 验证与证据

独立验证命令（输出放任务私有目录）：

```sh
clang++ -std=c++17 -fno-exceptions -fno-rtti -Wall -Wextra -Werror -pthread -I. ai_core/WorkflowRuntime.cpp tests/ai_core/WorkflowRuntimeTest.cc -o /absolute/task-output/WorkflowRuntimeTest
/absolute/task-output/WorkflowRuntimeTest
```

测试覆盖成功/失败/取消、身份隔离、同内容幂等/异内容冲突、重复/旧序号/旧代次、取消后迟到、模型绑定冻结、无副作用查询、恢复边界及 12 线程同身份/同事件竞争。`tests/editor/TestAIWorkflowRuntime.cpp` 供编辑器原生测试注册，覆盖字典规范化、节点模型、主线程拒绝、singleton 隔离、信号和视图重查。

实际独立 C++ 证据见 `tests/ai_core/build-evidence.json`。Godot 原生编译、Windows/MSVC、headless、三 Controller 接线和 UI/领域回归必须由整合候选另行验证；本模块的独立通过不能替代这些验收。构建归属及回退见 `build-impact.json`。
