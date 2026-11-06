# Godot Gameplay Framework（Unreal Engine 5.8.3 语义借鉴）

## 需求与授权

- 稳定需求 ID：`gameplay-framework-20261106`
- 用户目标：把 Unreal Engine 的 Controller、PlayerState、Pawn、GameState、GameMode、Component、Subsystem，以及 DS、网络相关性、属性同步、RPC、专服启动和用户连接等 Gameplay Framework 思路落到当前 Godot 4.8 分支。
- 授权来源：2026-11-06 用户明确要求“根据你的顺序落地”，随后要求“按大千系统拆分落地，并借鉴虚幻源码”。
- 参考来源：本机 Unreal Engine 5.8.3 release 源码。仅研究公开类型职责、生命周期和交互关系；不复制 Unreal 实现代码、注释或受保护资产。
- 目标平台与工具链：第一阶段 Windows x86_64、MSVC、Godot `tests=yes`；后续专服阶段覆盖 Windows/Linux headless，但只有实际构建过的平台才记为已验证。
- 交付目标：当前 Godot 仓库内可选的 C++ Gameplay 模块、类文档、自动化测试、代表性联网示例与可追溯设计；不改变现有 `Node`、`SceneTree` 或 `SceneMultiplayer` 的兼容语义。

## 大千模块边界

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
- Windows x86_64 / MSVC 本地候选已实际完成 `editor tests=yes` 与 `template_debug` 构建；最终 headless Gameplay 定向测试为 13 个用例、236 条断言，全部通过，覆盖两个 ENet 客户端认证加入、断线、新 peer ID 重连后身份/PlayerState/Controller 保持、拒绝新连接及已连接待准入客户端、drain 停服和审查修复回归。15 个类型的脚本实例化、GDScript 清理钩子及 World 隐式销毁 smoke 通过；另用三个独立 headless editor 进程完成 DS 与 Alice/Bob 认证加入、两次断开及最终停服。Linux 专服尚未实际构建，不记为已验证。
- 独立原生子 Agent `/root/sinan_d3a08e32761a2af8` 完成一次必要审查及受影响修复复核，最终源树 `0169531f6dcc977be342f7e39169cc4c8c80876f` 无剩余阻塞。修复涉及回调前阶段检查、准入后玩家对象重绑定、旧 Pawn ownership 清理、PREDELETE 清理时机，以及动态注册/嵌套生命周期保护；实际原生完成状态和共享认领释放均已对账。完整构建输入、二进制摘要、失败与修正、平台边界见 `data-collection/gameplay-gf2-validation-20261106.json`。
- 首次本地验证时当前宿主无法解析 `gh`，未执行远端步骤；2026-11-06 用户恢复 CLI 后，已回读 `kaiyunxue` 的 WRITE 权限，创建并回读父单 #175、GF-1 #176、GF-2 #177 及三个后续计划单，并完成 GF-1/GF-2 intake-only。正式提交、PR、CI、main 合入和关单沿真实回执继续记录。
- 交付恢复时隔离分支已快进至 `8c391908f911af7b8ac8f6f88c99a87b6122c802`；新增主线差异为编辑器/宿主接入，与 gameplay 核心无冲突。工作树中他方新增的两个未跟踪 replication 文件保留，不纳入本次候选；构建入口显式列出 GF-1/GF-2 的六个编译单元，避免未交付文件被通配符编入。

### GF-3：RPC 与属性复制策略

- 请求 ID：`gameplay-replication-policy-20261106`
- 依赖：GF-1、GF-2。
- 范围：server/owner/client/multicast RPC 包装，sender/ownership 校验；InitialOnly、OwnerOnly、SkipOwner、RepNotify、频率和分片描述。
- 验收：越权 RPC 被拒绝；每种复制条件在双客户端场景符合预期；大状态分片不因单包超过 MTU 静默丢失。
- 非目标：兼容 Unreal 网络协议或属性元数据格式。

### GF-4：网络相关性与复制图

- 请求 ID：`gameplay-relevancy-20261106`
- 依赖：GF-3。
- 范围：连接视图、空间网格、owner/队伍/距离策略、优先级、频率与带宽预算、休眠唤醒。
- 验收：代表性多连接场景只生成和同步相关对象；对象移动跨区正确增删；提供候选规模下的 CPU/带宽实测，不用估算冒充结果。
- 非目标：超大世界流送系统。

### GF-5：预测、校正与集成样例

