# Godot Gameplay Framework（Unreal Engine 5.8.3 语义借鉴）

## 需求与授权

- 稳定需求 ID：`gameplay-framework-20261106`
- 用户目标：把 Unreal Engine 的 Controller、PlayerState、Pawn、GameState、GameMode、Component、Subsystem，以及 DS、网络相关性、属性同步、RPC、专服启动和用户连接等 Gameplay Framework 思路落到当前 Godot 4.8 分支。
- 授权来源：2026-11-06 用户明确要求“根据你的顺序落地”，随后要求“按大千系统拆分落地，并借鉴虚幻源码”。
- 参考来源：本机 Unreal Engine 5.8.3 release 源码。仅研究公开类型职责、生命周期和交互关系；不复制 Unreal 实现代码、注释或受保护资产。
- 目标平台与工具链：第一阶段 Windows x86_64、MSVC、Godot `tests=yes`；后续专服阶段覆盖 Windows/Linux headless，但只有实际构建过的平台才记为已验证。
- 交付目标：当前 Godot 仓库内可选的 C++ Gameplay 模块、类文档、自动化测试、代表性联网示例与可追溯设计；不改变现有 `Node`、`SceneTree` 或 `SceneMultiplayer` 的兼容语义。

## 天枢模块边界

依照 `framework/specs/module-system.md`，拆为稳定核心契约、业务能力和接入子模块。模块是逻辑职责，不等于 Git submodule、独立进程或固定 Agent。

### 稳定核心契约

`gameplay/core` 不依赖具体传输后端：

- `GameplayWorld`：一个玩法世界的组合根与生命周期所有者。
- `GameplayGameMode`：权威端规则、玩家准入后的创建/退出、重生策略；客户端不得作为可信状态源。
- `GameplayGameState`：比赛阶段与玩家状态集合；状态由权威端写入。
- `GameplayPlayerState`：稳定玩家/比赛状态，生命周期独立于 Pawn；连接更换和 Pawn 重生不销毁它。
- `GameplayController`：非物理控制者，维护 PlayerState 和被控制 Pawn。
- `GameplayPawn`：可被控制的实体，维护 Controller 的反向引用。
- `GameplayComponent`：可组合运行时能力，与玩法拥有者建立显式关系。
- `GameplaySubsystem` 与 `GameplaySubsystemRegistry`：按 Application、World、LocalPlayer/Connection 作用域初始化和反初始化的服务。

核心不变量：

1. Controller 与 Pawn 的控制关系始终双向一致；换控先解除旧关系。
2. PlayerState 不因 Pawn 解除控制、销毁或重生而消失。
3. 网络 authority 与 gameplay ownership 分离；服务器权威模式下 Pawn 的同步 authority 不因客户端控制而转移。
4. GameMode 只在权威上下文运行；GameState 承载可观察状态。
5. Subsystem 的反初始化顺序与初始化顺序相反，且重复调用幂等。
6. 运行时新增组件或 Pawn 不依赖父节点 authority 的隐式传播。

### 业务能力模块

- `gameplay/session`：临时 transport peer、稳定 user/session、PlayerState 和 Controller 的绑定。
- `gameplay/match`：比赛阶段、加入/退出、出生、重生、观战和结束。
- `gameplay/replication-policy`：属性描述、复制条件、通知、频率和量化。
- `gameplay/relevancy`：连接视图、空间候选、优先级和带宽预算。
- `gameplay/prediction`：输入序号、确认、预测、校正和可选延迟补偿。

### Godot 与平台接入子模块

- `adapters/godot-scene`：Node 生命周期、场景实例化和信号映射。
- `adapters/godot-multiplayer`：RPC、MultiplayerSpawner、MultiplayerSynchronizer、authority 与 visibility 映射。
- `adapters/enet`：ENet 客户端/服务器传输。
- `adapters/dedicated-server`：headless 启动、配置、健康状态、优雅停服和拒绝新连接。
- 后续可替换 WebSocket、自定义 MultiplayerPeer 或非 Godot 协议，不反向污染核心契约。

## Unreal 5.8.3 源码借鉴结论

