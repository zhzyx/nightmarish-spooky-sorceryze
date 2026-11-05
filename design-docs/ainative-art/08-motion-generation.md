# 08-motion-generation 文字与视频生成动画

稳定需求 ID：ainative-art-08-motion-generation-20261106

父设计：[AINative 美术与人物工作流](../ainative-art-pipeline-20261106.md)。父工单见总设计回执；本页仅用于本子项身份。

范围：文字动作生成、视频身体/手/脸流、时间基准、置信度、遮挡、接触与动作清理。

验收：文字动作及视频动作各一条真实链路；重定向前明确源 Profile；低置信区可修正；帧率、根运动、循环可验证。

前置：05-rigging, 06-skeleton-interop。

非目标：其他子项的完整实现；任务登记不表示功能通过。

主责：Codex / kaiyunxue（当前操作者）；目标 main；先 intake-only，交付通过正式门禁和精确候选 CI。必要检查：契约单使用单元测试，其余使用该范围内真实资产、编辑器回放或目标工具回读；保留失败证据。
