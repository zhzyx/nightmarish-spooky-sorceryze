# G02　由 Git 提交定位多宝归档

G03 导入历史后，可用原仓完整提交 ID 在多宝查询该提交，再沿原顺序核对每个父提交。此契约对应 `gonggong-ai-workbench-plan1-g02`，承接 B04 对 Git 镜像与原生目录的核对，接收方为 G03 的隔离导入器。[原单 #1852](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1852) · [B04](gonggong-ai-workbench-b04.md) · [G03 #1849](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1849)

## 导入与回查契约

| 对象 | 导入与回查 |
| --- | --- |
| 来源提交 | `source_id` 采用清单已有格式 `github:<owner>/<repo>/commit/<完整 Git OID>`。仓库名称取本次目录的来源清单，`oid` 是原始 Git 对象 ID。兼容镜像用同一个 OID，原生导入器以 `github:<owner>/<repo>/history.bundle` 保存包含该对象的归档。 |
| 多宝定位 | 从 `publish_import` 回执保存租户、目标项目、目录模块 `module` 和目录修订 `revision`。同一目录里的多个 Git 提交共享该目录修订，查询时须再传各自的 `oid`。项目名可与源仓名称不同。 |
| 提交内容 | `tree` 是 Git 根树的完整 OID。`author` 与 `committer` 分别返回 Git 记录的姓名、邮箱及带原时区偏移的 ISO 8601 时间。查询从已归档提交取值，保留两种身份及两个时间。 |
| 父链与顺序 | `parents` 是原提交中从首个到末个的完整父 OID 数组。根提交为空数组，普通提交有一个父项，合并保留所有父项及其位置。回查父项沿用相同的租户、项目与目录修订。清单的通用关系集合会去重、排序，合并顺序应取归档提交本身。 |

HTTP 客户端使用 `GET /api/v1/migration/history/commit`，AI 客户端使用 `migration.history.commit`，均传 `project`、`revision` 和 `commit`。宿主按当前身份解析租户。省略目录修订时使用项目当前发布的目录，固定回查须传原修订。若项目已改指另一目录或租户不可见，返回 404。符号引用、缩写、非提交对象和不可达提交不能作为有效定位。要核对树内文件，可将相同定位和路径交给已有 `file` 入口。[已发布历史接口](../customizations/components/tianxuan/server/migration_history_api.py) · [归档读取](../customizations/components/tianxuan/migration/history_git.py)

## 双亲合并验收

隔离源仓 `sample/repo` 的两个子提交分别添加 `left` 和 `right`，合并树同时保留两份文件。通过现有 `import_inventory` 将 Git bundle 写入原生数据库，发布给目标项目 `demo`。用已发布目录修订查询原提交，HTTP 和 AI 返回相同的映射。目标再用返回的两个父 ID 分别查询到共同的根，根的父数组为空。[双入口用例](../customizations/components/tianxuan/server/test_migration_history_api.py) · [原始对象头及目标响应](../data-collection/gonggong-ai-workbench-plan1-g02.json)

| 核对项 | 源仓及接收端读数 |
| --- | --- |
| 原提交 | `5b055008d6c3a46b82546094b45fa77a9ee8c123` |
| 第一父、第二父 | `d14a7eed9b9d6e18ba258a13448c01cc072ea826`、`9e1f4e8a515c5e40ca5bdb76db6545fa246360da` |
| 根树 | `485cd1dd0cbf61b435801f2913d099bc65df5f51` |
| 作者及时间 | Source Author，`author@example.invalid`，`2026-11-18T09:15:30+05:30` |
| 提交者及时间 | Merge Operator，`merge@example.invalid`，`2026-11-19T07:00:00-04:00` |
| 多宝目录修订 | `6d71e4194aaea2a14dc85c1183eb5aa5e2c31188b1f697ba6ca97544f2cac285` |

在仓库根以服务测试环境运行 `python -m pytest -q customizations/components/tianxuan/server/test_migration_history_api.py` 可重建此样例。完整原始响应还包括项目、租户及模块，另附旧修订、其他租户、树对象和移动引用的拒绝回执。G03 可据此对实际导入水位逐个回查，并核验重复导入。