核对的主要入口为 `Engine/Source/Runtime/Engine/Classes/GameFramework`、对应 `Private` 实现和 `Subsystems` 实现：

- GameMode 把 `PreLogin`、`Login`、`PostLogin`、`Logout`、`RestartPlayer` 分成不同生命周期阶段；本框架保留“传输认证/业务准入/玩家创建/出生”分层，不把连接成功等同于加入比赛。
- PlayerState 具备停用、重新激活、属性复制和无缝迁移语义；本框架保留稳定状态与临时 Pawn 分离，但不照搬 Actor 复制实现。
- Controller 是非物理控制者，通过 Possess/UnPossess 与 Pawn 建立双向关系；本框架将该不变量实现为 Godot Node 组合。
- Subsystem 由外部作用域拥有，并有 ShouldCreate、Initialize、Deinitialize；本框架采用显式 Registry 与作用域，不把所有服务做成 Autoload。
- Unreal 的所有权、网络 authority、相关性和复制条件是不同维度；Godot 适配层也必须保持区分。

## 分阶段交付与验收

### GF-1：Gameplay 核心语义

- 请求 ID：`gameplay-core-20261106`
- 范围：九个核心类型、作用域服务、双向 Possession、PlayerState/GameState 集合、权威 GameMode 生命周期。
- 验收：模块可编译；类可由脚本实例化/扩展；单元测试覆盖换控、解绑、状态独立、集合去重、Subsystem 顺逆序与幂等；生成类文档。
- 非目标：网络传输、DS 启动、预测移动、编辑器可视化。

### GF-2：DS、连接与会话

- 请求 ID：`gameplay-ds-session-20261106`
- 依赖：GF-1。
- 范围：Server Bootstrap、ENet 接入、版本/认证/准入状态机、UserSession、断线宽限与重绑定、优雅停服。
- 验收：headless 服务端和两个测试客户端完成认证、加入、断开、重连；peer ID 更换后 PlayerState 身份保持；拒绝新连接和停服有自动化测试。
- 非目标：账号服务实现、云部署和跨区域匹配。

#### GF-2 本地候选记录（2026-11-06）

- 新增 `GameplayConnection`、`GameplayUserSession` 与 `GameplaySessionManager`，把临时 peer、稳定 user/session、PlayerState、Controller 分开建模，并强制传输连接、版本检查、认证、业务准入、玩家创建、Pawn 出生的顺序状态迁移。
- 新增 `GameplayServerConfig`、`GameplayDedicatedServer` 与 `GameplaySessionClient`。专服可从资源或 `--gameplay-*` headless 参数启动 ENet，认证和业务准入通过外部 Callable 接入；当前握手只服务 GF-2，不提供通用 RPC 或属性复制。
- 断线后立即解除并销毁临时 Pawn，PlayerState 与 Controller 在宽限期内保持并清除 peer 绑定；携带匹配重连凭据的新 peer 可重绑定同一对象身份，宽限期满则由 GameMode 正常移除。未完成玩家创建的认证会话不进入宽限保留。
- 停服先同时关闭传输和业务新准入，再等待现有 peer 排空或到达截止时间，最后关闭 ENet 并清理会话。ENet 握手本身不加密，类文档明确要求生产环境使用短期凭据和适当安全网络边界。
- Windows x86_64 / MSVC 本地候选已实际完成 `editor tests=yes` 与 `template_debug` 构建；headless Gameplay 定向测试为 8 个用例、151 条断言，覆盖两个 ENet 客户端认证加入、断线、新 peer ID 重连后身份/PlayerState/Controller 保持、拒绝新连接和 drain 停服。Linux 专服尚未实际构建，不记为已验证。
- 首次本地验证时当前宿主无法解析 `gh`，未执行远端步骤；2026-11-06 用户恢复 CLI 后，已回读 `kaiyunxue` 的 WRITE 权限，创建并回读父单 #175、GF-1 #176、GF-2 #177 及三个后续计划单，并完成 GF-1/GF-2 intake-only。正式提交、PR、CI、main 合入和关单沿真实回执继续记录。
- 交付恢复时隔离分支已快进至 `8c391908f911af7b8ac8f6f88c99a87b6122c802`；新增主线差异为编辑器/宿主接入，与 gameplay 核心无冲突。工作树中他方新增的两个未跟踪 replication 文件保留，不纳入本次候选；构建入口显式列出 GF-1/GF-2 的六个编译单元，避免未交付文件被通配符编入。

