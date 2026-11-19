<!-- gonggong-request:maliang-stability-batch-20261120 -->

## 范围

- 动态 Review：输入分析生成任务专属 `review_plan`，渲染、报告校验和定向缺项补审共享计划；人物不再默认追加头部视图。
- 生成结果持久化：工作流保存并恢复单图、图像集和 GLB 的完整结果，重开后直接预览，不重新执行生成。
- 生成服务配置：完成 #1624 的分服务草稿持久化、offline 移除和旧配置迁移，本地复制保持可用。

Fixes #1625
Fixes #1624

## 验证

- AINative Python：489 项通过，62 项按条件跳过。
- macOS arm64 编辑器构建成功：`f856b7bdba39f04a0ba989e788df359b8fcb47e06175a34363668f08b6cc15a7`。
- 实际 bundle：`e23e75f74c15b902db876006135ff73a60a4d1ea53c052fb65661e0325362258`。
- 隔离原生工作台：mesh-and-rig 164 项、independent-project 108 项、sample compatibility 22 项、relocated runtime 5 项通过。
- 配置界面 HTTP 夹具：113 项通过，覆盖草稿、切换、重开、异步检测和迁移。
- 图像集工作流：36 项通过；图像／GLB 节点预览：49 项通过。
- 新 bundle 动态渲染通过：右手正／背与下盔甲视图，未启用头部门禁。

## 证据边界

使用合成夹具和真实 Godot 渲染，未调用真实 AI 推理或重新生成模型。首次全量构建在任务时限处中断，增量续跑成功。复用受污染测试项目的补充入口检查未计入证据，清洁隔离 runner 全部通过。

实现与验证由 `kaiyunxue` 完成。未将自评声明为独立审查；正式门禁、精确候选 CI 和 main 回读在后续交付步骤核对。
