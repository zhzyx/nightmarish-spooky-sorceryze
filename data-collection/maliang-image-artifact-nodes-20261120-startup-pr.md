<!-- gonggong-request:maliang-image-artifact-nodes-20261120 -->

## 范围

- 图片生成后创建动态生成物节点，展示全部缩略图，支持逐张预览、批量下载、删除及提示词变更后的结果刷新。
- 每轮 Mesh 生成／调整都创建独立生成物节点，按轮次展示实际 GLB，支持逐轮保存及固定轮次下游输入。
- 指定轮次连线保存 Artifact 引用和不可变快照，工作流重开后仍使用同一轮次，不重新生成上游。
- 图片和 Mesh 的节点本体及缩略图双击均放大正确结果，并与右下角共用最大化、旋转、缩放和还原逻辑。
- 修复 fresh 安装仍引用已删除 `offline` 模式名的问题：首次安装选择 `local_mesh`，恢复内置模型连接，并携带正确的内置 Python 与宿主边界。

Fixes #1679

## 验证

- 图片、Mesh 生成物专项及双击目标与还原回归通过。
- 真实 Executor 合成回归：指定轮次作为直接不可变输入，不重新生成原上游；预览接口返回全部轮次并允许选择对应 Artifact。
- fresh 启动专项：自动恢复连接、选择 `local_mesh`、携带内置 Python 和宿主路径均通过；夹具仅使用假解释器，不启动真实模型。
- 多图、节点预览、端口契约、统一设置及提示词刷新 Godot 回归通过。
- AINative Python：491 项通过，62 项按环境跳过；最终格式修正后受影响测试与全部 5 个 Python 变更文件的 Ruff 检查通过。
- macOS arm64 编辑器构建成功：`4d303a00c997060d6b0ec88f5f794e0ae59182e8ff408465c3bd87ba9bac9897`。
- 实际 bundle：`325ba9a39afca904aca7da2239294a5b22dacae58a7a8ca346e77f2529050bc9`；原生入口、独立项目、样例兼容、运行时迁移及安装文件与清单 SHA256 一致性均通过。
- 用户已确认验收通过并授权合入 main。

## 证据边界

专项生成测试使用本地合成 GLB、图片、Provider 和假解释器，未调用外部模型，不宣称真实 Tripo 生成或模型质量验收。实现与验证由 `kaiyunxue` 完成，未将自评声明为独立代码审查；用户业务验收不替代精确候选 CI。

旧 PR #1682 与 #1691 的 Windows `maliang-offline / package-and-run` 均在“本地连接会话归属”检查失败，本次已定位并修复共同的 fresh 自动启动根因。当前候选必须重新通过对应检查；正式门禁、独立审查要求、精确候选 CI 和 main 回读分别核对。

本文件是 fresh 启动修复候选的追加交付说明，历史说明和验证回执保持不变；对应验收记录见 `data-collection/maliang-image-artifact-nodes-20261120-startup-validation.json`。
