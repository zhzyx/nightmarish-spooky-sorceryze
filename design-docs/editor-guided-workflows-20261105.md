# Godot 编辑器 AI 多步骤引导、目标注册与完成检测

<!-- gonggong-request:editor-guided-workflows-20261105 -->

## 原始需求与阶段关系

用户要求在 Godot 编辑器内通过对话完成配置、打开界面、界面高亮和点击引导，并明确分两个阶段、两个 Issue 落地。本阶段依赖“Godot 编辑器 AI 语义控制与单目标引导 MVP”，在其结构化命令和单目标高亮闭环上增加可扩展语义目标注册与多步骤引导。

第一阶段为 [Issue #59](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/59)，已由 `e79128a863ecb8c794edba920f437a947885e0df` 合入 main。本阶段关联 [Issue #60](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/60)，从 `ced0368bb2dd2a5d2199c1f3ec46760a3406dead` 隔离实现，适配主线现有 `target` 参数与设置快照写入机制，不重复提交第一阶段代码。用户在本次执行中明确要求“提交然后push”“push到main”；交付对象为源码及回归脚本，Windows 编辑器构建产物仅用于本地验证。

## 范围

- 建立语义目标注册表：目标具有稳定 ID、显示名、原生解析、可见性和可用动作；步骤选择声明式完成观察器。核心编辑器目标由原生代码解析，EditorPlugin 可通过受限接口注册/注销自身 Control 目标。
- 提供按需目标发现与描述：精确 ID 优先；可按关键词搜索；返回目标是否存在、是否可见、所属界面、可执行动作及有限候选，不发送完整 Control 树。
- 实现多步骤引导会话：每步可执行准备动作（打开界面、切换标签、展开、滚动到可见）、高亮目标、展示说明并等待用户或宿主观察器完成。
- 引导状态包括 preview、running、waiting_user、completed、cancelled、failed；支持下一步、上一步、取消、重新定位和“由 AI 执行当前步”。
- 实现用户完成检测：首批观察器覆盖控件按下、选中节点变化、主界面切换、设置值变化和目标失效；只把实际观察到的变化记为完成。
- 引导在窗口缩放、Dock 重排、设置对话框重建和目标暂时不可见后重新解析；超出重试边界时暂停并返回具体恢复动作，不模拟坐标点击。
- 引导状态按编辑器会话有界持久化，重启后只恢复为待用户确认的预览，不自动重放写操作或点击。
- 为 HTTP/OpenAI 与原生 Codex 通道暴露一致的目标发现、开始/推进/取消/查询接口，并补齐工具说明；CodeBuddy 的保留 host action 也传递同一结构化参数。
- 增加注册表、状态机、观察器、重定位、取消、重启恢复和插件注销回归测试；在第一阶段同一 Windows 编辑器候选链路上做增量验证。

## 非目标

- 不进行通用视觉识别、OCR 或坐标级鼠标控制；图像识别仅可作为未来独立降级方案。
- 不操控编辑器外窗口、系统权限弹窗或系统文件选择器。
- 不允许插件注册任意代码执行能力；插件只能发布当前宿主可验证的 Control 目标和声明式观察条件。
- 不把教程完成当作项目功能验收，不替用户决定不可逆、高风险或权限相关操作。
- 不修改共工共同框架、冻结纲领或 GitHub 工单权威状态。

## 安全与兼容约束

- 注册 ID 使用命名空间并拒绝覆盖核心目标；插件卸载或 Control 释放后目标立即失效。
- 每次推进前重新核对目标身份、所属窗口和可见性；对象 ID 不能跨编辑器重启复用。
- 自动执行当前步沿用第一阶段动作权限和确认策略；引导本身不能提升授权。
- 持久化只保存声明式步骤、稳定目标 ID 和进度，不保存对象指针、凭据、原始工具输出或待执行任意脚本。
- 完成检测记录触发条件和实际观察值；超时、取消、目标消失与用户完成必须可区分。
- 写设置的确认绑定旧值与当前步骤版本。等待确认时观察器推进到别的步骤，旧确认返回 `guidance_changed_since_confirmation`，不能写入下一步的值。设置窗口已经打开时，确认对话框嵌套于当前模态窗口，关闭后回到 AI Chat 所有权下。

## 接口与边界

统一入口为 `editor_action`，通过 `action` 选择：

| 动作 | 参数与行为 |
| --- | --- |
| `find_targets` / `describe_target` | `query`、`limit` 或 `target`；精确 ID 优先，候选上限 20，未知目标返回至多 5 个候选 |
| `reveal_target` | 按稳定 `target` 展开祖先 FoldableContainer、切换 TabContainer 并滚动到可见 |
| `start_guidance` | `title`、`steps`；先创建 preview，不执行准备动作 |
| `guidance_start` | 从预览开始，执行当前步骤的非写入 `prepare` 并高亮目标 |
| `guidance_next` / `guidance_previous` | 手动推进或返回；手动推进记录为 `manual_advance`，不冒充观察器完成 |
| `guidance_relocate` / `guidance_execute` | 重新解析当前目标，或执行当前步骤的声明式 `execute`；写操作沿用宿主确认 |
| `guidance_status` / `guidance_cancel` | 查询有界进度或停止计时器、解除观察信号并移除高亮 |

步骤字段为 `target`、`message`、可选 `prepare`、`execute`、`observe`。观察类型为 `manual`、`control_pressed`、`target_visible`、`main_screen`、`selected_node`、`project_setting`。主界面、选择和设置观察器比较开始时的基线；设置数字匹配兼容 JSON 整数经过浮点解析的情况，已有相同值不能误报变化。目标暂时不可见时每 100 ms 重试，超过 5 秒进入 failed 并返回恢复说明。

核心 ID 为 `scene_tree`、`inspector`、`filesystem`、`main_screen_tabs`、`project_settings`、`editor_settings`。插件使用 `AIChatEditorControl.get_singleton().register_target(id, control, display_name, owner_screen)`，ID 必须以 `plugin.` 开头且不能覆盖存活的其他对象；最多 128 个目标。注册表只存 ObjectID，每次使用时重新核对对象与场景树。脚本接口暴露注册、注销、发现、描述和状态查询，不暴露带确认标记的执行器。

每个工作流最多 32 步、步骤 JSON 最多 16 KiB，说明最多 240 字符。持久化路径为项目根解析的 `res://.godot/editor/ai_chat_guidance.json`，只含标题、声明式步骤和当前索引；重启恢复 preview，继续前必须显式 `guidance_start`。切换会话、切换后端或 Stop 会取消；正常退出只保存并暂停，不重放动作。

## 验收标准

- [x] 核心目标可列举、搜索和描述；未知/歧义 ID 返回有限候选，插件目标注册和卸载生命周期正确。
- [x] 一个至少三步的“打开 Project Settings → 定位 Display/Window → 修改或引导修改设置”流程可完整运行。
- [x] 用户手动点击/切换/修改后观察器推进下一步；无实际变化时不误判完成。
- [x] 可上一步、下一步、取消和重新定位；取消后无 Overlay、信号连接、轮询或待执行动作残留。
- [x] Dock 重排、窗口缩放、目标暂时隐藏及对话框重建后能重新定位，不能恢复时进入明确失败/暂停状态。
- [x] 编辑器重启后引导只恢复预览，用户确认后继续；任何写操作均不自动重放。
- [x] HTTP/OpenAI 与原生 Codex 两条通道的引导接口行为一致；工具权限和仅咨询边界保持不变。
- [x] 受影响单元/场景测试、格式检查和 Windows 增量编辑器构建通过；第一阶段回归保持通过。

## 验证记录（2026-11-05）

- `python -X utf8 tests/editor/run_ai_chat_semantic.py --godot bin/godot.windows.editor.x86_64.guidance60.console.exe --guidance` 已通过真实编辑器双进程场景：目标搜索/描述、有限未知候选、插件注册/注销/释放、按钮/主界面/选中节点/设置观察器、三步设置引导、拒绝写入、确认写入、过期确认拒绝、隐藏重试与超时恢复、跨窗口重排及尺寸跟随、目标重建、取消清理、重启仅恢复预览。
- 同一候选上不带额外参数的 `run_ai_chat_semantic.py` 第一阶段回归已通过，覆盖写入/清除、保存失败不改变内存、路径限制、高亮、拒绝确认、仅咨询与禁用权限。
- 原生 Codex 使用 `run_ai_chat_semantic.py --guidance --codex` 已通过同套引导与双进程恢复场景，离线子进程走实际桥接协议，业务调用未降级到 HTTP；`--interfaces` 与 `--bounds --codex` 也已分别通过核心界面和有界状态回归。最终结果见 `data-collection/issue60-candidate-validation-20261105.json`。
- `node --test tests/editor/test_codebuddy_bridge.js tests/editor/test_codebuddy_acp.js` 43 项、保留 host action 的 terminal 检查 3 项、`test_codex_bridge.js` 9 项通过；结构化参数和数组/尾随 shell 操作符拒绝边界已覆盖。
- `python -m SCons platform=windows target=editor extra_suffix=guidance60 -j12` 完成 Windows x86_64 MSVC 构建与链接；受影响 C++ clang-format、Python 编译、Node 语法及 `git diff --check` 通过。源码输入与构建产物摘要记录在同一候选证据中。

场景使用临时项目、隔离工单 fixture 和本地模拟模型响应；没有调用真实模型服务。高亮重排与窗口测试为无界面编辑器中的几何/生命周期断言，未进行人工桌面点击验收。脚本退出存在 RID/ObjectDB 清理警告；第一阶段故意触发只读保存失败的用例还输出 safe-save 与既有警告对话框日志，断言仍验证失败不改内存与后续工具可继续。不把这些日志声明为无错误退出。

## 依赖、执行范围与停止条件

硬依赖为第一阶段 Issue 的结构化动作、状态查询和单目标 Overlay 已通过验收。产物限定为 AI Chat 编辑器控制模块、受限目标注册接口、引导状态持久化和 `tests/editor/` 回归；目标平台仍为当前 Windows x86_64 MSVC 编辑器。完成上述验收后停止，不扩展视觉识别、系统级自动化或其他平台发布。

