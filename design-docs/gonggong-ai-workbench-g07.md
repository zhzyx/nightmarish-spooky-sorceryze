# G07　核对已发布 Git 历史的引用、对象和内容

G01 冻结快照的 683 个分支、3 个标签、954 个 PR 引用及 HEAD 在多宝回读中逐项匹配。由这些 tip 可达的 2,656 个提交、15,423 棵树和 36,394 个 blob 全部通过原始字节核验。目标为隔离项目 `migration-validation/g07-source-snapshot`，目录修订为 `b83cec0a4dba4b646ca2ef867c783236ef45224436e62f089661c90c1cdee614`。[原工单 #1804](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1804) · [冻结清单](../data-collection/gonggong-ai-workbench-g01-inventory.json) · [逐引用和对象报告，gzip JSON](../data-collection/gonggong-ai-workbench-g07-integrity.json.gz) · [发布回执与定向试验](../data-collection/gonggong-ai-workbench-plan1-g07.json)

## 生成报告

从仓库根执行下列命令，路径相对当前目录解析。第一个输入是完整源镜像，第二个输入可用 G01 清单或 G03 的 `git-report.json`。数据库、租户、项目、修订取自 G03 发布回执。此只读工具沿用天璇 Python/Git 运行环境；复用已有发布目录即可执行，回退时可移除该命令。[核验入口](../customizations/components/tianxuan/migration/audit_git_history.py) · [G03 发布入口](gonggong-ai-workbench-g03.md)

```sh
python customizations/components/tianxuan/migration/audit_git_history.py SOURCE_MIRROR INVENTORY DATABASE --tenant TENANT --project PROJECT --revision REVISION > integrity.json
```

工具核对源端地址、HEAD 与完整引用映射，再从指定的多宝目录修订导出并校验 `history.bundle`，恢复临时目标镜像。双端遍历各自引用可达的完整 Git 对象集，包括附注标签和历史树。对每个对象分块读取原始内容，计算 SHA-256，并使用类型、大小和 Git 对象头独立重算 OID。树中记录的子模块修订及 LFS 指针参与 Git 字节比较；历史引用指向的外部实物按 G06 核查。[G04 分支回读](gonggong-ai-workbench-g04.md) · [G05 标签回读](gonggong-ai-workbench-g05.md) · [G06 外部对象核查](gonggong-ai-workbench-g06.md)

报告的 `refs` 按完整引用名排列，`objects` 按完整 OID 排列。每行保存源、目标及比较结果，Git 提供的样例名称有助于定位具体文件。正常退出且 `complete` 为 true 表示全匹配。有差异时返回报告并以 1 退出。来源漂移、修订不可见或导出失败会报告输入或读取错误。

## 定向试验

隔离用例分别发布正确副本、删去一个分支的副本以及改写二进制文件的副本。正确项目的全部引用与对象匹配，包括轻量标签和附注原件。删除 `refs/heads/topic` 后，对象仍全部可达，报告只指出缺少该分支。将 `data.bin` 改为同长度内容并重建 tip 后，报告指出 HEAD 与 main 的新旧 tip，并列出该路径的原 blob、新 blob 及其两个内容摘要。完整的小型报告、项目修订与实际命令结果可在回执中复核。[用例](../customizations/components/tianxuan/migration/test_audit_git_history.py) · [试验回执](../data-collection/gonggong-ai-workbench-plan1-g07.json)
