# 马良已生成模型的衣服识别、表面提取与布料准备

<!-- gonggong-request:ainative-art-garment-split-20261122 -->

## 当前结论

- 用户目标：基于马良已经生成的模型识别并拆出衣服，为独立材质和后续布料动态提供资产；2026-11-22 当前会话明确授权“请按你的预期落地就好”。
- 本轮产物：本地可运行的 GLB 结构盘点、开放式衣服识别契约、可追溯表面提取、披风／裙摆布料准备接口，以及工作台“衣服拆分”节点；原模型不覆盖。
- 节点扩展授权：2026-11-22 当前会话先确认尚无工作台节点，用户随后明确“对 请落地”。节点使用本地 Provider，主结果为衣服集合 GLB，每件衣服另有独立 Mesh 动态产物，可预览、保存和作为固定输入连接下游。
- 已绑骨扩展授权：用户确认“这种聊清楚的按照原计划去做”，本阶段改为已绑骨优先，直接读取带 Skin 的 GLB，保留原骨架和蒙皮。
- Issue：[#2022](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/2022)；类别 `type:requirement`。
- 已验收：本地合成 GLB 契约、几何提取、CLI／Executor 冒烟、AINative Python 回归、源码工作台原生交互，以及新二进制的纯内置包节点创建和真实拆衣执行；具体命令与证据见文末。
- 已绑骨验收：带两个关节的 GLB 通过全部核心与原生测试，骨架、蒙皮权重和 Inverse Bind 完全保留；归一化 `uint16` 权重也通过。纯内置验收报告 `rigged-node-passed.json` 为 `state=passed` 且 `installed_bundle_matches_source=true`。
- 实际运行安装：`bin/godot.macos.editor.arm64` 已重建，最终工作台进程 31552 曾使用 bundle `98d0f05c8db6f6ab7c4a9d07462113be4bb0160c7873dac3b66aed2f6ec18d40`；该进程现已退出，安装包仍保留。
- AI 自动识别扩展：2026-11-23 节点默认空清单会渲染整模型及最多 4 个候选组件，由 AI 选择有图像证据的组件，普通界面不再要求填写 `component_id` 或审核三角面。初次 12 组件请求发生服务端读取超时，未自动重试；缩小批次后，真实牧师模型完整原生流程通过，运行 `40e7425953634072a92700625af55b00` 发布 4 件证据绑定衣服及 4 张原生卡片，5 项未解决语义保持显式，源 GLB 哈希不变。最终内置 bundle `aa5921d150c05e109ce762a686191bd1b156614e340f18f37f2cc173d57ad098` 与源码一致。该结果仍不等于完整视觉质量、目标骨架动画或布料碰撞验收通过。
- 完整换装扩展授权：2026-11-23 用户明确指出目标是“可独立换装的完整衣服”，并授权“你可以按你说的尝试落地”。本阶段不再把组件表面片段称为完整衣服；目标产物是多视角可见表面分割、去人体、封闭内侧与边界的独立服装 GLB。只有来源覆盖与拓扑检查均通过的项才进入 `wearable_shell`，视觉审核、目标骨架适配和动画碰撞仍分别验收；不能可靠分割或补全的项保持未解决，不以加厚碎片冒充完成。
- 真实模型几何证据：2026-11-23 对源 SHA `336188a4b65f0276fc6ccaee64953e28dfc0751dbbb889a732c35aa8a348f483` 的只读分析确认，247 个顶点索引连通组件在精确位置焊接后实际为一个封闭角色网格，共 1,402,552 个三角面、701,254 个位置顶点，边界边为 0。故本阶段停止把连通组件当服装语义边界，改用带可见三角面证据的多视角分割。
- 完整换装实现：`garment_complete.py` 采用“语义清单＋逐视角最多 6 件分批遮罩”，成功证据按源 SHA 恢复复用；同机位双 12 位 ID 图确定源三角面，按真实第二高投票检查归属冲突。通过完整覆盖的项由本地按边连通壳分别重建外侧、内侧与边界，保留材质、UV 和源面映射，并逐壳以位置焊接边检查证明封闭，避免顶点相碰的扇区形成四面共边。内部生成物使用独立高容量读取，用户源模型 128 MiB 输入限制不变。自动路径接受静态或已绑骨角色；已绑骨输入保留原骨架、Inverse Bind、关节索引和蒙皮权重，新增内侧与封口顶点继承蒙皮，并逐文件校验。
- 界面与验收边界：卡片区分“完整衣服”和“衣服表面片段”，集合显示未完成项数量；绑骨表面缩略图按实际渲染索引取景。原生合成工作台 26 项断言全部通过。前后右三个真实视角遮罩已叠加人工复核，左右身份仍待审核；其他真实视角、最终几何外观、视觉审核、目标骨架适配和动画碰撞不得提前宣称通过。
- 当前回归：最终候选 AINative Python 551 项通过、62 项按环境跳过；`git diff --check` 与受影响 Python 编译通过。纯内置入口在隔离工程通过本任务相关检查，但仍有一项与本任务无关的既有“模型调整工作流重开”失败，因此不宣称整份 `ainative_builtin.gd` 全量通过；安装 bundle 的拆衣脚本已按构建器 preload 重写规则回读比对。
- 视觉反例与纠正：首轮真实输出虽有三件封闭壳，但实际渲染稀疏破碎，明确移入 `output-sparse-rejected`，不得交付为完整衣服。根因是 140 万源面在 768 图像上的可见 ID 采样不足；后续以可见 ID 面为种子，仅在源组件内种子覆盖率达到 10% 时补全剩余细分面，并对低于 90% 的可见像素命中率和无法封闭的边界扇区继续失败关闭。最终渲染仍不合格，产物隔离为 `output-sparse-rejected-final`。
- 最终真实结果：当前没有满足“可独立换装完整衣服”的产物。长袍仍有 53 条侧墙非流形边，其余项覆盖率不足，`garment_complete_no_wearable` 失败且当前无输出目录。最终 bundle `8cee9aa37df618ba22383ddbdd986bb4b4642bce7853b3246d00012a097fd233` 已回读，与当前 90% 门禁源码一致。此结果属于工程闭环落地但真实业务目标未达成，不宣称完整换装或视觉验收通过。
- 已绑骨纠错：2026-11-23 用户在编辑器内以已绑骨 GLB 运行，遇到此前错误加入的“仅静态”限制。已恢复文档约定的已绑骨优先：ID 证据与完整衣服均保留原节点层级、Skin、Inverse Bind、关节索引和蒙皮权重，内侧与封口顶点继承蒙皮；输出三角面只统计实际引用的新 Mesh。合成已绑骨回归和真实 Godot 带 Skin 闭环均通过，输出 `rigged=true`、`skeleton_preserved=true`、`skin_weights_preserved=true`、`inverse_bind_matrices_preserved=true`；这仍不等于真实衣服的视觉、适配或动画验收通过。
- 真实编辑器输出：2026-11-24 对用户运行 `93b2c54316434c2a9d6b9165b22e8271` 的证据复算后，已生成 `full_length_white_robe.glb`、`central_tabard.glb` 与 `_garments.glb`，分别为开放边界独立衣服，保留原骨架、Inverse Bind 和蒙皮。当前状态为 `capability_limited`、`wearable_open`、`visual_review_passed=false`；渲染显示衣服已成形但边界仍有噪声，不宣称封闭或视觉验收通过。最终恢复逻辑优先复用 `segmentation.json` 和重定位后的证据路径，避免重复视觉请求。
- 责任人：kaiyunxue；目标为本地候选，2026-11-23 用户授权提交本次相关改动，不包含 push、PR 或 main 交付。本轮“尝试落地”授权只包含本地实现与验证，不重新解释上一轮提交授权，不执行 commit、push、PR 或 main 交付。

## 原始需求与目标

把已经生成的角色模型中的衣服、手套、盔甲、肩甲、护手、靴子等识别为开放集合，并提取独立 Mesh。第一版不恢复被遮挡的人体，不把衣服表面拆分等同于可换装或布料动态通过。披风和裙摆可以进入现有布料准备流程；其他衣服保留刚性或蒙皮分类。

## 范围与非目标

### 范围

1. 校验自包含、静态或已绑骨的 Y-up GLB 2.0，固定源文件 SHA-256；已绑骨模型还校验 Skin、关节索引、权重和 Inverse Bind Matrices。
2. 盘点 Mesh 节点、Primitive 和顶点连通组件，为 AI 或人工选择提供稳定 ID。
3. 定义开放式衣服清单：自由名称、类别、部位、刚柔行为、置信度、审核状态和组件候选。
4. 按连通组件或明确审核的源三角面提取衣服，保留材质、UV、常见顶点属性和源面顺序。
5. 拒绝跨衣服重复占用同一源三角面，记录每项来源、输出摘要和未解决事项。
6. 对已确认的披风／裙摆调用现有 `cloth_prepare`，输出 `cloth_prepared`；只有真实动画与碰撞验收后才能由下游成为 `cloth_ready`。

### 非目标

- 不生成裸体、完整素体或被遮挡的内层衣服。
- 不宣称仅凭整模型图片即可可靠恢复融合 Mesh 的精确三角面边界。
- 不支持稀疏 Accessor、外部 URI、非三角 Primitive 或 Primitive 扩展；静态 Mesh 仍要求恒等变换，已绑骨 Mesh 则保留原变换与层级。
- 不把 AI 语义判断记为人工确认，不把开放衣服壳补成完整服装。
- 不实现通用衣服重拓扑、宽袖／飘带模拟、布料自碰撞或多布料互碰。
- 不自动宣称独立材质、视觉审核、蒙皮、动画或生产质量通过。

## 设计方案

### 状态分离

- `recognized`：只有语义清单，没有几何选择。
- `surface_split`：已生成独立表面；另外记录 `automatic` / `needs_review` / `confirmed`，不冒充视觉验收。
- `cloth_prepared`：已生成模拟代理、渲染映射和固定边候选，仍需真实动画验收。
- `cloth_ready`：本轮工具不会自行设置；只能由下游实际动态验收产生。
- `capability_limited`：保留可用产物和明确未解决事项。

### 几何选择

结构盘点输出稳定 `component_id`。AI 只能在图像证据明确绑定组件时返回组件候选；融合表面的精确选择使用 `reviewed_triangles`，绑定源 SHA、Primitive 和三角面序号。未知组件、越界面号、退化输出和跨实例冲突均失败，不自动猜测。

每个输出 GLB 是独立的新文件，只渲染选中几何；材质和嵌入图片按原索引保留。静态输出的 Accessor 重新生成；已绑骨输出只替换索引缓冲，完整保留骨架、Inverse Bind、`JOINTS_0`、`WEIGHTS_0` 和原顶点属性。为避免蒙皮错位，未参与渲染的源顶点也保留。清单记录源面映射和输出 SHA，源文件在写后再次校验。

### AI 识别边界

AI 请求使用严格 JSON Schema，允许开放标签，不把衣服限制为固定枚举。输入可包含整模型多视角和带明确组件 ID 的预览。没有组件证据时，AI 可以返回名称、类别和刚柔建议，但几何选择必须进入审核，不能将文字描述直接当成三角面真值。

### 布料衔接

`cloth` 配置只接受 `cape` / `skirt` 及显式 cage、行列数和可选裙腰高度。该步骤复用现有作者采样与模拟代理能力；输出仍含重建误差和来源摘要，不宣称原 AI 拓扑已修复。

### 工作台节点

节点类型为 `garment_split`，已绑骨 Mesh 优先，同时接受静态 Mesh，参数为 `items` 数组及可选识别来源摘要。`garment-split` Provider 只执行本地几何操作，不选择或探测外部生成服务。Provider 版本绑定自身和几何核心文件摘要，Executor 继续负责输入快照、缓存和不可变产物。

主 `result` 为 `_garments.glb` 集合，便于一次预览全部衣服；各单件 Artifact 使用 `artifact_role=garment`、`iteration_of=result.id` 和稳定序号进入现有动态 Mesh 节点机制。界面以衣服名称、审核状态和保存动作展示，不把序号称为生成轮次。工作流保存重开后，单件产物和固定产物连线必须继续指向原字节。

已绑骨输入直接保留 Skin、骨架层级、Rest、Inverse Bind 和原顶点蒙皮权重，不重新绑骨；静态输入仍按原几何提取。节点不自动执行 AI 识别，参数编辑器负责合法 JSON 数组，完整语义和几何校验继续由核心完成。当前 `cloth_prepare` 仅用于静态输入，已绑骨布料准备会明确失败并保留表面拆分结果。

## 依赖及风险

- 复用 `geometry_repair.py` 的 GLB 读取边界和 `cloth_prepare.py` 的披风／裙摆准备能力。
- AI 视觉请求复用 `api_planner.py` 的显式端点、凭据环境变量、无重试和回执校验。
- 分离组件可自动提取；融合网格的自动语义分割准确率尚无真实模型证据，因此首版保留审核契约。
- 大量嵌入图片会增加输出体积；首版优先保证材质引用有效和源不覆盖，不做纹理资源 GC。
- 布料准备结果需要现有 Godot ClothPanel、目标骨架和真实动画继续验收。

## 验收标准

- [x] 结构盘点能稳定识别多个节点、Primitive 和连通组件，源内容 SHA 参与组件身份。
- [x] 开放衣服清单拒绝未知字段、无效行为、无效置信度、重复 ID 和未知组件。
- [x] 组件与审核三角面两种选择均可生成独立、可加载、仅含选中面的 GLB。
- [x] POSITION、NORMAL、TEXCOORD_0 等已声明属性及材质／UV 保持对应，输出索引有限且不越界。
- [x] 跨衣服重复面、越界面、空选择、非法 Skin、静态 Mesh 非恒等变换和外部依赖明确失败。
- [x] 输出目录或文件已存在时不覆盖，源 SHA 在运行前后保持一致。
- [x] 披风准备输出绑定版本和重建误差；稀疏输入失败保留表面结果，且状态不等于 `cloth_ready`。
- [x] 衣服拆分节点具有本地 Provider、结构化衣服清单、Mesh 输入和集合 Mesh 输出，不探测外部生成服务。
- [x] 已绑骨提取保留完整骨架、Inverse Bind、原顶点 `JOINTS_0` 和 `WEIGHTS_0`；归一化 `uint16` 权重通过。
- [x] Executor 实际发布集合与两件单件 Artifact；无服务文件的新项目可创建、执行、恢复和预览，源 GLB 不覆盖。
- [x] 单件 Artifact 携带 `artifact_role=garment`、语义名称和审核状态，编辑器传输保留固定产物输入所需字节与摘要。
- [x] 已使用实际 `bin/godot.macos.editor.arm64` 执行源码工作台原生验收：21 项节点断言通过；参数表单与端口类型回归也全部通过。
- [x] 节点扩展后的最终完整 AINative Python 回归通过；真实角色视觉和布料动态仍保持未执行，实际运行中引擎的 bundle 更新另行记录。

## 验证与采集证据

- 核心与节点新增回归：`python -m unittest discover -s tools/ainative -p 'test_garment_split*.py' -v`，18 项通过；另运行 `test_editor_host.py` 14 项和 `test_kimi_service.py` 11 项，均通过。新增 Godot 整数浮点传输用例覆盖本次实际内置运行发现的 `0.0` 索引问题。
- 实际 Godot 原生验收：`runtime/garment-split-native-20261122/final-report.json` 中 21 项全部通过；`parameter-form-report.json` 和 `port_type_acceptance.gd` 的实际运行也无失败。首次解析发现的 `context_row` 作用域错误已修复，并用最终脚本重新执行通过。
- 构建：`UV_CACHE_DIR="$PWD/runtime/uv-cache" uv run --with scons scons -j8 platform=macos target=editor arch=arm64 metal=yes vulkan=no angle=no accesskit=no`，首次完整构建及数字修复后的增量重链接均成功；新二进制版本 `4.8.beta.custom_build.f27dbd3b2`。
- 纯内置包业务验收：`runtime/garment-split-native-20261122/rigged-node-passed.json`，`state=passed`、`installed_bundle_matches_source=true`、bundle `98d0f05c8db6f6ab7c4a9d07462113be4bb0160c7873dac3b66aed2f6ec18d40`。已绑骨输入实际通过内置 Provider 执行、集合与单件 GLB 发布、骨架与权重保留、语义衣服卡片、Mesh 解码和源字节不变检查。
- 节点冒烟：`python runtime/garment-split-node-20261122/run_acceptance.py`，真实本地 Executor 运行 ID `a0dddf19e692412690088b7e5bec1134`；集合 SHA-256 `1001e16277254f368cbe029dc80cea8d5717db2efb09221081544f5b905b341b`，发布“披风”和“胸甲”两件独立 GLB。
- 节点私有摘要：`runtime/garment-split-node-20261122/node-acceptance.json`；记录 `remote_service_used=false`、`real_ai_called=false`、`visual_review_passed=false`、`cloth_ready=false`、`godot_ui_executed=false`。
- 最终已绑骨实现完整回归：`python -m unittest discover -s tools/ainative -p 'test_*.py'`，539 项通过、62 项环境跳过，186.726 秒；进程正常完成且结果为 `OK`。输出中的负向任务日志是测试预期，不是回归失败。
- CLI 冒烟：`python runtime/garment-split-20261122/run_acceptance.py`；合成源 SHA-256 为 `aae7256aab75cf7c73dd3fa19a8ed51758d4c7880e72bcbee154d38d4081ca65`，实际输出独立衣服 GLB、能力受限清单和 `cloth_prepared` 披风绑定。
- 私有验证摘要：`runtime/garment-split-20261122/cli-acceptance.json`；明确记录 `real_ai_called=false`、`visual_review_passed=false`、`dynamic_acceptance_passed=false`、`cloth_ready=false`。
- `git diff --check` 和新增／受影响 Python 文件 `py_compile` 通过。当前主机没有可调用的 Ruff，因此不声明 Ruff 已运行。
- 合成夹具只证明契约、几何行为、原生工作台交互和安装后内置节点执行，不证明任意真实模型的语义识别、视觉质量、蒙皮或布料动态。未执行真实供应商请求或目标动画碰撞；最终工作台进程 31552 已安装并加载已绑骨优先 bundle。
