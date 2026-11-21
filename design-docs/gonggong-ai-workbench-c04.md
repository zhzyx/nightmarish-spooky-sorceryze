# C04　恢复模块的最近工作位置

天璇为每个登录账号保存项目内各业务模块的最近位置。切换模块的客户端在离开 A 前保存 A，到达 B 时读取 B，回到 A 时用其稳定模块 ID 读取 A。服务端使用同一 SQLite 数据库，重启服务、注销后重新登录都可恢复。[原工单 #1784](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1784) · [方案一 C04](gonggong-ai-workbench-plan1.md#c04) · [上游 C02](gonggong-ai-workbench-c02.md)

## 保存与恢复

在 `/api/v1/business-modules/{module_id}/location?project=studio/game` 上使用以下两个操作。项目省略时取 `workspace`。模块 ID 使用业务模块列表返回的稳定值，包括项目内的 `default`。

| 操作 | 输入 | 成功响应 |
| --- | --- | --- |
| `PUT` | 完整工作位置，包含必填的 `position`，可附 `issue_id` 和 `conversation_id` | `{"location": {...}}`，两个可选引用省略时回读为 `null` |
| `GET` | 当前项目和模块 | 上一次成功保存且仍可访问的位置，初次到达或引用已失效时返回 `{"location": null}` |

例如，保存工单评论区时可传 `{"issue_id":"iss_…","conversation_id":null,"position":"issue/comments#7"}`。工单使用 C02 的真实工单 ID，对话使用已创建的工作台私人会话 UUID。位置串由调用端定义，长度为 1 至 2048 个字符，服务端原样保存。整组替换，最后提交的写事务生效，相同输入重试得到相同位置。[请求格式](../customizations/components/tianxuan/server/schemas.py) · [HTTP 入口](../customizations/components/tianxuan/server/api.py)

服务端从已认证身份派生租户与用户。位置表以租户、用户、项目、模块 ID 为联合主键。查询和写入都在单次事务中核对模块、工单当前归属与祖先需求读权，以及对话的真实所有者。失去引用读权时整组位置隐藏，重新获得读权后可恢复。工单移出模块后旧模块同样返回空位置。写入沿用 editor/admin 角色，权限拒绝或引用错误会回滚，保留先前成功的记录。私人位置响应禁止缓存。[领域实现](../customizations/components/tianxuan/server/tianxuan_core.py)

## 验收与接收

账号 A 和 B 登录同一租户。A 保存默认模块的工单、私人对话和评论位置，切换到另一个模块保存不同工单，再回到默认模块读回原三项。B 初次读取同一模块得到空位置，能保存自己的位置，也能读取同一张共有工单。B 使用 A 的对话 ID 写入时收到 404。重开数据库和原生 HTTP 应用后，A 重新登录，双方及两个模块分别恢复原值。

独立用例还覆盖同名默认模块跨项目和租户、禁用仅靠身份头读取私人位置、重复保存、祖先需求撤权和恢复、工单移出模块。回执含原生账号认证、真实 HTTP 回读、运行版本和候选文件标识。[定向用例](../customizations/components/tianxuan/server/test_module_locations.py) · [执行回执](../data-collection/gonggong-ai-workbench-plan1-c04.json)

C06 模块选择器可按模块 ID 调用保存与恢复接口。D12 可用返回的工单和对话 ID 接续草稿，I13 可按工单 ID 定位天枢在途工单。各后继按自己的其他前置接单。[C06 #1744](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1744) · [D12 #1748](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1748) · [I13 #1755](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1755)
