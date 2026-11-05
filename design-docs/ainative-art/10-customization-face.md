# 10-customization-face 捏人捏脸与面部叠加

稳定需求 ID：ainative-art-10-customization-face-20261106

父设计：[AINative 美术与人物工作流](../ainative-art-pipeline-20261106.md)。父工单见总设计回执；本页仅用于本子项身份。

范围：CharacterDNA 参数、形变修正、衣服再拟合、面部通道/口型/表情/注视仲裁。

验收：体型和脸型保存重开一致；极限参数校验；捏人后装备更新；身体动作与表情口型叠加，头颈写入无冲突。

前置：05-rigging, 07-garments, 08-motion-generation。

非目标：其他子项的完整实现；任务登记不表示功能通过。

主责：Codex / kaiyunxue（当前操作者）；目标 main；先 intake-only，交付通过正式门禁和精确候选 CI。必要检查：契约单使用单元测试，其余使用该范围内真实资产、编辑器回放或目标工具回读；保留失败证据。
