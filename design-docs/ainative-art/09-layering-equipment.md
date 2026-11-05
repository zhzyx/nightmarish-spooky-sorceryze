# 09-layering-equipment 上下半身分层与手持物

稳定需求 ID：ainative-art-09-layering-equipment-20261106

父设计：[AINative 美术与人物工作流](../ainative-art-pipeline-20261106.md)。父工单见总设计回执；本页仅用于本子项身份。

范围：动画层、骨骼遮罩、Socket、主副手握点、手指姿态、IK、冲突优先级。

验收：跑步瞄准、单手挥剑、双手武器及换装组合可回放；主手/道具/副手无循环依赖；全身动作正确覆盖局部层。

前置：07-garments, 08-motion-generation。

非目标：其他子项的完整实现；任务登记不表示功能通过。

主责：Codex / kaiyunxue（当前操作者）；目标 main；先 intake-only，交付通过正式门禁和精确候选 CI。必要检查：契约单使用单元测试，其余使用该范围内真实资产、编辑器回放或目标工具回读；保留失败证据。
