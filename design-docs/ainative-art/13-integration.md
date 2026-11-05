# 13-integration 端到端角色工作台验收

稳定需求 ID：ainative-art-13-integration-20261106

父设计：[AINative 美术与人物工作流](../ainative-art-pipeline-20261106.md)。父工单见总设计回执；本页仅用于本子项身份。

范围：整合示例场景、生成来源、错误恢复、发布、性能记录及原始需求覆盖。

验收：文字+图片生人物→目标骨架→独立装备→文字/视频动画→上下身/武器/脸部→布料毛发→保存重开发布；UE/Mixamo 分别回读。

前置：03-editor, 04-generators, 06-skeleton-interop, 07-garments, 08-motion-generation, 09-layering-equipment, 10-customization-face, 11-cloth, 12-hair。

非目标：其他子项的完整实现；任务登记不表示功能通过。

主责：Codex / kaiyunxue（当前操作者）；目标 main；先 intake-only，交付通过正式门禁和精确候选 CI。必要检查：契约单使用单元测试，其余使用该范围内真实资产、编辑器回放或目标工具回读；保留失败证据。
