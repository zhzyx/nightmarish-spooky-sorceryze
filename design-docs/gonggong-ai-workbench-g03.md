# G03　从隔离 Git 快照导入多宝历史

已完成的 `git_archive.capture` 快照可直接导入多宝项目。入口接受快照目录、原生数据库和发布身份，返回目录修订与项目的实际接收回执。该适配承接 G02 的提交映射，需求 ID 为 `gonggong-ai-workbench-plan1-g03`。[原单 #1849](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1849) · [G02 映射契约](gonggong-ai-workbench-g02.md)

## 在隔离项目运行

从仓库根运行下列命令，路径以调用方当前目录为基准。将参数替换为已核准的本地快照、数据库、租户、操作者和目标项目。该项目将展示此次发布的目录。演练使用独立数据库或专用项目。

```text
python customizations/components/tianxuan/migration/import_git_history.py GIT_DIR NATIVE_DB --tenant TENANT --actor ACTOR --project PROJECT
```

输入目录包含 `archive.git`、`git-report.json` 和 `history.bundle`，已盘点的 LFS 实物位于镜像对应对象目录。先完成快照制作，再以相同、静止的副本重跑。命令核对镜像与报告中的 HEAD、可达提交数、归档引用和来源。以所有引用可达的提交生成现有格式的 `record_only` 记录，每条含完整 OID 及原顺序的父 OID。按 OID 排序写清单，确保相同输入生成相同记录流。归档层回读原生块，核对 Git bundle 和已列入报告的实物摘要，再将核验过的目录发布给目标项目。[快照格式与采集命令](../customizations/components/tianxuan/migration/README.md) · [导入入口](../customizations/components/tianxuan/migration/import_git_history.py)

程序调用使用 `import_git_history(git_dir, database, tenant, actor, project)`。保存结果中的 `module`、`revision` 与 `publication`。固定该项目和修订后，客户端可通过 `GET /api/v1/migration/history/commit` 传入 `project`、`revision` 和原提交 `commit`，从返回的 `source_id` 与同目录记录双向核对。分支、标签与大对象核查分别由 G04、G05、G06 承接，后续以同一目录中的原始 bundle、引用报告及物料为输入。[发布历史入口](../customizations/components/tianxuan/server/migration_history_api.py)

## 验收实录

样例 `sample/repo` 在 `main` 上合并 `topic` 后，又在 `topic` 新增一个提交。两个分支共五个可达提交，默认分支只能到达其中四个。两次从命令行导入同一副本到隔离库，接收租户为 `owners`，项目为 `isolated`。[定向用例](../customizations/components/tianxuan/migration/test_import_git_history.py) · [逐提交源对象头、目标映射及两次接收回执](../data-collection/gonggong-ai-workbench-plan1-g03.json)

| 核对项 | 目标端读数 |
| --- | --- |
| 目标目录修订 | 两次均为 `a11bc39b4f6842ad2be9a0fea60752df129e00fa31f0c0df9b0ef12920dc3c85`，首次导入及发布时间一致。 |
| 重跑去重 | 两次均有 8 个原生内容对象、4 个模块头、4 条修订、4 条原生提交回执和 1 条项目发布记录。 |
| 全部源提交回查 | 从源 `git rev-list --all` 取得的 5 个 OID 均在目标列表出现一次。每个 OID 的来源键、树和有序父链均与源对象相符，来源键也能查回对应目录记录。 |
| 合并与非默认分支 | 合并 OID 为 `5f0105304646dcc890518e819a2e97fce1b322c6`，仅在 `topic` 可达的最新 OID 为 `c3edc8f4c9db777121a2e8077e9e0bc92192cf15`。 |
| 快照不一致 | 将报告中的提交数减一后重跑，命令拒绝该输入，原项目发布修订仍能回读。 |

本次变更位于既有天璇迁移 Python 宿主工具内，由 CLI 调用现有归档、原生存储和项目发布接口。移回前一版脚本即可恢复原有清单导入入口。已有归档可用 `importer.restore_inventory` 按租户、模块、修订恢复到新目录。目标接收实测及源文件版本均记录在上述回执中。
