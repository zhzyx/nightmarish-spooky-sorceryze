<!-- gonggong-request:engine-next-visual-runtime-m4-2-20261116 -->

# Engine Next M4.2 资产与 Deferred PBR

父工单为 [M4 #1323](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1323)，本阶段为 [#1334](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1334)。前置 M4.1 经 PR #1331 合入 `main`，基线为 `5afcb929df22d8cad02c3a4792e4b76f8b28c382`。用户于 2026-11-15 确认设计并要求落地，于 2026-11-16 再次确认完成实现和测试后直接提交、推送并合入主线。

## 交付范围

- 原 M3 `.enpak`、AssetManifest、SceneDocument 的类型、序列化和来源契约保持冻结。新增渲染器只读消费，AssetRef、场景摘要与包摘要贯穿加载、Cook、网络视图和报告。
- `Rendering/Cook/GltfDecoder` 在 M3 结构校验后解析三角形 primitive、POSITION/NORMAL/TANGENT/TEXCOORD_0、嵌入 PNG/JPEG、采样器、金属粗糙度材质、层次矩阵和当前默认场景。缺失法线生成平面法线，缺失切线生成正交基。输入预算、非法数值、索引、引用、变换和未知扩展有显式诊断。
- `RenderScene` 组合 SceneDocument 实体层次与 glTF 节点世界变换，保留 EntityId、原资产、primitive 与 node 的映射。场景验证和摘要核验通过后才替换输出。
- `GpuPackage` 提供确定性、little-endian、内容寻址的 `.engpu`，包含规范 JSON 清单和有界二进制页。页保存解码后的几何、材质、实例与原编码图像。发布使用独占临时目录和不覆盖重命名，相同输入重入核验已发布内容，失败保留已有目标。
- `next_asset gpu-cook` 与 `gpu-validate` 是正式 CLI 入口。`gpu-validate` 校验声明的源摘要、页摘要、格式和引用。视觉加载同时执行 `VerifyCookedScene`，将完整页的规范编码与实际源场景比较，防止仅修改页内容并重算摘要后替换源数据。
- `ImageDecoder` 采用独立 zlib 解压验证 PNG 的完整 IDAT、Adler 校验和、扫描行及 Adam7，然后由 WIC 解码像素。JPEG 先用独立 libjpeg-turbo 系数解码闭包严格检查熵编码和扫描预算，再由 WIC 生成 RGBA。错误回收停留在 C 适配层，C++ 层返回诊断。
- 纹理在启动时生成完整 mip 链。sRGB 在线性空间过滤，MASK 颜色按 alpha 权重过滤，法线重新归一化，ORM 通道独立处理，OPAQUE 和 emissive 的纹理 alpha 按 glTF 语义忽略。
- 延迟渲染输出四个 GBuffer，分别保存 sRGB base color、世界法线、roughness/metallic/AO 和线性 emissive，配合 reverse-Z 深度与全屏 GGX lighting。当前具有方向光、衰减点光、OPAQUE、MASK、双面和镜像变换路径。
- `EnvironmentLighting` 从自研线性 HDR 天空生成六面环境、diffuse irradiance、GGX 预滤 roughness mip 和 BRDF LUT。默认尺寸为 64、32、64，使用 128 个确定性样本。纹理上传后参与实际 split-sum IBL，天空背景使用同一环境。
- `ClientSession` 从原阻塞 RunClient 提取可逐 tick 驱动的状态，复用 M2 协议、固定步长预测、远端插值和重连。原验收 CLI 继续调用同一实现。视觉模式读拥有数据副本的快照，将 simulation local 位移经父级变换映射到玩家及其子网格。
- 视觉客户端报告实际 pass、资源状态、队列等待、GPU 时间、场景和包身份、网络输入、重连及 draw 世界位置。平台头文件和链接库仅在目标对应的私有实现范围准入。

## 可重建场景与入口

所有路径均以仓库根解析。

```powershell
python engine_next/Tools/BuildRuntime.py --compiler msvc --build-dir build/engine_next/runtime --run-tests
python engine_next/Tools/BuildVisualRuntime.py --build-dir build/engine_next/visual --run-tests
python engine_next/Tools/GenerateVisualBenchmarks.py --output build/engine_next/benchmarks
build/engine_next/runtime/next_asset.exe compile --request build/engine_next/benchmarks/B/BuildRequest.json --source-root build/engine_next/benchmarks/B --output build/engine_next/benchmarks/B/Scene.enpak
build/engine_next/runtime/next_asset.exe gpu-cook --package build/engine_next/benchmarks/B/Scene.enpak --output build/engine_next/benchmarks/B/Scene.engpu
build/engine_next/visual/next_visual_client.exe --asset-package build/engine_next/benchmarks/B/Scene.enpak --gpu-package build/engine_next/benchmarks/B/Scene.engpu --validation
```

`BuildRuntime.py` 使用当前 MSVC developer shell。`BuildVisualRuntime.py` 能在子进程中发现已安装 MSVC 和 Windows SDK。`GenerateVisualBenchmarks.py` 只使用 Python 标准库生成自研几何和纹理，并输出 `executor_artifact` 来源信息、参数和文件摘要。

B 包含 12 个材质球，覆盖三行 metallic、四列 roughness，以及法线、AO、自发光、alpha mask、负缩放和非均匀缩放。F 包含两个 `player_spawn`，每个使用有三个 primitive 的彩色角色。F 的 BuildRequest 通过相同 compile 入口创建。服务端和两个视觉客户端加载同一 `.enpak`，分别指定客户端身份。

```powershell
build/engine_next/runtime/next_server.exe --asset-package build/engine_next/benchmarks/F/Scene.enpak --bind 127.0.0.1 --port 28741 --duration-ms 60000
build/engine_next/visual/next_visual_client.exe --asset-package build/engine_next/benchmarks/F/Scene.enpak --connect --port 28741 --client-id A --vsync
build/engine_next/visual/next_visual_client.exe --asset-package build/engine_next/benchmarks/F/Scene.enpak --connect --port 28741 --client-id B --vsync
```

WASD 控制本地玩家。R 请求重连。相机方向固定沿 -Z，默认位于 `(0,0,5)`，垂直视场角 50 度。网络视图通过实际加载的 package digest 与渲染源交叉核验。

## 本阶段限制与后续验收

`.engpu` v1 的图像仍为源 PNG/JPEG，mip 与 HDR IBL 在视觉启动时生成。GPU 专用纹理块、持久化环境 Cook、cluster 页、几何流送和压缩由后续阶段继续实现。当前 GPU 页格式和 Cook 版本清楚记录这些边界。

当前拒绝 BLEND 透明绘制、非空 glTF 扩展、skin、morph 和 animation。clearcoat、anisotropy、transmission、decal、动态阴影、动态 GI、时域重建、体积效果、面积光以及完整 GPU-driven pipeline 的验收仍在 M4 父设计后续阶段。WIC 像素路径限 Windows，portable CI 覆盖几何、格式、mip 和环境算法。算术 JPEG 的 WIC 支持以实际解码结果为准，失败返回诊断。

解码器的 512 MiB 限制约束输出或数组数据，法线切线生成和校验另有有界临时内存，进程峰值需单独实测。

GPU Validation 的运行正确性、源码和链接独立性、M2/M3/AI 回归、干净源重建、截图、视频、GPU 捕获与精确 CI 分别留存。UE 同参 A–F 对照、4K 目标及长时稳定性属于最终 M4.6 验收，当前记录保留待测状态。
