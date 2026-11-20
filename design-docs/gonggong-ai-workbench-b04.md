# B04　从 Git 发布标签定位多宝历史

方案一的 G01、G02 需要分别盘点引用和定义标识映射。下表以源码基线 `b60ae96914cd25b0856f4be09b6b0b6a710cc717` 核对接口，并从原仓、既有隔离镜像和原生归档读取同一条发布记录。需求 ID 为 `gonggong-ai-workbench-plan1-b04`，类别为 `type:design`，无直接前置。[工单 #1853](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1853) · [方案一](gonggong-ai-workbench-plan1.md#b04)

| 对象 | Git 兼容多宝可保留的内容 | 原生存储和下游处理 |
| --- | --- | --- |
| 提交、树、父提交 | `GitService.import_repo` 以 `clone --mirror` 导入传输端提供的引用和可达对象。相同 Git 对象逐字节保留 OID 和父链。 | 迁移目录按 `source_id` 保存提交记录；归档的 Git bundle 承载 Git 对象。原生模块修订由模块名、父修订、对象摘要和依赖生成 SHA-256，需单列 Git OID 与原生定位。 |
| 分支 | `list_branches` 返回分支名；核对水位须再解析完整 `refs/heads/…` 的 OID。名称保留，后续提交会移动分支。 | 模块头按租户、模块寻址；原生组合按模块精确修订寻址。迁移保留源 ref、水位和快照版本。 |
| 轻量标签、附注标签 | 轻量标签直接指向对象。附注标签还有 tag 对象，镜像可保留该对象及内含的说明、签名。列表接口只返回名称和 SHA，优先取一层解引用值。核查附注标签须同时读 ref OID、对象类型和最终目标。 | 原生归档可恢复 bundle 中的引用。原生模块修订或产品发布频道自有标识。G05 另验轻量和附注标签全量映射。 |
| 合入、评审、工单 | 受保护分支通过队列进入，队列记录源、目标、可选 PR／工单与合入结果 `merge_sha`。直接调用 GitService 显式选择快进时可沿用已有提交；队列调用默认 `--no-ff`，须读回新 OID 和双方父链。 | 原生候选、选定和发布分别有独立回执。Git 镜像本身没有 GitHub PR 评论、检查与批准。归档它们时保存来源与精确修订；队列以分支名入队，G13/G15 需独立验证候选漂移与实际接收。 |

导入入口为管理员的 `POST /api/v1/git/import`；大任务可走 `/api/v1/git/import-jobs`。已有镜像通过 `GET /api/v1/git/repos/{name}/log?ref=…`、`/branches` 和 `/tags` 查询。配置队列后可用 `POST /api/v1/merge-queue`；角色和目标保护在入队与执行时核对。生产迁移还须核验未广告的引用、LFS 对象和子模块对应库。[服务入口](../customizations/components/tianxuan/server/api.py) · [GitService](../customizations/components/tianxuan/duobao/git_service.py) · [合入队列](../customizations/components/tianxuan/duobao/merge_queue.py)

## 发布标签的三处定位

1. **原仓**　GitHub 的 `git/ref/tags/gonggong-windows-x64-20261104-r2` 返回 `type=commit`，指向 `21780aea530778c2a2a636fbad5a1c3198c29601`。该提交的树为 `3a317a7ffb809b733f47223e5105df8dcec47b05`，唯一父提交为 `e6b9f5c8dad827af52a346f4b0342f30d2e2312f`。[原提交](https://github.com/zhzyx/nightmarish-spooky-sorceryze/commit/21780aea530778c2a2a636fbad5a1c3198c29601)
2. **多宝 Git 兼容库**　对 #1553 隔离演练的 `GongGong.git` 只读运行 `GitService.list_tags(repo)` 与 `GitService.log(repo, "gonggong-windows-x64-20261104-r2", 1)`。两个接口命中上述提交。两侧 `git show -s --format="%T %P" 21780aea` 的树和父提交相同。归档时 main 为 `a5137d854d687c4e9c8fa3d7148cb55198163818`。该演练库的 main 后来推进到 `5f704a260f10edda3f31fdd9a040cbbbcb57abe5`；历史样例固定在标签的确切对象。
3. **原生多宝归档**　租户 `gonggong-workspace`、项目 `zhzyx/nightmarish-spooky-sorceryze` 的演练归档修订为 `fb4f0172d86579b7f4c01f114bbe4fbf692b62a19b59f9e01133cbd529525e2e`。按 `github:zhzyx/nightmarish-spooky-sorceryze/commit/21780aea530778c2a2a636fbad5a1c3198c29601` 在该目录的记录批中查到 `record_only` 原件，核对了修订和内容摘要。标签另在该快照的 Git 引用表中，归档目录的 bundle 摘要与快照报告一致。完整模块、批修订和对象键见回执。[原生存储](../customizations/components/tianxuan/duobao/native_store.py) · [目录导入](../customizations/components/tianxuan/migration/importer.py) · [逐项读回](../data-collection/gonggong-ai-workbench-plan1-b04.json)

复核原仓可运行 `gh api repos/zhzyx/nightmarish-spooky-sorceryze/git/ref/tags/gonggong-windows-x64-20261104-r2`。持有隔离演练库的接收人可按第 2 项在本地核对，再以第 3 项的租户、项目、发布修订和来源键检索历史详情。兼容层另在临时裸库运行了镜像保留分支和标签、快进合入、冲突保持原目标、标签创建与删除四项测试，均通过。[定向用例](../customizations/components/tianxuan/duobao/test_git_service.py)

B07 可引用这份标识边界，G01 使用当前原仓重取盘点水位，G02 以本例验证源仓、引用、Git OID 与原生修订的映射。正式切换仍由 G20 至 G22 验收。
