<!-- gonggong-request:engine-next-visual-runtime-m4-2-20261116 -->

# M4.2 GPU Cook 派生数据补齐

本分片沿用 #1334 与父单 #1323 的已授权范围，基于基础实现提交 `475222285a4754c11dc21d4cb41a09914b48553e` 开发。基础 PR #1340 已于 2026-11-16 合入 main `021834b78727eb3481a8501c0c212719157ff7b9`，全部适用 CI 通过，本分片已同步该主线。

## 范围与兼容

`.engpu` v2 保存实际纹理 mip 链、材质槽位映射和初步 mesh cluster 数据，保留 v1 读取。三参数 C++ Cook 入口保留 v1 行为，新配置入口显式启用派生数据。CLI `gpu-cook` 默认生成 v2，`--layout-only` 明确请求 v1。M3 原包保持只读，所有 AssetRef 与 SceneDocument 语义沿用。

纹理按原 image、颜色空间和 alpha 策略去重复用。sRGB、normal、ORM 和 OPAQUE/MASK 的生成规则与基础渲染一致。v2 在可视运行时直接上传已存储的 mip，加载验证按实际源数据重新生成并比较。Windows WIC 像素解码路径继续复用，其他平台遇到带图像的完整 Cook 显式报平台能力不足。跨平台基础布局验收通过 `--layout-only` 运行。

初步 cluster 按输入三角形顺序确定性划分，每簇最多 64 个独立顶点、126 个三角形，保存 primitive 内顶点映射、簇内索引、AABB、保守包围球和退化三角形计数。覆盖原始三角形，保持可重建顺序。完整 LOD、GPU culling、indirect 和 streaming 仍按 M4.4 实施。

## 验收

- 两份 v2 完整 Cook 逐字节一致，原包摘要不变，重入保持已有内容。
- v1 读取及既有 layout-only CLI 回归通过。
- cluster 全索引重建、数量上限、包围体、非法引用和数值错误验证。
- 完整 mip 尺寸、内容、颜色空间及不同 alpha 策略测试。
- 伪造派生数据及重新计算页摘要的篡改仍被源内容核对拒绝。
- 实际 v2 mip 上传、B/F 场景和 GPU Validation 验证。
- 源码／链接边界、CI、独立审查及 main 回读。