### GF-3：RPC 与属性复制策略

- 请求 ID：`gameplay-replication-policy-20261106`
- 依赖：GF-1、GF-2。
- 范围：server/owner/client/multicast RPC 包装，sender/ownership 校验；InitialOnly、OwnerOnly、SkipOwner、RepNotify、频率和分片描述。
- 验收：越权 RPC 被拒绝；每种复制条件在双客户端场景符合预期；大状态分片不因单包超过 MTU 静默丢失。
- 非目标：兼容 Unreal 网络协议或属性元数据格式。

#### GF-3 本地候选记录（2026-11-06）

- 新增与传输解耦的 `GameplayRPCConfig`、`GameplayReplicationProperty`、`GameplayReplicationState` 和 `GameplayReplicationFragmenter`，以及只负责 Godot `MultiplayerPeer` 接入的 `GameplayMultiplayerReplication`。现有专服和会话客户端可选挂接该适配器，共享 GF-2 的 ENet peer 与轮询生命周期，不把 ENet 依赖写入属性策略或分片核心。
- RPC 只分派本地预注册的对象 ID、方法名与 Callable。server 入站使用 `get_packet_peer()` 的实际 transport sender，并要求其处于 `STATE_SPAWNED`、仍绑定活动 session；需要 ownership 的 server RPC 进一步比对服务器记录的 gameplay owner。owner/client/multicast 只能由 server 端发送，client 只接受 transport sender 为 server 的调用；消息内 sender、target 或 direction 声明均不能授予 authority。
- 属性运行时按 peer 保存 revision、InitialOnly 发送历史和最近发送时间，支持 Always、InitialOnly、OwnerOnly、SkipOwner、RepNotify、显式 dirty revision 与毫秒级频率节流。发送或分片失败会恢复对应 peer 的 dirty 状态并发出确定失败信号，不把失败更新误记为已交付。
- 大状态先用禁用对象解码的 Godot Variant 编码，再按默认 512 字节 payload 显式分片；适配层使用可靠 channel 1 且最终 envelope 有 1200 字节安全预算。分片包含传输序号、片序、总片数与总大小，支持乱序和相同重复片，拒绝冲突重复、旧序号、非法尺寸、超总量/片数/并发上限，并对缺片重组按超时失败。默认单次重组上限 1 MiB、2048 片、16 个并发 assembly。
- Windows x86_64 / MSVC 已实际完成 `editor tests=yes` 和 `template_debug` 构建。Gameplay headless 定向测试为 11 个用例、283 条断言，包含 GF-1/GF-2 回归及一台真实 ENet 服务端、两个客户端的 sender 伪造、非 owner 调用、server/owner/client/multicast 路径、InitialOnly/OwnerOnly/SkipOwner/RepNotify/频率节流和 4 KiB 多片状态；纯策略测试另覆盖乱序、重复、冲突重复、缺片超时、旧序号和超限。模板二进制 headless 版本启动与 editor headless 启动成功；默认模板禁用 `--path` override，因此没有把该配置拒绝误记为 Gameplay 失败。
- 运行时 doctool 已逐项比对 7 个新增/变更公共类的 API 签名，`doc/tools/make_rst.py --dry-run doc/classes modules platform` 以 0 退出并报告 class reference XML 无 warning/error；工具同时报告整仓 280 个既有 code-sample parity 诊断但未将其判为文档错误。Linux 专服仍未实际构建；空间相关性/复制图和预测未进入本候选。
- 当前已通过认证账号 `kaiyunxue` 回读 GF-3 Issue #178，并在同步本聊天授权后通过 intake-only。正式候选门禁随后被另一执行上下文留下的未跟踪 GF-2 `dispatch-307fd8becbf74edd813892eaaa17980e.json` 阻断；本线程未擅自暂存、移动或删除该并发文件，因此 GF-3 提交、推送、PR、CI、main 合入与 Issue 收尾均未执行，不以本地候选或测试结果冒充远端交付。

