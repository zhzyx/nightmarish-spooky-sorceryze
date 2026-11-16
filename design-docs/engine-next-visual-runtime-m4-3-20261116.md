<!-- gonggong-request:engine-next-visual-runtime-m4-3-20261116 -->

# Engine Next M4.3 阴影、后处理和体积

父 Issue #1323，前置 M4.2 #1334 的 Cook 候选为 69c6da448c44200e7f3bff3c5c039e8428b22ebe，签发 PR #1342。M4.3 完成条件依父设计及本工单执行。已授权的具体实现从配置与帧图基础开始，按下列分片逐步交付。参考 PC 为 i7-13700KF、RTX 4070 Ti 12GB，原生 4K High 参数在验证前固定。下列文件、参数和 PR 划分用于执行，尚待实现与实测。

## 已核对的输入

父设计明确 M4.3 包含 CSM、局部阴影、TAA、曝光、Bloom、Tone Mapping、体积、动态透明及反射初版。完整几何层级与流送属于 M4.4，动态 GI 和完整反射属于 M4.5，动态角色和材质剩余项须继续在父单追踪。其当前主张是右手 Y-up 米制、列向量矩阵、D3D [0,1] Reverse-Z、原生尺寸 TAA、固定抖动序列以及按实际代次失效历史。[父设计](../../design-docs/engine-next-visual-runtime-m4-20261115.md)

本地 UE Build.version 标记 5.8.3，Changelist 为 0。已查看 DeferredShadingRenderer.cpp 的阴影深度、反射、体积、透明与后处理调度，ShadowSetup.cpp 的视图相关级联和局部投影，TemporalAA.cpp 的速度与历史曝光校正，PostProcessing.cpp 的 TAA、曝光、Bloom 和 Tone Mapping 顺序，以及 VolumetricFog.cpp 的介质初始化、局部光注入、散射历史和深度积分。以下方案采用这些职责分离和资源寿命原则，具体算法及代码自行实现。[本地 UE Renderer](D:/Projects/UnrealEngine-5.8.3-release/Engine/Source/Runtime/Renderer/Private/DeferredShadingRenderer.cpp)

## 先完成的正常入口改造

现有 VisualRuntime.cpp 将图形 pass 数固定为 5，资源固定为 8，查询数量和描述符索引也按该形状计算。BuildGraph 校验固定 ID 和单个 compute producer，RenderFrame 通过字符串及特定数组下标分派，DrawLighting 在 shader 内直接 tone-map 到 RGBA8。M4.3 第一个 PR 要把这些限制改成有界、按实际编译图生成的结构。

- 新增 Rendering/RenderPipeline.h/.cpp，保存当前帧资源 ID、pass ID 与明确的 PassWork 枚举映射，生成 CompiledGraph。VisualRuntime 继续拥有 D3D12 资源和命令列表，按枚举调用具体录制函数。
- FrameContext 保存按图创建的查询范围和 GPU 资源绑定，FrameTiming 保存与报告 pass ID 对应的时间数组。查询总量由实际图计算，在创建前检查上限。去除 GraphicsPassCount 中默认只有一个 compute pass 的推导。
- 资源绑定表覆盖 persistent 与 frame-local 资源，资源描述包含 format、尺寸、mip、array/depth 和实际初始状态。上一提交完成后的最终状态用于下一图导入，空的历史先清理并标记无效。
- 首条完整 M4.3 路径将新增 compute dispatch 录制在 DIRECT queue 内，保留现有固定测试场景。DIRECT 支持 UAV 与 NonPixelShaderRead，先完成帧间正确性。后续 async compute 优化以明确的所有权转移、实测收益与一致图像为条件。
- FrameGraph 增加 DepthRead 与 ShaderReadAll 状态，D3D12 映射分别支持 read-only DSV 加 SRV、pixel 加 non-pixel SRV。Transparent 采样深度及绑定 read-only DSV 使用同一合法状态。新增同帧 bloom mip 级和跨帧 history 访问测试。

