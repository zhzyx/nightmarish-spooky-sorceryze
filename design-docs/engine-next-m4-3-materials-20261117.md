# Engine Next M4.3 材质扩展

## 当前交付

本分片提供材质覆盖配置的 CPU 解析、校验、源材质解析，以及各向异性 GGX 和清漆共享着色函数。配置入口使用 `material_overrides` 数组，包身份沿用外层渲染配置的 `source_package_sha256`。

`MaterialSettings.h` 定义以下接口。

```cpp
bool ValidateMaterialSettings(const MaterialSettings &, Assets::Diagnostics &);
bool ParseMaterialSettings(const Serialization::JsonValue &, MaterialSettings &, Assets::Diagnostics &);
bool ResolveMaterialSettings(const MaterialSettings &, const RenderScene &,
        std::vector<RuntimeMaterialAsset> &, Assets::Diagnostics &);
```

解析函数接收数组本身。每项使用 `asset_id` 和零基 `material_index` 定位。两项身份字段必填，扩展对象及对象内部字段可选，省略字段使用默认值。

| 字段 | 范围与单位 | 默认值 |
| --- | --- | --- |
| `clearcoat.factor` | 0 到 1 | 0 |
| `clearcoat.roughness` | 0 到 1，感知粗糙度 | 0.1 |
| `anisotropy.strength` | -1 到 1 | 0 |
| `anisotropy.rotation_radians` | -2π 到 2π，弧度 | 0 |

所有数值必须有限，索引必须是可表示为 `uint32_t` 的 JSON 整数。解析器拒绝未知字段、错误类型及重复材质定位。原 JSON 解析器负责拒绝重复对象键，外层配置加载器负责 64 KiB 文件上限。直接 CPU 接口按输入数组和实际材质范围校验。

以下片段指定一项材质覆盖。

```json
{
  "material_overrides": [
    {
      "asset_id": "material.demo",
      "material_index": 0,
      "clearcoat": { "factor": 0.7, "roughness": 0.15 },
      "anisotropy": { "strength": -0.6, "rotation_radians": 0.5 }
    }
  ]
}
```

`ResolveMaterialSettings` 按 `RenderScene.arrAssets` 和各资产的源材质顺序生成独立运行时数组。它复制完整 `MaterialData`，包括纹理索引、透明模式、双面标志和各因子，再附加转换为 binary32 的扩展参数。目标资产不存在、同一资产 ID 对应多个源资产、索引越界或配置非法时，输出保留调用前内容。输入的 M3 包、解码材质、顶点和切线保持只读。

配置结构保留原始 double 数值。运行时参数中低于 binary32 最小正规数的值归零，对齐 GPU 的次正规数处理方式。该转换也使极小强度与零强度遵循同一兼容路由。

## 共享着色数学

`MaterialBuildFrame` 对法线和切线采用缩放归一化，对切线执行 Gram–Schmidt 投影，再用 handedness 构造副切线。旋转在这个带镜像方向的切线框架内执行。退化输入使用有限正交框架。有限大切线先归一化再投影，避免点积溢出改变其投影方向。

