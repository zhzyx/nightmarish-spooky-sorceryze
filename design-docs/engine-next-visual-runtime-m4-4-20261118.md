<!-- gonggong-request:engine-next-visual-runtime-m4-4-20261118 -->

# Engine Next M4.4 — GPU 驱动几何、LOD 与流送

## 需求身份与执行决定

- 需求 ID 为 `engine-next-visual-runtime-m4-4-20261118`。
- 类别为 `type:development`，本阶段 Issue 为 [#1506](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1506)。
- 原生父 Issue 为 [Engine Next M4 #1323](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1323)。
- 用户已明确要求落地完整 M4。2026-11-18 回读原始附件，GPU 驱动几何与流送归入 M4.4，动态 GI 归入 M4.5。
- Codex 负责实现与回归，独立审查由其他工作者承担。阶段可分批提交，整体验收未完成时保持本阶段及父单开放。
- 既有 #1343 下的几何实验、测试和 GPU 记录保留原始身份。新工单接收这些历史观察及当前精确候选，新增正式记录绑定本需求。

## 原始需求与完整范围

依据父设计保存的原始 M4 需求，建立自有 Cluster / Virtualized Geometry 路线，完成以下范围。

1. Mesh Cluster 生成、局部索引、保守包围体与几何优化。
2. GPU 实例数据、视锥剔除、反 Z Hi-Z 遮挡剔除及 GPU 驱动间接绘制。
3. Cluster 层级与 LOD 选择，依据屏幕误差和覆盖率控制细节，保证层级覆盖及过渡稳定。
4. Mesh 与 Texture Streaming，按屏幕覆盖率请求页面、处理缺页并管理常驻数据。
5. 显存、暂存内存、上传带宽和常驻资源预算，包含后台加载、提交 fence、失败回滚和安全淘汰。
6. 自研 C 场景至少 1000 个实例、1000 万个展开场景三角形，包含建筑、植被、岩石或同级复杂内容，覆盖移动视角和冷热流送。
7. Culling、Cluster、LOD、Streaming 调试视图及实际实例、三角形、间接命令、缺页、常驻页和 CPU/GPU 耗时统计。
8. 高细节虚拟阴影页或等效路线，包含页请求、驻留、动态失效、缓存复用和更新预算。
9. 保留 M2 权威模拟、预测、插值和重连语义，保留 M3 资产身份及原始文件格式，保持材质、Alpha Test、双面、负行列式、运动历史和阴影正确性。

传统 LOD 兼容路径继续可用。Nanite 同级能力的结论须具备完整层级、分页、负载、画质和时序证据。

## 渲染与数据方案

### Cluster 与实例

渲染层沿用现有 `MeshPrimitive` 和每簇 64 顶点、126 三角形上限。源包使用原 M3 `.enpak`、AssetManifest、SceneDocument、资产 ID、revision 和 blob 摘要。缺少预烘焙簇的旧 GPU 包通过相同 CPU 生成器准备簇。

当前间接命令保存 64 位 DrawConstants GPU 地址及 `D3D12_DRAW_INDEXED_ARGUMENTS`，总步长 32 字节。实例变换来自已提交时域状态的当前帧矩阵，DrawKey 继续使用实体、资产、primitive 和 glTF node。材质及绕序桶仅分配各自真实容量。后续 GPU 批量实例化复用相同身份映射并减少重复命令。

### 显式帧图

正常场景入口执行 `GeometryUpload → GeometryCullDepth → GeometryDepth → GeometryHiZ → GeometryCullColor → GBuffer`，清计数、读回和资源退休独立声明。深度预绘制与 GBuffer 使用同一当前相机抖动、实例变换、Alpha Test 及双面绕序规则。Hi-Z 使用反 Z 最小值约简，近平面相交和不可稳定投影的包围体保守保留。

相机遮挡结果用于相机可见性。阴影保持各光源视图的完整几何覆盖，后续光源 GPU 列表采用独立剔除与更新依赖。

GPU 参数、UAV、间接参数和 CopySource 的状态均由 FrameGraph 管理。不可变上传参数采用 GENERIC_READ。所有资源在所属 graphics fence 退休后才能重写、回收或替换。发生可恢复的命令或分配容量不足时，采用完整传统绘制路径并记录原因。

### 虚拟阴影页

按父设计阶段表将 virtual shadow pages 纳入本阶段。阴影页请求由光源视图与接收者覆盖产生，按页记录静态缓存、动态投影者失效、清页和重绘。高细节页面分辨率、常驻页数与每帧更新量均显式受预算约束。移动光源、投影者、接收者和相机时检查缓存过期、漏影、边界接缝与精度。现有 CSM/局部阴影保持兼容路径，虚拟页或等效高细节能力单独完成验收。

### 分页、LOD 与流送

后续独立 GPU Cook 产物保存页表、簇层级、父子覆盖关系、几何误差及纹理 mip 依赖，继续绑定原包摘要。旧 v1/v2 包保持加载路径。每个新布局明确版本、大小、范围、对齐及预算，所有输入校验先于分配和发布。

页面状态至少区分未驻留、加载、上传待退休、驻留和淘汰待退休。CPU 文件加载与 GPU 上传分离。generation 标记抵御旧完成回调，取消和失败释放对应预留量。淘汰排除被在途绘制引用的页面，当前可用的父层或兼容几何维持覆盖。记录真实缺页、重试、上传字节、完成 fence 和常驻预算。

LOD 基于投影误差选择并约束相邻层级覆盖，视角移动、历史失效和层级切换纳入时域检查。Texture Streaming 使用同一屏幕覆盖反馈与独立格式/mip 预算，保留 sRGB、法线、采样器和材质槽语义。

## 文件级实施分批

| 批次 | 文件与行为 | 独立验收及剩余边界 |
| --- | --- | --- |
| 1 | `GeometrySettings`、`GeometryCulling`、`GeometryScene`、`GpuGeometry`、Geometry shaders、RenderPipeline 与 VisualRuntime 接线 | 簇范围、GPU 剔除、间接绘制、兼容与资源生命周期。当前工作树已实现并正在整理正式交付证据 |
| 2 | GPU Cook 层级与页面布局、LOD 构建/选择、对应 CPU/HLSL 测试 | 完整簇覆盖、误差约束、移动视角和 LOD 时域稳定 |
| 3 | 页面驻留、后台加载、上传/淘汰、Mesh 与 Texture Streaming 接线 | 最坏预算、缺页、失败、并发、重试、冷热启动及无缺失覆盖 |
| 4 | 虚拟阴影页/缓存、失效与更新调度 | 高细节阴影页面、动态更新、预算、缓存命中和边界验证 |
| 5 | 自研 C 复杂场景、诊断视图、动态和性能整体验收 | 实际 1000 实例/1000 万三角、帧时间、显存、流送、连续运行及父级集成 |

批次 1 的球体阵列提供精确负载基准，场景包含 1000 个 glTF node 实例、每实例 10000 三角形和 166000 个簇。后续 C 场景按完整内容要求扩展。分页、层级 LOD、流送与虚拟阴影页/缓存在当前批次仍待实现。

## 验收标准

- [ ] Cluster 和实例覆盖源几何，v1/v2 与新页格式保持身份和材质一致。
- [ ] 视锥、反 Z Hi-Z、间接绘制和 GPU 实例路径可由实际命令/资源读回核验，容量不足保持完整可见内容。
- [ ] 层级 LOD 依据屏幕误差工作，移动相机和 LOD 切换通过历史、突跳和边缘检查。
- [ ] Mesh/Texture Streaming 在有界显存和上传预算下工作，缺页、后台完成、失败重试与淘汰满足 fence 和 generation 生命周期。
- [ ] 高细节虚拟阴影页或等效路线完成，动态失效、缓存复用、页预算、阴影边界和投影者更新通过验证。
- [ ] C 场景达到至少 1000 实例和 1000 万场景三角形，主要绘制路径采用 GPU 命令生成与间接提交。
- [ ] 材质、双面、Alpha Test、透明、负行列式、阴影、运动与 M2/M3 必要回归通过。
- [ ] 调试视图和计数覆盖 Culling、Cluster、LOD、Streaming，包含 CPU/GPU 时间、P95/P99、1% Low、显存、页和上传统计。
- [ ] 真实 GPU Capture、当前二进制输出、重复视角轨迹和冷/热流送证据绑定源、shader 与场景摘要。
- [ ] 干净独立构建、同二进制 shader 更新/拒绝/回滚、适用跨平台 CPU 测试和候选 CI 通过。
- [ ] 原生 4K 与完整画质集成性能进入 M4.6 复验，父级平均 120 FPS、1% Low 90 FPS 和 30 分钟稳定性保持原始目标。

## 当前观察与正式归属

历史 #1343 候选已记录 359 个完整 C++ 测试、206731 次检查，以及 19 组 GPU 正常入口、40 帧和 11 组零像素差异比较。1000 实例/1000 万三角负载得到 153293 条视锥后命令，Hi-Z 后为 106767 条命令和 6512552 个 GBuffer 三角形。这些验证属于首批行为，验证层模式单帧数据不承担最终帧率验收。

D3D12 关于 ExecuteIndirect 改写 root binding 的验证精度提示保留在报告中，命令缓冲与实际 CBV 的独立捕获核查正在执行。初版基准配置缺少必填项的失败回执保留，修复后的五份配置已由实际 C++ 配置加载器校验。

现有公开历史记录位于 `data-collection/engine-next-visual-runtime-m4-3-geometry.json`。新正式观察以本 M4.4 需求和实际 Issue 关联，引用历史文件时保留其原 request/Issue 身份。

## 依赖、参考与整体验收

M1/M2/M3 已交付契约及 M4.1 RHI、M4.2 GPU Cook、M4.3 时域/阴影/体积是依赖。后续动态 GI 由 [M4.5 #1505](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1505) 跟踪。几何与并行 M4.5 GI 的 FrameGraph 和 descriptor 接线在整合时统一回归。

本机 UE 5.8.3 Nanite 仅用于理解层级选择、可见性、页反馈和资源生命周期职责。实现使用本项目代码及公开算法语义，引用来源另存实际审查记录。UE 同资产、相机和完整画质对照及最终性能保持父级验收责任。

父单完整设计与原文见 [M4 设计](engine-next-visual-runtime-m4-20261115.md)。本阶段完整范围未验收前，增量 PR 仅引用本 Issue，不自动关闭本阶段或父单。