当前 DrawConstants 已有 52 个 32-bit root constants，额外 previous matrix 会超过根签名预算。改为 FrameConstants、DrawConstants 的 CBV，256 字节对齐，frame-owned 上传区，描述符表继续复用。GPU 常量结构放入 Rendering/ShaderParameters.h，通过 sizeof/offsetof/static_assert 与 shader 测试核对。FrameConstants 提供 current/previous view-projection、inverse view-projection、相机相对原点、viewport、near/far、jitter、pre-exposure 和帧号。所有深度重建统一走矩阵，替换当前固定 camera z、FOV 和轴对齐重建公式。

HDR lighting 和后续中间图使用 RGBA16F。最终 SDR display target 继续 RGBA8，Tone Mapping 后进行既有 CopyToBackbuffer。Shader 输出的 transfer function 与 swapchain 显示格式集中定义，确保每帧只转换一次。

## 渲染配置与 M3 边界

新增 include/EngineNext/Rendering/RenderConfiguration.h、Rendering/RenderConfiguration.cpp 及 Schemas/RenderConfiguration-v1.json。CLI 增加 --render-config，沿用 next_visual_client 正常入口。配置以源 scene/package digest 绑定，引用 EntityId、glTF node/primitive 和 material index，保持 Assets::SceneDocument v1、AssetRef 三元组和 M2 协议原样读取。

配置包含相机、灯光、阴影质量、曝光、后处理、全局与局部雾、透明排序策略、固定种子粒子及基准动画轨迹。RenderSnapshot 保存该帧采样结果和配置代次。坐标单位、角度单位、有限值、范围、重复标识、未知字段、错误引用和总数预算在加载时验证。缓存使用 source digest 加配置 digest，渲染配置变化触发相应 history invalidation。

- 方向光采用 lux，point/spot 采用 lumen，并在统一转换函数中得到 shader 强度。灯光记录方向、位置、范围、spot 内外角、shadow enable 与 bias。
- 常规 alpha BLEND 已存在 MaterialData，先让透明 pass 消费此值。新增 transmission/IOR/thickness 等覆盖字段进入渲染配置和运行时材质描述，其验证与 GPU Cook 算法版本单独更新。HDR、temporal 和 volume 所需每个 shader entry 离线编译，BuildVisualRuntime.py、PackageVisualRuntime.py 及 RunM42BuildImpact.py 中既有固定七个 shader 清单同步扩展，所有实际输出写入来源清单。
- 基准移动对象和灯光使用渲染层可重放轨迹。网络刚体继续消费现有 ClientSession snapshot。完整 skin/morph 动态角色继续列为父单待实现项，PR 验收分别标注实际支持内容。

## 文件级实施与并行归属

| 归属 | 文件 | 正常入口及内容 |
| --- | --- | --- |
| 集成 owner | VisualRuntime.cpp、ShaderParameters.h、RenderPipeline.h/.cpp、FrameGraph.h/.cpp | 常量、资源、pass 调度、history 同步、HDR、报告与平台生命周期 |
| 配置 owner | RenderConfiguration.h/.cpp、对应 Schema、TestRenderConfiguration.cpp | 配置解析、灯光/雾/轨迹验证、Source digest 绑定，供 Snapshot 与 pipeline 使用 |
| 阴影 owner | ShadowData.h/.cpp、Shaders/Shadow.hlsl、TestShadowData.cpp | CPU 投影/级联分配、caster 列表、shadow 常量及采样函数，集成 owner 创建实际 D3D 资源 |
| 时域与后处理 owner | TemporalState.h/.cpp、PostProcessSettings.h/.cpp、Shaders/Temporal.hlsl、Shaders/PostProcess.hlsl、对应 tests | 稳定 history key、jitter、reprojection、曝光、Bloom、Tone Mapping |
| 反射与体积透明 owner | ReflectionSettings.h/.cpp、VolumeData.h/.cpp、Transparency.h/.cpp、Shaders/Reflections.hlsl、Shaders/VolumetricFog.hlsl、Shaders/Transparent.hlsl、对应 tests | SSR 追踪、体积参数/积分、透明排序和粒子数据 |

