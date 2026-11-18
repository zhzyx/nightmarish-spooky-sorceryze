# Engine Next M4.4 分层分页 Cook 数据增量

关联工单 [M4.4 #1506](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1506)，父工单 #1323。本分片提供 CPU Cook、索引、按范围读取、正常加载入口及首版 mesh 页驻留和 GPU LOD。纹理 GPU residency、后台 IO 调度、虚拟阴影页和完整场景性能验收继续由主设计跟踪，不以本增量关闭 M4.4。

## 代码与兼容

`GeometryLod.h`、`LodSelection.cpp` 和 `Cook/GeometryLod.cpp` 承接已独立审查的层级生成与完整 cut 选择。生成器复用 MIT meshoptimizer 1.2 的索引简化，保留原顶点属性、组外边界和共位置接缝，退化/非流形或验证预算不足时使用完整源几何。父误差含双向表面距离上界与子误差最大值。

`Cook/GpuPagedPackage.h/.cpp` 提供显式 `CookPagedGpuPackage`、`LoadGpuPageIndex` 和 `ReadGpuPage`。旧 `CookGpuPackage`、`LoadGpuPackage` 仍处理原 v1/v2。正常入口增量新增 `next_asset gpu-cook-v3`、`gpu-validate --source-package` 与 visual 的统一 `LoadVerifiedGpuPackage` 调用。原 `gpu-cook` 和仅声明 digest 的旧校验入口保持兼容；v3 的源绑定要求实际验证过的 M3 场景。`GpuPagedGeometry` 将 v3 mesh 页接入正常 VisualRuntime 的 GPU 页池和逐帧 LOD 切换；v1/v2 继续原路径。

`GpuPackageCodec.h` 复用既有 GPU scene codec。metadata 模式保留完整 scene/asset/revision/digest、primitive material、所有 MaterialData、sampler/texture 引用、encoded-image MIME、语义 mip 描述、材质 mip 绑定、mesh node instance、draw instance 和 double world transform。geometry/image/mip 的大字节块外置。metadata 提取直接复制小字段，避免先拷贝全部 payload 再清除。

## 文件布局

- `GpuManifest.json` 为 canonical JSON。包含版本 3、源 M3 包 digest、metadata 与 payload 摘要/字节数、页目录、LOD 森林及 canonical `lod_settings`。完整 Cook 参数用于可重建源绑定，包含分组大小、节点/输出索引/距离测试预算、验证深度、目标三角比例和覆盖单元半径。
- `metadata/<sha256>` 使用现有 little-endian GPU scene encoding 的 metadata 版本。所有大字节数组长度为零。纹理尺寸、语义、alpha policy 与采样器字段保留。
- `blobs/<sha256>` 包含按目录顺序连续排列的 payload。每页另外绑定自身 SHA-256，便于独立读取验证。

页类型为 MeshGeometry、EncodedImage 和 TextureMip。目录保存 asset、item、level、width、height、offset、bytes、sha256、pinned。MeshGeometry 的 item/level 对应 primitive/node，EncodedImage 对应 image/0，TextureMip 对应 variant/mip。mesh 的尺寸字段为零。纹理页保存原 encoded bytes 或 uncompressed RGBA8 mip bytes，语义与采样参数从 metadata 查询。

每个 mesh 页的 24 字节头按 little-endian 保存 magic、asset、primitive、node、vertex_count、index_count。随后每顶点占 52 字节，由原 source vertex ID 与原 MeshVertex 的 12 个 float 组成。末尾是局部 uint32 indices。读取会核对头身份、长度、原顶点 ID 唯一递增、局部索引范围、有限顶点属性、正交法线/切线及节点包围盒。

LOD 森林序列化每个节点的子范围、bounds、误差、page ID 及完整源 triangle interval。索引验证唯一父、无环、完整根覆盖、连续子覆盖、单调误差和页身份匹配。每个 primitive 的根几何页常驻。大型节点目前受单页字节预算约束，超出时明确失败，后续可再扩展单节点多页 ABI。

## 读取、预算和发布

`LoadGpuPageIndex` 只读取 manifest 与 metadata，并检查内容命名 payload 的路径与大小。它不遍历读取 payload。`ReadGpuPage` 对选定页执行实际 seek/read，校验页 SHA 与类型结构。返回统计包含请求数、实际读取字节数和已验证页数，失败保持旧输出。独立请求 1×1 mip 的测试确认只读取 4 字节 payload。

默认 index 上限 32 MiB、单页 64 MiB（可配置至 512 MiB 以容纳既有 8K RGBA mip）、payload 1 GiB、root/pinned 128 MiB、目录 262144 页。限制共同生效，所有加法用剩余预算检查。metadata 源 scene 的解码/准备继续受现有 M3 和 v2 Cook 限制。root 预算不足时索引和 Cook 均失败，旧索引或已发布包保留。

发布先创建独占 staging 目录，写入并刷新 metadata、内容命名 payload 和最终 manifest，重新读取全部页验证。随后复用现有平台 no-replace 目录发布。读者只能看到完整目录。重复相同内容会校验并幂等完成，不同内容保留旧目标并失败。测试覆盖两个 writer、并发 reader、半写 staging、损坏 payload 和目标冲突。

source digest 参数沿既有 GPU 包 API 表示调用者提供的已验证 M3 身份。Cook 自身通过 `LoadRenderScene` 从实际源生成内容。`VerifyPagedScene` 根据已验证源重新生成 metadata、全部页描述摘要和 LOD 森林，并逐字节绑定 canonical 描述摘要；验证不会读取 payload。正常加载随后只实际读取完整叶几何与 image/mip 数据，不读取冗余父 LOD 页。原始未引用顶点保持源值，引用顶点和索引从页恢复；材质、节点与实例身份不变。所有页读取仍核 SHA，失败不替换旧场景。源重算的累计距离查询默认上限为 1600 万，调用方可通过 `GpuPageLimits` 调整至最多 2.56 亿；超过预算有明确诊断且不以降级几何冒充已验证结果。此限额独立于不可信 manifest 所声明的单 primitive Cook 预算。v3 输出继续使用预烘焙纹理路径，并报告真实页请求和字节数。

## 验证边界

当前新增测试覆盖多层真实 Cook 往返、原材料与纹理语义保留、独立 mip 读取、旧 v1/v2 入口、overlap/gap/duplicate/range 错误、缺失字段、预算、SHA 损坏、重签摘要后的非法 mesh indices、发布竞争和输出事务性。GPU 页池另通过正常入口与独立 D3D12 生命周期/实际上传读回验证。纹理 GPU 页池与压缩仍在后续增量。

## 实际 mesh 页池和 LOD

`PageResidency` 管理有界驻留、generation ticket、失败重试、pin、LRU 和 copy/render fence。`GpuPagedGeometry` 使用同一 owner 线程和 DIRECT queue fence domain。GPU 页与 staging 按 `GetResourceAllocationInfo` 的实际分配字节计费；三个帧的 page-view upload 表也计入 staging 预算。默认 GPU 页预算 128 MiB、staging 16 MiB、每帧最多 16 次新加载。`geometry_culling` 的可选 `pixel_error` 默认 1 像素，`lod_hysteresis` 默认 0.1，`lod_enabled` 默认 true（仅 v3 且启用 geometry culling 时生效）。

每帧先用实际相机/世界变换选择完整 cut、请求缺页，在有界同步 IO 中验证并准备页；根据当前真正 resident 页重新选择 cut，避免引用本帧刚被回收的页。根页 pin；根未准备好或命令容量不足时使用完整原几何，不丢 draw。新上传页只有 GPU copy fence 退休后才可选择。新帧的 cut、使用 fence 与历史选择只在成功提交后发布；取消未提交列表时释放准备中的页和 reservation。

页中 source ID 留在 CPU 验证，GPU 只上传 48 字节 MeshVertex 和局部 uint32 索引。页 view 分帧维护。新的 64 字节 indirect 记录依次含 CBV 8、VBV 16、IBV 16、DrawIndexed 20 与 padding 4 字节，保留原 draw/entity/material 身份。原 32 字节 v1/v2 路径不变。原始完整 VB/IB 保留给阴影、GI 与透明绘制，当前不把页池字节节省宣称为整场景几何已完全虚拟化。

FrameGraph 的 GeometryPagePool 声明由宿主展开到每个真实 resident/pending 页资源，执行 Common → CopyDestination → VertexIndexRead → Common；VertexIndexRead 为 VB|INDEX 组合读状态。不存在用空资源替代实际页 barrier。LOD cut 变更时仅拒绝该 draw 的上一帧像素历史，防止 TAA 继续沿用旧三角覆盖。

当前 IO 在 owner 线程按帧有界执行；后台文件任务、更多复杂场景调度和页级性能仍需后续验证。报告包含真实读字节、驻留/峰值、失败、eviction、预算阻塞、indirect 容量和逐帧候选三角数。

相同索引身份和逐位相同的 binary32 world matrix 可复用完整世界空间 LOD 节点，缓存的节点与条目合计最多 64 MiB。相机变化仍重新选择 cut，公共选择校验不跳过。已提交的 active cluster 集仅在节点 cut、桶布局以及全部页 generation/residency 均一致时复用；每帧仍登记真实使用页的提交 fence，未提交的 Prepare/Discard 不成为复用依据。运行时使用本帧实际相机位置，包括交互移动偏移。

## 保守误差与验证阶段

双向误差验证使用目标三角 BVH，最多 64 MiB 临时索引/节点和 64 项遍历栈；大输入退原有线性查询。每个候选都是目标三角内的凸点，覆盖半径和数值余量保持原定义，剪枝只可能放大上界。距离预算仍计实际目标点测试；耗尽时不接受未经证明的简化。额外回归覆盖大/小坐标、退化 AABB、重排、NaN、预算失败与事务性。

旧 R4 CPU、正常入口 R2 和驻留 R2 证明各保留其原 source/native 身份。驻留 R2 已记录真实 v3 64B draw 与 v2/full 像素一致、1000 实例/1000 万源三角场景的按需读取和 1 MiB 回收；原 Cook 预算造成有限减面，这一结果不混作后续 BVH 新候选证明。BVH 后需重新 Cook、源绑定、完整构建及 GPU 验证。M4.4 完整 texture streaming、virtual shadow pages 等要求保持开放。

BVH 驻留 R4 正常入口已完成 536 帧：基础兼容、TAA/resize、1000 实例/1000 万源三角的五组各 60 帧及材质两组各 64 帧。粗 cut 为 500 万三角；精细页路径、完整源路径和容量不足回退的截图逐字节相同。1 MiB 页池出现真实逐出与预算等待，画面保持完整。该版本 CPU 选择开销较高，不能据此宣称目标帧率达标。后续缓存候选须重新验证；私有 CPU 对照只说明连续移动相机和局部 world 变更时 cut 与未缓存路径一致，不替代实际 GPU 性能验收。

同一帧内，第一次选择后保存逐页 resident 位图；请求、加载与回收完成后再次取得位图。仅当两份位图逐字节相等时复用这次已经验证的选择，否则重新选择。世界变换、相机、设置和上一已提交 cut 在该 owner-thread 调用内不变。UploadReady 不属于 Resident，故新载入页不会被提前绘制；驱逐变化会触发重新选择。此优化不跳过每帧初次公共输入校验，也不把未提交帧作为跨帧历史。`paged_geometry_selection_reuses` 记录这些准备过程中的复用决策，包含随后被取消的准备。

动画路径与分页路径保持明确边界：有实际动画变形的场景继续使用完整 source 几何和动态顶点上传，不以静态页替代变形结果；resize 后维持该回退。静态 v3 场景仍可用分页，动画配置启用但无动画资产时不强制关闭静态分页。DeformationUpload 与分页 upload 各保留真实资源依赖、失败取消及成功提交的 fence 处理。
