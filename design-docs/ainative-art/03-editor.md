# 03-editor 引擎内工作流编辑与发布

稳定需求 ID：ainative-art-03-editor-20261106

父设计：[AINative 美术与人物工作流](../ainative-art-pipeline-20261106.md)。父工单见总设计回执；本页仅用于本子项身份。

范围：节点编辑、上下文补充、任务进度、预览、人工确认、Godot Resource/Scene 发布。

验收：在引擎内保存重开图；图片与 Mesh 可预览；失败保留源资产；发布文件可重导入；编辑器不阻塞。

前置：01-contracts, 02-executor。

非目标：其他子项的完整实现；任务登记不表示功能通过。

主责：Codex / kaiyunxue（当前操作者）；目标 main；先 intake-only，交付通过正式门禁和精确候选 CI。必要检查：契约单使用单元测试，其余使用该范围内真实资产、编辑器回放或目标工具回读；保留失败证据。
