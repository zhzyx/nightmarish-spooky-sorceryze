# C03　跨模块共享资产

“角色移动”和“角色动画”需要各自打开同一个模型，也可以各自解除关联。天璇保存业务模块到多宝对象的显式关系。业务模块沿用 C01 的稳定 ID，多宝对象沿用 B05 的来源模块、不可变版本及逻辑路径。两处入口都返回原对象的字节。[原卡 #1806](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1806) · [方案一 C03](gonggong-ai-workbench-plan1.md#c03) · [C01 模块接口](gonggong-ai-workbench-c01.md) · [B05 模型样例](gonggong-ai-workbench-b05.md)

## 关系和产品接口

以下路径以 `/api/v1/native` 为前缀，项目使用查询参数 `project`，缺省值为 `workspace`。租户来自当前认证身份。模块显示名可以改变，关联始终使用项目内的模块 ID。

| 操作 | 请求 | 回读 |
| --- | --- | --- |
| 关联现有对象 | `POST /business-modules/{module_id}/assets`，JSON 含 `source_module`、`revision`、`path` | 返回三项来源字段和 `asset_id`。重试同一关系得到同一记录。 |
| 列出模块资产 | `GET /business-modules/{module_id}/assets` | `assets` 给出当前用户可读取的对象。 |
| 从模块打开 | `GET /business-modules/{module_id}/assets/{asset_id}` | 返回经多宝校验的对象字节。 |
| 解除关联 | `DELETE /business-modules/{module_id}/assets/{asset_id}` | 返回 204。此后从该模块打开返回 404，其他模块继续持有各自的关系。 |
| 从资产查模块 | `GET /assets/{asset_id}/business-modules` | `module_ids` 给出当前项目关联该对象的业务模块 ID，供 C07 与 V07 使用。 |

`asset_id` 是多宝按规范 JSON 编码的数组 `[source_module, revision, path]` 的 SHA-256。相同来源对象在两个业务模块中使用同一标识。新版本具有自己的标识，旧关系仍指向原版本。关系表以租户、项目、模块和资产标识为联合主键，反向索引以租户、项目和资产标识查询。解除关系只删除指定的关系行。[关系表](../customizations/components/tianxuan/server/tianxuan_core.py) · [接口实现](../customizations/components/tianxuan/server/business_asset_api.py)

创建和解除关系要求 editor 或 admin。查看列表、反查与打开时沿用多宝的来源读取权限。若私有来源收回共享，用户再次列出时看不到该资产，直接打开也会被拒绝。

## 接入与验证

天璇 Python 服务在注入多宝 `NativeStore` 时装配此路由。启动时在领域 SQLite 库创建关系表和反向索引，旧项目初始没有显式关系。服务回退到原版本后仍能按原接口读取多宝对象。该改动随天璇服务源码部署。[服务装配](../customizations/components/tianxuan/server/api.py)

在仓库根使用已安装天璇服务依赖的 Python 运行以下命令。

```powershell
python -B -X utf8 -m pytest -p no:cacheprovider -q customizations/components/tianxuan/server/test_business_assets.py customizations/components/tianxuan/server/test_business_modules.py customizations/components/tianxuan/server/test_native_api.py
```

实测通过 22 项。测试用 B05 清单的模型原件创建多宝版本，两名用户用各自的 Bearer 会话从两个业务模块分别读取 70,636 字节。解除移动模块的关系、重新打开两个 SQLite 库并重启 HTTP 应用后，移动模块返回 404，动画模块仍返回同一模型，反向索引仅列出动画模块。回执保留两个模块 ID、版本、资产标识和内容摘要。[回归用例](../customizations/components/tianxuan/server/test_business_assets.py) · [定向验证及接收回执](../data-collection/gonggong-ai-workbench-plan1-c03.json)
