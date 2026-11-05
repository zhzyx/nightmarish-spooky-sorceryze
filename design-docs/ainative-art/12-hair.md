# 12-hair 毛发生成、绑定与分级表现

稳定需求 ID：ainative-art-12-hair-20261106

父设计：[AINative 美术与人物工作流](../ainative-art-pipeline-20261106.md)。父工单见总设计回执；本页仅用于本子项身份。

范围：头皮、发根、Guide、Hair Cards/Mesh、动态骨骼、碰撞与 LOD；Strands 后续扩展。

验收：头发单独生成与绑定；换脸型后重绑定；Cards/Mesh 回退可用；LOD 和帽子遮挡组合可验收。

前置：10-customization-face。

非目标：其他子项的完整实现；任务登记不表示功能通过。

主责：Codex / kaiyunxue（当前操作者）；目标 main；先 intake-only，交付通过正式门禁和精确候选 CI。必要检查：契约单使用单元测试，其余使用该范围内真实资产、编辑器回放或目标工具回读；保留失败证据。
