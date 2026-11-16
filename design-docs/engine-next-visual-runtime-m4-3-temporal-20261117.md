<!-- gonggong-request:engine-next-visual-runtime-m4-3-20261116 -->

# M4.3 时域重投影分片

本分片继续 #1343 与父单 #1323，接续局部阴影 PR #1370 的候选。使用原生分辨率，线性 HDR 历史双缓冲与显式 FrameGraph 读写依赖。

## CPU 与 GPU 状态

TemporalState 在渲染线程上保存最后一次成功提交的相机和绘制变换。PrepareFrame 产生事务候选，CommitFrame 在提交、Present 和 fence signal 全部成功后推进。稳定绘制键包含原实体、资产、primitive 与 node 索引。八相位 Halton 抖动仅随成功提交推进。

GBuffer 新增 RGBA32F 运动目标和 R32_UINT 对象标识。运动目标包含去抖动 UV 位移、上一帧正向视距和有效位。相机与物体变换共同参与上一帧投影。DrawConstants 为 272 字节、上传步长 512 字节；FrameConstants 为 3120 字节、上传步长 3328 字节。

历史每组保存 HDR 颜色、线性深度、法线、对象标识，两组资源独立于三缓冲交换链。首次有效读取前清零，写入由全覆盖计算 pass 完成。按提交顺序选择读写组，同一 DIRECT 队列串行执行；帧槽描述符在原 fence 退休后重写。

## 解析与重投影

TemporalResolve 在 DIRECT command list 上 dispatch，FrameGraph 记录为 graphics 队列并使用 non-pixel shader-read 状态。输入包含当前 HDR、深度、法线、运动和对象标识，以及上一组四个历史目标。输出无抖动网格，ToneMap 直接读取本帧历史颜色。

重投影按当前无抖动 UV 加运动向量定位历史。历史双线性 footprint 中每个 tap 分别检查对象、线性深度、法线和有限值。3×3 YCoCg 邻域限制历史颜色。当前颜色按双线性重建，颜色 alpha 保存选定表面的覆盖权重，覆盖变化降低历史贡献。天空先采用当前帧颜色。

可选 temporal_aa 配置控制启用状态、历史权重和相对深度阈值。旧配置使用默认值。Resize、最小化进入与恢复、重连请求和连接代次变化重置历史；失效帧使用当前数据。无效配置保留原输出并返回诊断。

## 验证

- CPU 验证提交事务、绘制身份、抖动周期、配置范围及历史失效。
- 真实 GPU 检查双缓冲资源状态、运动值、深度、对象标识和历史读取。
- 同一二进制完成开启、关闭、恢复配置对照，静态相位收敛、运动边缘与显隐场景检查。
- 联机输入、预测、远端插值、重连和最小化回归使用原 F SceneDocument。
- 当前分片保留后续曝光、Bloom、体积、完整反射与原生 4K 验收。