一个 owner 修改 VisualRuntime.cpp、ShaderParameters.h、构建源列表、shader 打包清单及公共资源枚举。其他工作者交付 CPU 模块、shader entry、绑定表和测试，先约定常量结构与资源读写清单。配置与反射/体积可串行由同一工作者完成，适配当前并行槽数。

## PR1 配置、HDR、帧图与历史基础

入口仍为 next_visual_client --asset-package ... --gpu-package ... --render-config ...。新配置缺省值显式对应旧相机/灯光，用单独基准配置开启 M4.3。加入全尺寸 velocity RG16F、稳定 object ID R32_UINT、linear depth 或可重建 depth，以及 HDR 图。

历史按最后成功提交的画面推进，使用稳定键 EntityId/node/primitive 加 session/config/resource generation。previous world 来自上一提交的 RenderSnapshot，不能按 swapchain buffer index 选择。相机 cut、resize、最小化恢复、reconnect、teleport、材质和轨迹跳变使对应历史失效，记录原因位。previous transform 在 GPU 读取完成前由所属 frame 保存。

两个 HDR history 资源沿 DIRECT queue 顺序交替，previous depth/normal/ID 采用相同提交帧配对并明确存储，导入时声明精确状态。CPU 复用上传区前等待 frame fence，resize 和 shutdown 延续现有全部使用队列退休规则。初次使用写当前结果，previous 数据绑定已初始化资源，历史权重为零。

PR1 验证旧 fixed 场景、M4.2 v1/v2 资产入口、相机矩阵正逆与 Reverse-Z、描述符及根签名预算、图形/compute pass 查询映射、resize/minimize/reconnect 后代次失效。

## PR2 CSM 与局部阴影

方向光使用 4 cascade、固定 shadow distance、practical split 参数和过渡区。每级在 unjittered camera frustum 上构造 receiver 范围，light-space texel snapping 稳定投影。采用父设计 High 的 4096 atlas 起始配置，初始 2×2 放置四级，实际每级分辨率写入配置和报告。稳定朝向与深度扩张由场景 caster bounds 决定。

caster 列表按 light volume 构造，包含屏幕外遮挡物。点光 cube 为 6 个 D32 array slice，spot 使用固定 tile atlas，灯光稳定 ID 决定稳定布局。数量/分辨率预算在配置中固定，超额提供明确诊断。初期每帧重画需要的 shadow，缓存和虚拟页在后续阶段实施。

Shadow.hlsl 提供 depth-only opaque 和 alpha-test entry。双面、负缩放、alpha cutoff 与主材质保持一致。ShadowData 统一声明 shadow depth 约定，推荐沿用 Reverse-Z，clear=0、GREATER_EQUAL 及 comparison sampling 的 receiver bias 同步验证。PCF 先有固定 tap 成果，再加入有界 blocker search 与 PCSS penumbra，参数及采样数写入报告。

DeferredLighting、Transparent、VolumetricFog 共享相同 light/shadow 数据和 sampling helpers。验收包括 cascade 边界、相机微移稳定、moving light/caster、spot cone、point cube 接缝、屏幕外 caster、MASK 叶片、镜像实例、bias/peter-panning 和 GPU validation。

## PR3 TAA、曝光、Bloom 与 Tone Mapping

Deferred.hlsl geometry entry 输出 jittered raster position、current/previous unjittered clip position 和 object ID。velocity 定义为 previousUV-currentUV，屏幕 y 翻转集中处理。相机平移、旋转和刚体 motion 各自有静止背景对照，后续 skin/morph 接入相同 previous pose 契约。

Temporal.hlsl 以 HDR、depth、normal、velocity、ID、reactive mask 与 previous history 为输入，依次做重投影、越界/代次/深度法线身份拒绝、邻域/variance clipping 和有界 history 混合。抖动采用固定 Halton(2,3) 序列及明确像素单位，原生尺寸输出。HDR history 在使用前按 currentPreExposure/previousPreExposure 比值校正，debug 输出权重及拒绝原因。

