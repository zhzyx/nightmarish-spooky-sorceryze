# C02　模块和工单关系

一个业务模块可有多张工单。建单时沿用 C01 的 `project` 和 `module_id`，已有工单可在所在项目内调整模块。标题用于显示，客户端从列表保存工单 `id`，用它回读详情。工单编号 `number` 在租户内标识工单，列表按编号升序返回。[原工单 #1866](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1866) · [方案一 C02](gonggong-ai-workbench-plan1.md#c02) · [前置 C01](gonggong-ai-workbench-c01.md)

## 接口

| 操作 | 已认证的天璇接口 | 回读行为 |
| --- | --- | --- |
| 按模块列单 | `GET /api/v1/issues?project=studio/game&module_id=default` | 返回该租户和项目中归属此模块、且调用者有权读取的工单。可与原有 `requirement_id` 和 `status` 组合。 |
| 工具列单 | `POST /api/v1/tools`，工具名 `issue.list` | payload 接受 `project`、`module_id` 和原有 `requirement_id`。返回同一来源的 `issues` 列表。 |
| 定位一张工单 | `GET /api/v1/issues/{issue_id}` | 返回指定 ID 对应的可见工单，含编号、标题及当前项目和模块。 |
| 将已有工单关联到指定模块 | `PUT /api/v1/issues/{issue_id}/module?project=studio/game`，正文为 `{"module_id":"default"}` | 返回最新工单。相同值重试返回原记录。其他项目的工单或模块返回 404。 |

查询只传项目时可读取该项目所有可见工单，只传模块时选择 `workspace`。两个参数均省略时沿用原租户可见工单列表。每个项目都有自己的 `default`。自定义模块 ID 在查询和写入时均按租户与项目校验。读取工单继承关联需求及所有祖先工单的可见权限。写入还要求 editor/admin 角色及相应需求的写权限。[领域服务](../customizations/components/tianxuan/server/tianxuan_core.py) · [HTTP 入口](../customizations/components/tianxuan/server/api.py)

SQLite 在 C01 的旧表升级完成后建立 `(tenant_id, project, module_id, number)` 索引。调整模块时在同一写事务内核对权限、项目和模块并更新指定 ID 的工单。子单在创建时继承上级的默认归属，后续调整只作用于被选中的工单。

## 验收与下游

原生认证 TestClient 创建两个同名模块和三张同名工单。测试逐个按工单 ID 打开，然后将第二张工单从第一个模块移到第二个模块并重试。重开 SQLite 和 HTTP 应用后，第一个模块返回编号 1，第二个模块返回 2、3。REST 和工具端返回相同的工单 ID。独立用例覆盖跨租户及项目、同名默认模块、viewer、私有祖先需求、已有过滤参数及无筛选调用。[定向用例](../customizations/components/tianxuan/server/test_module_issues.py) · [实测 HTTP 回读与候选版本](../data-collection/gonggong-ai-workbench-plan1-c02.json)

接收方可将项目、模块 ID 和工单 ID 交给位置恢复、消息快照及建单消费端。各后继还须核对自己的其他依赖。[C04 #1784](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1784) · [C05 #1864](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1864) · [I01 #1859](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1859)
