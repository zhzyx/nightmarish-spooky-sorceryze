# 马良图片与 Mesh 的动态生成物节点

<!-- gonggong-request:maliang-image-artifact-nodes-20261120 -->

2026-11-20，用户最初要求在生成 Mesh 流程的图片生成之后增加可下载、可串联的动态生成物节点，随后要求支持删除及提示词变更后的结果刷新。后续需求扩展到 Mesh 逐轮生成物、每轮保存与下游输入、节点内直接 Mesh 渲染，以及所有展示节点双击放大。用户已确认全部验收完成并授权合入 main。

## 产品行为

### 图片生成物

- 图片生成成功后创建展示层“图片生成物”节点，显示本次结果的全部缩略图，并支持逐张预览及批量下载到项目目录。
- 图片结果被生成 Mesh 等下游节点引用时，画布展示为“生成图片 → 图片生成物 → 下游节点”；动态节点不进入实际执行 DAG，也不作为正式节点序列化。
- 动态节点采用圆角、青色边框，与正式流程节点区分；生成或恢复结果后按依赖分栏、按实际尺寸留白并适度缩放，避免重叠及完整链路被裁出视野。
- 动态节点支持右键及 Delete 删除。删除仅影响展示，不移除正式节点、生成历史或图片文件；普通重排不恢复已删除节点，新一次运行会显示该次结果。
- 单节点运行与整个工作流运行都会回读成功图片结果。提示词变更后，动态画廊与右侧预览同步到新生成的图片。

### Mesh 逐轮生成物

- 每次视觉引导生成／调整轮次都发布独立、不可变的 Mesh Artifact，正式 `result` 端口仍只指向最终交付，不改变既有执行契约。
- 每轮创建一个“Mesh 生成物”节点，按生成顺序串联并显示审核状态。节点直接渲染该轮实际 GLB，可独立交互预览和保存原始 GLB。
- 普通下游连线默认使用最终轮次；从指定轮次节点连线时，下游固定使用该轮 Artifact 的字节和 provenance，不得悄悄改用最终轮次。
- 指定轮次作为输入时以不可变快照编译为目标节点的直接输入；单节点运行不会因此重新生成原上游节点。工作流保存、重开后仍恢复全部轮次及指定轮次连线。
- 删除轮次展示节点不影响正式节点、历史或其他轮次文件；显式新结果可以恢复被删除的展示节点。

### 统一预览交互

- 图片和 Mesh 的展示节点本体、缩略图都支持双击放大，放大目标绑定当前图片或当前 Mesh 轮次。
- 双击复用右下角预览的最大化、旋转、缩放及还原逻辑；选择 Mesh 轮次后，右侧交互预览自动滚动到可见位置。
- 最大化窗口切换后不再对原 ScrollContainer 执行失效的延迟滚动。

## 实现范围

- `samples/ainative-workbench/addons/ainative/workbench.gd`：图片与 Mesh 动态节点、逐轮保存、固定轮次连线、持久化、直接预览、双击放大、删除、自动布局及结果刷新。
- `samples/ainative-workbench/addons/ainative/mesh_artifact_preview.gd`：节点内实际 GLB 渲染、相机取景和灯光。
- `samples/ainative-workbench/artifact_node_acceptance.gd`：图片画廊、下载、双击目标与还原、引用及布局验收。
- `samples/ainative-workbench/mesh_artifact_node_acceptance.gd`：逐轮 GLB 渲染、逐轮保存、固定输入、持久化、双击目标与还原验收。
- `samples/ainative-workbench/prompt_refresh_acceptance.gd`：全工作流提示词变更、结果刷新及动态节点删除验收。
- `tools/ainative/kimi_provider.py`：保存并发布全部审核轮次的不可变 Mesh Artifact。
- `tools/ainative/editor_host.py`：轮次预览、轮次选择与固定快照输入编译。
- `tools/ainative/test_editor_host.py`、`tools/ainative/test_mesh_vision.py`：轮次清单、预览传输和真实 Executor 固定输入回归。
- `tools/ainative/test_prompt_refresh_factory.py`：仅用于测试的本地提示词敏感图片 Provider，不进入内置运行包，不调用外部模型。

## 验收

- [x] 动态节点展示全部图片，下载文件与原图 SHA256 一致，引用连线和保存恢复正常。
- [x] 每轮 Mesh 都有独立生成物节点和实际 GLB 渲染，逐轮保存保持原始字节。
- [x] 指定轮次连线在真实 Executor 中使用该轮固定快照，不重新生成上游，不替换为最终轮次。
- [x] 图片和 Mesh 的节点本体与缩略图双击均放大正确结果，并按同一逻辑还原。
- [x] 动态节点删除、普通重排、显式新结果及工作流保存重开行为符合契约。
- [x] AINative Python 491 项测试通过，62 项按环境跳过；生成物、多图、节点预览、端口及提示词刷新 Godot 回归通过。
- [x] macOS arm64 编辑器候选构建成功；原生入口、实际安装 bundle、规范化源码与清单 SHA256 一致。
- [x] 用户确认验收通过并授权合入 main。

## 证据边界

专项生成测试使用本地合成 GLB、图片和 Provider，未调用外部模型，不宣称真实 Tripo 生成或模型质量验收。旧 PR #1682 的 Windows `maliang-offline / package-and-run` 在“本地连接会话归属”检查失败；新候选必须重新通过对应精确候选 CI，旧结果不作为通过证据。