PostProcess.hlsl 包含 histogram clear/build/reduce、exposure adaptation、Bloom downsample/upsample、ToneMap entry。histogram 中心亮度从 pre-exposed HDR 恢复场景亮度，曝光值经有限范围钳制，dt 有上限。当前帧 lighting 使用上一已提交曝光，新曝光用于显示并供下一帧使用，Tone Mapping 仅应用所需比值。manual EV100 模式固定曝光，自动曝光单独运行暗室/室外轨迹。

Bloom 每个 mip 为独立子资源，downsample、upsample 分别声明读写。Upsample 写目标另分配资源，避免同层 SRV/UAV 冲突。最终按确定曲线 tone-map 至 Rec.709，保留 pre-tone-map HDR 采集入口及曲线版本。PR3 验收包括细线/栅栏静止与横移、快速遮挡、teleport、透明 reactive、曝光步进、灰卡与高亮过渡、Bloom 溢出和 history NaN 检测。

## PR4 初版 SSR

SSR 先在 lighting direct+IBL 结果上产生反射候选，再合成 replace-weighted IBL specular，保存 IBL specular contribution 使替换时能量明确。这样每个 ray 使用当前 opaque HDR，图中存在清晰的 LightingBase→SSR→ReflectionComposite 依赖。

Reflections.hlsl 使用 depth min/max mip 或明确保守约定的 reverse-depth hierarchy，屏幕投影 DDA/hierarchical traversal，有限步数、厚度、最大距离和 roughness 范围。该 depth pyramid 仅作为反射数据，后续 M4.4 culling 复用前再核其语义。trace 输出 radiance、confidence、hit distance；bilateral resolve 结合 depth/normal/roughness，miss 由既有 IBL 贡献接管。首次 PR 使用固定空间 resolve，时域反射 history 随 TemporalState 契约增加，避免把 TAA history 同时作为当前光照输入形成环。

验收包含粗糙度阶梯、镜面薄物体、屏幕边缘/屏幕外、掠射、远近相交、相机 cut，以及 SSR confidence/fallback 可视化。DXR offscreen coverage 继续归 M4.5。

## PR5 Froxel、透明与确定性粒子

VolumetricFog.hlsl 分为 medium setup、light injection/scattering、temporal reprojection、front-to-back integration、opaque composite。初始 froxel 网格按父设计 480×270×64 和 log-depth，RGBA16F 单 volume 约 63.3 MiB。extinction、scattering albedo 和 HG g 有有限范围，世界空间高度雾和局部 box/sphere 体积以确定顺序组合。

积分存储 accumulated scattering 与 transmittance，按实际 segment length 计算 Beer-Lambert 衰减。历史以 previous camera、体积/光源代次和 pre-exposure 校正，newly exposed cells 权重清零。GPU debug counters 记录 NaN、负 extinction、超预算和历史拒绝。局部光贡献复用 PR2 shadow 数据。

Transparent.hlsl 首批实现常规 alpha BLEND，稳定排序键为 view depth 加 EntityId/node/primitive。RenderScene 中分离 opaque、MASK、BLEND draw 列表。opaque HDR 保留只读副本供折射，透明目标独立，主 depth 采用 read-only DSV。每个透明片元按自身深度采样累计 fog，再合成，避免所有透明面统一使用 opaque depth 的雾。

动态粒子由固定种子和 RenderSnapshot time 生成有界实例，输出 velocity、soft-depth fade 和 reactive mask。基准先冻结 alpha/additive 模式及最大粒子数。复杂交叠的正确排序仍由后续独立透明 PR补齐 PPLL 或已验收等效方案，其 capacity/overflow 作为显式失败诊断；父级完整透明验收保持跟踪。

