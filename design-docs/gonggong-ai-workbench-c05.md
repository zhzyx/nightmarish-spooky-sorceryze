# C05　单条消息的上下文快照

天璇工作台在接收消息时，将本轮选择和消息 UUID 放入同一条私有会话记录。先提交数据库事务，再调用模型。模型回复、后续提问和设计草稿均沿用各条消息自己的引用。旧客户端可继续只发送正文和期望会话版本，已有记录按原格式读取。[原工单 #1864](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1864) · [方案一 C05](gonggong-ai-workbench-plan1.md#c05) · [前置 C02](gonggong-ai-workbench-c02.md)

## 发送与回读

在 `POST /api/v1/workspace/conversations/{key}/turns` 的 `id`、`content`、`expected_version` 旁提交可选的 `context_snapshot`。发送方从当前选区一次取出完整快照，重试时使用首次发送的消息 UUID 和载荷。下面的项目与模块键、工单和文档 ID 应替换为当前账号实际读到的值。

```json
{
  "project": "studio/game",
  "module_id": "default",
  "issue_id": "iss_example",
  "references": [
    {"kind": "document", "object_id": "doc_example", "revision": 1}
  ]
}
```

| 字段 | 来源与消费 |
| --- | --- |
| `project`、`module_id`、`issue_id` | 取自 C02。服务使用当前身份回读工单及其项目、模块归属。工单可以为空，此时单独核对租户下的项目与模块。 |
| `references` | 按发送顺序保存，每条至少含对象和精确修订。空数组表示该消息无对象引用。 |
| `kind=document` | 使用天璇文档 ID 和正整数版本。接收前校验文档读权和版本存在。打开原件时用当前凭据请求 `GET /api/v1/docs/{object_id}/versions/{revision}`。 |
| `kind=editor` | 编辑器提供含来源的对象标识，例如 `res://scenes/Hero.tscn#Arm`，以及 40 或 64 位小写十六进制修订摘要。服务按值保存标识和摘要。选区提供者负责从真实输入取修订，打开时由来源宿主核对身份与字节。 |

在 `GET /api/v1/workspace/conversations/{key}` 的 `turns` 中按消息 ID 读取 `context_snapshot`。在同一会话重复发送同一 ID、正文和快照，返回现有记录；同一 ID 改换快照会返回 409。会话仍按租户和本人隔离，打开引用时仍经来源服务授权。快照只携带定位字段。[服务入口和事务](../customizations/components/tianxuan/server/workspace_conversations.py) · [客户端数据类型](../apps/tianxuan/lib/workspace-conversations.ts)

## 验收

从仓库根运行 `python -B -X utf8 -m pytest -q -p no:cacheprovider customizations/components/tianxuan/server/test_workspace_conversations.py customizations/components/tianxuan/server/test_module_issues.py`。实测创建两个同名模块、工单及文档，发送第一条消息后切到第二组选区，将原文档改为第 2 版并移动原工单。再次发送后，模型网关收到两条消息各自的原始引用。重启 HTTP 服务、重开 SQLite，通过第一条消息的引用读回第 1 版正文，通过第二条读回另一份同名文档。受限账号、范围不匹配、缺失版本和可变修订的拒绝路径均核对了返回状态。测试使用认证应用接口、隔离数据库和 HTTP 模型替身。[定向用例](../customizations/components/tianxuan/server/test_workspace_conversations.py) · [候选和实际回执](../data-collection/gonggong-ai-workbench-plan1-c05.json)

C08 负责选区失效判定，D01 消费消息快照实现现场咨询。U08、U10、U11、U12 提供页面选区输入，U15 展示及移除草稿引用。上述后继从本条消息契约取得数据，各自核对原生交互验收。[方案一任务索引](gonggong-ai-workbench-plan1.md)
