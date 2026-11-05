# 06-skeleton-interop UE 与 Mixamo 骨骼兼容

稳定需求 ID：ainative-art-06-skeleton-interop-20261106

父设计：[AINative 美术与人物工作流](../ainative-art-pipeline-20261106.md)。父工单见总设计回执；本页仅用于本子项身份。

范围：独立版本 Profile；语义映射、参考姿态、骨轴、根运动、辅助骨、模型重绑与动画重定向。

验收：UE4、UE5 Manny/Quinn、Mixamo 各有授权测试夹具；模型目标绑定与双向动画重定向分别验收；接触/根运动/手指检查；导出经目标工具回读。MetaHuman Body 单独扩展，面部不计入身体兼容。

前置：05-rigging。

非目标：其他子项的完整实现；任务登记不表示功能通过。

主责：Codex / kaiyunxue（当前操作者）；目标 main；先 intake-only，交付通过正式门禁和精确候选 CI。必要检查：契约单使用单元测试，其余使用该范围内真实资产、编辑器回放或目标工具回读；保留失败证据。