验收包括 homogeneous fog 解析值、零密度、极薄/高密度、g=0/0.5/0.8、背光柱、local volume 边界、moving shadow/light、透明前后交叉、soft particles、固定轨迹逐帧重放和历史失效。

## 完整图的起始顺序

ShadowDepth → GBuffer/Velocity/ID → DepthPyramid → LightingBase → SSR/Resolve → ReflectionComposite → FogScattering/History/Integration → FogOpaqueComposite → Transparent → TAA → Histogram/Exposure → Bloom → ToneMap → CopyToBackbuffer → Present。

ShadowDepth 与 GBuffer 分别从同一 snapshot 读取矩阵及材质。Fog 介质初始化可提前录制，使用 shadow 的 scattering 保持显式依赖。后处理可以在 DIRECT queue 上使用 compute PSO。图谱报告记录真实 pass、子资源、状态、尺寸、调度及时间，性能分析按当前队列频率分别计算。

## 主要风险与收口条件

1. 当前根常量预算、固定 pass/query/descriptor 形状会先阻塞新增功能，PR1 必须先落地。
2. 三个 frame-local HDR 图、两帧 history、velocity/ID/depth 和多个 3D volume 容易新增数百 MiB 显存。以 GetResourceAllocationInfo 和 DXGI budget 记录实际 committed/transient/history 占用，资源创建前检查总预算。M4.3 首版保持资源寿命可审计，alias 优化随后依据真实 happens-before 实施。
3. previous frame 的定义需要跟提交顺序一致，swapchain 顺序、网络 tick 和 presentation frame 各有独立编号。cut、最小化和重连用代次驱动历史重置。
4. 相机旋转、矩阵重建、Reverse-Z shadow compare 与 texel snapping 是跨 CPU/HLSL 高风险点，各自建立 golden 与动态图像用例。
5. WIC 派生纹理、颜色空间、pre-exposure 与 Tone Mapping 需要共同冻结，v2 Cook 摘要与 shader/PSO 摘要共同进入场景证据。截图差异以 HDR 与最终 SDR 分别归因。
6. 初版 SSR 和 sorted transparency 各有覆盖边界，报告包含 hit/miss/overflow/排序案例。完整父验收继续要求后续实际证据。
7. 每 PR 合入前运行 portable math/graph/config tests、Windows完整资产入口、v1/v2包、validation下resize/reconnect，再运行对应 A–F 轨迹。最终原生4K吞吐和UE同参数对照待真实条件具备后执行，阶段功能测试使用其实际输出尺寸标注。

## 本地参考源定位

- 阴影职责和 caster 范围参考 ShadowSetup.cpp、ShadowDepthRendering.cpp、ShadowRendering.cpp。[ShadowSetup.cpp](D:/Projects/UnrealEngine-5.8.3-release/Engine/Source/Runtime/Renderer/Private/ShadowSetup.cpp)
- 后处理顺序与历史校正参考 PostProcessing.cpp、TemporalAA.cpp、PostProcessEyeAdaptation.cpp、PostProcessTonemap.cpp。[PostProcessing.cpp](D:/Projects/UnrealEngine-5.8.3-release/Engine/Source/Runtime/Renderer/Private/PostProcess/PostProcessing.cpp)
- SSR 的 depth hierarchy、ray result 与历史依赖参考 ScreenSpaceRayTracing.cpp。[ScreenSpaceRayTracing.cpp](D:/Projects/UnrealEngine-5.8.3-release/Engine/Source/Runtime/Renderer/Private/ScreenSpaceRayTracing.cpp)
- 体积的 medium、scattering、integration 与 history 分离参考 VolumetricFog.cpp。[VolumetricFog.cpp](D:/Projects/UnrealEngine-5.8.3-release/Engine/Source/Runtime/Renderer/Private/VolumetricFog.cpp)
- 透明输出及 SceneColor 采样副本参考 TranslucentRendering.cpp。[TranslucentRendering.cpp](D:/Projects/UnrealEngine-5.8.3-release/Engine/Source/Runtime/Renderer/Private/TranslucentRendering.cpp)
