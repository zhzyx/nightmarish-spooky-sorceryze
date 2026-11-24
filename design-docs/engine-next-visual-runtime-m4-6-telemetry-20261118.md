<!-- gonggong-request:engine-next-visual-runtime-m4-6-20261118 -->

# Engine Next M4.6 — 全程测量、对照与完整交付

## 身份与执行授权

稳定需求 ID 为 `engine-next-visual-runtime-m4-6-20261118`，类别为 `type:development`，本阶段工单为 [#1539](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1539)，原生父单为 [#1323](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1323)。用户已要求“请落地”以及“全部测试后提交推送 main”。本阶段可以分批提交，但全部原始验收未满足时保持本阶段与父单开放。当前子增量是正常入口的完整时序采样，不能据此标记完整渲染或性能目标完成。

## 原始完整验收范围

依据父设计 `design-docs/engine-next-visual-runtime-m4-20261115.md` 中保存的用户原文：

1. 指定 Windows PC 上原生 3840×2160、High/Ultra、自研固定 A–F 场景，保持核心渲染特性、材质与光照质量。
2. 常规目标平均至少 120 FPS、1% Low 至少 90 FPS，连续 30 分钟无持续资源增长或周期性卡顿。
3. 挑战目标单独记录：原生 4K 平均至少 144 FPS、1% Low 至少 120 FPS，连续 60 分钟稳定运行。不得降低分辨率、删减场景或核心效果换取指标。
4. 在同资产、相机、光照、曝光与质量参数下，完成 UE5.8.3 的固定 A–F 画质和性能对照。覆盖角色、GI、反射、阴影、材质、体积、透明、运动以及 M2 网络呈现。
5. 记录完整帧样本和 P95/P99、最大帧时间、1% Low、超 16.67/33.33 ms 卡顿、CPU/GPU/Pass、同步与上传、显存预算、进程内存、句柄及实际资源/页计数。
6. 输入时间、消费/提交/完成/Present 的可观察范围必须标明；软件时间戳不冒称实际扫描或光子延迟。硬件外测未完成则明确保留未知。
7. 干净发行包、全部相关回归、依赖和许可证、失败恢复、原生/数据模块变更与回退、签发 CI 和 main 回读。

当前约 9.4 ms GPU 的历史 4K 样本不满足 8.33 ms 的 120 FPS 预算。基础功能增量和短时成功不是以上长跑验收。

## 当前子增量：正常入口全程时序

新 `--telemetry PATH` 输出 JSONL，不改变普通 `--report` 的 65536 帧尾窗。`--duration-seconds 1800` 或 `3600` 使用真实墙钟停止；若同时设置 frame limit，先到者结束。采样从正常运行循环开始，初始化及驱动冷启动是否计入由每帧时间明确显示，不默认剔除首帧。

`FrameTiming` 与唯一 JSON 字段表移入私有 `Rendering/FrameTelemetry.h/.cpp`，普通报告和流式输出调用同一实现。仅在既有 fence 退休后写入完整帧；不新增 GPU 同步。输出文件由原子 exclusive-create 打开并持续持有同一句柄，竞争写入只允许一方成功，不以 exists 预检代替原子创建。头记录 QPC 频率和范围，图变更记录 epoch/pass 名，帧记录稳定 ID，尾记录实际/预期数量与成功状态。默认每 256 帧刷新并在结束关闭；崩溃或 I/O 失败保留部分文件且没有有效完成尾记录。额外内存与总时长无关，不保留所有帧数组。

QPC 记录 frame begin、最近窗口事件观察、主循环观察输入、提交、Present 开始/返回以及 CPU 观察到 fence 退休。独立的 input revision 仅由被接受的键盘/鼠标输入消息推进，focus/paint/resize 与失焦合成释放不计入。成功呈现帧绑定消费的最新 revision、接收 QPC 与消费观察 QPC，记录被合并的输入消息数；统计仅覆盖每帧最新消费输入到 Present 返回的 API 范围，未观测的较早合并输入不冒称已逐条测量。它不证明像素改变，也不是 M2 权威 tick 或扫描出光时间。GPU Pass 使用既有 timestamp/readback，不混合 CPU/GPU 时钟计算硬件延迟。

资源记录明确量纲与范围：DXGI 本地 usage/budget，进程 private/working-set/handle，图逻辑资源数量、descriptor 容量、分配的 mesh 页资源及 renderer 自有 eviction/stall。不能将 renderer 页驱逐称为驱动 DXGI eviction。同步页读取字节、实际计划 CopyBufferRegion 字节、动画 map/copy 和完整 page prepare 时间分别记录；后者包含选择及文件 I/O，不称为纯复制耗时。

`AnalyzeFrameTelemetry.py` 用 SQLite 磁盘临时表与 8 MiB cache 排序，不把完整长跑帧放进 Python 数组。按稳定 frame ID 恢复退休次序。P95/P99 为 nearest-rank，1% Low 为 `1000 / 最慢 ceil(N/100) 个帧时间的均值`。明确 CPU 帧、GPU 队列与 Present-return 间隔的统计来源，导出逐帧资源 CSV，原 JSONL 校验 SHA256。缺尾、重复帧、断帧、非有限数据和截断记录拒绝当作完整样本。epoch 存入磁盘表；Pass 汇总默认最多 4096 组，可显式设置到最多 65536 组或选择帧区间，超预算明确拒绝，不静默丢失。读写均支持真实 FrameGraph 的 1024 Pass 上限。

## 文件与验证

实现位于 `Rendering/FrameTelemetry.*`、正常 `VisualRuntime`/CLI 和只读分页复制计数。Windows 私有 SDK `psapi.h` 仅加入已有 visual profile，不扩大公共或 M2/M3 边界。工具为 `Tools/AnalyzeFrameTelemetry.py`。

CPU 回归包括超过 65536 帧不丢失、乱序退休、旧输出拒绝覆盖、失败/非有限值、截断/重复 ID、nearest-rank 与两项最慢 1% 的独立算例。真实 GPU 普通入口、资源曲线、开关采样开销、30/60 分钟及 UE 对照另留实测证据，未执行前不记通过。

## 最终功能组合与独立宿主

本阶段组合 M4.4 的 BC7/BC5 纹理 mip 后缀流送、M4.5 的 GI／DXR／虚拟阴影与分页几何，以及完整帧遥测、诊断和并行阴影录制。资源发布、barrier、查询、间接绘制、bundle 执行及队列提交由 owner 控制；工作线程只录制稳定快照。默认单线程，显式允许两或四线程，并分别统计实际录制和执行数量。

诊断覆盖用户要求的十九种视图。剔除、cluster、LOD 和几何流送为实际 GPU 数据图集，GI Probe 显示真实探针数据；不冒称世界空间覆盖图或 SDF。纯 SSR 视图拒绝混合 DXR 的不可分离结果。原生模式和 DXGI 空间拉伸分别记录 render、backbuffer、client 与捕获尺寸；后者不计入原生 4K 验收。

复杂 C 场景由 `GenerateEscarpmentBenchmark.py` 重建，包含砖石建筑、层状岩体、针叶树和台地。源资产、M3 包与独立 GPU 派生产物共享身份，UE 对照从同一 GLB 导入。球阵列继续作为算法负载夹具，不能替代复杂场景验收。

独立 Cook 在各平台共用非隔行 8 位 RGBA PNG 的像素解码，复用已有 zlib 和结构、CRC、扫描线及完整压缩流校验；其他 PNG 布局和 JPEG 保持 Windows WIC 路径或明确的平台错误。五种行过滤用固定精确像素复验，原 WIC 与便携路径烘焙的所测 v4 包逐字节比较。最大逻辑像素输出为 256 MiB，不代表进程峰值。

UE 参考须读回实际灯光阴影开关和求值后的骨骼姿势。相同动画时间字段不能代替姿势一致；环境立方体用于照明与绘制可见背景分别核对。配置错配的截图保留为原始证据，修正后的对照单独采集。

独立 AI 验收通过 `engine_next/Tools/ExecutorCli.py` 进入既有 Executor，显式使用 `LocalCopyProvider:factory`。该入口只添加确定的模块根，透传原协议、标准流和退出码；本地 copy 复用原有实现与 schema，避免编辑器聚合 factory 的可选服装服务依赖。使用 `python -I -S` 从干净导出执行 create／step／export，再通过真实 `next_asset ai-run` 检查字节、身份、恢复和故障边界。本地复制明确不是 AI 生成，不改变 M3 资产语义或其他 Provider。

上述功能组合交付仍不代表 M4 完成。A–F 的实际 UE 图像、动态视频与 GPU Capture、原生 4K 性能和 30／60 分钟稳定性、真实输入及完整发行包验收分别保留待验证状态。