### GF-4：网络相关性与复制图

- 请求 ID：`gameplay-relevancy-20261106`
- 依赖：GF-3。
- 范围：连接视图、空间网格、owner/队伍/距离策略、优先级、频率与带宽预算、休眠唤醒。
- 验收：代表性多连接场景只生成和同步相关对象；对象移动跨区正确增删；提供候选规模下的 CPU/带宽实测，不用估算冒充结果。
- 非目标：超大世界流送系统。

#### GF-4 本地候选记录（2026-11-06）

- 新增传输无关的 `GameplayConnectionView`、`GameplayRelevancyObject` 与 `GameplayReplicationGraph`。连接视图只保存服务器给出的 peer、位置、队伍和每轮估算字节预算；距离对象进入均匀三维网格，owner/team/always 对象进入非空间候选集，再以精确策略过滤。策略是互斥枚举：always 对全部视图相关，owner-only 只匹配服务器记录的 owner，team-only 只匹配非零同队，owner-or-team 接受任一条件，distance 在网格候选后做精确半径判断。
- 每连接调度以对象优先级、预算未命中的饥饿积分、稳定 object ID 排序，并在成功调度后按对象更新间隔节流。估算大小不超过连接预算的对象会随饥饿积分增长最终获得机会；单对象估算本身大于连接预算属于无可行预算配置，不以突破预算冒充调度成功。图输出 entered/left/selected，现有 `GameplayMultiplayerReplication` 仍负责 GF-3 的属性条件、脏状态、分片、sender/owner 校验和实际 `MultiplayerPeer` 写入。
- 休眠对象保留在相关集合但不进入发送选择。进入休眠时记录 `GameplayReplicationState` 的本地 change serial；后续属性变更或显式 dirty 会以更大 serial 自动唤醒，也可由服务器显式唤醒。对象或视图跨格后，图在下一轮给出确定的 entered/left；适配层为离开连接清除 peer 发送历史，为重新进入连接重新登记，从而发送最新状态和 InitialOnly 初值。
- 相关性控制不接收客户端状态：只有配置为 server、且 peer 已处于 spawned 会话的适配器能安装/更新连接视图；配置后的客户端不能安装复制图。入站 `gameplay_relevancy_control` 一律拒绝并记录 `client_cannot_control_relevancy`，消息内位置、队伍或 owner 声明不能改变服务器可见性。
- Windows 11 `10.0.22631`、Intel Core i7-13700KF（16 核/24 线程）、MSVC Visual Studio 14.5 / Windows SDK 10.0.26100.0 的 editor headless 单进程实测：4096 个距离对象、32 个不同位置连接、100 m 网格、300 m 最大查询、150 m 精确半径的一轮规划用时 2809 µs；累计网格候选 19728、精确相关 3319、预算内选择 2018，选择估算 258304 字节。该 CPU 和候选数来自测试进程实际计时/计数，不是外推。
- 同一环境的真实 ENet 三客户端、四对象样本覆盖不同位置/owner/队伍视图和四类策略；Alice 的实际有数据发送对应配置估算累计 1400 字节，成功传给 `MultiplayerPeer.put_packet` 的 JSON/分片编码负载累计 2264 字节。这里的“实测发送字节”是应用到 Godot peer API 的实际 payload 长度，不包含 ENet、UDP、IP 或链路层头，不冒充抓包线速字节。
- Windows editor `tests=yes` 与 `template_debug` 构建通过；Gameplay headless 定向测试为 16 个用例、4592 条断言，覆盖 GF-1～GF-3 回归及三连接策略差异、对象/视图跨格、优先级/频率/预算与无饥饿、休眠脏唤醒/显式唤醒、客户端伪造拒绝和上述规模样本。editor/template_debug 的 headless 版本启动均以 0 退出；运行时 doctool 比对新增/变更 API，完整 `make_rst.py --dry-run doc/classes modules platform` 无 class reference warning/error，仍报告整仓 280 个既有 code-sample parity 诊断。GF-5 的预测、校正、插值和回滚未进入候选。

