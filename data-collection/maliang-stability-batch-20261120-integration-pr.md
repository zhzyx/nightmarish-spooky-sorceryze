<!-- gonggong-request:maliang-stability-batch-20261120 -->

## 范围

- 动态 Review：输入分析生成任务专属 `review_plan`，渲染、报告校验和定向缺项补审共享计划；人物不再默认追加头部视图。
- 生成结果持久化：工作流保存并恢复单图、图像集和 GLB 的完整结果，重开后直接预览，不重新执行生成。
- 本候选基于 `226ec1dc0adb89d7a5e07b57644289dd3ead9da4`，保留主线已交付的 #1624 服务配置实现；不重复改写该实现或其历史证据。

Fixes #1625

## 主线整合

旧候选 #1646 的精确 head CI 已全部通过，但 main 前进后出现真实路径冲突，未直接合入。本次在隔离工作树整合最新 main，唯一文本冲突为 #1624 的旧验证回执，保留主线版本；业务源码与旧候选逐字一致。新候选仍须独立取得审查和精确 head CI。

## 整合后验证

- AINative Python：489 项通过，62 项按条件跳过。
- 隔离原生工作台：mesh-and-rig 164 项、independent-project 108 项、sample compatibility 22 项、relocated runtime 5 项通过。
- 配置界面 HTTP 夹具：113 项通过，覆盖草稿、切换、重开、异步检测和迁移。
- 编辑器：`f856b7bdba39f04a0ba989e788df359b8fcb47e06175a34363668f08b6cc15a7`；实际 bundle：`e23e75f74c15b902db876006135ff73a60a4d1ea53c052fb65661e0325362258`。
- `git diff --cached --check` 通过；整合后的 samples、tests 与 AINative tools 和已构建旧候选一致。

## 证据边界

使用合成夹具和真实 Godot 渲染，未调用真实 AI 推理或重新生成模型。旧候选的 macOS Engine Next 网络排干验收经定向重试通过；该结果不冒充新候选 CI。实现者自评不作为独立审查，正式门禁、独立审查、精确候选 CI 和 main 回读在后续交付步骤核对。
