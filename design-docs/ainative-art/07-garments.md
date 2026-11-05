# 07-garments 独立衣服盔甲生成、拟合与装配

稳定需求 ID：ainative-art-07-garments-20261106

父设计：[AINative 美术与人物工作流](../ainative-art-pipeline-20261106.md)。父工单见总设计回执；本页仅用于本子项身份。

范围：面向角色或 AvatarProfile 独立生成；刚性/蒙皮/布料分区；共享骨和附属骨；派生拟合、遮挡及换装。

验收：独立上衣、胸甲、带裙摆装备各完成生成和装配；同 Profile 两个体型可拟合；越界体型报告失败；源衣服不被覆盖；UE/Mixamo 骨架各验证一例。

前置：05-rigging, 06-skeleton-interop。

非目标：其他子项的完整实现；任务登记不表示功能通过。

主责：Codex / kaiyunxue（当前操作者）；目标 main；先 intake-only，交付通过正式门禁和精确候选 CI。必要检查：契约单使用单元测试，其余使用该范围内真实资产、编辑器回放或目标工具回读；保留失败证据。
