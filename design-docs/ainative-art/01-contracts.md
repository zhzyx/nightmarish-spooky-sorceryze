# 01-contracts 资产、上下文与扩展契约

稳定需求 ID：ainative-art-01-contracts-20261106

父设计：[AINative 美术与人物工作流](../ainative-art-pipeline-20261106.md)。父工单见总设计回执；本页仅用于本子项身份。

范围：版本化 Artifact、带角色/局部作用域的文字图片上下文、不可变依赖、节点能力与发布适配器契约。衣服允许先生成后绑定。

验收：契约往返序列化；拒绝悬空依赖、循环与不匹配绑定；未知扩展类型保留；独立装备及 UE/Mixamo 目标请求样例通过。

前置：无。

非目标：其他子项的完整实现；任务登记不表示功能通过。

主责：Codex / kaiyunxue（当前操作者）；目标 main；先 intake-only，交付通过正式门禁和精确候选 CI。必要检查：契约单使用单元测试，其余使用该范围内真实资产、编辑器回放或目标工具回读；保留失败证据。

## 本次实现与验收映射

实现位置：tools/ainative/contracts.py、extensions.py；Windows / Python 3.11+ 标准库，无新增运行依赖。范围为数据契约和接口验证，不执行真实生成、不编译 Godot。

| 原验收项 | 实现和验证 |
| --- | --- |
| 契约往返序列化 | canonical、版本化 NodeRegistry 深拷贝注册和 JSON 往返测试 |
| 拒绝悬空依赖、循环及不匹配绑定 | Manifest 验证及 input/output 版本、类型检查；保留原始 10 项测试 |
| 未知扩展类型保留 | Artifact payload 不解释；节点端口按插件声明的类型字符串校验，合成扩展样例往返无损 |
| 独立装备、UE/Mixamo 目标请求 | unbound 衣服可无目标；两个骨架 Profile 目标请求分别通过，过期版本和错误类型拒绝 |
| 节点能力及上下文 | 图文上下文 role/scope/strength 保留；节点或 Provider 不支持图片时拒绝调用 |
| Provider 与发布适配器契约 | describe/submit/poll/cancel Protocol、状态和输出验证；PublishAdapter 纯编码与单文件独占发布，已有文件不覆盖，失败不留下临时文件 |

必要检查：`python -m unittest discover -s tools/ainative -p "test_*.py"`，当前 22 项通过，包含节点定义及终态回执的 JSON 数字类型不可变回归。停止条件为本单契约验收与仓库交付检查通过；实际 API、持久执行器、多文件 Godot 发布、骨骼几何兼容仍分别由 #143 以后工单负责。远端 main 接收及关闭由主执行者追加，当前实现者不以本地测试代替交付。
