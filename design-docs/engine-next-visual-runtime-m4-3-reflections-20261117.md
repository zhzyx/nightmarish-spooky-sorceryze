<!-- gonggong-request:engine-next-visual-runtime-m4-3-20261116 -->

# M4.3 屏幕空间反射首版

接续曝光与 Bloom 分片，继续 #1343 和父单 #1323。当前分片采用粗糙度相关的屏幕空间反射与既有 HDR IBL 回退，Windows x86_64、MSVC C++17 与 D3D12 为实际 GPU 验证平台。公开接口和 CPU 数学同时做 clang 编译回归。完整 GI、HiZ 加速及 UE 对照沿 M4 后续验收继续推进。

## 渲染流程

反射开关默认关闭。开启时，DeferredLighting 将直接光、漫反射 IBL 和自发光写入 BaseLighting，将预过滤环境镜面项写入独立 EnvironmentSpecular。两者使用当前帧相同预曝光。ReflectionRadiance 先将两项合成完整的非 SSR 辐亮度，生成五级独立降采样纹理，连同原始分辨率组成六级追踪输入。完整辐亮度保留被反射金属表面的环境镜面高光。

ReflectionTrace 从当前抖动深度重建右手视图空间位置，沿镜面反射方向进行逐屏幕像素单元的透视正确 DDA 遍历。射线裁剪到屏幕、相机近平面与远平面及配置距离，最多执行 256 步。深度区间采用 inverse-depth 插值，命中需满足表面厚度、有效深度、最小距离和命中法线朝向检查。边界进入采用整数单元规则，覆盖 4K 与 8K 的负向射线。

粗糙度选择相邻颜色层级并混合。命中颜色乘接收表面的 split-sum BRDF 和 AO，与环境镜面项保持同一单位。ReflectionComposite 输出 BaseLighting 加按置信度混合的环境镜面与屏幕镜面。未命中、屏幕外或预算耗尽使用环境镜面。结果进入现有 TAA、曝光、Bloom 和 ToneMap。

## 配置和生命周期

可选 reflections 对象包含 enabled、max_distance、thickness、normal_bias、max_steps 与 max_roughness，严格验证未知字段及非法数值。所有设置即使关闭也验证。三个正浮点参数需要在 binary32 中可表达为正正常数。原 M3 场景、资产与 GPU Cook 契约继续复用。

每帧槽独占 EnvironmentSpecular、Reflection、ReflectedHdr 与五级颜色纹理，所有读取和写入由 FrameGraph 声明。描述符按资源固定分配，帧槽 fence 完成后复用。Resize 先退休队列，再重建尺寸相关目标。启用反射后的新增实际 D3D12 分配字节单独记录。

## 验收

测试覆盖配置事务、默认兼容、反射开关图结构、透视深度、裁剪、整数像素边界、无效数据、预算耗尽、粗糙度权重、颜色采样和能量合成。自研镜面地面、彩色物体、粗糙度条带及薄遮挡场景通过现有 M3 入口构建。GPU 验收包含开关对照、实际资源数值、屏幕边界回退、相机与物体运动、曝光变化、Resize 和联机回归。

当前 mip-zero 遍历的成本和屏幕信息缺失范围明确记录。独立反射历史、HiZ 加速和完整镜面间接光在后续分片验证。当前分片完成条件为上述功能、必要回归、GPU 图像与捕获、正式提交门禁、精确候选 CI 及 main 回读全部通过。
