<!-- gonggong-request:engine-next-assets-ai-workflow-m3-20261114 -->

# Engine Next M3：独立资产体系与 AI 原生内容工作流

## 当前结论

- 用户目标：复用现有 MVC、`AICore::Runtime`、AINative Executor／Provider 和 M2 运行时，新增中立资产契约、独立资产包、宿主进程适配，以及新旧运行时对同一场景的消费。
- 用户已于 2026-11-14 23:00 明确“开始落地”，确认按本文件五个 PR 连续实施。PR 1／2／3 已分别由 PR #1272／#1277／#1280 合入并回读 main；PR 4 已完成本机实现、独立审查和验证，正在进入精确候选交付，PR 5 与整单验收仍未完成。不得据此宣称 M3 完成。
- 需求 ID：`engine-next-assets-ai-workflow-m3-20261114`。
- Issue：[#1240](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1240)。
- 类别：`type:development`。
- 责任人：当前 Kimi Work 会话。
- 隔离分支：`engine-next-assets-ai-workflow-m3-20261114`；其他工作树及原工作区未跟踪文件保留。
- 初始基线为 `main@c28d8175e870f75e5756355c5cc18c3bce4864fa`。PR 1 经格式修正和独立审查修复后已整合最新 `main@2d896aa6a6cbccc8a773eb0d128375779c479e92`；R1／R2 失败与修复、R3 审查和复验证据分别保留，不混用旧候选结果。
- `issue_gate.py --intake-only` 已对 #1240 实际通过，绑定 `type:development`、`status:in-progress` 和稳定需求 ID。

## 前置交付回读

| 依赖 | 权威状态 | 实际交付证据 |
| --- | --- | --- |
| M1 #939 | 已关闭并完成验收 | PR #970／#983，交付回执 PR #987；main `0010a548ad5b52ef268e28c5e9c2c6b9a4ae26e2` |
| M1.1 #1025 | 已关闭并完成验收 | 实现 PR #1028 merge `d5a77b1d539a9b92a1b81fc84c4df447dab82a7d`；回执 PR #1039 merge `78fe4c2bfe9c7e340f20e1318ec8d5edadbfbd02` |
| M2 #1042 | 已关闭，13 条验收完成 | 实现 PR #1052／#1071／#1113／#1161／#1225；最终证据 PR #1237 merge `6ef7879a8e606a50ecbd3b720dabbdb6eee5d583` |
| AI 公共框架 #1086 | 已关闭，七项验收完成 | PR #1230；签发 `89f86b843caa9ab3dcc43153929c7065a98d1174`，main merge `5f9f4fd491096d7098e055f0e86e28c5dab6e9d6` |

已回读 `ai_core/README.md`、`ai_core/Runtime.h/.cpp`、`modules/ai_core/AIWorkflowRuntime.h/.cpp`、马良 `workbench_controller.gd`／`workbench.gd`、`tools/ainative/contracts.py`／`executor.py`／`executor_cli.py`／`editor_host.py`、Provider 测试及持久取消／恢复实现，并回读 M2 的 World、SessionManager、ServerRuntime、ClientRuntime、RuntimeConfig、构建／发布／干净源码入口和契约门禁。

已召回并采用以下已验证方法：按实际构建消费者分类；完整候选而非空签名差异进入静态检查与精确 CI；依赖交接核对实际候选和验收回执；外部进程只有结果、输出流和终态均完成后才发布成功。

## 原始目标与完成定义

建立引擎中立的内容链：

```text
离线／合成 Provider
  → 现有 AINative Executor（executor_cli.py）
  → 无 View WorkflowController
  → 既有 AI Artifact Manifest
  → 中立 Artifact→Asset／Scene 适配
  → .enpak/{AssetManifest.json, Scene.json, blobs/<sha256>}
  → next_asset inspect / validate
  → next_server + next_client A + next_client B
  → legacy Godot 适配器读取并发布同一场景
```

完成时必须同时证明：

1. 现有 Executor 和离线／合成 Provider 在无 Godot 进程中完成 M3 AI 工作流。
2. `ai_core/Runtime.cpp` 以原路径、原来源和许可证直接进入独立目标，不复制或改名。
3. Artifact Manifest 只负责 AI 生产与溯源；AssetManifest／SceneDocument 只负责运行时资产和场景，三者不混用。
4. 同一输入在两个干净目录产生相同 canonical manifest、Scene 和包摘要；包内无时间戳、本机路径或凭据。
5. 同一 `.enpak` 驱动 M2 三进程和 legacy Godot；对齐 ID、revision、场景语义和引用，不比较 `.tscn` 字节。
6. 非 AI 的 `next_server`／`next_client` 资产加载和模拟不依赖 Python；只有显式 `next_asset ai-run` 使用声明的 Python 宿主。
7. 五个 PR 全部完成正式门禁、精确候选 CI、main 回读和最终验收前，不关闭 #1240、不宣称 M3 全部完成。

## 非目标

- 不重做 AIChat、马良、天枢 MVC，不重写 `workbench.gd`，不开始 M4 可视编辑器。
- 不编写另一套 C++ DAG／Provider，不调用真实模型，不评价生成质量。
- 不做渲染器、窗口、GPU 解码、材质上传、网格视觉／拓扑／动画／骨骼验收。
- 不做通用 ECS、完整 GameMode、RPC、场景脚本、联网资产下载、热更新或 M2 协议升级。
- 不承诺任意 `.tscn`／`.tres`／GDScript 转换；Godot 格式只在 legacy 迁移边界出现。

## 现有实现核对与复用边界

### 直接复用，不复制

- `AICore::Runtime` 已提供请求幂等、冻结输入、单调 generation／sequence、终态和迟到事件拒绝。M3 直接编译它。
- `AIWorkflowRuntime` 继续是 Godot `RefCounted` 适配器；它及 `modules/ai_core` 不进入 `next_asset`、`next_server` 或 `next_client` 的链接输入。
- `workbench_controller.gd` 继续拥有 legacy 执行、进程、取消和恢复；`workbench.gd` 只管理控件、输入和预览。两者均不被新运行时链接或包含。
- `executor_cli.py` 已有 `create/status/step/cancel/retry/export`，直接复用其 JSON、SQLite DAG、不可变 Artifact、幂等键、reconcile、持久取消和恢复语义。M3 不需要为 export 改写 `editor_host.py`。
- `editor_demo:factory` 提供真实 Executor 路径上的离线 copy Provider；测试合成 Provider 只实现既有 Provider 接口，不构成新生产 Provider 体系。
- M2 的 World、PredictionModel、PredictionReconciler、InterpolationBuffer、SessionManager、ENet 协议和有界队列继续使用，不升级网络协议。

### 当前缺口及 M3 修正点

- 独立核心只有 Run 状态机，快照／payload 由 Godot 适配器保存；M3 新增中立快照适配层，不把 Dictionary 代码复制进核心。
- M2 当前由 `SessionManager` 以 SessionId 分配 EntityId，出生状态为零值；固定步长 16 ms 和最大速度 8 仍存在硬编码。M3 场景装配层提供稳定 EntityId、出生位置、步长和速度。
- `ServerRuntime`、`ClientRuntime` 和 `SessionManager` 中服务器时间、重连 tick、drain tick、输入间隔使用硬编码 16；接入 Scene 后统一由已验证的 fixed step 推导。
- `RuntimePackage.json` 只描述可执行文件；M3 不向其塞入资产字段，也不改变其发布语义。`.enpak` 作为单独输入复制到干净运行目录。
- 当前 `ExportCleanSource.py` 只导出 `engine_next` 和契约工具；M3 显式增加 `ai_core/Runtime.h/.cpp` 与 AI 宿主最小允许清单，而不是复制 Godot 或整个工具目录。

## 总体架构与所有权

```text
EngineNext::Serialization::Json
  └─ 有界 JSON 值、严格解析、canonical writer

EngineNext::Assets
  ├─ AssetManifest / SceneDocument：纯值与语义验证
  ├─ BlobValidator：PNG / JPEG / 自包含 GLB 结构验证
  ├─ AssetCompiler：场景引用闭包、内容寻址、确定性清单
  └─ AssetPackage：安全读取、诊断、包摘要、原子 no-clobber 发布

EngineNext::AI
  ├─ WorkflowSnapshot：AICore::Runtime 的中立快照／JSON 适配
  ├─ ArtifactAdapter：Executor 输出 → Asset + SceneDocument
  ├─ IProcessTransport：参数数组、stdin/stdout、状态、取消、超时
  └─ WorkflowController：代次、进程生命周期、恢复、事件与发布门禁

next_asset：唯一 M3 View，仅 headless / CLI，读取快照并输出结构化 JSON

legacy Godot scene_adapter.gd：独立 host_tool
  ├─ import：白名单 .tscn → BuildRequest + staged blobs
  ├─ publish：.enpak → Godot 节点／.tscn + 本地资源文件
  └─ verify：实体、变换、玩法参数、资产引用语义比较
```

所有公共运行对象单线程串行；外部 Provider 只存在 Python Executor 进程。Controller 在外部副作用前回读运行状态，在事件转发和资产发布前再次核对 run、generation、Executor run、结果代次及取消状态。

## Schema v1

后续实现将机器可读约束保存在 `engine_next/Schemas/AssetManifest-v1.json`、`SceneDocument-v1.json` 和 `AiAssetRun-v1.json`；C++ 验证器与 Schema 同步测试，未知字段一律拒绝。以下为本轮待确认正文。

### 公共身份与引用

- `asset_id`、`scene_id`：1–128 字节 UTF-8，首字符为 ASCII 字母／数字，后续仅允许 ASCII 字母、数字、`.`、`_`、`-`；不使用路径作为身份。
- `revision`／`scene_revision`：1–64 字节，采用同一受限字符集；同一 AssetId + revision 不得对应不同内容。
- `entity_id`：JSON 无符号整数，范围 `1..2^63-1`，避免跨宿主符号和浮点精度歧义；稳定且非零。
- SHA-256：64 个小写十六进制字符。`byte_size` 为实际 blob 字节数。
- `AssetRef` 固定为：

```json
{
  "asset_id": "player.mesh",
  "revision": "r1",
  "content_sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
}
```

- Artifact 引用保持既有 `{id, revision}`，只在生产溯源和适配输入出现；Provider `job_id` 不作为 revision，路径不作为 AssetId。
- 既有 AI Artifact 的扩展 `payload` 必须完整保留，WorkflowSnapshot 和 ArtifactAdapter 不得按 M3 字段白名单裁剪。只有新定义的 M3 v1 Schema 拒绝未知字段；该规则不反向施加到旧 Artifact Manifest。

### AssetManifest.json

```json
{
  "schema_version": 1,
  "scene": {
    "scene_id": "m2.dual-spawn",
    "scene_revision": "r7",
    "content_sha256": "<Scene.json canonical bytes 的 SHA-256>"
  },
  "assets": [
    {
      "asset_id": "player.mesh",
      "revision": "r1",
      "type": "mesh",
      "media_type": "model/gltf-binary",
      "content_sha256": "<blob SHA-256>",
      "byte_size": 1234,
      "dependencies": [],
      "source": {
        "kind": "executor_artifact",
        "artifact_id": "make_mesh.result",
        "artifact_revision": "artifact-r3"
      }
    }
  ]
}
```

约束：

- `type` 仅允许 `image`／`mesh`；媒体类型分别为 `image/png`／`image/jpeg` 和 `model/gltf-binary`。
- assets 按 `asset_id` 排序；dependencies 按 `(asset_id, revision, content_sha256)` 排序，重复 ID、重复依赖和自依赖拒绝。
- 每个引用必须匹配同包资产的精确 revision 和 digest；悬空引用、循环依赖、digest／size 不符均失败。
- `source.kind` 为 `executor_artifact` 时必须含 Artifact 身份；legacy 导入使用 `godot_whitelist_import` + `importer_version: "1"`。来源不得包含本机路径、URI、凭据或时间戳。
- 清单只包含 Scene 引用及其依赖闭包，不携带无关资产或元数据。

### Scene.json

```json
{
  "schema_version": 1,
  "scene_id": "m2.dual-spawn",
  "scene_revision": "r7",
  "simulation": {
    "fixed_step_ms": 16,
    "max_speed": 8.0
  },
  "entities": [
    {
      "entity_id": 101,
      "name": "player-a",
      "node_type": "Node3D",
      "parent_entity_id": 0,
      "transform": {
        "translation": [0.0, 0.0, 0.0],
        "rotation_xyzw": [0.0, 0.0, 0.0, 1.0],
        "scale": [1.0, 1.0, 1.0]
      },
      "gameplay": { "kind": "player_spawn" },
      "assets": []
    },
    {
      "entity_id": 205,
      "name": "player-b",
      "node_type": "Node3D",
      "parent_entity_id": 0,
      "transform": {
        "translation": [2.0, 0.0, 0.0],
        "rotation_xyzw": [0.0, 0.0, 0.0, 1.0],
        "scale": [1.0, 1.0, 1.0]
      },
      "gameplay": { "kind": "player_spawn" },
      "assets": [
        {
          "role": "mesh",
          "asset_id": "player.mesh",
          "revision": "r1",
          "content_sha256": "<与 AssetManifest 完全一致>"
        }
      ]
    }
  ]
}
```

约束：

- entities 按 `entity_id` 排序；EntityId 和 name 均唯一。`parent_entity_id=0` 表示根，否则必须指向已定义实体；父环拒绝。
- `node_type` 仅允许 `Node3D`／`MeshInstance3D`；MeshInstance3D 必须有且仅有一个 `role=mesh` 引用，Node3D 不得有 mesh 角色。
- Transform 为局部变换；平移／旋转／缩放均为有限、可由 binary32 表示的数。旋转四元数必须归一化（容差 `1e-5`），缩放分量非零。M2 只消费 player_spawn 的平移；legacy 保留完整已定义 Transform。
- `gameplay.kind` 仅允许 `player_spawn`／`static`；`fixed_step_ms` 为 `1..1000`，`max_speed` 有限且 `(0, 10000]`。
- 资产引用额外含 `role`，其余与 AssetRef 相同；引用按 `(role, asset_id)` 排序。Scene 中不得出现 GDScript、Node 对象、ObjectID、UID、URI 或绝对路径。
- M2 场景消费要求恰好两个 player_spawn；服务器按 EntityId 升序将尚未使用的 spawn 分配给新会话，重连保持原 EntityId。客户端仍从既有 welcome 得知自己的实体，不增加协议字段。

### AiAssetRun 输入与溯源适配

`next_asset ai-run --request AiAssetRun.json` 的输入包含：

- `schema_version`、`request_id`、可公开的 `model`、Executor `graph` 和既有 Artifact `manifest`。
- `scene_template`：Scene v1 的实体、Transform、simulation，以及 `asset_bindings`。
- 每个 `asset_binding` 包含显式 `asset_id`、`role`、`output: {node, port}`；输出在 Executor export 后解析为真实 Artifact `{id, revision}`。
- Artifact 必须带既有 `content_base64` + `content_sha256` 内联快照；适配器验证 digest 后写入内容寻址 blob，Asset revision 显式取该 Artifact 的不可变 revision。
- `binding` 冻结 scene_id、scene_revision、scene_template 和 graph／manifest 摘要；Python、factory、数据库和状态目录只存在 `ProcessTransportConfig`，不进入 model、binding、Artifact、Trace 或包。
- create 回读后核对 Executor 冻结的 Provider manifest 与公共 model；不匹配则失败，不发布资产。

### 规范事件与快照

中立快照字段与 `ai_core/README.md` v1 一致：`schema_version`、`workflow`、`scope`、`run_id`、`request_id`、`generation`、`sequence`、`kind`、`state`、`model`、`binding`、`payload`、`text`、`artifacts`、`tool_requests`。

- Begin 产生 `run_started`，sequence 从 1 开始；Runtime 负责幂等和代次，快照适配器只提交已接受事件。
- Executor `running/reconcile/succeeded/failed/cancelled` 分别映射到 `running/reconciling/succeeded/failed/cancelled`。
- `artifact_ready.payload` 至少包含 `asset_id`、`revision`、`content_sha256`、`artifact: {id, revision}`；Scene 完成后另含 `scene_id`、`scene_revision`、`scene_content_sha256`、`package_digest`。
- 同一 Controller 持久状态按 `(asset_id, revision, content_sha256)` 去重 artifact_ready；重启不重复提交 Provider，保留原 Executor run 和资产 revision。
- AICore 核心没有恢复接口，本阶段不伪造核心代次恢复：进程重启创建新的公共运行附着到原 Executor run，持久记录二者的显式关联；原 Executor run 和 Artifact revision 不变。

### 包摘要

包内不增加自引用 digest 字段。`next_asset`、server、client 和验收脚本使用同一算法计算：

```text
SHA256(
  "ENPAK1\0" +
  对 ("AssetManifest.json", canonical bytes)、("Scene.json", canonical bytes)
     以及按 content_sha256 排序的 ("blobs/<sha256>", blob bytes)：
     uint64_le(名称字节数) + 名称 UTF-8 + uint64_le(内容字节数) + 内容
)
```

该摘要覆盖清单、场景和全部 blob，不包含目录路径、文件时间或宿主元数据。

## 确定性、预算与失败语义

### Canonical JSON

- UTF-8、对象键按 Unicode 码点排序、无空白、无重复键；数组按 Schema 规定的稳定键排序，不保留无意义输入顺序。
- 字符串只转义必要控制字符、引号和反斜杠；非 ASCII 直接以 UTF-8 保存。
- 整数使用十进制；浮点仅允许有限值，使用 C++17 shortest-round-trip 后统一指数格式，`-0` 归一为 `0`。包由同一 C++ writer 生成，不要求与 Python 既有 Artifact canonical 字节相同。
- 输入 JSON 深度最多 32；AssetManifest.json 和 Scene.json 各最多 4 MiB。未知字段、非有限数、重复键、不安全整数均拒绝。

### 首批预算

| 项 | 上限 |
| --- | --- |
| 资产数／场景实体数 | 1024／256 |
| 单资产依赖数 | 256 |
| PNG／JPEG 单文件 | 16 MiB |
| PNG／JPEG 尺寸 | 1..16384 每轴，且总像素不超过 67,108,864 |
| GLB 单文件 | 64 MiB |
| GLB 顶点／三角形 | 1,000,000／2,000,000 |
| 包 blob 总量 | 256 MiB |
| 单次 Executor 请求／结果 JSON | 各 384 MiB，受 Controller 和 transport 双重限制 |
| Controller 状态文件／单个运行快照 | 各 16 MiB |
| 单命令超时／恢复等待 | 默认 60 s，可显式收窄；轮询间隔有界 |

预算在分配或读取完整文件前先按实际长度检查；解析与遍历也有深度和计数上限。

### 格式验证边界

- PNG：签名、IHDR、关键块顺序、尺寸、CRC、IDAT／IEND 和 trailing bytes；不解码像素。
- JPEG：SOI／EOI、段长、SOF 尺寸和熵编码段边界；不做视觉或完整解码验收。
- GLB：magic、version 2、声明长度、JSON／BIN chunk、对齐、buffer／bufferView／accessor 范围、POSITION 顶点与 index 三角形预算。buffer 和 image 只能引用内部 BIN／bufferView；外部 URI、data URI 和缺失依赖拒绝。不宣称几何、材质或视觉质量通过。
- 所有结构错误返回 `{code, path, message}`；诊断按 `(path, code)` 排序，包内路径只使用规定相对名。

### 安全发布

- 输入 root、输出包及所有父组件拒绝符号链接；只接受规定文件名和 `blobs/<64 lowercase hex>`，拒绝 `..`、绝对路径、反斜杠逃逸、重复路径和额外文件。
- 先在与目标相同的文件系统创建有界 staging 目录，完整写入、flush 并重读校验后，使用平台 no-replace 原子重命名；失败只清理本次 staging，来源和已有包不变。
- 已存在目标不覆盖。若恢复时发现目标已存在，则必须逐字节和包摘要完全一致才报告 `reconciled_existing`，否则 `already_exists`；不删除或改写对方包。
- 取消在 Runtime 立即进入 cancelled，再 best-effort 取消 Executor。迟到 create 结果只允许补发 Executor cancel；不得 export、发 artifact_ready 或发布包。编译后、原子重命名前再次核对运行和结果代次。

## 无 View Controller 与进程契约

### IProcessTransport

```text
Start(ProcessSpec{executable, arguments, stdin_bytes, limits}) -> ProcessId / structured error
WriteStdin / CloseStdin
Poll -> running / exited + bounded stdout/stderr + exit code
Cancel -> best-effort terminate, then bounded kill
Shutdown -> 回收全部拥有进程和临时资源
```

- executable 与 arguments 分离，Windows 使用 `CreateProcessW`，POSIX 使用 `posix_spawn`／wait 接口；不经过 shell。
- stdout／stderr 有界读取并避免管道死锁；超时、缺失 Python、无法启动、结果过大和畸形 JSON 均为明确错误。
- Controller 拥有 transport，View 不持有 PID、Executor 状态或文件句柄。
- 状态采用原子替换的 canonical JSON，记录 request、公共运行关联、Executor run、已发布 Artifact 和包发布状态；不记录凭据。

### 正常、取消和恢复序列

1. `Start` 冻结 model／binding，Begin 成功后启动 create；create 未成功前允许取消。
2. create 成功立即持久化 Executor run；之后按 status／step 推进，一次只进行一个外部操作。
3. succeeded 后调用现有 export；只有当前运行仍 running、代次匹配且未取消时才映射 Artifact。
4. 所有资产和 Scene 验证成功后发布 artifact_ready，再编译到 staging；最终复核通过后 no-clobber 发布并 completed。
5. 恢复入口只读取已有状态和 Executor run，先 status，再按 running／reconcile 继续 lookup／poll；不得再次 create 或盲目 submit。
6. Python 不存在只使 ai-run 返回 `python_unavailable`；validate／inspect／compile 和 M2 运行时仍正常工作。

## M2 场景消费设计

- 新增 `SceneRuntime` 装配值，保存场景身份、包摘要、PredictionModel 配置和按 EntityId 排序的 SpawnDefinition。
- `--asset-package PATH` 为可选参数；不提供时保持 M2 默认行为。提供时包内 fixed step／max speed 为权威值，拒绝同时用 `--fixed-step-ms` 覆盖。
- Server 和 Client 在网络启动前完整验证包并输出 `scene_id`、`scene_revision`、`scene_content_sha256` 和 `package_digest`；失败不启动传输。
- SessionManager 从 SpawnDefinition 创建实体并写入出生位置；重连不重新分配，welcome 的 fixed step 和 server tick 使用场景步长。
- Server 和 Client 的 PredictionModel／PredictionReconciler 使用同一步长和最大速度；snapshot server time、输入间隔、重连和 drain deadline 均消除硬编码 16。
- A 的预测／校正和 B 的远端插值沿用 M2；验收按 `spawn + 24 * max_speed * fixed_step_ms / 1000` 计算期望位置，不再固定断言 3.072。
- 三进程报告必须具有相同 scene_revision 和 package_digest；保留原重连、网络损伤、有界队列和优雅停服断言。
- `RuntimePackage.json` 和 Release 可执行包保持独立；M3 验收仅将 `.enpak` 作为另一明确输入复制到干净目录。

## legacy Godot 适配与白名单导入

`tools/engine_next_legacy/scene_adapter.gd` 只在显式 Godot 宿主进程运行：

- `publish`：读取已验证 `.enpak`，按 EntityId／parent 创建 Node3D／MeshInstance3D，应用局部 Transform 和玩法元数据，引用包内 GLB／PNG／JPEG；可保存新 `.tscn`，no-clobber。
- `verify`：直接读取同一包并实例化 legacy 节点，对实体、稳定 ID、父子、Transform、simulation 和 AssetRef 做结构化语义比较；不比较 `.tscn` 字节。
- `import`：只接受白名单 `.tscn` 中可映射的 Node3D／MeshInstance3D 层级、Transform、M3 gameplay 参数和本地自包含 GLB／PNG／JPEG；输出 BuildRequest 和 staged blobs，再由同一 C++ AssetCompiler 生成 `.enpak`。
- 对脚本、不支持的 Node／Resource、外部 URI、丢失或来源不明依赖、继承场景、`uid://` 重定向和不能保持语义的非默认属性明确失败，不静默忽略。
- legacy 输出目录及 `.tscn` 不进入新运行时链接、干净源码或运行闭包。

## 文件级实施设计

以下为确认后的计划文件，不代表已创建实现。

### PR 1：中立数据、Scene／Manifest、AICore 独立构建

新增：

```text
engine_next/include/EngineNext/Serialization/Json.h
engine_next/Serialization/Json.cpp
engine_next/include/EngineNext/Assets/{Types,AssetManifest,SceneDocument}.h
engine_next/Assets/{AssetManifest,SceneDocument}.cpp
engine_next/include/EngineNext/AI/WorkflowSnapshot.h
engine_next/AI/WorkflowSnapshot.cpp
engine_next/Schemas/{AssetManifest-v1,SceneDocument-v1,AiAssetRun-v1}.json
engine_next/Tests/Serialization/TestJson.cpp
engine_next/Tests/Assets/{TestAssetManifest,TestSceneDocument}.cpp
engine_next/Tests/AI/TestWorkflowSnapshot.cpp
```

修改：

- `engine_next/Tools/BuildRuntime.py`：加入中立库、独立测试和 `ai_core/Runtime.cpp` 的真实对象／链接清单。
- `engine_next/Tools/TestBuildRuntime.py`、`engine_next/Tools/ExportCleanSource.py`：真实输入和干净导出覆盖。
- `tools/engine_next_contract.json`、`tools/test_check_engine_next_contract.py`：显式允许 `ai_core` 公共核心和本 PR 标准／系统依赖；继续禁止 Godot。
- `ai_core/README.md`：只登记中立快照适配的消费者和边界，不改核心规则。
- `engine_next/build-impact.json`：按 native 实际输入更新，证据在实施时追加。

验收：JSON 正负例、Schema 漂移、ID／revision／依赖／Transform 语义、AICore 幂等／并发隔离／终态／迟到事件、无 Godot 符号和动态依赖。PR 1 不提供资产包或运行时场景消费。

### PR 2：资产编译、`.enpak`、`next_asset` 与格式负例

新增：

```text
engine_next/include/EngineNext/Assets/{BlobValidator,AssetCompiler,AssetPackage}.h
engine_next/Assets/{BlobValidator,AssetCompiler,AssetPackage}.cpp
engine_next/Apps/NextAssetMain.cpp
engine_next/Tests/Assets/{TestBlobValidator,TestAssetCompiler,TestAssetPackage}.cpp
engine_next/Tests/Fixtures/M3/{README.md, …受控最小 PNG/JPEG/GLB…}
```

修改：`BuildRuntime.py`、构建工具测试、干净导出、契约 CI 和 build-impact，加入 next_asset 的实际链接清单。

实现 `compile／validate／inspect`，覆盖去重 blob、确定性、no-clobber、原子失败、路径／链接／ID／revision／依赖／摘要／预算和全部格式负例。此 PR 不启动 AI 或 M2 场景消费。

### PR 3：IProcessTransport、无 View Controller、取消／恢复

新增：

```text
engine_next/include/EngineNext/AI/{IProcessTransport,ProcessTransport,WorkflowController,ArtifactAdapter}.h
engine_next/AI/{ProcessTransport,WorkflowController,ArtifactAdapter}.cpp
engine_next/Tests/AI/{TestProcessTransport,TestWorkflowController,TestArtifactAdapter}.cpp
engine_next/Tests/AI/SyntheticProvider.py
```

修改：

- `NextAssetMain.cpp`：仅增加 `ai-run` CLI View 与结构化输出。
- `BuildRuntime.py`／契约配置：加入真实进程适配和明确平台系统接口。
- `ExportCleanSource.py`：仅加入 `tools/ainative/{executor_cli,executor,contracts,extensions,editor_demo}.py` 和显式合成测试宿主；不复制 Godot 或 Provider 凭据。

复用现有 Executor Python 文件，不修改 DAG 或 Provider。覆盖真实 create／status／step／export、无 Godot、并发运行、取消迟到、崩溃恢复、未知提交 lookup、不重复 submit、凭据拒绝、Python 缺失和有界输出。

### PR 4：M2 场景消费、legacy 发布器与白名单导入器

新增：

```text
engine_next/include/EngineNext/Runtime/SceneRuntime.h
engine_next/Runtime/SceneRuntime.cpp
engine_next/Tests/Runtime/TestSceneRuntime.cpp
engine_next/Tools/RunM3SceneAcceptance.py
tools/engine_next_legacy/scene_adapter.gd
tools/engine_next_legacy/build-impact.json
tools/engine_next_legacy/fixtures/{Whitelist.tscn,ScriptRejected.tscn,UnsupportedNode.tscn, …}
```

修改：

- `RuntimeConfig.h/.cpp`、`RuntimeHost.*`、`World.*`、`SessionManager.*`、`ServerRuntime.cpp`、`ClientRuntime.cpp`：只增加场景装配和以场景值替换硬编码，不改协议。
- `RunM2Handshake.py`、`RunM2Soak.py`：可选资产包、身份摘要和由 Scene 推导的期望值；原无包入口继续回归。
- 构建与 CI：加入三进程同包验收及显式 Godot legacy host_tool 验收。

验收同一包的 A 预测校正、B 插值、重连、停服和语义一致的 legacy 读取／发布；白名单导入成功，所有禁止项有结构化诊断。

### PR 5：跨平台、干净环境与完整交付

修改 `.github/workflows/engine_next_contract.yml`、必要构建证据和设计验收映射；追加 `data-collection/` 与 `gonggong-diting-data/` 实际证据。

- Windows x86_64／MSVC、Linux x86_64 headless／Clang、macOS arm64／Clang分别记录实际结果，不外推。
- 两个干净目录重复构建包并比较 manifest／Scene／包摘要。
- 无 Godot 安装和缓存的干净环境完成 compile／validate／inspect／ai-run／M2 三进程闭环；AI 只使用明确声明的 Python 文件和解释器。
- 所有新目标执行 `--require-sources`、真实 `--require-link-manifest`、符号和动态依赖检查。
- 完整 AINative Python、AICore／AIChat／马良／天枢、M1／M1.1／M2 legacy 回归按实际候选运行。
- 最终回读 main、核对全部 13 条原始验收和五个 PR 后才收尾 #1240。

## 构建消费者与回退

- `engine_next`：`native`。中立数据、资产库、AICore 源和 CLI 直接进入实际对象／静态库／可执行文件；Schema 作为测试和编译输入入键。运行时资产不是编译输入。
- `.enpak`：`runtime_package`。在不变的 server／client 二进制上验证旧包／新包、同包三进程、错误摘要拒绝和恢复旧包；不覆盖 RuntimePackage.json。
- `tools/ainative` 既有 Executor：独立 Python `host_tool`，由 ProcessTransport 调用；M3 首选路径无需修改它。
- `tools/engine_next_legacy`：独立 Godot `host_tool`，记录宿主命令、输入／输出摘要、不支持格式和回退。
- 每个 PR 合入后均可用其前序 main 恢复；无资产包参数保持 M2 原行为，legacy Workbench 和 Godot AIWorkflowRuntime 始终保留。

## 验收标准

- [ ] 无 View Controller 使用真实 Executor 和离线／合成 Provider 完成工作流，无 Godot 进程。
- [ ] AICore generation／sequence、幂等、冻结输入、并发隔离、唯一终态和迟到拒绝通过。
- [ ] 取消后迟到结果不发布 Artifact 或资产包。
- [ ] 重启恢复不重复提交 Provider，保留 Executor run 与资产 revision。
- [ ] 两个干净目录的 canonical manifest、Scene 和包摘要一致。
- [ ] 路径逃逸、符号链接、重复 ID、错误 revision、悬空／循环依赖、非法 PNG／JPEG／GLB、错误摘要和超限输入全部失败。
- [ ] 同一包驱动 server + 两 client 完成 M2 权威模拟、预测、校正、插值、重连、停服和有界队列；三者 scene_revision／package_digest 相同。
- [ ] legacy Godot 读取同一场景并保持一致语义；不比较 `.tscn` 字节。
- [ ] 白名单 `.tscn` 导入成功，脚本、不支持节点／Resource、继承、UID、外部 URI 和语义不可保留属性明确拒绝。
- [ ] 现有 AI MVC、Controller、Executor、Provider 和 M2 回归通过。
- [ ] 新目标通过真实源码、链接清单、符号和动态依赖门禁。
- [ ] 无 Godot 安装／缓存的干净环境完成资产闭环；非 AI 运行不依赖 Python。
- [ ] Windows x86_64、Linux x86_64 headless、macOS arm64 只按实际结果验收。
- [ ] 五个 PR 均保留 legacy 回退，正式门禁、精确 CI、main 回读和 Issue 收尾完成。

## 待确认决策

1. 采用上述 AssetManifest／SceneDocument v1 字段、受限 ID／revision 和明确预算；如后续需要扩展，使用新 schema version，不在 v1 静默加字段。
2. M3 AI 宿主直接复用 `executor_cli.py`，不为 export 修改 `editor_host.py`；离线 copy 使用现有 `editor_demo:factory`，合成 Provider 仅用于测试。
3. AICore 进程重启时建立新的公共运行并附着原 Executor run，不伪造核心内部 generation 的持久恢复。
4. M2 新会话按升序分配两个场景 player_spawn，客户端身份仍由既有 welcome 返回，不新增网络字段。
5. 用户确认本设计和五个 PR 边界后，才从 PR 1 开始修改实现代码。

## 验证与采集证据

- PR 1／2 的中立契约、资产编译和包证据见 `data-collection/engine-next-assets-ai-workflow-m3-pr1-*` 与 `pr2-*`，对应 PR #1272／#1277 已合入。
- PR 3 的源码审查与本机验证见 `data-collection/engine-next-assets-ai-workflow-m3-pr3-r3-review.json`、`pr3-r3-verification.json` 和 `pr3-r3-build-impact.json`；R1／R2 审查与证据保留用于追踪 CI 格式、负责人和 Windows 兼容性修正。真实 Executor 离线／恢复／进程边界、52 个原生测试、ASan／UBSan、干净源码树和真实链接清单均已执行；Executor／contracts／extensions 定向回归共 44 项通过。
- PR 4 的独立审查见 `data-collection/engine-next-assets-ai-workflow-m3-pr4-review.json`；本机证据覆盖 54 个原生测试、同包与无包三进程、Godot 4.4.1 的导入／验证／发布／回读及禁止项。Windows／Linux 的 PR 4 结果仍以精确 CI 为准。
- 当前内置 Python 的 AINative 全量 422 项回归记录为 17 失败、42 错误、62 跳过，包含 `os.waitid` 缺失及关联 Provider／owned-process 失败，不得记为全量通过。完整 AI 回归、PR 5 和整单验收仍是独立待办。
