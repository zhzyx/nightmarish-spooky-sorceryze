# 马良：Kimi Native 接入 Tripo API 直接三维生成

<!-- gonggong-request:maliang-kimi-native-sculpt-20261112 -->

日期：2026-11-12（Asia/Shanghai）。路径基准：仓库根。关联 Issue：[#885](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/885)。稳定需求 ID 保留首次建单值 `maliang-kimi-native-sculpt-20261112`。

## 用户目标与基线

用户先要求“让 Kimi Native 支持和你说的两个模型相同的流程”，随后指出此前聊天中的 Kimi 3D generate 可以直接制作、无需 Blender。经读取当前已安装 `model3d_generation` 插件的真实脚本确认：Kimi Work agent-gw 的 `client.tools.invoke("generate_3d_model", …)` 由 **Tripo API** 提供直接三维生成，支持文字、单图和 2–4 视图，返回 GLB 与可选预览，不需要本机 Blender。

此前将目标理解为复用 Blender 固定算子属于路线偏差，相关未提交改动已撤回，没有把 Blender 依赖或 `registered_turnaround` 留作本单前置条件。

开发基线为 `origin/main` 的 `93006dd2bdec4a7c1c2982a254d2fdef9151e7a1`，隔离分支 `codex/maliang-kimi-native-sculpt-20261112`。真实 Issue #885 已回读为 OPEN／`status:in-progress`，intake-only 在相同基线上取得 `operation_reverified`。前序 #646 已完成原语版；#543 的 Blender 算子及人物外观验收保持独立。

## 范围与不变约束

- 新 `kimi_native` Mesh 任务通过用户已安装的 Kimi Work `model3d_generation_tool.py` 调用 Tripo API，直接取得本次新生成的 GLB。不得调用 Codex、ComfyUI、混元、K3 原语规划或 Blender，不得用旧 GLB 或 Godot 原语结果冒充成功。
- 支持 `text_to_mesh`、单图 `image_to_mesh` 和 2–4 视图直接生成。单张普通图片使用 `image_url`；明确的三视图整图按正面／右侧／背面裁切后使用 `multiview.front_url/right_url/back_url`，不把整张拼图当作单视角图片。
- 保留持久任务、幂等、取消、恢复、节点连线、原生预览、发布与保存重开。旧 `KimiNativeProvider` 原语快照只按原实现恢复，新任务使用独立状态目录，不改写历史数据库、Artifact 或终态。
- Kimi Work 二维图像 Provider 保持独立。Workbench 明确区分 Tripo API 三维生成、Kimi Work 二维图像与旧原语快照，不强制 K3 Mesh 规划或 Blender。
- 不扩大到自动绑骨、动画、生产级任意拓扑或照片级外观承诺。返回 GLB、几何有效和预览非空不代替人物相似度、材质、布线及多视角外观复核。

## 实现设计

1. 在既有 `kimi_provider.py` 增加直接三维 Provider，复用 `KimiWorkImageProvider` 已验证的本地意图、拥有进程、上传、监视、取消与不可变终态机制。配置只包含 3D 工具、无窗口运行时、生成模型和状态目录；agent-gw SDK 管理凭据，Provider 不读取密钥。
2. 本地工具探测核对 `model3d_generation_tool.py`、launcher、watcher 及其摘要。每个新意图先写入本地记录，再上传图片和启动一次 Tripo API 任务；未知回执不自动重复上传或生成。
3. 计划阶段验证文字、图片、上下文和生成参数。三视图裁切仅在用户明确标记三视图时启用；保留原图摘要、裁切框、各视角摘要和实际上传 URL 的摘要，公开记录不保存签名 URL。
4. launcher／watcher 只返回受控私有目录中的新 GLB。Provider 校验文件身份、GLB 结构、顶点／三角形／字节预算，记录 Tripo API 返回的 `task_id`、模型版本、输入模式、来源与输出摘要及可选预览；Artifact 保持 `provider=kimi_native`。
5. `generation_service` 与 Workbench 将新 Mesh 节点路由到直接三维 Provider，二维节点仍路由到 `kimi_work_image`。运行快照按配置结构区分直接三维与旧原语任务，旧结果继续只读恢复。
6. `kimi-config.example.json` 与 README 更新为直接三维配置、三视图顺序、恢复规则和 Tripo API 归因，不再把 Blender 或 K3 原语计划作为新任务依赖。

## 模块与构建边界

本需求不新增独立业务模块、Agent 或 Skill，不新增 `module.json`／组件声明。实现位于既有 `tools/ainative` 宿主工具与 Workbench 资源中，分类为 **host_tool**；引擎内置版本同时沿用既有 **runtime_package** 分发边界。

实际输入为用户文字／图片、Kimi Work 3D 工具及 Tripo API 返回；宿主接口为 `generation_service`、持久 Provider／Executor 和现有 Workbench。构建或资源包验收须核对受影响资源摘要、同一二进制上的新包更新与回退、缺失工具／运行时的明确阻断。新任务没有 Godot 原语回退；旧快照只按原实现恢复。

## 验证与交付

- 本地合成 worker 验证文字、单图、多视图、裁切顺序、GLB／预览发布、身份与摘要，不调用真实服务。
- 服务测试验证工具依赖、旧原语快照恢复、新直接三维快照恢复、混合 Mesh／Kimi Work 图像节点及无 Codex／ComfyUI／Blender 调用。
- 具备凭据时用当前用户三视图执行一次真实 Tripo API `generate_3d_model` 任务，记录 `task_id`、GLB 和预览，检查原生预览、保存重开与独立几何统计；人物外观另行复核。
- 运行受影响的 Python、Workbench／原生编辑器回归、静态检查与内置资源更新／回退验证。原始图片、签名 URL、API 原始响应与大资产只保留在私有运行目录，公开证据只含摘要、统计与未知项。
- 本地必要验证通过后，沿正式门禁、精确候选 PR／CI、main 回读及 Issue 验收连续交付；未实际完成或外观未验收的项目保持未知，不倒写成通过。


## 实施与验证结果（2026-11-12）

- 新增 `KimiNativeDirectProvider`，新 Mesh 任务通过 Kimi Work `model3d_generation_tool.py` 和 agent-gw 调用 **Tripo API** `generate_3d_model`，不经过 Blender、K3 原语规划、Codex、ComfyUI 或混元。旧原语快照仍按原 Provider 恢复。
- 真实三视图按 front/right/back 裁切上传。首次任务因本机 agent-gw 0.2.6 低于要求而在首次上传前失败；升级到 0.5.0 后以新幂等键显式重试，Tripo API 返回 `task_id=5567a16a-a5c7-40db-81f2-a08f81c12085`。关联依赖缺陷 #898 已复验关闭。
- 实际 GLB：47,089,392 bytes，778,552 vertices，1,497,506 triangles，SHA-256 `bcc799074cfbbfee4cd013c3cb070bca3976e09474bbe1f4e6cb6ede4ef76b2c`。Godot 原生加载、发布及保存重开通过，顶点数一致；headless 无法读取截图纹理，已检查服务返回的预览图，未把该缺口记为原生截图通过。
- 直接三维合成 5 tests、Kimi 服务 7、二维图像 7、多图 8、旧 Kimi 13、服务套件 33、Provider 隔离 10、Workbench GUI 1 均通过。全量 404 tests 中另有两个 MotionProvider 既有异常，在未修改原主线上同样复现，不计为本需求通过范围。Ruff 0.17.1 check／format 通过。
- 候选 Godot 增量重建及 `run_ainative_builtin.py` 全部通过，内置资源与源码一致、项目隔离和重定位通过。候选二进制 SHA-256 `bdfcef2124543d759d8000f53e0654942121d85fee0e36678e6a3f36bec86213`，资源包版本 `90c5bc9af5ba1aa9ba7664bc9e4510fd9a510f03d9b03af2ded126c70c793f3c`。
- 旧二进制缺少新增 3D 字段的兼容性反证成立；其既有 Kimi 设置与离线 Mesh 预览仍能运行。完整旧套件另有四个基线失败，未宣称全量回退通过。
- 公开证据：`data-collection/maliang-kimi-native-sculpt-20261112-validation.json`。原始用户图片、签名 URL、API 原始响应与 GLB 均留在私有运行目录，不进入 Git。服务预览显示角色法袍、肩甲、腰部配饰与面部明显优于原语结果，但生产级视觉、拓扑、绑骨与动画验收仍保持开放。


## 最新主线整合（2026-11-12）

候选已整合 `origin/main=55e41ffb6dbe537c8bfc1fa2450ffc20fc1a040e`。唯一重叠文件 `tools/ainative/kimi_work_image_provider.py` 同时保留上游指纹修复和本候选运行时／TMPDIR 修复。整合后相关 Provider 测试全部通过，按该主线重建的四组原生验收再次全部通过。最新候选二进制 SHA-256 为 `210d94bdd9b84368122daf8efc8f2db0f0be8234f6480639d19e7665d955cc65`，资源包版本为 `0453427a8ada8302b9976666019dfbbdc1d523a0a8bcb74f02d366cf10c14145`。
