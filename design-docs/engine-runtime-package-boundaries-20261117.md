# 引擎业务包边界与既有 Engine Next 复用核查

需求 ID：engine-runtime-package-boundaries-20261117。父需求：[AI 原生引擎 #1382](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1382)，设计条款 P0-B。

用户于 2026-11-17 授权开始执行，要求优化内嵌头文件、模块化交付及多 Agent 工作流，渲染/3D 至少支持《血源诅咒》参考的 AA 写实沉浸目标，Windows 优先。当前 main a22d44c5 含 Engine Next M3/M4 等已有实现及在途工作，先核验可复用边界，禁止重复创建运行时或抢占他人代码。

此独立子项输出精确可执行的模块迁移契约、实际消费者清单和验证方案，覆盖：
- daqian_scripts/startup_checks/daqian_board/ainative bundle/gonggong_validation 生成头的输入、原生引用与实际执行入口；已有 tianshu-ui/1 包的使用、兼容与回退证据。
- engine_next 的 AICore、Executor、Artifact/Asset/Scene、包、WorkflowController、独立运行时和渲染里程碑；远端 Issue/PR 当前责任与状态，区分已交付、在途和未知。
- 分清可外置脚本/宿主工具、必须保留或重构的原生接口及会影响画质/帧时间的路径。模块逻辑边界不以扩展名推断。
- 给出首个业务包迁移的固定接口、读写边界、依赖、同二进制更新/不兼容拒绝/回退验收，以及与多宝模块修订的接合方式。

本子项只读产品代码，文档与机器可读证据写入本子项授权文件；不更改源码、构建、运行安装或其他任务分支。实际迁移按核查结果另拆开发子项。当前责任者核验源文件/消费点与工单回读后方可接收；仅规划说明不代表完成外置或 AA 验收。

资源：本子项产生的私有派发回执保留；只读不启动图形窗口、不运行生产模型、不触碰凭据。

## 2026-11-17 核查结论与证据等级

产品源码固定在 `a22d44c536835316b33a807426774008f4dfba02`，稀疏副本未物化的文件通过 `git show HEAD:<path>` 读取。路径均以该仓库根为解析基准。机器证据为 `data-collection/engine-runtime-package-boundaries-1387.json`，保存源码字节摘要、远端 Issue/PR 实际回读和时间；远端 main 后续交付与本地源码分别记录。本次仅静态核查，没有重新运行编辑器、GPU 或生产模型。宿主描述 `codex-current-host` 不是精确模型名称，实际模型未知。

已召回本租户 `godot-build-placement/trace-native-consumer` revision 17，状态 verified、unavailable 为空。适用方法是沿生成器和原生消费者追踪；反例是 Python 仍可成为原生嵌入输入，不能按后缀排除构建依赖。本次据此修正包边界：`daqian_board` 目前是有条件的旧宿主兼容适配，并非所有看板请求的唯一运行包。

### 实际输入、消费与执行链

| 产物 | 精确源与消费者 | 迁移结论与限制 |
| --- | --- | --- |
| `editor/docks/daqian_scripts.gen.h` | `editor/SCsub` 将 `editor/docks/daqian/{graph_rules,operation_details,issue_inspector,canvas_context,spatial_workbench,workspace,workflow_controller,model_settings}.gd` 和 `customizations/components/godot-host/silent_validation.gd` 交给 `editor_builders.daqian_scripts_builder`；非桌面另含 graph_layout/issue_graph。`daqian_dock.cpp::load_editor_script` 调用 set_source_code/reload，`create_daqian_dock` 实例化并注入脚本及对象。 | 可拆业务资源，但控制器依赖、对象属性与原生 Callable 是实际 ABI；目前变更仍须原生重建。不能将整个头文件统称纯 UI，silent_validation 和空间编辑器也在其中。 |
| `startup_checks.gen.h` | `SCsub` 输入 startup_checks/startup_git/session_memory GDScript 及 session_credentials/startup_git_helper Python；`daqian_dock.cpp::create_gonggong_startup_checks` 注入 git_script、memory_script、helper source、EditorSettings metadata_saver、automatic_enabled。 | 分离启动、会话与可选 Git 适配，保留可信宿主凭据和恢复模式/命令行保护。无 Git 的多宝模式需新增模式契约和实测，现有代码不证明无 Git 可运行。 |
| `daqian_board.gen.h` | `daqian_board_builder` 将 `customizations/components/godot-host/daqian/{editor_board_entry,board,board_delta,progress}.py` 打成确定性 ZIP，入口改名 `__main__.py`，计算 ZIP SHA256，再 Base64。`create_daqian_dock` 注入 `board_bundle_base64/board_bundle_sha256`。`workspace.gd::_board_entry_args` 仅在宿主 board.py 是 LEGACY_BOARD_HASHES 之一且没有 board_delta.py 时物化到编辑器 cache `gonggong-board-<sha>.pyz`。 | 首选独立外置候选，但必须保留条件分支。现代宿主、未知 board.py 或缺文件走原脚本。执行 `python -I -B <pyz> --workspace-board-sha256 <digest>`；`editor_board_entry.py` 再验证当前 workspace board.py，附加宿主导入路径后调用 board.main。四文件包不是完整独立宿主，不能删除 workspace 依赖。 |
| `editor/ainative/bundle.gen.h` | `SCsub` 收集 samples/ainative-workbench/addons/ainative/*.gd（排除 plugin.gd）、tools/ainative/*.py（排除 test_）、image_contact_sheet.gd；`editor/ainative/builders.py::bundle_sources` 补 tools/editor_provenance_process.py。bundle_files 改写 res 路径、产出 scripts/tools/manifest.json；build_bundle 对路径和内容计算总摘要。`ainative_editor_plugin.cpp::install_ainative_bundle` 逐文件摘要检查、临时文件替换；`_prepare_workbench` ResourceLoader 加载 scripts/workbench.gd。 | 可外置内容包；当前内容寻址安装目录不等于支持独立选择包版本。需增加 manifest/host ABI/整体摘要验证和选包、回退。保持 `ainative_builtin`、`ainative_tools_dir`、项目路径摘要隔离的 state_dir、UnifiedSettings settings_source_ready 生命周期。未知依赖不得从 bundle 中遗漏。 |
| `gonggong_validation.gen.h` | 仅 macOS，输入 macos_validation.gd 与 tests/editor/daqian_ai_entry.gd；`install_gonggong_startup_validation` 加载验证脚本，注入 probe_source，并由 silent_validation 协调；recovery/cmdline 时退出。 | 独立宿主验证包候选，需 macOS 自身验收；Windows 不代验。 |
| `bin/tianshu-ui[.self_update_a/.self_update_b].json` | `tools/package_tianshu_ui.py` 打包 graph_layout/issue_graph；`SCsub` 桌面分支采用 Requires，脚本包不参与编辑器链接；`daqian_dock.cpp::load_tianshu_package` 校验后供 create_daqian_dock 编译。 | 可复用的加载模式仅覆盖两个图形脚本。默认包从可执行文件旁读取，macOS app 从 Resources；Web/mobile 保留嵌入。 |

### 已有天枢 ABI 与历史回退证据

现行 ABI 是 **`tianshu-graph/1`**，并非 `tianshu-ui/1`。包为 JSON envelope `{sha256,payload}`，payload 为 JSON 字符串，字段为 abi、非空 version、graph_layout、issue_graph。最大 4 MiB。默认文件仅校验 envelope payload 摘要；环境覆盖 `GONGGONG_TIANSHU_UI_PACKAGE`/`GONGGONG_TIANSHU_UI_SHA256` 必须同时形成绝对文件路径和 64 位十六进制整包 pin，拒绝 URI。读取使用 SKIP_PACK 且同次打开的字节用于校验与编译。`verify_candidate_package` 将安装包摘要绑定到候选清单。摘要完整性不自行代表审查授权。

`data-collection/tianshu-versioned-ui-package-689.json` 是历史 Windows/MSVC 证据：同一二进制 `6f0abedad3a4bc448c7fa19ffea9941fb0530f4d5f2de88d3a7db1d805da1c4a` 上 installed→selected→rollback 为 48→96→48，独立更新槽验证，错 pin、缺 pin、项目路径、缺失包、损坏 payload、不兼容 ABI 均 blocked；修改真实 layout 输入后 EXE 与 daqian_scripts 头摘要不变，仅包改变。锁定安装包替换失败时恢复原可执行文件、包和 inventory。这是启动选包/回退与 headless 验证，不能称运行中热换；既有 graph regression 使用另一个明确记录的二进制。Linux/macOS 本地运行未在该 Windows 回执中执行，亦不能推导本次 AA 画质。

### Engine Next 复用与在途责任

| 现有边界 | 源码消费者与复用方式 | 实际交付/未知 |
| --- | --- | --- |
| AICore | `ai_core/Runtime.h/.cpp` 的运行身份、代次、终态规则；`engine_next/AI/WorkflowSnapshot.cpp` 直接调用 AICore；`engine_next/Tools/BuildRuntime.py` 显式编译 Runtime.cpp。 | 复用现有核心，禁止再造运行状态机。`ai_core/README.md` 要求宿主持有存储、线程与凭据；公共数据不携带秘密。C++ 源级接口不等于稳定 DLL ABI。 |
| Executor/Controller | `engine_next/AI/WorkflowController.cpp` 经 IProcessTransport 以 Python CLI 调 create/status/step/export/cancel，冻结 request/model，记录 executor run、request digest、published artifacts；`HostConfig` 固定 Python、脚本、factory、数据库、state/output、超时与输出限制。 | 复用无 View 控制器和现有 tools/ainative Executor/Provider，不引入第二套执行协议。发布前 cancellation 与失败、恢复、模型身份需继续回归。 |
| Artifact→Asset | `ArtifactAdapter.cpp`/`ArtifactAdapter.h` 的 ParseAiAssetRequest/AdaptArtifacts，把绑定的 node/port、asset_id/role、Scene template 和 export 形成 PackageData；AssetManifest/SceneDocument v1 为中立契约。 | 不把 Provider job_id、文件路径当资源 ID；保持不可变 revision/content digest，AI Artifact 扩展与严格 M3 Schema 分离。 |
| 资产与运行时 | `Assets/AssetPackage.cpp` 提供 ComputePackageDigest/LoadPackage/PublishPackage/PublishPackageGuarded；`Apps/NextAssetMain.cpp` 与 `Runtime/SceneRuntime.cpp` 真实消费 LoadPackage；BuildRuntime 构建独立运行时。 | 复用 `.enpak` 和既有 next_asset/server/client，不能仅因包格式相似改写成多宝对象存储。接入层引用精确包摘要及 AssetId/revision，跨系统接收、验收、发布仍分开。 |
| 可视运行时 | `Rendering/VisualRuntime.cpp`、RenderPipeline、FrameGraph、Cook/GpuPackage 是原生渲染及 GPU Cook 边界；M3 原始资产经渲染层 cook，不能污染原资产契约。 | 原生逐帧、GPU 资源与同步不迁到文本解释、HTTP 或模型。以现有 M4 负责人为唯一推进者，本项不更改其分支或候选。 |

远端回读：M2 #1042 CLOSED；M3 #1240 CLOSED，最终 #1302 合入 `0bc22d445086e8f9cdacd43dfe3817c7690bcf41`，责任来源 kaiyunxue。其最终评论报告跨平台 423 项 AINative 等回归和新旧运行时验收，属于历史交付报告，本次未复跑。M4 #1323 OPEN；其后续评论明确用户已授权 M4.1–M4.6，实现确认等待已经解除，不能只读最初 body 判为未授权。M4.1 #1327、M4.2 #1334 CLOSED；M4.3 #1343 OPEN，现有工作者 `codex-m4-implementation` / kaiyunxue；#1349 OPEN，不能以绿色 CI 擅自关闭间歇故障。

M4.3 #1350 方向阴影已有交付；后续 TAA #1384 merge `952aff5ac92dce16d9ed45a080b6d5f9b0fdd533`、曝光/Bloom #1390 merge `83775e6c2ffb5b3a518c4ffebbe0f3777c7dce06` 均为本地基线之后的远端交付。最新 #1343 评论称正于隔离工作树继续 SSR，体积/动态透明、父单完整几何流送/GI/UE A–F 对照/原生 4K 性能稳定性仍未完成。保留这些责任和未完成项，不另建同义渲染任务。#951 OPEN 且 #1234/#1245 OPEN，涉及控制器准备/父级续跑；全量 workspace/controller 外置须先与其责任者确认具体文件和候选归属。无 assignee 不代表无人占用。

## 首个独立实施：只读看板兼容宿主包

建议另拆实现子项 `tianshu-board-compat`，先移除四个 Python 内容对原生生成头的依赖，保持当前看板行为；不是本审计已实现的能力。它比全 workspace/controller 或马良外置更容易隔离。生产改动范围拟限 `editor/SCsub`、`editor/editor_builders.py`、`editor/docks/daqian_dock.cpp`、新增打包器与专属验证；如需改 workspace.gd，先核对 #951 占用，尽量通过原有两个注入字段保留消费方式。不改四个 Python 业务语义、不改共享模型/渲染运行时。

固定拟议 ABI **`tianshu-board-compat/1`**，与 `tianshu-graph/1` 独立：

1. JSON envelope `{sha256,payload}`；payload UTF-8 JSON 字符串含 `abi`、非空 `version`、`bundle_base64`、`bundle_sha256`、`entries`。entries 只允许 `__main__.py,board.py,board_delta.py,progress.py`，对应每个解压文件的 SHA256；拒绝重复、目录穿越、绝对路径、符号链接条目。bundle_sha256 是解码 ZIP 的摘要，envelope.sha256 是 payload 字节摘要，部署 pin 是完整 envelope 文件摘要，三者不得混用。
2. 第一版整包上限 4 MiB、解压内容总量上限 16 MiB；均是拟议验证约束，实施前测量当前真实包并留证。拒绝未知 ABI、缺字段、错误类型、超限、Base64/ZIP 非法或摘要失配。不得在失败后执行未校验字节。
3. 宿主一次读取并验证字节，注入现有 `board_bundle_base64/board_bundle_sha256`；默认从可执行文件相邻、对应 self_update 槽的 `tianshu-board[.<slot>].json` 读取，macOS Resources 路由保留待本机验收。显式选包使用拟议 `GONGGONG_TIANSHU_BOARD_PACKAGE` 与 `GONGGONG_TIANSHU_BOARD_SHA256`，必须成对且为绝对文件路径/有效整包 pin，绕开项目 pack。
4. 保留 `_board_entry_args` 的全部条件、LEGACY_BOARD_HASHES、cache 原子写和摘要核验、`-I -B`、`--workspace-board-sha256` 绑定及原始 CLI 参数/result JSON。包失败只允许回到既有可信宿主原脚本路径并显示可读诊断；显式选择被拒必须留明确拒绝回执，不能伪称选包成功。此回退不是执行不可信包，也不放宽宿主 repo/user/session 核验。
5. 只在启动/新会话选择包；已运行会话固定其包摘要，旧缓存受占用时不删除、不原地改写。更新使用临时写入、校验、原子选取；回滚恢复前次已验收包 pin，下一启动生效。Windows sharing violation 保留旧包与指针，先回读实际状态。
6. 读集合固定宿主 ABI、四个源文件摘要、打包器版本、legacy helper 摘要、候选清单；写集合限包输出、编辑器 cache 和既有 result/private 会话路径。不得写凭据、其他工作者副本或更新业务权威。`editor_board_entry` 仍依赖所选宿主导入闭包，其摘要/版本须进入兼容性验证。

多宝接合采用模块修订 `{module_id, revision, parent_revision, content_digest, exports, exact_dependencies, placement, evidence_refs}`：模块可 placement=host_tool，原生加载器为 native，版本化 envelope 为 runtime_package。exports 固定上述 ABI；exact_dependencies 固定 loader ABI、Python/宿主适配器身份。发布清单只选已验收精确修订。多宝模块 ID/对象身份不使用 Git SHA 或 Issue 号；本次 SHA/Issue 只是实现来源与证据。旧宿主 Git board 适配可作为可选依赖，不能据此宣称新多宝内核已经无 Git。跨模块 ABI 变化使用新 ABI 与组合验收，不能仅替换字符串。

### 必须提供的回归证据

- 同一 Windows 二进制记录 SHA256，包 A→B→A 触发可观测只读结果差异且恢复；记录包 pin、会话、结果。运行 A 会话时安装 B，A 的工具请求仍使用 A，下一会话使用 B。
- 包错 pin、payload/ZIP/entry 摘要错误、未知 ABI、缺失、超限、损坏 ZIP、目录穿越、锁定替换失败均拒绝；旧包/指针与在途会话可回读，回退行为与显式选包失败分别留证。
- legacy 两个 helper 摘要、有 board_delta.py 的现代宿主、未知 helper、缺失 helper、写 cache 失败、执行前 helper 被改变、取消/结果迟到逐项对比旧行为。repo/user/session/result/delta 语义保持；无授权副作用不被包迁移新增。
- 改四个源文件只改包摘要，不重编/链接编辑器；改 native loader、宿主 ABI、仍嵌入输入必须触发正确构建失效。检查真实构建命令/产物摘要，不能只靠配置文字断言。
- 现有图形包、启动检查、马良首次打开与设置、控制器续跑和 process provenance 回归；实际消费者受影响才扩大矩阵。模块打包不修改 M2/M3；若改公共 AICore、Executor 或资产接口，补既有独立构建、取消恢复、资产负例、legacy 和真实链接依赖验证。
- 本审计不验收 AA。父需求 Windows 写实沉浸底线继续保留；#1323 自有原生 4K High ≥120 FPS、1% Low ≥90 FPS/30 分钟目标不自动变成 #1382 的最低硬件承诺。两条验收分别保留，固定资产/镜头/灯光/曝光/驱动/二进制测量 CPU/GPU 帧时间、P95/P99、显存、加载与真实画面；后台多 Agent 负载对前台帧时间另测。无 GPU 测试、截图或平均帧率不代替完整画质/动态/稳定性验收。

## 验收余项与资源

本项已产出消费者清单、真实源码摘要、远端状态及可实施契约；仍需责任者独立核查与接收。后续实际开发另拆任务，不能把本审计关闭等同于模块已外置、Engine Next M4 完成或 #1382 整体验收。提交前刷新远端在途责任，但不得追赶无关源码重做本静态基线。未创建临时安装、图形窗口或测试设置；仅保留本设计及机器证据，无本子项临时分支/worktree 可清理，父任务共用工作树不触碰。
