# 完整场景、资源与信号业务接口

来源：[父需求 #386](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/386) F10。用户原授权继续有效。首批只有受限的内置、非脚本/继承/实例场景及叶节点删除/移动，不能把它声称为完整场景能力。

范围：完善非叶子节点增删/移动、脚本/继承/实例场景的原生编辑规则；资源赋值、信号连接及导入/导出业务动作；明确可支持的 Variant/资源类型。复用宿主原生 UndoRedo、引用重写和保存/导入/运行状态，不新增任意脚本调用或修改模型授权设置。所有写操作具有可审阅提案、目标实例/旧值/版本绑定和实际宿主确认。父子归属、owner、动画轨道、NodePath 与撤销均需真实回读，拒绝不能安全验证的作用域并给出原因。

验收：macOS arm64 headless 隔离场景，包含子树、资源、信号、动画与属性冲突案例，真实 EditorSettings 摘要不变；导入导出仅临时项目内并保留文件摘要。脚本副作用/外部路径等边界不能通过通用执行接口绕过审批。编译、独立审查、正式门禁与精确候选 CI/main 回读。视觉、原生文件/退出窗口和外部认证仍单列未知，不控制用户桌面。

依赖与责任：首批基础候选实际合入后由本 Codex 继续；遵循真实工单占用和准入，保留其他工作树与运行进程。首批及本单分别计证据，未完不关闭父单。

## 2026-11-07 隔离实现记录（#408）

责任者 kaiyunxue；授权引用 `codex:user-delegation:01a1b41f-8907-7f92-a860-1ba585079f4f`。按根任务接单先完成真实 Issue intake-only（tenant `gonggong-workspace`）。执行顺序由根调整为：以独立验收后的首批精确候选 `92eb1f193a050bb71c241f350d01b634ac093662` / signed `d7693851626f2e1952789ae52a6c14c791060466` 在隔离工作树进行可逆本地实现，首批 main 接收仍是集成交付硬前置；未把首批候选当成 main。随后根提供 PR #421 的真实接收回执（2026-11-07T08:33:34Z，merge `208e6cc8fcd7072084ad2a6151a19083ab3aff4e`），本树快进该真实 main 后重建复验。此工作者不提交、不推送，由根组织独立审查与正式集成交付。

实现仍从现有 `AIChatEditorSceneActions::perform` 入口进入，工具、consultation、Bearer/session、宿主 busy 和实际批准由原宿主负责。新增动作均返回 `manual_confirmation_required=true`，包括开启 auto execution 时也需要原生批准。无任意 call、脚本执行、命令或修改权限设置入口。根负责 control/schema 接线，本单不改其文件。

- 子树删除/改名/重挂继续使用 `SceneTreeDock::fill_path_renames/perform_node_renames`，与结构变更放入同一原生 UndoRedo。保存并逐个恢复每个后代的真实 owner，而非将实例内部 owner 改成当前根；撤销恢复原父节点和顺序。局部重挂保持本地 transform（现有动作语义）。
- 使用原生编辑规则：继承来的节点禁止结构调整；本地新增节点和实例根可结构调整。实例内部节点需启用 Editable Children 才能覆盖固定原生属性，不允许删除/重挂其内部结构。附着脚本不再导致整场景拒绝；预览用 ClassDB 原生属性元信息与 `get_native`，应用和撤销用未注册、不可由工具调用的固定 native setter。脚本属性、扩展类和内部节点不在此入口开放。
- 快照绑定根与目标实例、父/owner/索引、选择、UndoRedo版本、实例可编辑状态、脚本/继承/实例文件 SHA-256。RefCounted 身份使用十进制字符串以免 JSON 数字损失精度。仍保留100节点、16 KiB整体/12 KiB节点快照容量限制。
- `scene_assign_resource(target,property,resource_path)`：固定支持 Sprite2D/TextureRect.texture、Line2D.gradient、GeometryInstance3D.material_override、MeshInstance3D.mesh。输入为已原生导入的 png/jpg/jpeg/webp，或无外部/子资源/脚本的自包含原生 `.tres`（Gradient、Curve、StandardMaterial3D、ORMMaterial3D、BoxMesh、SphereMesh、StyleBoxFlat）；最终资源还需符合属性类型。无JSON到Resource/Callable通用转换。预览只读文件及导入元数据/产物哈希，批准后才 ResourceLoader 加载。加载后重新解析目标 ObjectID，并重建原提案比较全部旧状态/版本/输入哈希；loader 删除/替换节点或改旧值时拒绝创建事务。
- `scene_connect_signal/scene_disconnect_signal(target,signal,receiver,method)`：同场景真实信号和已存在方法，持久连接，不调用方法，不接受bind/callable代码。禁止断开继承或非持久连接；原生 UndoRedo 恢复连接及原 flags。
- `scene_import_resource(resource_path)`：仅项目内 png/jpg/jpeg/webp；原生 `EditorFileSystem::reimport_files` 后 `scan_changes`，读回真实 import_valid、importing 和 `.import` 哈希。失败/仍进行中不报告成功。
- `scene_export_resource(target,property,destination)`：固定原生资源属性另存 `.tres`，不称为项目导出。`project_export(preset,format,debug,destination)` 复用既有 preset/platform（不改preset），format 为 project/pack/zip，运行原生 export_project/export_pack/export_zip。绑定 preset实例、配置/过滤器/选中文件摘要、export_presets.cfg、输入树及既有输出摘要；项目树最多2000条目/256 MiB/32层。目标只允许无符号链接的 `res://` 项目内既有父目录；不下载模板，不读取/修改宿主认证数据。需外部凭据的加密/签名配置、外部自定义模板明确拒绝。原生导入和文件导出不是 UndoRedo 动作，提案显式标注 `undoable=false`；资源赋值、信号和节点编辑可撤销。

验收程序：`tests/editor/run_editor_scene_completion.py` + `editor_scene_completion.gd`；通过 `copy_editor` 创建独立可执行副本/EditorSettings/临时项目，通过真实HTTP会话和原生批准信号执行，命令回执位于项目外，避免污染导出输入摘要。无桌面或全局设置控制。实际包含子树与实例 owner、RemoteTransform2D NodePath、Animation轨道、脚本/继承/实例、资源、信号、Undo/Redo、旧值/输入hash过期，以及批准后自定义loader删除/替换/修改旧值案例。测试用loader仅存在于隔离验收脚本，未暴露生产绕过。

截至本地首轮实际main验收，13组检查通过，包含项目PCK真实产物与哈希、原生重导入有效性；真实 EditorSettings 摘要前后均为 `6eec2d16db85fec5fac37ffef6e2c8eda9c405ec9a63706d1dc1db3acab5a490`。应用导出因隔离环境缺少模板真实返回 `project_export_unavailable` / missing_templates；不能据此声称平台应用导出成功。PNG/JPEG/WebP资源加载、各白名单资源类型、ZIP和真实平台应用的完整组合未逐一实测，保留为组合覆盖缺口；视觉/原生文件退出窗口/外部认证仍为未知。最终候选编译、静态和复验结果由根结合实际报告接收，未以本地代码产出代替整体验收。

最终本地复验：真实 main `208e6cc8f` + 本单未提交改动，macOS arm64 `platform=macos target=editor arch=arm64 dev_build=no debug_symbols=no vulkan=no accesskit=no tests=yes -j4` 增量构建成功（11.48s）。隔离 native SceneActions 单测 6/6、87/87断言成功；上述13组实际业务验收全通过，新增 NodePath 引用移动/删除/撤销与信号目标调用次数保持0也通过。精确编辑器 SHA-256 `a0f9585d8edde9f06248c7b9bf95774408da4a8aff8e25fe70d2c707626fcf29`；该轮项目 PCK SHA-256 `2b47143e30177ee5b40675771a5e2d6fbfb8a6f7a706c432bdce0ff7d4cab0b1`；真实EditorSettings摘要仍与前述一致。报告保留为宿主临时证据 `scene408-final-acceptance.json`、`scene408-unit.log`、`scene408-final-build.log`，由根接收而非当作main/CI回执。

限定本单文件的 copyright/header guard/include/file format/clang-format 22.1.5、ruff 0.17.1、mypy 2.4.0、git diff --check 全部通过。headless编辑器脚本退出仍记录195 ObjectDB实例、3 resources及若干RID的teardown泄漏诊断；无SCRIPT ERROR，进程返回0、业务断言及结果读回均通过。该退出诊断尚未归因，单列限制，不据业务通过推断编辑器退出无资源泄漏。应用格式导出仅实测缺模板拒绝；不将PCK成功替代平台应用成功。

## 2026-11-07 独立复核后的正确性修复（#408，本地待接收）

基线仍为真实 main `208e6cc8fcd7072084ad2a6151a19083ab3aff4e`，在独立修复副本完成；未提交、推送或修改原工作副本、AIChatDock/control、模型授权、真实 EditorSettings 或用户桌面。先前13组通过只能证明原覆盖，独立复核指出的三个缺陷不得因旧报告通过而视为解决。

1. 结构、owner、信号与selection的UndoRedo操作改为未注册的私有RefCounted receiver，UndoRedo强引用保活，do/undo/redo均重解析ObjectID后调用固定C++原生成员，不再向附脚本节点发送`set_name/reparent/add_child/remove_child/move_child/set_owner/connect/disconnect`字符串方法。提交后读回实际结构/连接/属性结果。`SceneTreeDock::perform_node_renames`为本动作新增native-only分支，NodePath使用原生属性receiver，Animation使用固定C++成员callable；普通编辑器调用维持既有默认分支。自然原生通知仍可能执行正常tool脚本，不把通知禁用当作修复。
2. 项目导出摘要补入`.import`所有原生remap输入（含feature分支）、`.godot/imported`、原生customization的`.godot/exported`缓存、global class/extension/UID缓存及EditorFileSystem实际UID；总量仍受2000条目、256MiB、32层约束，拒绝路径链接和项目外资源依赖。`.godot/editor`回执和无关shader缓存不参与摘要。PCK/ZIP完成后再次校验稳定source/import/template摘要，原生exported缓存生成属于输出，不由该后校验自失效。脚本/扩展export plugin不能形成可审阅的固定输入闭包，明确拒绝；GDExtension库及dependencies配置不允许逃出项目。
3. 应用模板仅只读绑定，不改全局模板。PC使用原生`get_template_file_name`和与`find_export_template`相同的EditorPaths版本目录解析，macOS绑定`macos.zip`，并绑定PC wrapper/debugsymbols候选以及text-server support data。绝对路径只进入本地hash计算，不返给模型。项目内显式custom template仍可绑定。其他应用平台目前返回`unsupported_platform_template_snapshot`；这不是“缺模板”。本地PC应用仍仅能实测原生缺模板拒绝，未据PCK成功宣称应用导出成功。
4. 资源旧值、已缓存输入与另存对象改为封闭原生资源图内容快照，不以edited_version代替内容。通过ClassDB固定storage元信息及`get_native`读取字段，原子Variant以原生二进制hex编码保留精确类型/数值；数组、字典、子资源、metadata、十进制字符串身份均递归绑定。拒绝脚本/扩展/非资源对象、资源循环、超12层/1024项/8KiB原子负载/12KiB资源JSON，packed数组最多256项。封闭候选类为Gradient、Curve、StandardMaterial3D、ORMMaterial3D、BoxMesh、SphereMesh、StyleBoxFlat；若某字段不能纯native快照，则明确拒绝，不降级通用getter。CompressedTexture2D仅在固定native像素读回成功且宽高<=4096/像素数据<=64MiB时支持赋值旧值快照；不能读回时拒绝，不用文件hash冒充内存内容。纹理另存仍不支持。另存直接使用原生ResourceFormatSaverText，排除自定义saver；加载后保持root/target重解析与完整状态复验，保存前后/赋值提交后重验内容。
5. UndoRedo version可由undo后新分支复用。新增私有RefCounted观察者监听原生`version_changed`，绑定history身份及单调epoch；二者均用十进制字符串。观察集合清理销毁history并受128条容量限制，不能建立观察时拒绝动作。原version只保留为辅助状态。

新增验收覆盖附脚本同名原生方法计数保持0的改名、增删、重挂、owner、连接/断开及Undo/Redo；Gradient set_colors保持edited_version不变而内容快照变化，旧另存/赋值批准拒绝、重新预览正常保存；嵌套脚本资源、资源循环和容量拒绝；导入ctex/global class cache变化拒绝旧PCK批准，重新预览正常导出，无关editor回执不使批准失效；历史版本复用但值不变时旧批准拒绝。最终构建、native与业务回执见`data-collection/receipts/scene408-fixes-*`。这些为本地验证证据，仍需根接收、独立复核及正式精确候选交付，不当作main/CI/业务验收结束。

本轮最终本地证据：`scene408-fixes-summary.json`记录19组业务验收、7组native/96断言、全部上述静态检查通过，业务runner与隔离native均返回0。精确编辑器SHA-256为`68063f6f9c1b45ebf92339313b70ebad6d40e53b56a094fa64d96b5f60254cf7`；真实EditorSettings前后仍为`6eec2d16db85fec5fac37ffef6e2c8eda9c405ec9a63706d1dc1db3acab5a490`。history观察者由history原生metadata强持有，静态表只保存弱ObjectID，避免退出时晚于ObjectDB销毁RefCounted；observer自身身份也入摘要，防观察者重建重置epoch。添加该观察者的中间轮曾在19组断言后退出非0；更改其生存期后同一套19组及退出码均通过，未隐藏中间故障。原RID/ObjectDB/3 resources退出泄漏诊断仍在最终log中，未归因且未据返回0宣称无泄漏。未逐一验证所有封闭资源候选类/图形像素读回/PNG-JPEG-WebP赋值组合、ZIP、既有真实模板的各平台应用导出、脚本自定义NodePath字段、视觉原生窗口与外部认证；保持明确覆盖缺口。

### 独立复核后第二轮三个窄缺口

旧冻结二进制用普通`@export var path: NodePath`复现：移动Branch后，原生RemoteTransform及Animation正确指向`Destination/Branch/Leaf`，脚本字段仍为`../Branch/Leaf`，旧动作却返回成功；完整复现报告保留在`data-collection/receipts/scene408-gap-probe.json`，其中同时保留原19组通过结果。当前实现不声称能纯native安全维护脚本字段：结构改名/删除/重挂前，只通过原生Script声明元信息检查整个100节点作用域；发现存储NodePath、Array、Dictionary、Object或未限定Variant字段时，明确返回`unsafe_script_reference_scope`，不读写脚本值或自定义getter/setter，不创建事务。脚本声明列表最多256项；脚本资源本身须为非脚本附着、非扩展/placeholder的CORE原生实现。普通只含标量字段的附脚本场景保留结构编辑能力，既有同名原生方法回归继续适用。此限制有意保守：即使某数组当前不含NodePath，也不会猜测其内容而绕过getter边界。

`run_project/run_scene`此前独立分支确实只绑定数值scene_version，现同样绑定共享history_state的history/observer身份及单调epoch。新增正常no-op history事务undo后另建分支、复用相同version/相同场景值的实测，旧run_project和run_scene批准均须拒绝，且没有启动运行进程。

所有相关pure-native资源/脚本/节点检查明确追加`ClassDB::is_gdextension`及`is_extension_placeholder()`；preset/platform/export plugin及native NodePath资源递归亦同。不能以CORE父类名证明placeholder为纯原生对象。新增native单测使用Object原生`reset_internal_extension`/`clear_internal_extension`建立**合成placeholder状态**，证明它报告Gradient/CORE、is_gdextension为false时，顶层及metadata嵌套快照仍拒绝，清除placeholder后正常恢复。该测试不是脚本伪装，也不声称加载了真实独立编译的GDExtension动态库；真实动态库加载组合仍未覆盖。

旧`scene408-fixes-*`19组回执保留。新候选的构建、完整扩展验收、native及静态回执另记`scene408-gaps-*`，不覆盖旧冻结报告。

第二轮最终冻结：完整21组业务验收通过，editor退出0；隔离native 8组/103断言通过；指定全部静态检查通过。精确编辑器SHA-256 `cb6d1b5e67d5465d36e0931e37a31f3676d64b9868345beb9b62ea82e00eed13`，真实EditorSettings摘要仍不变。自定义getter fixture在原生编辑器附着脚本后已有基线调用计数1，三种结构拒绝前后计数保持1（增量0）；没有把正常编辑器附着流程的既有getter调用误归到结构检查，也不声称整个编辑器从未触发getter。新断引用/运行批准测试及纯native placeholder测试见`scene408-gaps-summary.json`、`scene408-gaps-acceptance.json`、`scene408-gaps-native.log`；旧19组报告完整保留。其余此前列出的未测组合、原生退出泄漏诊断与独立复核/正式交付要求不变。

### 正常ZIP/macOS应用导出与动态metadata复核

独立正常验收指出的两个P1均确认并修复：ZIP的原生save_zip最终使用ACCESS_FILESYSTEM移动文件，直接传`res://`不能完成移动；现在project/pack/zip统一只把已验证项目目标的globalize_path传给原生导出器，输出仍通过项目路径读回。credential相关preset值改为严格Variant类型判定：允许NIL、false、数值0、真正空String/StringName及真正空的Array/Dictionary/packed集合，其他值拒绝；非空集合即使只包含空字符串也拒绝。该代码只读preset，不切换签名、公证或认证设置。

普通无脚本Node metadata同样不能由ClassDB属性遍历覆盖：旧21组二进制用`set_meta("path", NodePath("../Branch/Leaf"))`复现移动后metadata保持旧路径、原生RemoteTransform/Animation已改且动作返回成功，见`scene408-metadata-probe.json`（原21组同时通过）。当前结构操作在事务前用固定原生get_meta读取有界metadata图，发现NodePath（包括Array/Dictionary键和值）、非空Object或不透明Callable/Signal即明确返回`unsafe_metadata_reference_scope`；不调用通用Object::get或脚本getter。检查限100节点、每节点256 metadata项、12层、1024值、每集合256项；不能维护的作用域拒绝。普通标量metadata保留正常移动与Undo，已实际验证。

本轮完整25组验收通过、editor退出0，隔离native 8组/103断言通过，全部指定静态检查通过。新增正常正向包括Linux preset ZIP实际归档校验、macOS禁签名preset默认空PackedStringArray/Array的ZIP成功、两种非空集合拒绝，以及确认后原生API导出真实unsigned arm64 `.app`：Info.plist、CFBundleExecutable对应文件及完整目录hash均读回。测试全部在系统TemporaryDirectory的项目/编辑器副本中执行；未运行导出应用，也未修改全局模板。临时macOS preset按本源码设置`binary_format/architecture="arm64"`、有效bundle identifier、codesign/notarization关闭，临时项目启用ETC2 ASTC。最初使用并非本源码字段的`application/architecture`且缺少bundle ID时，原生can_export明确拒绝配置；纠正测试fixture后成功，未将该失败解释为缺模板。

父任务提供的只读私有模板归档SHA-256为`18580e4778d36b522643761e7695db11a41d5116672094b4bd072a47fbda1d98`（来源5026ac8f、optimize=none，仅功能测试），只复制到临时项目`res://templates/mac-arm64.zip`后使用。最终编辑器SHA-256 `d6ed6c857cd19adc000656765edbc20e5636410f7500ed6ca9b9b3833dbf8a89`；本轮macOS应用目录manifest SHA-256 `3c9354c7c0d4091d2724ffa6ecb3558090533df96475552547a3e441ee602f39`。真实EditorSettings摘要仍为`6eec2d16db85fec5fac37ffef6e2c8eda9c405ec9a63706d1dc1db3acab5a490`。新证据独立保留为`scene408-export-fixes-{summary,acceptance,static}.json`及build/native/acceptance.log，旧19/21组回执未覆盖。ZIP与本次真实macOS arm64应用导出已补正常覆盖；其他平台/模板组合、应用可运行性、资源全部组合、图形像素读回、原退出泄漏诊断及正式独立接收要求仍按此前限制保留。

### 交付准备：最新main与受限工具定义接线

本树先逐一核对原408九个冻结源码SHA-256均与独立v3已验候选匹配，再用唯一标签生成本树stash并回读精确对象`e28d3127ddc895ea0dae0c8fc8764de0a700bc9d`，将本分支快进到真实origin/main `cfd1bc5e8b52db878a4938194f3d98f1073b936c`，只用该明确SHA apply恢复；未使用共享stash pop、未删除其他工作树或其他stash。原408九源码整合后仍逐一保持原hash，main的新provenance/模型刷新/其他功能保留。

交付补丁只在`AIChatEditorControl::tool_definitions`接入receiver、signal、method、resource_path、destination、preset、format字符串字段及debug布尔字段，保持additionalProperties=false；描述补齐scene_assign_resource、scene_connect_signal/scene_disconnect_signal、scene_import_resource、scene_export_resource、project_export，纠正旧leaf-only及整场景脚本拒绝描述。不新增任意执行字段或改变工具/模型授权。新增schema原生回归实际读取公开工具定义，检查字段类型、闭合参数集和动作描述。后续407/F05主线接入若修改同一函数，须保留UI动作和本408两组受限能力；本轮未提前复制未交付407实现。

同时复制已验389隔离助手及其测试（来源db6c8728，签发PR由根另行负责），防止私有编辑器继承工作区祖先或GONGGONG_WORKSPACE。完整25组在系统临时项目/编辑器副本上用新助手通过，原8组/103断言加工具schema共9组/129断言通过；389助手单测8项中7通过、1可选真实重启专项因未指定ISOLATION_TEST_EDITOR明确跳过。本轮25组实际使用新助手并确认真实EditorSettings摘要仍不变，未把该跳过项称为通过。

本轮按原macOS arm64配置增量构建65.33s成功；更新源来自main实际变更，未切optimize=none或dev_build=yes。独立v3此前已对精确旧408冻结二进制`d6ed6c...3dbf8a89`复跑25组/native8/103及额外真实ZIP/.app正向，且无阻断；该旧独立回执与新增main/schema/389集成验证分开列证，不把旧审查当新二进制的独立验收。公开验证记录见`data-collection/issue408-scene-completion-main-integration-validation.json`，对应Diting step事件仅准备本地证据，不声明采集已送达、CI/main交付或Issue验收完成。当前仍不提交、不推送，由根组织新精确候选复核及正式交付；所有早期失败/旧回执保留。

### 已审查候选的PR签发准备

最终独立回执已对精确编辑器`89f6c6db739359ee8ddf6b2bac1cc56b5e169415cc1b3c6760f36d2040281ec1`及工具接线独立复跑25组、native9/129并判定无阻断；摘要SHA-256 `be7d9336b5020803efda92f778100401ef201be3aea4007c7a15a56c072ab3cd`。独立回执的真实settings前后摘要均为`869970a00b6c9290d8df035522cef509036071bd4d3b3afaa5be40bb96e11ecc`；这与先前本轮宿主读取摘要属于不同时间观测，均只声称各自运行前后未变，不伪称跨全部会话的全局设置从未变化。

签发前实际main回读为`3451c1ef9ced0311e95685a7bfae9dab3e24b01b`（389已进入main）。本树以明确stash`cc334625801bb8ebd651143704839a16e302c0b9`保存、快进并apply该SHA，未用共享pop；前16冻结文件全字节相同。新增main仅两份已经复制并实际验证的389 helper及389文档/证据，C++无变化，因此按根明确授权绑定新baseline/sourcehash而不重复25组。公开追加记录为`data-collection/issue408-scene-completion-pr-validation.json`；旧公开验证、旧step及所有私有失败回执不覆盖。实际GitHub Issue408在本次授权下重新回读，新增同tenant/request、kind=request、source_ref精确IssueURL的请求回读事件；仅准备/文件记录不等于Diting已落库消费。

根已明确授权正常writer_submit创建PR，说明保留原九文件及已独立验收新schema。此工作者不merge、不关闭Issue；取得PR回执后停止源码修改，由根统一顺序推进407/408精确候选CI及main回读。未来合入407修改同一工具定义时继续保留两组能力，不能把本候选验收自动转移到不同组合二进制。
