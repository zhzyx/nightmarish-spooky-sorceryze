# G04　读取已发布历史中的分支和 tip

从 G03 接收的 Git bundle 恢复分支。HTTP 客户端按项目和目录修订访问 `GET /api/v1/migration/history/branches`，AI 客户端调用 `migration.history.branches`。两者返回同一组 `items`，每项包含完整分支名 `ref` 和提交 OID `tip`。调用者可将 tip 交给 G02 的 commit 查询以读取原提交。租户由已认证账号决定。[G04 工单](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1846) · [G03 导入入口](gonggong-ai-workbench-g03.md) · [历史接口](../customizations/components/tianxuan/server/migration_history_api.py)

查询按完整引用名排序。传 `offset` 和 `limit` 逐页读取，页大小为 1–100；收到 `next_offset: null` 时读完。翻页时固定同一项目与已发布目录修订。目录更新后，旧修订查询会报告不可用。接口只枚举 `refs/heads/` 命名空间，以完整名称区分不同团队或发布线上的同名末段。[分支读取实现](../customizations/components/tianxuan/migration/history_git.py)

## 验收

| 来源和目标 | 实际比较 |
| --- | --- |
| 隔离合并样例 | main、releases/shared、teams/shared 在 Git 中分别指向合并提交、第二父、第一父。HTTP 返回前两行，AI 工具返回第三行。名为 shared 的标签不占分支条目。过期修订及其他租户均返回 404。[接口测试](../customizations/components/tianxuan/server/test_migration_history_api.py) |
| G01 的真实源快照 | 从冻结的 1,640 个引用重建独立镜像和 bundle，用 G03 导入、发布全部 2,656 个提交。以页长 100 从目标依次读取 7 页，最后一页 83 项。将每个完整分支名及 tip 与 G01 源清单比较，683 项全部相同，缺少、多出、tip 不同各 0 项。[源清单](../data-collection/gonggong-ai-workbench-g01-inventory.json) · [导入修订与比较回执](../data-collection/gonggong-ai-workbench-plan1-g04.json) |

实测源 main 为 `0e1dcb293a55e3034bf92b4e02bc6b0028e5fb14`，多宝项目为 `g04-source-snapshot`，发布修订为 `fbf8f07104d4a6823e82f5b6d2b54151f7dda9cac7affc92238ea395a9d3228d`。G07 可复用相同分页读取做完整性比较，G10 可用完整分支名定位具体开发线。