### GF-5：预测、校正与集成样例

- 请求 ID：`gameplay-prediction-20261106`
- 依赖：GF-3、GF-4。
- 范围：输入命令序号、服务端确认、客户端重放校正、插值缓冲、基础延迟/丢包测试；组合前四阶段的示例项目。
- 验收：受控延迟与丢包下移动最终收敛；服务端拒绝伪造状态；样例可按文档启动一个 DS 和两个客户端。
- 非目标：通用物理回滚、竞技级命中回溯和所有游戏类型的一体化移动方案。

#### GF-5 本地候选记录（2026-11-06）

- 新增传输无关的 `GameplayPredictionInput`、`GameplayPredictionState` 与 `GameplayPredictionModel`。基础模型只对有限、长度不超过一的移动意图做固定步长运动，不接入刚体或场景物理；输入只有单调序号、意图和固定步长，不包含客户端位置、速度、owner 或其他权威状态。
- 新增 `GameplayServerPrediction` 与 `GameplayClientPrediction`。服务端按实际 transport sender 和服务器记录的 gameplay owner 消费输入，拒绝重复、过旧、跳号过大、错误步长、非法向量和超速率命令；客户端立即预测，保存有界未确认历史，在权威确认后回到确认状态并且只重放更大序号的未确认命令。断线重连时，更高的合法服务端确认成为新基线并推进本地下一序号。
- 新增 `GameplayInterpolationBuffer`。样本按服务端时间有界排序，允许乱序到达；空缓冲、单样本、目标早于范围、范围内插值、正常末值保持和长时间缺包后的 `stale_held` 均有确定结果，不进行无界外推。
- 新增 `GameplayNetworkSimulator` 与 `GameplayNetworkPrediction`。测试适配器用显式种子提供有界应用层单向延迟、对称抖动、丢包和队列上限；预测适配器共享 GF-2 的 `MultiplayerPeer`，服务端只信任 `get_packet_peer()` 给出的 sender 与已 spawned 会话，客户端不能通过消息提交位置/速度。未确认输入按有界间隔重试，重复输入只促使服务端重发当前确认而不重复模拟；断线时清除旧 peer 的延迟队列和相关性视图。
- `GameplayDedicatedServer` 与 `GameplaySessionClient` 可选挂接预测适配器；GF-4 图的当前相关集合选择远端快照接收者，owner 总能得到确认。`modules/gameplay/examples/prediction_demo` 提供一台 headless DS、Alice 和 Bob 两客户端的启动命令，组合 GF-1 生命周期、GF-2 会话/重连、GF-3 属性复制、GF-4 相关性和 GF-5 owner 预测/remote 插值。
- Windows 真实三进程样例在每个方向 18 ms 基础延迟、±7 ms 抖动、15% 应用层丢包下实际完成连接、出生、持续移动和远端插值；Alice 从 peer `1940011177` 重连为 `1374998476`，两次服务端日志中的 PlayerState 实例均为 `28252833321`，四个进程 stderr 均为空。这些 peer/对象实例值只记录本轮实测，不是协议常量。
- Windows editor `tests=yes` 构建通过；Gameplay headless 定向回归为 20 个用例、4740 条断言，GF-1～GF-4 原有用例全部保留。预测集成测试在相同 18 ms / ±7 ms / 15% 条件下最终确认序号 29、发生 1 次校正、服务端记录 1 次预期拒绝、远端缓冲得到 19 个样本并最终精确收敛；纯策略测试另覆盖无延迟一致、重复/过旧/大跳号/owner 不匹配、校正只重放未确认输入、缓冲乱序/不足/陈旧保持，以及历史、输入速率和网络队列上限。
- Windows `template_debug` 构建通过，editor 与 template_debug 的 headless 版本启动均以 0 退出。运行时 doctool 对全部 Gameplay 公共 API XML 的方法、参数、返回、属性和信号签名逐项比对一致；完整 `make_rst.py --dry-run doc/classes modules platform` 无 class reference warning/error，仍报告整仓 280 个既有 code-sample parity 诊断。Linux 专服未实际构建，不记为已验证。

