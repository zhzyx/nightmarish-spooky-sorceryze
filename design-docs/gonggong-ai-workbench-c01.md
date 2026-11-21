# C01　业务模块稳定标识

本卡为天璇工单增加项目内稳定的模块引用。业务模块属于账号所在租户，项目键沿用迁移入口的 `project`，可取 `studio/game` 或单段名称。显示名支持重名，工单保存 `project` 和 `module_id`。改名只更新模块名称。[C01 验收](gonggong-ai-workbench-plan1.md#c01) · [工单 #1868](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1868) · [B02 接口盘点](gonggong-ai-workbench-b02.md)

## 产品接口

| 操作 | 已认证的天璇接口 | 回读行为 |
| --- | --- | --- |
| 列出模块 | `GET /api/v1/business-modules?project=studio/game` | `modules` 中的每项包含 `id`、`project` 和 `name`。同名记录可按 ID 区分。 |
| 新建模块 | `POST` 同一路径，传 `name` 和 `call_id` | 返回服务生成的 `mod_` 前缀 UUID。重试同一请求返回原回执，不同调用键可以创建同名模块。 |
| 重命名 | `PATCH /api/v1/business-modules/{module_id}?project=studio/game`，传 `name` | 返回原 ID 和新名称。其他项目、租户中的自定义模块 ID 不可用于此操作。 |
| 建单和回读 | `POST /api/v1/tools` 的 `issue.create` 在 payload 接受 `project`、`module_id` | `GET /api/v1/issues` 中的可见工单持有这两个引用字段。省略归属的子单继承父单所在项目和模块。 |

viewer 可列出本租户项目模块，写操作沿用 editor/admin 权限。业务模块表与已安装的原生工具目录分别存储。项目键是租户内的命名空间，工单正文仍受既有需求和祖先工单 ACL 约束。[领域实现](../customizations/components/tianxuan/server/tianxuan_core.py) · [HTTP 实现](../customizations/components/tianxuan/server/api.py)

## 旧库与接续

原工单没有模块字段时，数据库升级将其归入项目内的 `default`。迁移建单回执记录了来源项目的，从回执及父子关系恢复项目。缺少项目来源的旧单保留在 `workspace`。每个项目均可读取并独立改名自己的默认模块。以前持久化的工具回执仍可重放，当前归属从工单列表读取。[迁移入口](../customizations/components/tianxuan/server/migration_api.py)

下游 C02 可用租户、项目和模块 ID 查询或关联工单。C03 可使用同一组键表达资产所关联的多个模块。[C02 #1866](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1866) · [C03 #1806](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1806)

## 定向验证

在 `customizations/components/tianxuan/server` 下用 Python 3.14.3 安装该目录的 `requirements.txt` 后运行。

```powershell
python -B -X utf8 -m pytest -p no:cacheprovider -q test_business_modules.py test_tool_receipts.py test_migration_api.py test_issue_ancestor_acl.py test_api_session.py test_scope_idempotency.py test_work_management.py test_api_auth_mode.py
```

98 项通过。原生模式 TestClient 携带有效 Bearer 会话创建两个“场景”模块，将工单指向第一个，改名为“城镇”，重启领域存储和 HTTP 应用，回读原工单及两个模块。旧表升级、旧回执重放、租户及项目隔离和只读角色另有覆盖。[定向用例](../customizations/components/tianxuan/server/test_business_modules.py) · [候选与读回结果](../data-collection/gonggong-ai-workbench-plan1-c01.json)