感知粗糙度平方得到 GGX 斜率宽度，下限为 0.0025。各向异性长宽比使用 `sqrt(1 - 0.9 * abs(strength))`，负强度交换两个主轴。共享函数计算完整各向异性 GGX 法线分布和高度相关 Smith 可见性。其数学背景参考 Heitz 的微表面遮蔽函数分析及 Disney 的材质参数化。[Heitz 2014](https://jcgt.org/published/0003/02/03/paper.pdf) [Burley 2012](https://media.disneyanimation.com/uploads/production/publication_asset/48/asset/s2012_pbs_disney_brdf_notes_v3.pdf)

底层漫反射使用入射和出射 Fresnel 透射率乘积。清漆固定折射率 1.5，对应 F0 为 0.04；底层漫反射与镜面均乘清漆两次界面透射，再加入清漆 GGX 反射。当前两层共用着色法线。

`MaterialShadeLight` 对省略覆盖以及清漆权重、各向异性强度同时为零的材质调用兼容入口。兼容入口保留既有 GGX 分母下限和 Schlick 几何近似。扩展材质通过新模型返回线性辐射度，预曝光与透明预乘由运行器接线统一处理。

## 环境光积分

`MaterialEnvironment.hlsli` 提供确定性 Hammersley 序列以及底层镜面、清漆、漫反射三种无纹理采样函数。每个函数返回 `Direction`、`Weight` 和 `Pdf`。底层镜面使用各向异性 GGX 半向量分布，清漆使用自身粗糙度的各向同性 GGX 分布；反射方向的概率密度为 `D(H) * NoH / (4 * VoH)`。漫反射采用余弦分布。

`Weight` 已包含对应 BRDF、余弦和概率密度的比值。调用方按方向读取原始环境辐射度，累加加权结果后除以该层总样本数。落入表面下方的反射方向返回零权重，仍计入总样本数。底层与清漆使用独立采样预算，避免重复计入同一层贡献。

环境光和直接光共用 `MaterialEvaluateLobes` 的 Smith、Fresnel 和清漆双透射计算。方向相关的漫反射透射也通过余弦采样积分。运行器可从已有环境资源的第零级读取辐射度，以保留原始方向信息。零参数由 `MaterialEnvironmentUsesLegacy` 选择既有环境光入口。

高质量模式的初始接线预算为底层镜面 32 次、非零清漆 16 次、漫反射 8 次采样。最终预算需要结合真实 GPU 耗时与视觉结果确定。CPU 验证对 72 组材质各使用 8192 个样本，并将四组结果与同一 BRDF 的独立方向网格积分比较。

## 验证方式

正式 `TestMaterialLobes.cpp` 通过 C++ 值类型适配直接包含 `MaterialLobes.hlsli`。独立脚本将测试中的兼容参考与当前 `Deferred.hlsl` 原函数体比较，再分别使用 MSVC 和 clang-cl 编译。共享文件还通过 DXC 的实际 compute 入口编译。

CPU 测试覆盖配置默认、数值边界、重复定位、非法类型、事务回滚、源字段完整复制、缺失资产和歧义资产；着色测试覆盖零参数兼容、各向同性极限、镜像和旋转、主轴交换、清漆双透射、互易性及有限大切线。

白色介质及金属材质的 72 组半球积分采用 256×256 采样，组合粗糙度 0.2、0.5、1，各向异性 -0.9、0、0.9，视线 NoV 0.3、1，以及清漆权重 0、1。该有限采样用于发现能量增长回归，数值结果保存在构建目录的独立测试报告。

## 运行器接线

外层配置先验证源包摘要，再调用材质解析器。运行器在创建材质 GPU 资源前解析每个覆盖目标，将扩展参数写入现有每次绘制常量的尾部。`DrawConstants` 为 288 bytes，预留步长为 512 bytes，已有世界矩阵、前帧矩阵和对象身份的偏移保持兼容。

存在非零扩展参数时，延迟路径增加两个 GBuffer 目标。材质参数使用 RGBA32F，依次保存清漆权重、清漆粗糙度、各向异性强度和旋转；切线使用 RGBA16F 保存世界切向量及镜像符号。参数保留与透明绘制常量一致的 binary32 精度。两个目标按帧持有，几何写入后由光照和反射读取，帧末回到 Common，resize 沿既有 fence 退休顺序释放和重建。

透明网格复用相同 BRDF、环境积分和每次绘制参数。默认材质与显式零参数选用已有透明着色入口，非零扩展使用独立 `MaterialTransparent.ps.cso`。这组 shader permutation 随发布包校验。

环境积分读取原始环境第零级。底层镜面、清漆、漫反射分别使用 32、16、8 个确定性样本。SSR 对扩展材质沿底层和清漆的采样方向执行有界屏幕空间追踪，并按每个样本的置信度组合命中辐射度与环境回退。环境回退乘本帧预曝光，命中颜色已经来自预曝光的非递归辐射图。反射合成用这份完整镜面结果替换对应环境项。

自研 B 场景包含七个球体、一个透明法线面板、地面和背景，覆盖金属、塑料、镜像切线、正负各向异性及旋转。九组固定配置共享同一源包和 GPU 派生包，两次独立生成的十九个文件逐字节相同。

R3、R4 各九组正常入口 GPU 回归完成。R4 修正了参数 GBuffer 的半精度截断，实际读回验证微小正负参数，并检查延迟、透明及 SSR 的资源绑定。R6 的 MSVC 和 clang-cl 各通过 341 项测试、206,466 次检查，九组串行 GPU 配置通过 168 帧验证。附加的 3840×2160 隐藏渲染目标同时启用材质扩展、SSR、TAA、Bloom、体积和未绑定实体的视觉粒子，通过 12 帧验证。真实双客户端输入、最小化与恢复使用 R5 候选，其运行时代码段和 32 份 shader 与 R6 逐字节一致。

固定 32、16、8 次环境采样在高对比太阳环境中出现离散亮点。使用相同 R4 程序、配置、帧常量和 GBuffer，将私有参考 shader 的样本数提高到 512、256、128 后，31,052 个球面内部像素中的局部亮度尖峰从 24 个降至 0 个，平均亮度保持接近。该参考仍有较弱的结构性采样纹理，后续环境重要性采样与完整画质验收继续推进。原低采样结果和高采样参考均保留实际身份。

## 剩余验收

当前采样预算的高对比环境稳定性、原生 4K 性能和 UE 同场景对照继续验证。透射、独立清漆法线、扩展材质纹理、Decal 和面光由后续 M4 工作推进。完整 M4 的 GI、几何流送、动态变形、高细节阴影及长时稳定性由开放父工单跟踪。