## 设计内的 Issue 拆分与交付记录

- 原始需求 ID / 父 Issue URL：`gameplay-framework-20261106` / https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/175 。
- 设计版本 / 文件与条款锚点 / Git 摘要：本文件 v1；当前隔离分支 `codex/gameplay-framework-20261106`。
- 设计定版决定及实际责任人：用户于 2026-11-06 明确要求按既定顺序及大千系统拆分落地，并在依赖阶段完成后授权继续 GF-5；当前 Codex 执行者负责本地 GF-1～GF-5 最终候选，GitHub 操作者为已回读的 `kaiyunxue`。
- 父级整体/集成验收及主责：五阶段全部验收，GF-5 主责最终组合验证；各子项只对自身可独立交付行为负责。
- 关系最后回读时间 / 来源 / 待同步项：2026-11-06，经 GitHub REST API 回读 #175 的全部五个 sub-issue 及每个子项的 parent 均一致；#180 已按父对话授权完成 intake-only 和本地候选验证，随后与 #176～#179 一并回读为 in-review。父项保持 in-progress；#180 仍是最终候选和未完成正式交付的主关联。
- GF-1～GF-4 尚未单独发布；GF-5 基于这些未发布基础形成同一最终模块候选。本次跨子项候选以 #180 / `gameplay-prediction-20261106` 为唯一活动主关联，#176～#179 作为一并回归的基础贡献。分别复核和记录 GF-1～GF-5 验收；在正式门禁、PR、CI 与 main 回读完成前不能关闭 #175 或任一子项。

| 子项 ID / Issue URL | 原生父单 | 设计条款 | 范围及非目标 | 验收/必要检查 | 前置依赖 | 主责 | 交付目标 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| [`gameplay-core-20261106` / #176](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/176) | #175 | GF-1 | 核心语义；不含网络 | 编译、单测、文档 | 无 | 当前 Codex 执行者 | 可独立合入的 C++ 模块 |
| [`gameplay-ds-session-20261106` / #177](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/177) | #175 | GF-2 | DS/连接；不含账号后端 | headless 集成测试 | GF-1 | 当前 Codex 执行者 | DS 与会话闭环 |
| [`gameplay-replication-policy-20261106` / #178](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/178) | #175 | GF-3 | RPC/复制策略；不兼容 Unreal Engine 协议 | 双客户端权限/复制测试 | GF-1、GF-2 | 当前 Codex 执行者 | 可组合复制策略 |
| [`gameplay-relevancy-20261106` / #179](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/179) | #175 | GF-4 | 复制图；不含世界流送 | 功能与规模实测 | GF-3 | 当前 Codex 执行者 | 相关性调度层 |
| [`gameplay-prediction-20261106` / #180](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/180) | #175 | GF-5 | 预测与样例；不承诺通用回滚 | 延迟/丢包收敛及启动文档 | GF-3、GF-4 | 当前 Codex 执行者 | 最终集成样例 |

## 当前停止条件与风险

- GF-1～GF-5 已形成同一隔离 worktree 的最终本地候选；本轮在 GF-5 全部验证并固定候选后停止，不继续扩展通用物理回滚、命中回溯或其他移动模型。
- 不修改原主工作树的未提交文件；全部生产写入隔离 worktree。
- Unreal 源码版本、Godot 基线或公共接口发生变化时只复核受影响设计。
- 没有真实远端 Issue、准入、CI 或 main 回读时不得声称相应步骤完成。
- 当前正式 #180 提交门禁仍被另一执行上下文留下的未跟踪且受保护 GF-2 `dispatch-307fd8becbf74edd813892eaaa17980e.json` 阻断；本候选不暂存、修改、移动或删除它，因此提交、PR、CI、main 合入和工单收尾保持未执行。
- 当前 Godot 网络同步仍有每同步器 64 个变化属性、对象属性不支持和大单包跳过等限制；GF-3 必须显式处理，不能由 GF-1 暗中扩展解决。
