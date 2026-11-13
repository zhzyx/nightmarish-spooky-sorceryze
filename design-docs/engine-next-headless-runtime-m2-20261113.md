<!-- gonggong-request:engine-next-headless-runtime-m2-20261113 -->

# Engine Next M2：独立 Headless 运行时

## 当前结论

- 用户目标：把 Godot 从构建和运行环境中彻底拿掉后，`next_server` 与两个真实 `next_client` 仍完成同一套连接、出生、输入、权威模拟、预测、校正、插值、重连和停服闭环，才视为 M2 完成。
- 用户已讨论并确认采用五个纵向 PR、同一会话连续推进；2026-11-13 进一步明确要求查找最新项目 C++ 规范并基于规范落地。
- 编码规范：`CPP_CODING_STANDARD.md` v1.1，最新规范提交 `89a9996539c210684eaef48bac089553b2ad10c3`。语言基线为 C++17，不使用更新标准特性，不使用 `throw`、`try`、`catch`；第一方新文件和接口执行 PascalCase、显式宽度类型、明确所有权、输出参数及无异常错误返回约定，上游第三方保持上游风格。
- 基线：`main@e9684f34cfc4fded923d43f4469d32a0096a8af3`。M1 #939 与 M1.1 #1025 已交付并关闭；本任务复用其独立 `PredictionModel`、`InterpolationBuffer`、构建契约和 legacy 回归，不重开 M1。
- 需求 ID：`engine-next-headless-runtime-m2-20261113`。
- Issue：[#1042](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1042)。
- 类别：`type:development`。
- 责任人：当前 Kimi Work 会话；设计、实现、验证、正式门禁、精确候选 CI、main 回读和工单收尾沿既有授权连续执行。

## 完成定义与非目标

### 完成定义

1. 仅从 `engine_next/`、明确准入的第三方源码和独立构建工具组成干净源码树，不复制 Godot 根目录、构建系统、可执行文件或缓存，能够构建 `next_server` 和 `next_client`。
2. 将实际二进制复制到另一个空运行目录，在不安装、不编译、不链接 Godot 的环境中启动一台服务器和两个独立客户端进程，以真实 ENet UDP 完成本设计全部验收。
3. 源码、真实编译包含、对象、库、链接 response、符号、动态依赖和发布文件共同证明无 Godot 依赖；源码扫描或本地启动均不能单独充当完成证明。
4. 既有 Godot editor/template 只作为独立 legacy 回归，不进入干净构建或干净运行任务，不改变旧运行行为。

### 非目标

- 渲染、窗口、音频、物理、动画、GDScript、C#、场景格式、通用 ECS、物理回滚、命中回溯和大世界流送。
- 完整 GameMode、GameState、ReplicationGraph、通用 RPC、生产账号、匹配、加密、云部署和跨平台主机兼容承诺。
- Godot 网络协议兼容，或把 Godot headless、GDExtension、`MultiplayerPeer` 改名成新运行时。
- 编辑器部署面板和远程部署服务。M2 只提供真实二进制、场景执行器、部署／停止接口和 Trace；编辑器以后复用这些能力，不扩大 M2 验收。

## 架构与所有权

```text
next_server ─┐
             ├─ EngineNext Runtime / Network / Session / Gameplay
next_client ─┘             │
                           ├─ M1 PredictionModel
                           ├─ 共享 PredictionReconciler
                           ├─ M1 InterpolationBuffer
                           ├─ ITransport ─ 纯净上游 ENet 适配器
                           └─ C++17 与明确准入的系统库

Godot legacy ─ 仅经兼容壳复用共享 Gameplay 算法，不进入上述链接闭包
```

- `RuntimeHost` 显式拥有配置、日志、Trace、Clock、World、Transport 和角色运行时；初始化失败按已完成初始化的逆序回滚，正常关闭先停止准入和网络，再销毁会话、World 和基础服务。
- 所有运行时对象单线程亲和；M2 不以后台线程隐藏生命周期。真实循环先 Poll 传输，再推进固定 tick，最后flush有界发送队列。
- `World` 不依赖场景树、传输或 Godot。EntityId 非零，创建、查找和销毁显式；模拟和快照按 EntityId 稳定排序，不能依赖无序容器迭代顺序。
- `PeerId` 只存在于传输及会话绑定边界；`SessionId` 表示一次稳定会话；`EntityId` 由服务器分配。三者不互换，消息声明不能授予所有权。
- `ITransport` 只暴露 PeerId、字节、连接事件、发送结果和有界队列统计；ENet 类型仅存在于适配器实现。
- 服务器收包回调只校验并入队，不直接模拟。每个实体每个固定 tick 最多消费一条输入，客户端每个本地固定 tick 最多预测一条输入。

## 独立依赖与构建

- 上游 ENet 固定为 `v1.3.18`，tag 对象提交 `2662c0de09e36f2a2030ccc2c528a3e4c9e8138a`，来源 `https://github.com/lsalzman/enet`，许可证为 MIT。
- 当前仓库 `thirdparty/enet` 含 `enet_godot.cpp`、`enet_godot.h` 和 Godot socket patch，不进入 M2 源码或链接闭包。M2 在 `engine_next/thirdparty/enet/` 保存上述上游精确版本的必要 C 源码、头文件、LICENSE 和来源记录，不保留无关 Godot 修改。
- 不引入 CMake、Ninja、包管理器或新测试框架。独立 Python 标准库构建入口直接驱动 MSVC／Clang／平台归档与链接工具。
- 不接入根 Godot `SConstruct`。`next_server`、`next_client` 和运行时测试分别从实际 linker response 生成清单，禁止人工编造对象、库或摘要。
- 延续 M1 的 C++17、严格警告、警告即错误、无异常及浮点编译策略；新增 Linux 的符号与动态依赖审计，Windows 和 macOS 使用既有平台工具语义。
- `tools/engine_next_contract.json` 显式准入上游 ENet 根、`enet/` 包含前缀和实际系统库；每个可执行文件独立执行 `--require-sources --require-link-manifest`。
- 干净构建与干净运行使用独立任务。发布目录采用允许清单，拒绝 Godot 可执行文件、PCK、`.tscn`、`.tres`、`.gd`、`project.godot` 和未声明运行文件。

## 版本化二进制协议

### 公共帧头

固定 32 字节，所有多字节整数显式 little-endian 编解码；浮点以 IEEE-754 binary32 位模式编码，解码后验证有限性。不直接写内存结构体，不依赖对齐、宿主端序或编译器打包。

| 顺序 | 字段 | 类型 | 约束 |
| --- | --- | --- | --- |
| 1 | `magic` | 4 字节 | ASCII `ENXT` |
| 2 | `protocol_version` | `uint16` | 当前为 1 |
| 3 | `message_type` | `uint16` | 下述六类消息 |
| 4 | `header_bytes` | `uint16` | 当前为 32 |
| 5 | `flags` | `uint16` | 未定义位必须为零 |
| 6 | `payload_bytes` | `uint32` | 与实际帧长严格一致 |
| 7 | `message_sequence` | `uint64` | 连接及通道内单调，从零以外的 1 开始 |
| 8 | `session_id` | `uint64` | 握手前为 0；握手后必须与绑定会话一致 |

- 单个 UDP 数据报最大 1200 字节，M2 不做应用分片；截断、 trailing bytes、非法字段、未知必填位和超大包全部拒绝。
- 通道 0 承载可靠有序控制消息；通道 1 承载不可靠有序的 input／snapshot。消息序号不能代替玩法输入序号或服务器 tick。
- `PeerId` 不在消息头中传输。服务器只使用实际传输事件的 PeerId 查会话，再核对 SessionId 和 EntityId。

### 消息负载

| 消息 | 类型值 | 负载字段及顺序 |
| --- | --- | --- |
| `client_hello` | 1 | `client_nonce:uint64`、`resume_session_id:uint64`、`resume_token:[16]byte`；首次连接后两项为零 |
| `server_welcome` | 2 | `entity_id:uint64`、`resume_token:[16]byte`、`server_tick:uint64`、`fixed_step_msec:uint32`、`snapshot_interval_ticks:uint32`、`confirmed_input_sequence:uint64`、`position:vec3f32`、`velocity:vec3f32` |
| `input` | 3 | `entity_id:uint64`、`input_sequence:uint64`、`step_msec:uint32`、`movement:vec3f32` |
| `snapshot` | 4 | `server_tick:uint64`、`entity_id:uint64`、`last_processed_input_sequence:uint64`、`position:vec3f32`、`velocity:vec3f32` |
| `disconnect` | 5 | `reason:uint16`、`acknowledge_sequence:uint64`、`drain_deadline_tick:uint64` |
| `error / reject` | 6 | `rejected_type:uint16`、`reason:uint16`、`fatal:uint16`、`rejected_sequence:uint64` |

- `server_welcome` 的 SessionId 位于公共帧头，服务器同时轮换重连凭据。客户端以 welcome 的权威状态建立预测基线。
- `server_time_msec` 由 `server_tick * fixed_step_msec` 经溢出检查后得到，不信任客户端时间。
- 错误版本在帧头可安全解析时返回 `protocol_version_mismatch` 并关闭；无法安全解析的帧只记录并丢弃，避免错误响应放大。
- 重复和过旧输入不再次模拟，返回当前确认快照；伪造 owner、非法跳号、错误步长、非有限向量和超速率输入返回确定错误码并计数。

### 默认有界参数

| 参数 | 默认值 |
| --- | --- |
| 固定步长 | 16 ms |
| 快照间隔 | 3 tick |
| 最大输入跳号 | 32 |
| 每实体待处理输入 | 64 |
| 客户端未确认历史 | 256 |
| 插值样本 | 32 |
| 插值延迟／陈旧阈值 | 100 ms／500 ms |
| 输入重试间隔 | 50 ms，按 tick 限额轮转 |
| 重连宽限期 | 5000 ms |
| 每连接损伤队列 | 256 |
| 数据报上限 | 1200 字节 |

所有历史、待处理输入、重发和损伤队列都有硬上限及高水位 Trace。历史满时客户端拒绝新输入并报告，不静默丢弃最老未确认输入。ENet 适配器限制每 tick 发送预算，记录实际可观察队列；不能把未审计的内部队列宣称为无界安全。

## 会话、固定 tick 与重连

### 握手和出生

1. 服务器接受传输连接后仅等待 `client_hello`，其他消息按状态拒绝。
2. 首次合法 hello 创建非零 SessionId、EntityId 和短期重连凭据，World 显式创建实体并返回 welcome。
3. 服务器将实际 PeerId、SessionId、EntityId 绑定；后续输入必须同时满足实际 PeerId 绑定、帧头 SessionId 和负载 EntityId。
4. 两个客户端获得不同 SessionId／EntityId。新连接不能通过声明他人的 SessionId、EntityId 或 owner 获得控制权。

### 权威模拟与预测

- 输入通过所有权、序号、步长、频率、重复、过旧和最大跳号检查后进入该实体有界队列。
- 队列按实际到达顺序消费，不排序成另一套模拟。每个服务器 tick 每实体最多处理一条；无输入时该实体不推进 PredictionModel。
- 允许最大 32 的合法跳号。若较新输入先处理，迟到的缺失输入成为过旧输入；权威快照触发客户端回到确认状态，只重放更大序号的未确认输入，由此产生可解释校正并重新收敛。
- 服务器 tick 每固定步递增，快照按间隔发送，即使实体本 tick 没有新输入也不凭空推进位置。
- `PredictionReconciler` 在独立内核中实现并由 `next_client` 与 Godot `GameplayClientPrediction` 兼容壳共同消费，保持旧脚本 API、字典键和重放语义，避免两份确认／重放算法长期分叉。
- Godot `GameplayNetworkPrediction`、传输和 Session 不进入 M2 新链接闭包；旧网络线只保留必要回归。

### 服务器时间线与插值

- 客户端不能用本机墙钟直接采样服务器样本。`ServerTimeline` 保存最新服务器时间及接收时的本地单调时间，估算当前服务器时间，再以 `estimated_server_time - interpolation_delay` 采样。
- 本地实体快照进入 Reconciler；远端实体快照进入 M1 InterpolationBuffer。
- 无样本、单样本、范围前、插值、保持和陈旧保持沿用 M1.1 语义；长时间无样本进入 `stale_held`，不无界外推。

### 重连、重复重连和超时

1. 断线后在宽限期内保留 Session、Entity 和权威状态，旧 PeerId 立即失去输入权限，实体不再消费旧队列。
2. 正确凭据的新连接在宽限期内恢复同一 SessionId／EntityId；PeerId 换绑与凭据旋转是同一原子步骤。
3. 活跃会话的重复重连返回 `session_already_active`；宽限期内第一次重连成功后旧凭据失效，旧连接迟到或排队输入均被拒绝。
4. 客户端以 welcome 的权威状态重建预测基线并清空旧未确认历史，下一输入序号为确认序号加一。
5. 宽限期超时由服务器确定性销毁会话、输入队列和实体；远端客户端按样本缺失进入 stale_held。通用实体删除复制不在 M2 扩展。
6. 凭据不写日志或 Trace；本阶段只声明本地测试能力，不宣称生产认证、加密或账号安全。

### 优雅停服

- `BeginDrain` 先关闭传输和业务新准入，新连接得到 `server_draining`。
- 现有客户端完成有界输入和必要快照排空；服务器发送带 deadline 的 disconnect，等待客户端确认或超时。
- 正常路径在全部确认后关闭传输并销毁 RuntimeHost；超时强制关闭必须记录为异常，不能记作优雅停服通过。

## 文件级实施边界

```text
engine_next/
├── include/EngineNext/
│   ├── Runtime/{Clock,FixedStepLoop,World,RuntimeConfig,RuntimeHost,Trace}.h
│   ├── Network/{ITransport,Protocol}.h
│   └── Gameplay/PredictionReconciler.h
├── Runtime/{Clock,FixedStepLoop,World,RuntimeConfig,RuntimeHost,Trace}.cpp
├── Network/{Protocol,EnetTransport,ImpairmentTransport}.cpp
├── Server/{ServerRuntime,SessionManager,AuthoritativeSimulation}.cpp
├── Client/{ClientRuntime,ServerTimeline}.cpp
├── Gameplay/PredictionReconciler.cpp
├── Apps/{NextServerMain,NextClientMain}.cpp
├── Tests/{Runtime,Network,Gameplay,Integration}/…
├── Tools/{BuildRuntime.py,TestBuildRuntime.py,RunM2Acceptance.py}
└── thirdparty/enet/…
```

同步修改：

- `modules/gameplay`：仅 Reconciler 兼容适配、原有类实现转发、SCsub、测试和必要 API 文档，不改变公共脚本签名。
- `tools/engine_next_contract.json`、必要检查器及测试：增加真实第三方和两个可执行目标边界。
- `.github/workflows/engine_next_contract.yml`：增加运行时构建、干净环境和真实 UDP 验收。
- `engine_next/build-impact.json`：记录 native 输入、实际消费者、失效、回退和证据。
- `data-collection/` 与 `gonggong-diting-data/`：只追加实际请求、验证和交付回执，不预填跨平台结果。

## 五个顺序 PR 与完成门槛

五个切片共享同一不可分割的三进程验收链，保留一个 M2 Issue，不为关单拆成无法独立满足用户目标的子 Issue。每个 PR 从最新 main 创建精确候选，合入并回读后再开始下一片。

1. **独立构建与运行时**：Clock、FixedStepLoop、World、RuntimeHost、Trace、独立 main；两个程序实际启动并推进固定 tick，真实链接清单和干净源码树构建通过。
2. **连接与出生**：纯净 ENet、协议、实际 PeerId 会话绑定；一台服务器和两个真实客户端完成 hello、welcome 和不同 Entity 分配，负例协议测试通过。
3. **权威移动闭环**：固定 tick 输入队列、权威模拟、共享 Reconciler、ServerTimeline 和远端插值；A 收敛且 B 观察 A 移动，Godot 兼容回归通过。
4. **网络韧性**：重连、凭据旋转、旧连接失效、网络损伤、恶意包、stale_held 和优雅停服；受控校正及有界队列通过。
5. **M2 完成证明**：真实三进程 10,000 tick、干净构建／运行、符号和发布包检查、实际平台验收、完整 legacy 回归及交付回执。

## 验收清单

- [ ] 干净源码树没有 Godot 仍可构建服务器和客户端，启用 `--require-sources` 和真实 `--require-link-manifest`。
- [ ] 干净运行目录中一台服务器和两个独立客户端以真实 UDP 完成连接和不同 SessionId／EntityId 出生。
- [ ] A 持续输入，服务器固定 tick 权威模拟；A 最终与服务器确认状态收敛。
- [ ] B 通过服务器时间线和 InterpolationBuffer 观察 A 移动；长时间无样本进入 stale_held，不外推。
- [ ] 固定种子的延迟、抖动和丢包下至少产生一次可解释校正并最终收敛；确定性内存测试同种子 Trace 一致，真实 UDP 不伪装逐包确定。
- [ ] A 使用新 PeerId 重连后保持原 SessionId／EntityId；旧连接、重复重连、超时和凭据轮换行为确定。
- [ ] 伪造 owner、重复输入、过旧输入、超大跳号、错误版本、畸形包和超大包被拒绝。
- [ ] 服务器停止新连接，完成排空后优雅停服；强制超时不能冒充正常通过。
- [ ] 至少运行 10,000 个固定 tick，输入历史、插值缓冲和网络队列不超过配置上限并记录高水位。
- [ ] 真实对象、库、response、路径、SHA-256、平台符号和动态依赖无 Godot；发布包无 Godot 可执行文件和项目格式。
- [ ] Windows x86_64／MSVC 服务器与客户端、Linux x86_64 headless 服务器、macOS arm64／Clang 开发构建及客户端联调仅按实际运行结果记通过。
- [ ] 新旧两端共享预测、校正和插值算法；既有 Godot editor/template 必要回归通过，旧行为不变。
- [ ] 五个 PR 的正式门禁、提交后 Git 核验、精确候选 CI、main 回读和最终 Issue 收尾完成。

## 验证与采集证据

每个切片记录实际命令、平台、候选提交、结果和失败。干净环境、真实 UDP、跨平台和优雅停服没有实际回执时保持 unknown，不用单元测试、源码检查或模拟结果替代。
