# Engine Next M4.5 动态 GI 与探针运行时

本阶段对应 Issue #1505，依据父 Issue #1323 与 [M4 总体设计](engine-next-visual-runtime-m4-20261115.md)，交付请求为 `engine-next-visual-runtime-m4-5-20261118`。早期配置、数学和 GPU 实验沿 Issue #1343 的请求执行，原始测试和事件保留当时身份，正式交付追加本阶段关联。

当前增量实现独立配置、clipmap 探针、BLAS/TLAS 更新、硬件 inline ray query、SH9 与距离矩历史，以及 deferred/forward 漫反射消费。原始 M4.5 范围还包括完整 specular 间接光、动态角色、去噪和 A/B/D/E 参考场景验收，阶段工单持续跟踪这些要求。

## 阶段验收与交付边界

- 动态 diffuse 多反弹、自发光、动态光源与动态几何更新必须产生真实可见且稳定的间接效果。
- Specular 间接光、SSR 与 probe/IBL 回退需要在相同材质和曝光下核验。
- 更新预算、去噪、历史拒绝、漏光和残留需要动态视频及 GPU 读回证据。
- A、B、D、E 场景保留完整要求，并与相同资产、相机、曝光和灯光的 UE 5.8.3 场景对照。
- 当前基线的贴面探针起点退化、既有阴影条纹和最终画质仍需后续实现与验收。基础增量通过后，M4.5 与父 M4 保持开放，直至完整范围满足。

## 配置与范围

新增 `GlobalIlluminationSettings` 和独立 `ParseGlobalIlluminationSettings`，预留 `global_illumination` 对象入口。现有 RenderConfiguration 与 M3 文件契约保持现状。所有字段可省略，未知字段拒绝，禁用状态仍检查内容。解析、预算与格子构建失败时保留调用方输出。

| 字段 | 默认 | 合法范围与语义 |
| --- | --- | --- |
| enabled | false | 布尔 |
| world_bounds.minimum / maximum | [-12,-4,-12] / [12,20,12] | 第零级轴对齐包围盒，单位米，严格递增 |
| probe_counts | [24,24,24] | 每级包含两端点，各轴至少 2，总探针最多 65536 |
| clipmap_levels | 3 | 1 至 3，外层尺寸固定乘 2 |
| updates_per_frame | 128 | 1 至 65536，实际批次取探针总数与该值的较小值 |
| rays_per_probe | 32 | 16 至 1024，每个更新探针的方向采样数 |
| trace_distance | 50 | 正常 binary32 正数，转为 float 后的平方仍有限 |
| hysteresis | 0.95 | 0 至 0.99 |
| normal_bias / view_bias | 0.05 / 0.1 | 非负有限 binary32 范围，极小值转零允许 |
| bounce_strength | 1 | 0 至 1，漫反射反馈乘数 |
| history_change_threshold | 0.2 | 0 至 1，零仅允许相同 GPU 信号继续使用历史 |
| max_gpu_bytes | 134217728 | 显式正字节预算，最高 536870912 |

包围盒及各级全部探针坐标必须能表示为严格递增的有限 float，cell spacing 必须是正常 float，且按 `1.0F / float(spacing)` 计算的 inverse spacing 必须保持正的正常 float，以满足 GPU 常量缓冲中倒数坐标映射的 FTZ 边界。上传坐标中的 subnormal 分量显式归零，归一化后仍须严格递增。CPU 保存配置 double 原值，GPU 上传时进行 float 转换。非常小的 history threshold 可转零并沿用零阈值语义。trace distance 必须在 GPU 上保持正值，因此采用正常 binary32 下界。

父设计 High 的 24³ 三层可以表达。父设计 Ultra 的 32³ 三层超过当前 65536 探针上限，后续必须结合真实显存和更新成本提高已验证上限后验收。当前预算与默认更新数量属于可执行实现边界，质量档仍需 A/E 场景测量后冻结。

## 格子与更新

`BuildProbeGrid` 保持配置中心，各层使用同一计数并逐级扩大两倍。`SnapProbeGrid` 接收相机中心，为每级按 cell spacing 吸附到最近整数中心，恰好半格向远离零方向取整。输出位置的 xyz 为世界坐标，w 为层号。索引依次按 x、y、z、level 增长，层偏移显式存储。

`BuildProbeUpdateIndices` 使用成功 GPU 提交的序号计算有界循环批次。序号先模探针总数再乘实际更新数量，UINT64_MAX 也保持定义明确。函数自身没有隐藏可变状态。调用方只在提交成功后推进序号。

运行时需要以世界 cell 身份判断跨格后的保留、迁移和失效。新增格子清空 SH 与距离矩有效状态，重叠格子复制到新快照，旧 GPU 读者完成 fence 后才退役旧快照。当前 CPU 模块仅输出新布局。相机 cut、包围盒或计数变化、场景几何版本变化都需要明确的历史失效策略。

