# 马良：Kimi Native Mesh Provider 第一阶段

<!-- gonggong-request:maliang-kimi-native-mesh-20261109 -->

日期：2026-11-09（Asia/Shanghai）；开发回交更新：2026-11-10。路径基准：仓库根。

## 用户目标、授权与边界

用户通过独立开发交接单明确要求新增可配置的 `kimi_native` Mesh Provider，至少真实支持 `text_to_mesh` 与 `image_to_mesh`，并连续完成调查、实现、必要测试及仓库交付流程。授权来源为工作区 `handoffs/maliang-kimi-native-mesh-20261109.md` 及本次开发指令；本文件只以稳定需求 ID 和授权说明溯源，不把本机交接路径写成运行依赖。

`kimi_native` 中 Kimi 是唯一的生成式语义／建模模型来源。允许 Kimi 返回受严格 Schema 约束的建模计划，再由固定 Godot 构造器产生真实 GLB；构造阶段、模型身份和输入／输出摘要必须分别记录。选择本 Provider 后不调用或要求 ComfyUI、Hunyuan3D、ChatGPT／Codex，不以其他 Provider、旧 GLB、离线复制或静默回退冒充成功。

保留全部既有 Provider、节点连线、预览、保存重开、来源、Executor、发布、Fit／绑骨及诊断入口。本阶段不扩大为自动绑骨、动画或生产级任意拓扑角色生成。

## 可交付单元与验收

本需求是一张不可分割的 Provider 端到端工单：配置、模型调用、固定构造、持久任务及原生节点预览共同构成同一个可独立验收行为，不再拆成仅接口或仅 UI 的子单。

- T0／T1：确认最新主线、真实 Issue、intake-only、Kimi API 认证及文字／图片／严格结构化输出能力；新增语义稳定的 `kimi_native` 设置和不含秘密的配置示例。
- T2：Kimi HTTP 建模计划 → 有界计划验证 → 既有固定 Godot 原语构造器 → 非空自包含 GLB。计划限制部件数、数值范围、顶点／三角面／输出字节预算；不执行模型生成的代码。
- T3：复用 Executor 与持久 Provider 契约，保持本地幂等、终态不可变、取消、恢复、迟到结果隔离及未知回执不盲目重复提交。
- T4：马良本机设置可选择 `kimi_native`；只有 Kimi 配置时，检测、建节点与运行不依赖 ComfyUI／混元／Codex。不支持的多图、角色或参数显式失败。
- T5：真实文字与图片 GLB 均进入现有原生 Mesh 预览、保存重开、发布及 Fit／几何诊断入口；记录一致的几何统计。
- T6：增加配置、Schema、HTTP 协议、GLB、来源、无隐藏回退、恢复、取消和 UI 测试，运行完整 `tools/ainative` 与受影响原生编辑器回归；保留真实模型、GLB、Godot 与截图证据并更新 README。

目标平台为 Windows x64、Python 3.11+、当前 Godot 4.8 定制编辑器。停止条件为上述两项真实任务及工程门禁完成；若 Kimi 接口、认证或能力实际不可用，保留精确阻塞证据，只交付已验证的非伪造部分，不用其他生成模型补齐表面完成度。开发自报不替代原会话独立验收。

## 实施路线与证据边界

优先复用 `modeling_provider.py` 已验证的固定计划 Schema 与 `modeling_builder.gd`，但新增独立的 Moonshot/Kimi HTTPS 调用、认证、响应校验、任务记录及 `kimi_native` 来源，不改名套壳。凭据只从本机环境或宿主安全配置读取，不进入图、Artifact、日志、仓库或公开回执。Provider／模型／构造器版本与配置指纹参与 Executor 缓存身份。

真实 API 文档、模型响应和原始输入保留在私有运行目录；公开证据只含模型 ID、请求／响应／计划／GLB 摘要、用量、几何统计及阶段来源。headless Godot 回读只证明实际几何与保存重开，不冒充人工视觉验收；截图单独保留。

