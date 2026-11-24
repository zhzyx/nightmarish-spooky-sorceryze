# B01　Godot 原生入口清单

[工单 #1873](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1873) · [方案一与验收卡](gonggong-ai-workbench-plan1.md#b01) · 源码基线 `b60ae96914cd25b0856f4be09b6b0b6a710cc717`。下表“去向”是后继卡的设计输入。本次核对注册、打开与宿主关系；同一新入口的按钮、快捷键、模态焦点与系统窗口实测分别由 U01–U06、Q01、Q10、Q11 接收。

## 主屏与布局

用包含本仓库定制的 Godot **编辑器**打开一个项目。以下按新布局的顺序列出页签。窄窗口可从 **Workspaces** 菜单选同名项；旧布局恢复其保存的选择。AI Chat、马良、天枢和设置被选中时，主屏会隐藏场景标签、侧边及底部面板；检查场景和文件时应切回 2D 或 3D。[注册顺序][node]，[Workspaces 与主屏可见性][main]，[历史布局与十页签回执][order]。

| 当前入口 | 打开方式与观察点 | 原生挂载与定位 | 方案一去向 |
| --- | --- | --- | --- |
| AI Chat | 点 **AI Chat → 会话**，可见输入框、会话标签和“仅咨询”。单纯打开无需模型凭据。 | [`AIChatDock::AIChatDock`][chat]，主屏键 `AIChatMainScreen`。 | U13 把旧页签、旧布局和深链重定向到 U01/U02 的唯一工作台，携带原会话。 |
| 马良 | 点 **马良**，进入默认 Mesh 生成页，选择图像或 Mesh 节点；切换骨骼绑定、角色等导航。GDScript 和可写编辑器数据目录用于首次加载内置包。 | [`AINativeEditorPlugin::_prepare_workbench`][art] 将 `AINativeWorkbench` 加到 `AINativeMainScreen`；[宿主探针][arttest]覆盖五个导航按钮、图与绑定。 | 保留图像生成、图转 Mesh、文转 Mesh、模型调整、绑定、产物与发布业务。U12 给当前业务页提供引用；服务和环境仍走设置。 |
| 天枢 | 点 **天枢**，在个人/项目工单间切换，再选列表/依赖图。空板可见“新建需求”。项目身份影响能读的单。 | [`create_daqian_dock`][plan] → `DaqianMainScreen/DaqianWorkspace`；桌面版依赖通过加载校验的天枢 UI 包与 GDScript，失败时页签显示错误。 | U13 迁移入口、工单深链与旧布局，S07 从完整工作台呈现原步骤、阻塞、运行状态、产物，保留原工单定位。 |
| 天璇 | 点 **天璇**，输入部署的 HTTPS 站点或允许的 loopback 开发地址，点“连接”。站点登录后按账号权限使用文曲、需求、工单、多宝等页面。 | [`CreateWebPlatformDock` / `WebPlatformDock::UpdateSurface`][web]，`WebPlatformMainScreen` 的原生浏览区域。Windows MSVC/clang-cl 需 WebView2 运行库和匹配 loader，macOS 使用 WKWebView，headless 只显示外壳。[平台条件][webguide] | 保留站点业务及登录，由天璇承载工单/设计原件，多宝承载代码历史；工作台提供对应对象的原生详情和原件定位。通用引用只覆盖宿主可读的页级信息。 |
| 2D | 点 **2D**，打开有 Node2D 或 Control 的场景，点视口或场景树节点。 | [`CanvasItemEditor::CanvasItemEditor`](../editor/scene/canvas_item_editor_plugin.cpp#L3906)，主屏 `2D`。 | 保留画布编辑；U07 传当前场景和选中节点。 |
| 3D | 点 **3D**，打开含 Node3D 的场景并选节点；工具栏另有“天枢”，见下表。 | [`Node3DEditor::Node3DEditor`](../editor/scene/3d/node_3d_editor_plugin.cpp#L3375)，主屏 `3D`。 | 保留视口、变换和选区；U07 传节点引用，模型与工单关联交 C03/C07。 |
| Script | 点 **Script**，从 FileSystem 双击脚本，选一段文本。 | [`ScriptEditorPlugin::ScriptEditorPlugin`](../editor/script/script_editor_plugin.cpp#L4750)，主屏 `Script`。 | 保留脚本编辑；U08 明示选段、文件和版本。 |
| Game | 在普通启动模式点 **Game**；运行已设置主场景的项目可观察游戏运行视图，嵌入能力取决于平台。 | [`get_game_view_plugin` 的条件注册][node]，[游戏页挂载](../editor/run/game_view_plugin.cpp#L1533)。恢复模式跳过该插件。 | 保留运行和调试，工作台从当前页唤起，U12/V 系列承接可读取的上下文与预览。 |
| Asset Store | 点 **Asset Store**（资源商店），可选择条目查看详情。显示页签取决于非 Web 编辑器、有 TLS、非恢复模式；加载线上条目另需网络。 | [`EditorAssetLibrary` / `AssetLibraryEditorPlugin::is_available`](../editor/asset_library/asset_library_editor_plugin.cpp#L2407)。 | 保留资源浏览与安装。U12 引用当前页面，已落地的项目资源由 U09 引用。 |
| 设置 | 点 **设置**，或从顶部 **AI 配置**直达“对话与 Agent”。宽屏左侧分类、窄屏下拉；另有“运行环境”“个人模型库”“图像与 Mesh”“美术工具”。 | [`UnifiedSettingsEditorPlugin`][settings] → `UnifiedSettingsMainScreen`；`ProjectAIToolbar` 挂 `CONTAINER_TOOLBAR`；`_bind_sources` 借用真实业务控件。插件与马良的[注册处][register]。 | 保留配置入口和原凭据归属。“AI 配置”打开配置；U03 的会话按钮、U04 的快捷键调用 U01。 |

## 同一主屏内的其他 AI 操作

| 表面 | 打开方式与条件 | 挂载与源码 | 去向 |
| --- | --- | --- | --- |
| 会话导航 | AI Chat → 会话 → “+”；右键已有标签选“重命名…”，点标签的叉号出现关闭确认。 | [`AIChatDock`][chat] 的 `AgentsPage/AgentTabs`、`AgentContextMenu`、`AgentRenameDialog`、`AgentCloseConfirmation`。 | U13 保留原会话与草稿定位，U06 把确认后焦点交还发起控件。 |
| 定时器 | AI Chat → 定时器 → 新增任务；选中已有任务可编辑、删除或进入该任务的执行会话。 | [`_build_scheduler_ui`](../editor/docks/ai_chat_scheduler.cpp#L129)，`TimersPage` 下有任务列表和会话宿主，`ScheduledTaskDialog`、`DeleteScheduledTaskConfirmation` 为独立窗口。 | 保留已有任务、频率、启停、执行会话与删除确认。统一工作台承接原会话；业务入口迁移需保留已有配置。 |
| 共工与本地环境 | AI Chat → 共工，查看工单号、需求 ID、框架状态/诊断/校验；点“环境设置”进入统一设置。设置 → 运行环境 → “AI 自动配置本地运行环境”打开配置窗口。 | [`GongGongPanel`][gg] 的 `GongGongPage` 与原生非独占 `GongGongRuntimeSetup`；[设置控件归属][settings]。 | 工单绑定随工作台上下文，宿主诊断、安装及回退仍由运行环境负责。 |
| 工具详情与批准 | 在已有工具结果的会话展开“工作过程”，点“查看此步骤详情”。在隔离用例中，开启本地工具、禁用相应自动批准，触发需人工决定的工具提案，查看预览后可取消。 | [`_show_details`](../editor/docks/ai_chat_dock.cpp#L1903) → `AIToolDetails`；[`_show_confirmation`](../editor/docks/ai_chat_dock.cpp#L3998) 先尝试原工单批准卡，普通确认窗挂到当前独占窗之下。 | U06 保留弹窗上下文、批准范围和原焦点；已绑定工单沿原操作卡回读。 |
| 图片 | AI Chat → 会话 → 添加图片，选择支持的图片后点缩略图；已发送消息的缩略图也可查看。 | [`_choose_images` / `_show_image`](../editor/docks/ai_chat_dock.cpp#L1643)，`AIImagePicker`、`AIImagePreview`。 | 保留附件选择与预览，U06 支持辅助窗，U15 显示发送前引用。 |
| 历史与快照 | AI Chat → 会话 → 修改记录；有该会话已记录的文件修改时，选一轮查看差异、修改前后内容或跳回消息。还原预览另需确认。 | [`_show_snapshot_history`](../editor/docks/ai_chat_dock.cpp#L9201)、`_show_snapshot_changes` 与 `_preview_snapshot_restore`。 | 旧轮次从原会话访问，保留本地快照与还原确认；G 系列另接多宝历史。 |
| 配置、编译与日志 | 会话 → AI 设置/环境设置，或顶部 AI 配置。设置 → 运行环境 → 编译日志；“编译并更新引擎”或就绪候选上的“重启到新版本”可出现确认。 | [`AIChatDock` 的配置及构建按钮](../editor/docks/ai_chat_dock.cpp#L8694)，`EngineBuildApproval`、`EngineBuildLogDialog`；[运行环境页的启动检查](../editor/docks/daqian/startup_checks.gd#L34)。 | 保留编译、更新、登录、状态和模型连接验证的专用工具；通过 U06 取打开窗上下文。 |
| 天枢画布对话 | 连接工作区并核实协作者后，在总览或某工单画布底部输入“询问当前画布，或描述要执行的操作”，可选模型。 | [`canvas_context.gd::build`](../editor/docks/daqian/canvas_context.gd#L34)、[`_send_canvas_message`][work]。随画布范围保存草稿，发送时捕获身份与工单。 | U13 路由到同一入口，保留画布范围、工单、草稿和待处理轮次；C05 固定引用。 |
| 天枢需求、模型与工单对话 | 天枢 → 新建需求打开内联需求表单，可保存草稿；打开有权限的工单 → 工单对话与模型 → 推进对话；“选择司南模型”定位判断节点。 | [`_compose_requirement`、`_open_issue_conversation`、`_mount_conversation`][work]；右侧 `ConversationInspector` 通过 [`mount_daqian_chat`](../editor/docks/ai_chat_dock.cpp#L4863) 借用当前聊天控件。 | 需求讨论与偃师文档接 D 系列；S07 展示实际运行；U13 保留工单和原会话，释放挂载后回到来源。 |
| 天枢工单详情与天璇弹窗 | 在列表/图中打开一单，选流程卡查看详情、需求文档与关联项；详情点“天璇”。需有效外部标识、登录身份和可达的服务，返回数据后才弹出需求/子单等信息。 | [`_open_issue_inspector` / `_show_tianxuan_dialog`][work]，[详情中的“天璇”按钮](../editor/docks/daqian/issue_inspector.gd#L62)。 | 保留原件与关联定位，D/I 系列接原生详情，U06 承接弹窗请求。 |
| 天枢流程工具 | 流程有待确认操作时点“查看待确认操作”看原卡；有澄清问题时点“补充需求”，优先定位内联答复，无法定位时打开“补充工单需求”窗。有图像节点时点“选择图片”。打开可调试工单的“调试记录”看本机记录。 | [`_start_or_view_direct`、`_open_clarification`、`_show_debug_history`][work]、[`operation_details.gd`](../editor/docks/daqian/operation_details.gd)、[图像节点选择器](../editor/docks/daqian/issue_graph.gd#L489)。 | 保留原操作、版本、答复草稿与调试记录；工作台显示对应阶段/工单，弹窗走 U06。 |
| 天枢模型库/工作区连接 | 天枢 → 工作区连接会转到设置 → 运行环境；直接点设置 → 个人模型库，核对身份后访问模型目录。 | [`_open_connection`、`_open_models`][work]；原生宿主设置 `unified_settings=true`，[`_bind_sources`][settings] 嵌入实际控件。独立 `models_dialog.popup_centered()` 走无统一设置的条件分支。 | 保留共享配置与身份复核，避免为每个聊天宿主再建立一套连接。 |
| 3D 天枢右栏 | **3D → 视口工具栏“天枢”**，点按切换右栏。打开已保存 3D 场景并单选节点，再点“关联与内容…”选已回读工单、查看登记资源；“天枢总览”回主屏。 | [`spatial_workbench.gd::build / describe_selection`][spatial]，`Tianshu3DToggle` 挂 `CONTAINER_SPATIAL_EDITOR_MENU`，`Tianshu3DPanel` 挂 `CONTAINER_SPATIAL_EDITOR_SIDE_RIGHT`。 | 保留模型身份、显式关联及产物路径，U07/C07 将当前选区带入工作台。 |
| 3D 内联详情与对话 | 右栏选已回读工单点“工单详情”或“答复 / 推进”；“工单聊天”需要已验证的目标工单，“新任务”可在场景总览发起。点“返回模型工单”退出。未连接时“新任务”给出工作区连接提示。 | [`open_detail / open_response / open_chat`][spatial]；后两类对话操作（工单聊天、新任务）经 `Tianshu3DChatHost` 复用 AI Chat，已被别处挂载时返回提示。详情抽屉中的设计只读。 | 旧聊天按钮按 U13 带场景、节点、目标单转唯一入口；模型选区与现场编辑保留。[3D 回执][spatialtest] |
| 马良的工具窗口 | 在马良的生成节点或绑定页打开本机文件选择；有真实失败的节点时看可复制的失败详情；能力受限的交付可显示复核提示。可用现有探针中的合成失败/能力样例复现后两窗。 | [`AINativeEditorPlugin::_prepare_workbench`][art] 加载版本化脚本；[文件选择、失败和能力提示探针][arttest]。 | 保留业务窗口、产物、服务配置及人工决定，U06/U12 接当前页面或窗的可读上下文。 |

## 编辑器通用表面与工具窗口

这些是未来同一 AI 可以从中唤起的来源。复现以默认布局、普通桌面编辑模式为准。项目自装插件随项目变化，由其真实注册与可见项确定；清单给出可以在原生基线复现的扩展页及动态入口规则。

| 表面 | 实际打开方式与挂载 | 去向 |
| --- | --- | --- |
| Scene / Inspector / FileSystem | 从 2D/3D 打开场景，在 Scene 树点节点后查看 Inspector；在 FileSystem 选资源。三者由 [`EditorNode` 加入 DockManager](../editor/editor_node.cpp#L9439)。 | 保留各 Dock，U07/U09 取节点、属性、文件路径与可读范围。 |
| Import / Signals / Groups / History | 场景编辑布局中选可导入资源看 Import；选节点点 Signals 或 Groups 标签，切 History 看撤销历史。标签是否展开取决于当前布局。[原生 Dock 注册](../editor/editor_node.cpp#L9442) | 保留导入、信号、分组、历史业务。U12 提供无专用选区时的页级引用。 |
| Output / Debugger / Animation | 选择常规编辑主屏，从底部打开 Output、Debugger；在场景树选 AnimationPlayer 激活动画编辑器。见[日志 Dock](../editor/editor_node.cpp#L9477)、[调试器注册](../editor/editor_node.cpp#L9583)、[动画编辑器注册][node]。 | 保留原输出、断点与时间轴。U12 取页面；动画选段/预览由 V 系列承接。 |
| 项目设置、编辑器设置、命令面板 | 选 **Project → Project Settings…**、**Editor → Editor Settings…**；命令面板用 Ctrl+Shift+P（macOS 用 Cmd+Shift+P，均为默认绑定）。[原生命令](../editor/editor_node.cpp#L9231) | U06 在当前窗请求 AI，返回原输入焦点；U04 提供可改绑的工作台命令。 |
| 项目工具弹窗 | **Project → Tools**，分别选 **Orphan Resource Explorer…**（孤立资源）、**Engine Compilation Configuration Editor…**（构建配置）、**Upgrade Project Files…**（升级）、**Clear Project Cache…**（缓存确认）。仅打开即可核对，最后两项在确认前返回。[四个菜单注册](../editor/editor_node.cpp#L8268)，[`_tool_menu_option` 四个窗口](../editor/editor_node.cpp#L4223) | 各窗保留原工具动作；U06 在模态内发起请求并还原焦点。插件的自定义 Tools 项沿同一分发器。 |
| 辅助窗口与扩展页面 | 支持多窗口时，右键可浮动的 Inspector 等 Dock 标签 → **Make Floating**，可见独立窗口；内建扩展页可用“马良”重现。自装插件有自己主屏时启用项目对应插件并选其页签，老式 `has_main_screen` 在兼容构建由原生包装器创建 Dock。[浮动动作](../editor/docks/editor_dock_manager.cpp#L962)，[扩展包装器][main] | U06 跟随实际焦点窗，U12 获取可读的扩展页名；保留浮窗及插件原业务、原布局。 |

## 回读与验收边界

从仓库根运行以下只读命令，可重查核心注册、操作信号和历史回执。源码锚点固定到文首修订解释，后续改动应重新定位调用者和条件。

~~~powershell
git rev-parse HEAD
rg -n 'add_dock\(memnew\(AIChatDock\)\)|add_dock\(create_daqian_dock\(\)\)|add_dock\(CreateWebPlatformDock\(\)\)|add_by_type<(AINativeEditorPlugin|UnifiedSettingsEditorPlugin)>' editor/editor_node.cpp editor/register_editor_types.cpp
rg -n 'CONTAINER_SPATIAL_EDITOR_(MENU|SIDE_RIGHT)|mount_daqian_chat\(chat_host\)' editor/docks/daqian/spatial_workbench.gd
(Get-Content -Raw -Encoding utf8 data-collection/tianxuan-tab-order-1598.json | ConvertFrom-Json).phases | Select-Object phase,initial_selected_key
~~~

基线回读为上列三项直接注册、两项插件注册，3D 的两处加入、两处移除及一次聊天挂载。历史主屏探针返回 initial、legacy_maliang_last、legacy_maliang_selected、pre_daqian_layout、pre_maliang_layout、restart 六阶段；该次二进制 SHA-256 为 `d79677422cf8b360874d9aeb1bb402691625723de1e3bdeb6183f00ce812248a`。[布局探针](../tests/editor/ai_chat_tab_order.gd)，[完整回执][order]。

历史 3D 原生、重开和身份到聊天挂载均已通过，其中未发送外部模型请求。[实测回执][spatialtest]。设置的原生控件与马良独立生成/绑定分别有 [Windows 设置实测](../data-collection/editor-unified-settings-validation-20261107.json)、[马良覆盖范围](../data-collection/maliang-workbench-ui-coverage-20261107.json)。上述历史结果对应各自记录的候选；本次 B01 验证为源码与回执回读。Q01 在实现后按表核对唤起、引用、返回与焦点，Q10/Q11 在各自系统窗口复验。

[node]: ../editor/editor_node.cpp#L9623
[main]: ../editor/editor_main_screen.cpp#L55
[register]: ../editor/register_editor_types.cpp#L235
[chat]: ../editor/docks/ai_chat_dock.cpp#L8229
[gg]: ../editor/docks/gonggong_panel.cpp#L52
[plan]: ../editor/docks/daqian_dock.cpp#L293
[work]: ../editor/docks/daqian/workspace.gd
[spatial]: ../editor/docks/daqian/spatial_workbench.gd
[settings]: ../editor/plugins/unified_settings_editor_plugin.cpp
[art]: ../editor/plugins/ainative_editor_plugin.cpp#L86
[arttest]: ../tests/editor/ainative_builtin.gd
[web]: ../editor/docks/WebPlatformDock.cpp
[webguide]: ../customizations/components/godot-host/web-workbench.md
[order]: ../data-collection/tianxuan-tab-order-1598.json
[spatialtest]: ../data-collection/tianshu-3d-click-integration-819.json
