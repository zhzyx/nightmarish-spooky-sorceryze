# 复杂控件的受控语义接口

来源：[父需求 #386](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/386) 与目标接口 #388，沿用户原授权继续，不需要新增模型或工具授权。基线为首批基础接口交付候选；生产前回读实际 main 与工单占用。

范围：F02/F03 尚未覆盖的 PopupMenu 原生 Window 实例、Curve/Gradient 资源编辑器、GraphEdit 节点/端口/连线，以及 Tree/ItemList 激活和上下文业务动作。优先语义命令，不以任意坐标/键盘模拟绕过控件及认证边界。为条目、端口和连接提供分页/值/实例/旧状态/容量说明。密码、exclude、编辑场景自动控件排除和 AI Chat page_only 保持；执行仍走原 tools/consultation/host confirmation/session/Bearer/busy 链路。

验收：macOS arm64 headless 编译、原生拒绝路径与真实隔离编辑器命令往返；延迟弹窗可发现，修改前预览且变化后拒绝。不能把信号发出当成业务已完成，GraphEdit 操作需业务状态回读。容量边界明确，不无差别提高原上限。独立审查、正式门禁及精确 CI/main 回读。像素/IME/原生认证窗口单列，禁止操作用户桌面。

责任：本 Codex 接续至实现、验收及 main；依赖首批基础接口实际接收，不抢占其他工作树。未实现项不计为首批完成。

## 第一冻结版实现记录（第二版在后文覆盖）

本地可逆实现按根协调从已独立验收的首批候选 `92eb1f193a050bb71c241f350d01b634ac093662` 开始，未将候选当作主线交付。收到 PR421 的真实 main 接收回执后，工作树快进到 `208e6cc8fcd7072084ad2a6151a19083ab3aff4e` 再编译和验收；提交、推送与最终验收仍由根整合，不在本工作树执行。

- Registry 保留原 Control API，增补 `resolve_node()` 发现 PopupMenu 原生 Window；复杂编辑器可作为自身页面入册，继续剪除 exclude、secret、page_only 后代及正在编辑的场景子树。节点/目标/条目上限维持 50000/8192/4096，条目页仍最多100项/8192字节。Graph节点摘要每方向最多100端口并明确 `ports_truncated`；`read_graph_ports(value={node,direction},limit,offset)` 提供独立端口分页（4096容量），动作端口上限仍100。
- 复用描述入口为 `AIChatEditorRegistry::describe_node(Node *, id, owner_screen)`；内部统一 `is_protected()` 祖先拒绝检查。自动目标 `describe(id)` 也使用该入口，不新增工具权限。core/显式别名详情的接线不属于本次改动。
- 菜单：`read_menu_items(limit,offset)`、`activate_menu_item(index)`；原生 `activate_item` 使用菜单 ID 到达已有业务处理器。预览须可见；host确认对话框会原生隐藏菜单，因此批准阶段允许同一实例已隐藏，但仍匹配完整条目指纹与场景/选择/撤销上下文。指纹含 id、完整文本hash、禁用、checkable/radio/checked、submenu、accelerator、shortcut与多态、metadata身份hash。元数据不对外返回，Object身份不调用脚本字符串转换；递归/容量超限拒绝激活。
- 曲线：`read_curve`、`curve_preset(value=0..4)`，调用实际 CurveEdit 的原生预设处理链。渐变：`read_gradient`、`gradient_add_point(value=[offset,r,g,b,a])`、`gradient_remove_point(index)`、`gradient_set_color(index,value=[r,g,b,a])`、`gradient_reverse`，调用 GradientEdit 原生方法。修改在不合并的原生 EditorUndoRedo 事务中执行，避免原生 MERGE_ENDS 吸收此前用户操作；`undo_resource_edit` 只撤销本适配器最后一次、资源/控件实例、完整资源状态及历史version均一致的操作。资源实例对外以十进制字符串编码，避免高位RefCounted ObjectID经过JSON失真；Node身份使用有限精确整数，旧值统一经JSON数值规范化比较。
- Graph：`read_graph_nodes` 读节点身份、位置、端口方向/索引/类型/slot；`read_graph_connections` 读连线。`graph_connect`/`graph_disconnect(value={from,from_port,to,to_port})` 只发出固定原生业务请求；不直接伪造GraphEdit连线。`graph_move_node(value={node,position:[x,y]})` 走原生 begin/set_drag/position_offset/dragged/end链，每个可触发同步回调的阶段后重取ObjectID并检查父子关系和保护边界。失效立即停止后续调用并回报halted。每次返回可观察UI状态hash及后续可分页读回的状态，不把UI变化当业务模型完成。
- Tree/ItemList：`activate_tree_item`/`activate_item`、`tree_context_menu`/`item_context_menu(index)` 设置原生当前条目后，只构造固定 `ui_accept`/`ui_menu` 事件直接进入控件原生处理，不控制用户桌面。上下文动作要求控件已允许右键选择。无任意signal名、方法名、脚本、坐标或按键输入接口。

菜单、图及列表请求一律 `requested:true, business_completed:false`，可用 `readback/state_changed/target_available` 与后续读回核对；命令路由的 completed 仍只表示命令处理终态。Curve/Gradient只有原生资源实际改变且回读成功才 `business_completed:true`。原 tools/consultation/host确认、Bearer/session/busy、preview旧值与实例边界不改。

第一版当时未实现（Curve、Gradient偏移和子菜单随后已在第二版补齐）：Curve任意单点/切线编辑（原生入口私有，且依赖拖拽初态）；Gradient单点offset移动（公开方法依赖私有 `pre_grab_index/pre_grab_offset`，直接调用会错误撤销）；原生子菜单悬停展开；Graph业务数据类型的通用完成判定、超100端口的连接动作；真实像素/IME/原生认证窗口。上述项不以信号发送、计划或现有测试代替验收。

## 第一冻结版本地验证（2026-11-07，macOS arm64）

基线为真实 main `208e6cc8fcd7072084ad2a6151a19083ab3aff4e`，下列测试运行本工单未提交的本地实现。编译命令：

```text
/Users/kevinxue/.local/venvs/godot-build312/bin/python -m SCons platform=macos target=editor arch=arm64 dev_build=no debug_symbols=no vulkan=no accesskit=no tests=yes -j4
bin/godot.macos.editor.arm64 --headless --test --test-case='*[Complex]*'
bin/godot.macos.editor.arm64 --headless --test --test-case='*[Complex]*,*[AIChat]*Registry*'
/Users/kevinxue/.local/venvs/godot-build312/bin/python tests/editor/run_editor_complex_controls.py --godot bin/godot.macos.editor.arm64 --report /tmp/407-complex-report.json
/Users/kevinxue/.local/venvs/godot-build312/bin/python tests/editor/run_editor_capability_routing.py --godot bin/godot.macos.editor.arm64
```

结果：编译退出0；独立Complex原生测试7例45断言通过，组合Registry回归16例240断言通过；真实headless编辑器经 `copy_editor` 复制二进制、独立editor_data/项目后通过HTTP与host确认往返，报告 `EDITOR_COMPLEX_CONTROLS_HTTP_OK`、7组检查通过、退出0。原有能力路由HTTP/CLI回归 `EDITOR_CAPABILITY_ROUTING_HTTP_CLI_OK`、退出0。

实际检查包含：Popup原生ID激活、延迟创建、实例替换、文本/metadata/全局选择上下文变化后拒绝；分页容量；Graph端口分页与原生异步owner对业务model及连线的连接/断开读回、dragged对model位置读回；Tree/ItemList的原生激活及上下文处理器；真实Inspector Curve常量预设、UndoRedo恢复与重建控件后的资源绑定；Gradient新增/删除/重着色/反转及对应UndoRedo、连续颜色修改不吞前次编辑、无关原生历史变更后拒绝撤销、资源旧值变动拒绝；资源高位ObjectID经JSON字符串往返；工具许可及consultation拒绝。原生测试另覆盖同步begin_node_move回调删除Graph后的停止，及统一描述入口的secret/page_only祖先拒绝。Curve其余预设枚举虽走同一原生入口，本次未逐一实测。

本机证据：`/tmp/407-build.log`、`/tmp/407-native-complex.log`、`/tmp/407-native.log`、`/tmp/407-complex-report.json`、`/tmp/407-complex-report.editor.log`、`/tmp/407-capability-regression.log`。组合原生回归仍有原Registry的缺EditorSettings主题诊断；独立Complex范围无该诊断。两个真实编辑器runner均有退出时RID/ObjectDB泄漏诊断，未把退出0等同于无警告。扩展fixture曾将编辑器GraphNode留在全局EditorSelection后取消Inspector导致退出崩溃；最终先清空该测试选择再取消资源检查及释放fixture，保留正常Inspector取消选择场景，复验退出0。未单独认定该人工选择清理问题为生产缺陷根因。

静态检查：copyright_headers、validate_includes、clang-format 22.1.5（dry-run/Werror）、header_guards（仅.h）、ruff 0.17.1 check/format、mypy 2.4.0 --follow-imports=silent、git diff --check均通过。未提交、未推送；独立审查、整合集成与业务最终验收由根继续，以上产物不冒充工单整体验收。

## 第二冻结版范围明确（继续原 #407）

真实Issue407正文“执行中范围明确”已由根更新并由本工作树回读：原F02完整菜单语义允许本隔离树 `scene/gui/popup_menu.h/.cpp` 增加窄C++子菜单展开包装，复用私有原生状态机；不注册通用ClassDB执行接口、不改外部引擎。继续原407占用补齐Curve点/切线/mode、Gradient offset及受绑定Undo/Redo；首版证据保留在 `/tmp/407-freeze1/`，不以首版预设代替整单完成。后续验证单独使用 `/tmp/407-v2-*`，尚未冻结的结果不得混作通过证据。

第二版当前实现：

| 固定命令 | 参数与原生路径 |
| --- | --- |
| `curve_add_point` | `value=[offset,y]`；Curve公开API在纯原生副本计算排序及自动切线，保留完整数据快照。 |
| `curve_remove_point` | `index`；保存完整原生点数组，支持恢复删除点及邻点切线。 |
| `curve_set_point` | `index,value=[offset,y]`；允许跨点排序，拒绝重复/近重复offset。 |
| `curve_set_tangents` | `index,value=[left,right]`；两侧须为free模式，有限切线范围±1000000。 |
| `curve_set_tangent_modes` | `index,value=[left_mode,right_mode]`；0=free、1=linear，调用原生mode及自动切线处理。 |
| `gradient_set_offset` | `index,value=offset`，范围[0,1]；拒绝重复/歧义排序，分别绑定排序前后index，保留颜色与点身份。 |
| `undo_resource_edit` / `redo_resource_edit` | 仅本适配器最近一条资源记录，绑定资源实例、完整before/after、history实例/version及单调epoch。当前控件实例每轮重新预览确认；Inspector重建控件不丢失同资源记录。 |
| `open_menu_submenu` | `index`；短生命exclude job挂实际SceneTree根，只弱绑父子ObjectID。host确认焦点/延迟hide结束后分两阶段重验旧态与保护，再调用窄C++ `PopupMenu::open_submenu`，进入既有 `_activate_submenu`。 |

Curve坐标须在资源domain/value范围，输入及派生切线结果须finite；已有点必须严格有序，点容量仍4096。新Curve点操作用未注册的原生RefCounted receiver上的typed callable进入EditorUndoRedo，避免无ObjectID的static callable被原生history跳过；全数组do/undo保留邻点自动切线。Gradient偏移用同类typed receiver调用原生setter，写后回读排序后的完整offset/color数组；不匹配不得标业务完成或登记可误撤记录。读写曲线/渐变在动作入口拒绝attached script、GDExtension及extension placeholder；typed receiver执行时再次拒绝，脚本方法不能覆盖固定原生数据操作。

版本数字不是history身份：原生Undo会减小version，分支新动作可复用同值。资源fence订阅实际UndoRedo.version_changed，并在own Undo/Redo后更新记录；外部历史事件使旧记录失效。菜单fence同时订阅manager.history_changed/version_changed及原生Undo实际会选择的global、remote、当前scene histories的version_changed。菜单快照含各history版本、scene history ID、单调epoch与observer实例身份；普通同名全局资源动作即使复用version、保持菜单外观/场景/选择不变也拒绝旧确认。observer由原生manager metadata强持有，函数static仅保存弱ObjectID；资源fence为Registry实例成员，不存在static Ref容器跨ObjectDB teardown析构。

菜单job在popup/open_submenu同步业务回调后核对自身ObjectID存活，再访问成员；每阶段核对原父/子实例、子菜单绑定、完整旧态、scene/selection/history上下文及exclude/page_only祖先。`submenu_request_status`固定为queued/opened/stale/not_visible（未请求为idle），由describe_target回读；opened只表示native展开当时成功，当前显示以子窗口描述的visible为准。命令本身始终requested/business_completed=false，不把异步提交或信号发出当完成，不修改全局路由completed契约。

第二版的当前限制：连接动作端口上限100（端口读取独立分页4096）；Graph通用业务完成判定仍为requested，需回读实际owner业务数据；真实GDExtension/placeholder动态库实例未装载实测，拒绝分支由原生ClassDB/placeholder检查覆盖。像素、IME、macOS原生系统菜单实际焦点及认证窗口不计入headless验收，未操作用户桌面。

### 第二冻结版实际验证（2026-11-07，本地候选，未提交）

基线为真实main `208e6cc8fcd7072084ad2a6151a19083ab3aff4e`。本版另补Tree/ItemList新业务动作的条目metadata身份：仅输出有界安全指纹，绑定对象身份用十进制字符串，无法完整指纹的选中条目拒绝执行。相同控件/行/文本但metadata路径漂移必须重新确认；不改变旧read_items/select接口。

最终精确命令（工作目录为本隔离树）：

```sh
/Users/kevinxue/.local/venvs/godot-build312/bin/python -m SCons platform=macos target=editor arch=arm64 dev_build=no debug_symbols=no vulkan=no accesskit=no tests=yes -j4
bin/godot.macos.editor.arm64 --headless --test --test-case='*[Complex]*,*[AIChat]*Registry*'
/Users/kevinxue/.local/venvs/godot-build312/bin/python tests/editor/run_editor_complex_controls.py --godot bin/godot.macos.editor.arm64 --report /tmp/407-v2-complex-report.json
/Users/kevinxue/.local/venvs/godot-build312/bin/python tests/editor/run_editor_complex_controls.py --godot bin/godot.macos.editor.arm64 --case resources --report /tmp/407-v2-resources-report.json
/Users/kevinxue/.local/venvs/godot-build312/bin/python tests/editor/run_editor_complex_controls.py --godot bin/godot.macos.editor.arm64 --case native_graph --report /tmp/407-v2-native-graph-report.json
/Users/kevinxue/.local/venvs/godot-build312/bin/python tests/editor/run_editor_capability_routing.py --godot bin/godot.macos.editor.arm64
```

第二版完整HTTP检查11组，资源子集5组，真实C++ VisualShader owner子集2组通过。组合原生18例257断言通过（包含最后追加的Tree/ItemList metadata-only旧态拒绝）；旧能力路由HTTP/CLI回归通过。runner全部使用已交付copy_editor独立二进制及私有editor_data/临时项目，报告只在被测编辑器退出0后写ok。Curve点数据与Gradient排序前后offset/color完整数组逐次验证do/undo/redo；真正native history直接undo并同version复用分支会拒绝旧资源记录；普通同名全局资源历史直接undo/复用也拒绝旧菜单确认。Popup原生展开、正常同步关闭父菜单及about_to_popup替换子窗口分别回读opened/not_visible/stale；业务动作回调后自身和目标生命周期均实际验证退出0。Graph另由内置C++ VisualShader owner对真实VisualShader资源完成连接、断开及位置读回，适配器仍诚实返回requested而非通用业务完成。

证据位于 `/tmp/407-v2-build.log`、`/tmp/407-v2-native.log`、`/tmp/407-v2-run.log`、`/tmp/407-v2-complex-report.json`及对应`.editor.log`、`/tmp/407-v2-resources-report.json`、`/tmp/407-v2-resources-run.log`、`/tmp/407-v2-native-graph-report.json`、`/tmp/407-v2-capability-regression.log`。资源/Graph单独子集在最后仅涉及Tree/ItemList条目绑定的修正前通过，最终完整11组包含其全部相同业务断言；原生组合和完整HTTP在最终源上重跑。仍有首版已记录的退出RID/ObjectDB诊断及组合原Registry主题诊断；未声称无警告。旧冻结证据保留于`/tmp/407-freeze1/`，不以第二版覆盖首版结论。

静态检查沿用copyright→validate_includes→clang-format 22.1.5顺序，header_guards只检查.h；ruff0.17.1 format/check、mypy2.4.0及git diff --check通过。最终接线建议：`AIChatEditorRegistry::describe_node(Node *, const String &, const String &)`供core/explicit别名共享保护及含值描述，`resolve_node`仅扩展Node/Window兼容，旧`resolve`保持Control契约。没有修改dock或主模型刷新，也未修改全局命令completed路由契约。发布、整合和独立审查继续由根负责，本地测试产物不等于整单业务最终验收。

## 最终整合接线

#388 F05核心/插件显式别名与自动目标共享describe_node及同一祖先保护、文本预算；PopupMenu原生Window补位置/大小/焦点/可用原因，状态元数据类型检查后读取。4项AliasMetadata原生测试与20组command runner验证接线；本段结果以最终组合公开JSON为准。407独立冻结版本已由另一工作者实际通过11组HTTP业务及18例257断言，binary SHA349168bc568a8a10fe2dd93ff9003f9f61e34c63ea0a3854a4ba8ee6e55178e5，不能替代最终组合复验。
