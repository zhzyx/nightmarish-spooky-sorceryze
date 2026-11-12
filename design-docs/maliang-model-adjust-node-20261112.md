# 马良：模型调整节点（原模型＋文字／图片上下文）

<!-- gonggong-request:maliang-model-adjust-node-20261112 -->

日期：2026-11-12（Asia/Shanghai）。路径基准：仓库根。关联 Issue：[#913](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/913)。稳定需求 ID：`maliang-model-adjust-node-20261112`。

## 用户目标与基线

用户要求在现有三维工作流中增加“模型调整”节点：已生成模型为必选输入，微调文字与补充图片为可选输入；输出应是基于原模型及文字／图片上下文生成的新模型。开发使用从 `origin/main=42e04327b051921382f5a842b291a90bcea5b510` 创建的隔离工作树和分支 `codex/maliang-model-adjust-node-20261112`。Issue #913 的 intake-only 已在开发前通过。

本单复用 #885 已交付的 Kimi Native 直接三维 Provider、Kimi Work `model3d_generation` 工具及 Tripo API 凭据边界，不恢复此前已否决的 Blender 路线，也不重新生成原人物模型。

## 范围与接口

- 新节点机器类型为 `model_adjust`，中文名“模型调整”，`source` 输入要求 `mesh`，`result` 输出为 `mesh`。
- 文字与图片都可留空。支持无引导、仅文字、文字＋一张风格图、仅一张图片、四张视角图且无文字。四图按 `front/left/back/right` 顺序传递；2～3 张图、四图同时带文字、缺原模型均在启动前拒绝。
- 原模型支持 GLB 与内嵌 glTF。优先读取原 Artifact 的 Tripo API `task_id`；本地模型没有上游 ID 时，通过工具的存储上传接口取得 `model_url`。上传与生成各自保留私有回执，不公开签名 URL。
- 实际算法为 **Tripo API `texture_3d_model`**，默认 `v3.5`，不是重新执行 `generate_3d_model`，不调用 Blender。当前范围以材质／外观微调为主，不承诺任意几何拓扑修改、严格几何不变、生产级布线或绑骨。
- 新结果写入独立的 `adjusted.glb` 和新 Artifact，不覆盖原模型。GLB 输入独立验证几何；内嵌 glTF 验证结构与依赖；新 GLB 始终验证几何、文件身份与摘要。
- 保留持久意图、幂等、取消、恢复、预览、发布及保存重开。其他生成服务模式明确拒绝该节点，不以 ComfyUI、Codex 或旧原语 Provider 代替。

## 实现设计

1. `kimi_provider.py` 为直接三维 Provider 增加 `texture_model` 配置、模型调整计划、输入验证、原模型上传与 `texture` 子命令调用。输出 Artifact 的 provenance 记录原／新任务 ID、原模型 SHA、引导模式、图片摘要、原／新几何、`original_model_not_overwritten=true` 和 `blender_used=false`。
2. `comfy_provider.py` 只注册公共节点协议；`generation_service.py` 负责 Kimi Native 路由、能力检测、可选文字／模型源格式、独立 `texture_model` 快照及不兼容服务拒绝。旧直接三维快照缺少该可选字段时仍按默认 `v3.5` 恢复。
3. `editor_host.py` 仅允许 `model_adjust` 的源端口使用 GLB／内嵌 glTF；补充图片仍只接受 PNG/JPEG，其他生成节点不接受模型源。
4. Workbench 增加节点入口、Mesh 输入／输出连线、单模型文件选择、多参考图选择、可选文字提示与保存重开。Kimi Native 的 `texture_model` 随机服务配置恢复；工作流不保存本机工具路径或凭据。
5. 使用原有人物模型 `task_id=5567a16a-a5c7-40db-81f2-a08f81c12085` 做一次真实文字微调：“将金色装饰稍微调暗，保留人物面部、白色法袍、肩甲结构与 T Pose。”真实图片引导只用合成测试验证，不冒充真实服务结果。

## 模块与构建边界

本需求不新增独立业务模块、Agent、Skill、`module.json` 或组件声明。实现位于既有 `tools/ainative` 宿主工具和 Workbench 资源，分类为 **host_tool**；引擎内置版本继续沿用既有 **runtime_package** 分发边界。

实际输入为原模型、可选文字／图片、Kimi Work 工具与 Tripo API 返回；宿主接口为 `generation_service`、持久 Provider／Executor 和 Workbench。资源更新须核对实际摘要，并在同一候选二进制上验证内置包、独立项目和重定位；不切换现有有效发布。失败时保留原模型、原意图及既有二进制，不自动重发未知任务。

## 验证计划与当前记录

- 已完成 Python 编译及首轮 20 项合成／服务测试：覆盖任务 ID＋文字＋风格图、无引导、单图、无任务 ID 的本地 GLB 上传、四图顺序、非法输入、Kimi 路由、模型编译、快照恢复及原文件不覆盖。合成 worker 不代表真实 Tripo API 结果。
- Workbench／原生编辑器验证覆盖节点入口、模型与图片选择器、可选文字、Mesh 连线、输入快照保存重开、旧原语／直接三维 Provider 恢复和既有预览发布。
- 真实 Tripo API `texture_3d_model` 复用上述原任务 ID；每个独立意图只提交一次并监视其持久回执，记录新任务 ID、GLB、几何与预览，不以排队或启动当作成功。
- 静态检查、受影响回归、候选 Godot 重建、内置资源更新／回退验证、正式门禁、精确候选 PR／CI、main 回读和 Issue 关闭按实际结果逐项记录。公开证据为 `data-collection/maliang-model-adjust-node-20261112-validation.json`；原模型、签名 URL、原始响应与大文件留在私有目录，不提交 Git。

## 实施与验证结果（2026-11-12）

- 已增加 `model_adjust` 节点及完整的 Provider、Executor、Workbench 和持久快照链路。必选输入为一个 GLB／内嵌 glTF；文字与图片可独立或组合使用；输出独立 `adjusted.glb`。真实调用使用 Tripo API `texture_3d_model` v3.5，不使用 Blender。
- 首轮仅文字任务返回 `ab54cc09-65b4-46fd-8ed8-36de68bfe8aa`，新 GLB SHA-256 为 `2da31f61adef63b0da321ac1045bb9ef6b5d4c8dd80f368fed29e53460ced48e`。预览保留几何与 T Pose，但白色法袍被大面积改成深色／红金，未充分满足保留要求，故另做明确参数纠正而非覆盖或重发未知任务。
- 第二次使用英文保留约束＋原预览风格图，返回 `53c26924-7c67-4b3f-9477-1878fdb968c3`。新 GLB 为 48,569,872 bytes，SHA-256 `3caba1c9e658b9326c4f8e0c24640319341f08dc0edba524472c61f9c86aa463`，778,552 vertices、1,497,506 triangles，边界与原模型一致。预览保留白色法袍、轮廓和 T Pose，更接近要求，但肩部与胸前纹样仍重绘，不宣称精确局部纹理编辑。
- 原模型 SHA-256 始终为 `bcc799074cfbbfee4cd013c3cb070bca3976e09474bbe1f4e6cb6ede4ef76b2c`。第二次结果已在最终候选 Godot 中加载、发布并重开，778,552 个顶点一致。headless 不能提供服务视觉截图，已直接检查 Tripo API 返回预览。
- 直接三维／Executor 合成 12 tests、Kimi 服务 9、相关服务回归 62、Workbench GUI 1 均通过。完整“生成网格 → 模型调整”持久执行链路通过。全量 414 tests 只有既有 MotionProvider 一项 failure 和一项 error，不计为本需求通过范围。
- Ruff 0.17.1 check／format、mypy（6 files）、Python 编译均通过。最终主线基线为 `2739fc7fb20294e232878a5f29737a09be9d6ac1`；相对已构建验证的 `3e2e655abb851143608a4e73f3124aeff9c675f5` 仅新增编码规范与记录，引擎输入未变。候选 Godot SHA-256 为 `303eaf31aa21161c768771e6d8e70a0a703fbca79a2dc5aa8d5d30986ef8f4d1`，资源包版本为 `68f6c01522c412c7b67bb1fc903a9af2a624fbf004b6006afa149cadd4fef119`。
- 最终内置资源与源码一致，mesh-and-rig、independent-project、sample-addon-compatibility、relocated-runtime 均通过。旧二进制不识别新节点；同一旧二进制运行原有四组验收全部通过，回退边界成立。
- 本地 GLB 无任务 ID 的上传路径、单图独立引导和四图顺序已通过合成测试；真实服务验证为上游任务 ID＋文字及任务 ID＋文字／风格图，未把本地模型上传或四图引导冒充真实服务结果。
- 公开证据：`data-collection/maliang-model-adjust-node-20261112-validation.json`；需求事件：`gonggong-diting-data/events/gonggong-workspace/maliang-model-adjust-node-20261112/request-913-model-adjust-node-20261112.json`。事件落库只证明 `recorded_file`，提交、CI 和 main 状态另行回读。