关联 Issue：[#646](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/646)，2026-11-09 创建并以 `status:in-progress` 回读；`issue_gate.py --intake-only` 已通过。开发基线为 `origin/main` 的 `d237ef78cc394a98db85b6eb1b39f0184217297d`，隔离分支 `codex/maliang-kimi-native-mesh-20261109`。实际候选、测试、PR／CI／main 与 Issue 状态在交付时追加，未回读项保持未知。

## 已实施的 Native 路线

- `kimi_provider.py` 是独立 `KimiNativeProvider(ModelingProvider)`，使用自己的 `kimi-native-jobs.sqlite` 和严格的五项本机配置。官方 HTTPS 端点、K3/K3.1 模型白名单、无代理／无重定向、受限请求与响应、私有原始回执和公开摘要均在 Provider 内执行。
- 只有 `--probe`／`--api` 子进程读取 `KIMI_API_KEY` 或 `MOONSHOT_API_KEY`。每个新建模意图最多一次严格 JSON Schema Chat Completions POST；图片作为 base64 data URL 发送。未知回执不自动重发，取消只终止本任务拥有的子进程。
- 通用固定计划、GLB 与 Executor 路径复用既有实现。新增独立 POSITION／索引／退化面／顶点与三角面预算／有限坐标／TRS／bounds 校验，原生 builder 回执必须与独立统计一致。
- `generation_service.py`、`generate.py` 和 Workbench 新增 `kimi_native` 路由；既有 `comfy` 默认值和其他 Provider 保留。Kimi 仅接受 `text_to_mesh`／`image_to_mesh`，二维节点显式拒绝，采样与不适用参数不冒充已生效。
- Artifact provenance 分开记录 `kimi_strict_modeling_plan` 与 `fixed_godot_primitive_construction`，并记录 `fallback_used=false`、`generated_code_executed=false`、模型与响应 ID、各阶段摘要及 builder 几何回执。

## 真实模型与 Godot 自报证据

本节是开发自报，不是原会话独立验收结论。两次真实任务均已完成，后续 Godot 验收只读恢复既有 Executor 结果，没有重发文字／图片建模 POST，也没有重新生成参考图或真实 GLB。

| 输入 | Executor run | Kimi response | 模型 | usage（tokens） | GLB | 独立几何 |
| --- | --- | --- | --- | --- | --- | --- |
| 文字 | `3830b6892c5946ca92049de556542738` | `chatcmpl-BetHJeFlUVZZmSr47ghV5RR1` | `k3.1-pro` | prompt 795；completion 826；reasoning 215；total 1621 | 6492 bytes；SHA-256 `697fff3ba2f92822c08fbda10989db25eb2a3762c31d6826ef4621cc35e65d16` | 9 parts；216 vertices；108 triangles |
| 图片 | `e747633215b14ab598cdb50b0421bb05` | `chatcmpl-HYuEQ6PnT2LxmhrOjJCSyxf8` | `k3.1-pro` | prompt 1594；cached 256；completion 1311；reasoning 452；total 2905 | 8176 bytes；SHA-256 `f189ca536b443863ee4a0abba10bd8e0b0aec95a1332c44a57df79667e2c539d` | 13 parts；312 vertices；156 triangles |

两次完整摘要、幂等键、请求／响应／计划摘要、bounds 和 builder 摘要见 `data-collection/maliang-kimi-native-mesh-20261109/validation.json`。原始提示词、base64、完整响应和 GLB 只保留在私有证据根，不进入公开记录。

- 真实 `/models` 探测已连接所选模型；该探测只读，不生成内容。
- 真实 Workbench `load_preview()`、`review_publish()` 和确认信号已完成两类 GLB 的预览、暂存与审核发布。预览、暂存和发布的顶点／三角面统计一致。
- 独立 Godot 进程以 `ResourceLoader.CACHE_MODE_IGNORE` 重开四份 staged／published 场景，`process_independent=true`，几何统计一致。
- 文字木桌已进入实际 Fit 入口并读取 216 vertices／108 faces；状态为 `needs_landmarks`，不是自动人形绑骨成功。几何诊断记录退化面与重复面均为 0。
- 两类离屏真实渲染均有 800 × 600 非空截图，开发过程中已逐张读取。headless 主回执的“无像素”记录不作为截图证据。

## 最终回归与未验证边界

- Kimi／服务／计划协议与真实固定 builder：35 tests，OK，无跳过；真实 builder 使用合成计划，未调用模型。
- 全套测试按模块分两组覆盖全部发现项：177 tests，OK（4 skipped）；193 tests，OK（39 skipped）。两组共 370 tests。单独完整 `discover` 在 300 秒工具上限处被终止，未形成最终汇总，不记为通过或失败。分组跳过的 Kimi `RealGodotBuilderTests` 与 GUI 已由上述独立实测补齐；既有 `test_modeling_provider.ModelingTests.test_real_builder_end_to_end_manifest_recovery_and_idempotency` 仍因未设置该套件 Godot 环境而跳过，不能由 Kimi builder 测试冒充覆盖。其余跳过为 25 项 Blender、11 项 Blender 运行时 NumPy、2 项 Pillow 和 2 项 Windows symlink 权限。
- 最终 Workbench 隔离 GUI 回归：1 test，OK。覆盖七项服务设置、Kimi 路由、二维拒绝、无密钥保存／重开恢复及既有 ComfyUI／离线复制路径；HTTP 仅本地只读夹具，没有模型推理。
- `test_portable_scene` 与此前间歇性子进程导入测试已单独复核通过；两项需要 Windows symlink 权限的测试明确跳过。
- 原生 `tests/editor/ainative_builtin.gd` 尚未执行到新增 Kimi 断言。现有 Godot 为 `4.8.beta.custom_build.ced0368bb`（2026-11-05），在第一项“native AINative editor plugin is registered”失败；原生 AINative 入口由后续 `b4ae145bdfa851f147abec78d739521d13e9795c`（2026-11-07）加入。未重建引擎主线，不声称原生 UI 回归通过；实际通过的是同一 Workbench 的 sample GUI 路径。
- 变更 Python 文件已通过 AST／`py_compile` 检查；环境没有 Ruff，未声称 Ruff 通过。静态脚本仍列出的长行位于既有 Codex 提示词／项目字符串，不属于本次新增行。
- 当前产物证明有界 Godot 原语 Mesh 路线，不证明任意复杂形体、贴图、生产拓扑、自动绑骨、动画或性能质量。截图不替代原会话视觉验收。

## 本地交付门禁结果

正式 `issue_gate.py` 提交前门禁执行一次，退出码 1：`GitHubCommandError`，`GITHUB_RUNTIME: gh executable missing; set GONGGONG_GH to the authenticated host CLI`。返回 incident `6d0e65d84d35c6b809a6b04559fbb194e645056d3d32fa86eaef7817a939b5d3`，状态 `pending_kuafu_intake`。按本次仅本地回交、门禁受阻即停止的约束，没有重试，没有创建候选 commit，也没有执行提交后 `git-check --require-committed`。

HEAD 与 merge-base 仍为开发基线 `d237ef78cc394a98db85b6eb1b39f0184217297d`；16 个变更文件保留为未提交的精确暂存候选。push、PR、CI、main 合入均未执行，Issue 状态未主动推进。最后成功工单回读仍是 intake-only 时的 `status:in-progress`；最终独立 `gh issue view` 与正式门禁均因缺少 `gh` 无法复核当前远端状态。开发自报证据仍需原会话独立验收。

## 2026-11-10 续办：原生补验与交付（开发侧）

以上旧引擎失败和门禁受阻记录保留为当时历史，不被本节倒改。本节只追加续办结果，不能代替原会话的最终独立复核。

1. **原会话已独立通过的范围**：核心 Mesh 功能验收通过，包括真实文字／图片 GLB、固定 Godot 构造、预览发布、重开及 Fit／几何诊断；独立复跑协议与真实 builder 35 tests、两组共 370 个唯一 Python tests（0 failure／error，43 skipped）以及 Workbench GUI 1 test。结论仍限于简单有界原语 Mesh，未扩大到生产拓扑、贴图、动画或任意复杂模型。原报告当时的“完整原生编辑器与交付验收暂未通过”须在最终复核中重新判定。
2. **本轮开发完成的补验**：原 16 文件候选依次无损快进至 `1e5f504d8b12db3c898081bc4ab4db3fa99cb17a`、`b8f4757b3d80d3db2a69bd27576e8f4d6138e1bd` 和本次签发目标基线 `c454886b31c5ada42fc90a3f60d6b63aa88f5987`。这些主线更新均不与原 16 文件产生路径冲突；最后一次仅涉及同目录 `tools/ainative/start_local.ps1` 的 UTF-8 配置读取、宿主脚本及非 Windows 构建的 Linux 头文件等，不是候选文件修改。原候选补丁标识 `96ec985604da0543f042fb606970f62821b6aa6c` 保持不变。已使用 MSVC 14.50.35717／Windows SDK 10.0.26100.0，以主线 `tools/build_gonggong_editor.py` 参数实际构建 Windows x64 编辑器；缓存只改放私有工作区，不改构建参数。69 个静态库目标分组正常结束后，完整 builder 完成链接、缓存发布和 `[AIChat]*` 检查：45 test cases、638 assertions 通过，筛选外 1514 项 skipped。最终基线的构建输入摘要为 `cfddfe8ecf73bca65bbf4032051f4f5c8c2cc1a23851c2713a31ca8c786f819c`，原生缓存键为 `f1517b859a5f44457c93514e84feea46a06bf0ffdd1135ee04b0d4b3284ef776`；SCons 确认目标无需重编译，二进制 SHA 不变，并已在此基线再次通过相同原生场景。后续主线新提交不再造成无限追新，按精确签发回执与仓库合入规则处理。
3. **二进制与资源包**：`bin/godot.windows.editor.x86_64.exe` 为 176584704 bytes，SHA-256 `485bf8e82ff61636c674f543f9493a3bb6e18da5d4909862132739404906e084`；console 为 240128 bytes，SHA-256 `21ec0ad49ab5bde755a8e7f4f292c10deb0ecbc03dc79842d1785f524a669f7c`。版本输出为 `4.8.beta.custom_build`，精确来源由上述基线与候选区分。安装后的 70 个内置资源文件逐一匹配源码 SHA-256，聚合版本为 `ee843c1583d274a7d443717a96719634e23cf57222ca940bd5b8e39bd0644490`，`installed_bundle_matches_source=true`。
4. **真实原生断言**：仓库相对命令为 `python tests/editor/run_ainative_builtin.py --godot bin/godot.windows.editor.x86_64.exe --report <private-report>`；runner 固定 `AINATIVE_PROVIDER_FACTORY=editor_demo:factory`，使用离线合成资产，未发送任何 Kimi 建模 POST。`mesh-and-rig`（108 checks）、`independent-project`（64）、`sample-addon-compatibility`（22）和 `relocated-runtime`（5）均 returncode 0、failures 为空；项目隔离、同引擎资源包及项目源不变均通过。原生插件、马良主屏入口、Kimi 语义 Provider／官方端点／模型设置、双 Mesh 路由、二维拒绝、无密钥保存与真实重开均实际断言通过。编辑器退出日志仍有 RID、ObjectDB 和资源清理诊断，以及 sample 插件 debugger detach 信息；业务断言通过不表示这些清理诊断已消除，本轮未扩大为内存管理修复。
5. **真实事件与交付状态**：新增同租户 `request` 事件，来源精确绑定 Issue #646，摘要只含授权范围；没有模型用量回执，保持 unknown，不伪造消费。正式门禁首次失败是宿主 Python 无法直接启动 shell 版 Node 包装，incident `23824cfc97c79583c98d7e701c87bfc038a9abd7ea2cef28ab729d75e2a9369b`；使用隔离 Node 运行时及正确 PATH 后，可信框架完整性和原正式门禁均已通过，记录为 `quality_issue` 事件。两份事件是相较原 16 文件候选新增的全部公开路径。恢复已认证 GitHub CLI 后，Issue 仍为 `OPEN`／`status:in-progress`；intake-only 已成功，先前一例未传正确租户的 intake 调用错误已纠正，不作为产品缺陷或交付成功证明。候选 commit、签发 head、CI 和 main 合入结果只能在其发生后回读，保留在 PR 时间线与最终回交包，不倒写进更早的候选树；公开 JSON 明确标记其快照时点。
6. **仍待原会话复核**：本轮仅闭合开发侧原生构建／断言、主线对齐和已实际取得回执的 Git 交付步骤。原会话需要独立复核新原生报告、日志与最终 Git 状态，并重新判定完整 Issue #646 验收；本轮不自行宣布整单完成，不将 #646 标为 done 或关闭。
