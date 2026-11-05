# 04-generators 图像与 Mesh 生成节点

稳定需求 ID：ainative-art-04-generators-20261106

父设计：[AINative 美术与人物工作流](../ainative-art-pipeline-20261106.md)。父工单见总设计回执；本页仅用于本子项身份。

范围：文生图、图生图、图生 Mesh、文生 Mesh；文字与图片可追加到各阶段。

验收：至少一个实际 Provider 完成四种流程并留版本/参数/来源；mock 不能替代真实生成验收；缺能力显式返回不支持。

前置：02-executor, 03-editor。

非目标：其他子项的完整实现；任务登记不表示功能通过。

主责：Codex / kaiyunxue（当前操作者）；目标 main；先 intake-only，交付通过正式门禁和精确候选 CI。必要检查：契约单使用单元测试，其余使用该范围内真实资产、编辑器回放或目标工具回读；保留失败证据。
