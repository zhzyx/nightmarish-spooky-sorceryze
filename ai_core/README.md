# AI 公共运行契约

修改 AIChat、马良、天枢或接入新的 AINative 工作流时先读取本文件。本文是公共运行边界的唯一正文。产品需求、实现过程和单次证据进入 design-docs 与 data-collection。

## M、C、V 的职责

M 由本目录的引擎无关 Runtime 和各领域模型组成，持有运行身份、冻结输入、状态及终态规则。核心只使用 C++17 标准类型，独立编译。宿主负责序列化、存储、线程同步、Provider 和外部工具适配。公共头文件的本地依赖只能指向本目录。

C 持有运行核心与传输的生命周期，接收用户意图，调用领域服务，将进度、正文、工具请求和产物转换为公共事件。Controller 可持有宿主 Node 或回调作为传输适配端口。其权威状态使用普通数据，界面重建时仍可查询。模型调用、进程启动、网络轮询和迟到回执判断属于 Controller 或 Provider 适配器。

V 创建控件、收集输入、渲染 Controller 快照、显示预览，并发送用户意图。会话状态、任务状态和传输句柄的唯一责任者分别由模型或 Controller 持有。兼容属性直接转发该责任者，避免维护第二份状态。

## 宿主接口

Godot 适配器是 modules/ai_core/AIWorkflowRuntime，在场景初始化阶段注册，编辑器和无界面样例共用。C++ 使用 BeginRun、Publish、Cancel、Snapshot，GDScript 使用同名 snake_case 绑定。适配器是 RefCounted，由 Controller 持有，所有调用在主线程串行执行。

| 操作 | 输入及结果 |
| --- | --- |
| begin_run | workflow、scope、request_id、model、binding，返回新运行或同输入的原运行快照 |
| publish | run_id、generation、kind、payload、可选 state，返回已接受事件的快照 |
| cancel | run_id，接受一次取消终态并返回快照 |
| snapshot | run_id，返回深复制的当前数据 |

拒绝的输入、未知运行、代际不匹配、冲突请求和终态后的事件返回空字典。Controller 在开始外部副作用前回读快照，检查运行仍为 running、代际和绑定仍匹配。事件订阅可以同步取消，转发事件后也须复核。重复请求只有 workflow、scope、request_id 以及冻结的 model/binding 全部一致时才复用原运行。请求的业务参数和来源修订应包含在 binding 中。重试使用新 request_id，保留原调用关联。

model 是会话或节点本次明确选择的 Provider、模型、协议和能力等元数据。binding 包含调用参数、工程/操作者/业务对象身份、来源修订等实际需要的绑定。二者在 begin_run 时深复制并冻结。凭据由宿主传输保存和核验，公共数据中不放密钥、令牌或授权句柄。

## 事件与状态

事件与快照使用 schema_version=1，包含 workflow、scope、run_id、request_id、generation、sequence、kind、state、model、binding、payload。Godot 适配器的 event_received 信号在状态已提交后发送，接收者可同步查询当前快照。

所有数据只使用 JSON 可表达的空值、布尔、有限数字、字符串、数组和字符串键对象。Godot 适配器将 StringName 键和值递归转换为 String，拒绝转换后的重复键。Node、Object、Callable 和二进制对象通过调用方转换为稳定引用或可序列化的数据。输入深度最多 32，拒绝循环引用。

| kind | 状态及语义 |
| --- | --- |
| run_started | 创建运行，running，sequence 从 1 开始 |
| progress | 更新进度，可显式进入 running、waiting_tool、waiting_confirmation、reconciling |
| text_delta | payload.text 为字符串，追加到 text |
| tool_requested | 默认 waiting_tool，payload 记录工具请求，执行仍由宿主现有授权入口决定 |
| artifact_ready | 将领域产物引用追加到 artifacts，由领域服务校验内容和版本 |
| completed | 唯一成功终态 succeeded |
| failed | 唯一失败终态 failed，payload 保存结构化原因和恢复信息 |
| cancelled | 唯一取消终态 cancelled |

generation 在同一 Runtime 内单调分配。所有回调带原运行身份及 generation，调用方按实际传输 ID/偏移过滤外部重放。每个接受的事件增加 sequence，进入终态后拒绝后续事件。输入请求幂等和终态去重属于核心，Provider 副作用的幂等、未知回执对账及取消能力由相应适配器实现。

文本、工具和资产工作流共享此运行契约。领域服务继续维护 DAG、工单 revision、Provider job_id、审批和资产完整性。已有历史会话、运行快照和持久化存储通过原领域适配器读取。重启恢复时核对实际任务，重新附着到公共运行。恢复动作保留原业务身份。

## 接入与验收

新增工作流提供 Controller 和领域适配器，通过上述运行接口发布实际事件，View 订阅快照。按能力声明选择 Provider，显式模型选择与在途快照应得到保留。业务权限沿宿主的现有执行入口核验。

验收覆盖正常入口、无 View 的 Controller、并发运行隔离、冻结模型和来源、取消与迟到事件、失败恢复、重复终态以及原持久化数据。原生及嵌入文件的变更沿 customizations/module-boundaries.md 追踪实际构建消费者，并验证当前候选。公共契约变更同步更新所有受影响消费者和定向回归。
