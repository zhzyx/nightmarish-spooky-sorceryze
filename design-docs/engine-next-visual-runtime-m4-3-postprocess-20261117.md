<!-- gonggong-request:engine-next-visual-runtime-m4-3-20261116 -->

# M4.3 曝光与 Bloom 分片

接续已合入的 TAA PR #1384，继续 #1343 与父单 #1323。曝光、Bloom 和诊断使用独立 D3D12 资源及显式 FrameGraph。M3 的资产标识、SceneDocument、GPU Cook 与网络协议沿用现有契约。

## 配置与数学

旧数值字段 exposure 保持原倍率含义。可选 exposure_settings 提供 legacy、manual 和 automatic 模式。Manual 以 EV100 与补偿计算曝光倍率，标定常数为 1.2。Automatic 从 256 桶 log2 亮度直方图取得分位区间的几何平均，以 18% 灰为目标并夹至配置 EV 范围。分位跨桶时保留部分权重，浮点分位退化为同一位置时使用该位置所在桶。

自动适应在 log2 曝光空间执行，明暗两个半衰期分别以秒配置。每步时间不超过 0.1 秒。确定性运行使用已有固定帧时钟。首个有效计量直接确定曝光，重置后的第一帧重新计量。

Bloom 可配置开关、强度、阈值、soft knee 与 1–6 层。阈值作用于单个源纹素后再滤波，逐级降采样与上采样使用归一化核。上下两组纹理彼此独立，每次 dispatch 的输入输出均声明在图中。

可选 light_animation 在现有方向光照度上应用时间线倍率，支持 linear、step 与循环。最多 256 个关键帧，从零秒开始并严格递增。空轨道保持基础照度，非循环轨道保持末值。运行时同帧计算一次实际照度，供阴影、光照和诊断共同使用。时间线采用现有帧时钟，回放及网络恢复沿用同一配置。

## GPU 状态与历史

曝光双缓冲独立于交换链。记录保存当前显示曝光、当前帧预曝光、目标 EV 与计量亮度。第 n 帧所有 HDR 贡献采用上一成功提交的显示曝光 Pn。TAA 读取的历史颜色先乘 Pn/Pn-1，再做邻域限制和混合。直方图恢复场景亮度，ToneMap 使用 En/Pn，保证曝光只应用一次。

PrepareExposure 初始化首次读取记录并清理当前直方图。HistogramBuild、ExposureAdapt、Bloom、ToneMap、PostProcessReadback 按图声明执行。读回缓冲每帧槽独立，CPU 在对应 fence 完成后读取。直方图计数必须与实际视口像素数一致，报告保留无效样本数量及逐帧曝光值。

清理缓冲使用与 CPU 描述符一致的 typed UAV 别名。Shader 使用结构化视图。全部 frame-local 描述符在该帧槽退休后更新，曝光读写组随成功提交交替。

## 验证

CPU 与同源 HLSLI 测试覆盖曝光范围、分位裁剪、半衰期、有限值、Bloom soft knee、孤立高亮纹素、常量图及奇数尺寸。真实 GPU 对照固定倍率与相同 EV、零强度 Bloom、各 mip、自动曝光直方图及读回数据。显式灯光时间轴提供可重放的暗亮切换，逐帧检查实际光照、曝光适应与 TAA 预曝光校正。

GeneratePostProcessBenchmark.py 生成自研辐亮度 1 灰卡、小面积高亮块和黑色背景，通过现有 M3 构建请求与 GPU Cook 入口使用。灰卡在 EV100 约 2.210897 时应得到 0.18 的曝光后线性亮度，EV100 10 时应得到约 0.000813802。验收读取真实 GPU 纹理并允许单次 RGBA16F 舍入误差，Bloom 开关对照检查黑色邻域光晕。自动曝光的 241 帧明暗切换同时核对 GPU 计量、曝光适应、历史预曝光和 TAA 重置状态。

初版显示曲线继续使用已验证的 exponential tone mapping 与 pow(1/2.2)。最终 UE 同参数对照、原生 4K 性能、完整体积和反射验收继续由父单跟踪。
