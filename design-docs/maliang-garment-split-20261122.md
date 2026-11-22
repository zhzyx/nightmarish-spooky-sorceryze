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
- 剩余验收：真实 AI 识别质量、真实角色多视角视觉审核，以及目标骨架实际动画／碰撞仍未执行；不得由合成测试推定通过。
- 责任人：kaiyunxue；目标为本地候选，2026-11-23 用户授权提交本次相关改动，不包含 push、PR 或 main 交付。

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