默认 41472 探针以每次 128 个更新需要 324 次成功提交完成一轮。真实运行时需要结合可见接收面、最老采样年龄、光源变化与几何 dirty 区域选择优先更新，才能满足父设计动态响应。固定轮转函数保留为有界公平的基础路径。

## 数据布局与预算

每探针使用九个 float4 SH 系数，RGB 为带符号系数，w 保留。方向相关距离矩为 8×8 个 float2，保存归一化距离的一阶和二阶矩，归一化除数为 trace distance。世界距离由归一化量乘 trace distance 还原，最小正常 trace distance 也可以使用而不会要求存储其原始平方。距离方向通过八面体映射查询，边界采样需要折叠处理。单个全方向平均距离无法表达遮挡方向。

| 数据 | 每元素字节 | 数量 |
| --- | --- | --- |
| SH9 | 144 | 两组 history × N |
| 距离矩 | 8 | 两组 history × N × 64 |
| 探针有效状态与版本 | 16 | 两组 history × N |
| 世界位置与层号 | 16 | N |
| 光线 radiance / distance | 16 | 三帧 × U × R |
| 光线结果状态 | 16 | 三帧 × U × R |
| 更新探针索引 | 4 | 三帧 × U |

预算公式为 `1360*N + 96*U*R + 12*U` 字节。默认总数为 56796672 字节。C++ 结构通过 static_assert 绑定 stride。HLSLI 的 GiSh9 是本地数学表示，读写 GPU float4 buffer 时须显式装载和存储 RGB。

此预算覆盖所列 GI buffer。D3D12 resource allocation 对齐、descriptor、BLAS/TLAS、构建 scratch 和既有 framebuffer 由运行时单列并纳入整机显存预算。物理 GPU allocation 结果仍须通过 GetResourceAllocationInfo 记录。

## 数学与历史

生产 `ProbeMath.hlsli` 由 C++ shim 直接包含进行测试。SH9 使用真实球谐基，余弦卷积的 l0、l1、l2 系数分别为 π、2π/3、π/4。缓存计划保存未预曝光的物理 radiance，消费端应用本帧曝光。这样 probe history 不依赖屏幕 TAA 的曝光单位。

距离矩的 Chebyshev 可见性采用距离尺度归一后计算方差与偏差，避免固定 epsilon 吞掉小尺度数据，也避免平方溢出。亮度历史拒绝使用原始当前与历史信号的相对差，先比较再做插值。零 threshold 对相同信号保留 hysteresis，对任何可见差异拒绝历史。非有限输入走明确的失效结果。

CPU 基础 Lambert 模型的反馈漫反射为 `direct + previousIrradiance * albedo * bounceStrength / π`。实际 GI shader 对既有材质采用相同的 Fresnel 漫反射系数，对扩展材质按其 Schlick/clearcoat 传输计算 l0..l2 精确卷积，并在反馈和 receiver 共用系数。有界反照率下的迭代收敛有独立回归；理想全白封闭环境仍需运行时采样与能量限制审查。SH 系数允许负值，最终 irradiance 才截为非负。极端 finite 输入的乘加采用有限范围保护，真实场景必须另外验证能量守恒与泄漏。

## GPU 实现与后续验收

运行时为相关离屏实例创建 BLAS/TLAS，记录静态构建、动态更新、scratch 和 fence 生命周期。Opaque、MASK 材质遵循当前 raster alpha 语义，透明参与 GI 的策略仍需完善。基础 BLAS/TLAS 后端已经过独立硬件 Inline RayQuery 测试，覆盖 MASK、空场景、实例变换、正反面与 fence 退休。完整探针场的 direct lighting、environment miss、自发光与反馈已接入运行器，真实场景验收持续推进。

推荐 FrameGraph 顺序为 acceleration structure 更新、选择探针、trace、SH/距离矩聚合、历史合成与光照消费。未更新的有效探针必须从已提交 history 延续，首次历史先初始化。资源切换与更新序号都在提交成功后生效。

后续按 A 的双拐角、遮光薄墙、红绿反弹、离屏 emissive、灯光开关和动态遮挡验收，同时记录更新延迟、漏光、历史残留、GPU 预算与内存。E 继续验证动态角色 BLAS、快速运动与 camera cut。该分片的 CPU 测试不能代替这些真实 GPU 结果。

## 架构参考

只读参考本机 UE 5.8.3 的 `Renderer/Private/Lumen/LumenRadianceCache.h/.cpp` 中只读更新输入、有效状态、trace budget 与外部历史资源职责，`LumenRadianceCacheInternal.h` 的持久 cache 与 RDG 读写资源职责，以及 `LumenScreenProbeFiltering.cpp` 的历史拒绝与过滤职责。审查额外核对 RadianceCache 的 clipmap、更新预算、历史重映射和硬件 trace 调度。当前实现采用自有数据结构和公式，没有复制 UE 实现代码。

当前阶段尚未进行 UE 同资产画质对照。