- 请求 ID：`gameplay-prediction-20261106`
- 依赖：GF-3、GF-4。
- 范围：输入命令序号、服务端确认、客户端重放校正、插值缓冲、基础延迟/丢包测试；组合前四阶段的示例项目。
- 验收：受控延迟与丢包下移动最终收敛；服务端拒绝伪造状态；样例可按文档启动一个 DS 和两个客户端。
- 非目标：通用物理回滚、竞技级命中回溯和所有游戏类型的一体化移动方案。

## 设计内的 Issue 拆分与交付记录

- 原始需求 ID / 父 Issue URL：`gameplay-framework-20261106` / https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/175 。
- 设计版本 / 文件与条款锚点 / Git 摘要：本文件 v1；首次候选位于 `codex/gameplay-framework-20261106`；交付恢复后为避开并发 GF-3 修改，从精确暂存树 `cccba3f0d3211dda950dfea5e704c7411e457077` 新建 `codex/gameplay-gf2-delivery-20261106`，当前工作树 `D:/Projects/godot-gameplay-gf2-delivery-20261106`。原工作树及其所有未提交内容均保留。
- 设计定版决定及实际责任人：用户于 2026-11-06 明确要求按既定顺序及大千系统拆分落地；当前 Codex 执行者负责 GF-1/GF-2，GitHub 操作者为已回读的 `kaiyunxue`。
- 父级整体/集成验收及主责：五阶段全部验收，GF-5 主责最终组合验证；各子项只对自身可独立交付行为负责。
- 关系最后回读时间 / 来源 / 待同步项：2026-11-06，经 GitHub REST API 回读 #175 的全部五个 sub-issue 及每个子项的 parent 均一致；GF-1/GF-2 为 in-progress，GF-3/GF-4/GF-5 为 planned。后续阶段仅登记，不开始本轮实现。
- 当前 GF-1 尚未单独发布，GF-2 的类型注册、核心生命周期和测试基于该未发布基础组成同一初始模块候选；本次跨子项交付以 #177 / `gameplay-ds-session-20261106` 为唯一主关联，#176 作为一并验收的基础贡献。分别复核和记录 GF-1/GF-2 验收，不能据此关闭 #175 或后续阶段。
- 发布必要的 CI 前置修复：当前 main 的 [GHA run 42219878669](https://github.com/zhzyx/nightmarish-spooky-sorceryze/actions/runs/42219878669) 在创建任何 job 前以 `startup_failure` 结束，GitHub 明确报告 Windows 被调用工作流申请 `actions: read`，调用方却只允许 `actions: none`。本候选只为 runner 显式声明 `contents: read` 和 `actions: read`，恢复现有 CI 的合法调用，不添加写权限或放宽检查。
- 提交前已整合 `c21ce691ca2dc50de90985d9fdd5dfbbf5e64a40`，相对实际构建基线 `8c391908` 仅新增宿主 Python 接入和证据，不改变 Gameplay/引擎构建输入。复用上述验证并明确其输入对应关系，远端 CI 另绑定实际签发 head；后续真实候选、PR、CI、main 回执及各子项关闭证据写入 #177/#176 时间线，由本设计的真实 Issue 链接保持溯源，不预填未知发布结果。
- 首次正式交付已通过门禁及提交后谛听核验，内容提交 `3f9c06bcfb9a4bb9c215c2bf55da9bd5c3edb6de`、GitHub 签发 head `25c3206b80f0238b391ec85223b963d55339603e` 与 [PR #185](https://github.com/zhzyx/nightmarish-spooky-sorceryze/pull/185) 均已回读，Issue 关联检查通过。实际 CI 随后发现 21 个早已跟踪的 #55 历史验收日志被 `*.log` 忽略，阻断全量 gitignore 检查；本轮仅对这 21 个精确路径添加例外，保留全部历史字节和现有检查，沿新精确候选重新签发。详情见 `data-collection/gameplay-gf2-ci-preflight-20261106.json`；不因旧候选已有提交而跳过失败检查。
- 重新签发前主线推进到 `c364925d2662e82106be215944ee3337f34a0013`，本地任务提交已重基且暂存修复完整恢复。新增主线为大千编辑器与宿主接入，不涉及 Gameplay 核心及其底层 Node/MultiplayerPeer 输入；复用逐文件相同的模块验收，新增编辑器整合由新候选 CI 验证，不把先前二进制声称为该基线重新构建。
- 当前交付为 [PR #187](https://github.com/zhzyx/nightmarish-spooky-sorceryze/pull/187)，旧 #185 已注明替代并关闭，分支和证据均保留。第二轮实际 CI 已通过历史日志规则、模块格式/脚本/文档及 Issue 关联检查；新模块 CODEOWNERS 登记已按构建/文档/测试类别补齐并本地验证。剩余失败为现有共工离线冻结登记相对框架多出 28 文件、37 文件摘要不同（无缺失），与本 Gameplay 候选无差异关联，已独立登记 [阻塞项 #189](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/189)。冻结登记需要确认真实批准精确版本及独立审查，本轮不改写登记或批准；main 合入及 #176/#177 完成关闭保持阻塞。详细回执见 `data-collection/gameplay-gf2-ci-blocker-20261106.json`。

| 子项 ID / Issue URL | 原生父单 | 设计条款 | 范围及非目标 | 验收/必要检查 | 前置依赖 | 主责 | 交付目标 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| [`gameplay-core-20261106` / #176](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/176) | #175 | GF-1 | 核心语义；不含网络 | 编译、单测、文档 | 无 | 当前 Codex 执行者 | 可独立合入的 C++ 模块 |
| [`gameplay-ds-session-20261106` / #177](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/177) | #175 | GF-2 | DS/连接；不含账号后端 | headless 集成测试 | GF-1 | 当前 Codex 执行者 | DS 与会话闭环 |
| [`gameplay-replication-policy-20261106` / #178](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/178) | #175 | GF-3 | RPC/复制策略；不兼容 Unreal 协议 | 双客户端权限/复制测试 | GF-1、GF-2 | 待实际派发 | 可组合复制策略 |
| [`gameplay-relevancy-20261106` / #179](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/179) | #175 | GF-4 | 复制图；不含世界流送 | 功能与规模实测 | GF-3 | 待实际派发 | 相关性调度层 |
| [`gameplay-prediction-20261106` / #180](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/180) | #175 | GF-5 | 预测与样例；不承诺通用回滚 | 延迟/丢包收敛及启动文档 | GF-3、GF-4 | 待实际派发 | 最终集成样例 |

## 当前停止条件与风险

### GF-2 恢复交付（2026-11-07）

- #189 已由其他协作者经 [PR #206](https://github.com/zhzyx/nightmarish-spooky-sorceryze/pull/206) 修复，实际合入 main `a870e312eed410c8f487075997297790016a001d`（北京时间 11 月 7 日 00:29）。此前 #205 是关闭且未合入的替代版本。本聊天只整合已接收主线，不重复修复或重写冻结登记。
- 整合后离线快照检查实际通过（280 个冻结文件），正式框架校验为 `approved_file_integrity`，#177 intake 回读通过。Gameplay 树仍为 `e2139f2ebf54b32e450b1af0fb09a697aca4ba55`，底层 Node/MultiplayerPeer/Object 输入不变，保留既有 13 用例/236 断言、Windows 构建及脚本/三进程实测；不把它们冒称为新提交实跑。
- Windows 可复用工作流的调用权限仅在 `windows-build` job 明确为 `contents: read` 与 `actions: read`，不改变全仓 job 默认权限，不增加写权限。受影响差异的独立复核无阻塞；新精确签发 head 的 CI 和 main 回读另按实际结果推进。
- main 已包含历史日志的精确忽略例外，本候选移除重复条目，使 `.gitignore` 与当前主线一致。旧失败记录保持历史原样，恢复证据见 `data-collection/gameplay-gf2-resume-20261107.json`。
- 精确签发 head `2ed4bcf78a6817b827240229e119976fefa74986` 的远端 CI 静态检查、MSVC/GCC release 模板和 clang-cl 编辑器通过；MSVC 编辑器在既有 `ai_chat_gonggong.cpp` 两处局部 `request` 遮蔽成员时报 C4458，并因 `/WX` 失败。发布前置修复只改局部变量名和 clang-format 缩进，保留所有请求键、参数与业务行为；最终文件已用 `/W4 /WX` 单对象编译通过并独立复核无阻塞，新精确 head 仍须完整 CI。证据见 `data-collection/gameplay-gf2-strict-compile-20261107.json`。

- GF-1 与 GF-2 已形成同一隔离 worktree 的本地候选；本轮在 GF-2 验证后停止，不开始 GF-3。
- 不修改原主工作树的未提交文件；全部生产写入隔离 worktree。
- Unreal 源码版本、Godot 基线或公共接口发生变化时只复核受影响设计。
- 没有真实远端 Issue、准入、CI 或 main 回读时不得声称相应步骤完成。
- 当前 Godot 网络同步仍有每同步器 64 个变化属性、对象属性不支持和大单包跳过等限制；GF-3 必须显式处理，不能由 GF-1 暗中扩展解决。
