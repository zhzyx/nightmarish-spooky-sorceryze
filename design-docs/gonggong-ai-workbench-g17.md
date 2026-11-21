# G17　从已合入的 GitHub PR 增量同步到多宝

原仓 PR #1663 于 2026-11-20 03:02:44 UTC 合入 main。合入前三秒，PR 留下了独立验收批准的原文。G17 用真实第一父提交重建隔离库，按原仓合入 OID 同步，再通过 Godot 天枢读取原评审。[原 PR](https://github.com/zhzyx/nightmarish-spooky-sorceryze/pull/1663) · [批准评论](https://github.com/zhzyx/nightmarish-spooky-sorceryze/pull/1663#issuecomment-7029024766) · [G17 工单](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1741)

## 运行同步

迁移负责人使用可读原仓的 GitHub CLI 身份、含合入提交的原仓 Git 镜像，以及要更新的多宝数据库、租户、操作者和项目。项目须已有发布的 Git 历史，原目标分支可在镜像和发布基线中定位。路径以调用者工作目录为基准。从本仓根目录执行下列命令，尖括号处换为实际值。[迁移入口](../customizations/components/tianxuan/migration/sync_merged_pull.py) · [原生基线导入](gonggong-ai-workbench-g03.md)

```sh
python customizations/components/tianxuan/migration/sync_merged_pull.py \
  <原生数据库> <原仓镜像> 1663 422c07ad5eaa7585494ae063382ea147074dcf09 \
  --tenant <租户> --actor <操作者> --project <归档项目>
```

入口从当前项目的已发布目录取得原仓身份，读取 GitHub 的合入状态、精确 OID、PR 会话、正式审查与行评论。在隔离副本中取回该合入提交，按目标分支新增可达提交，并把原 PR、评审、原始链接和合入 OID 关联起来。目标分支已包含该提交时可补录评审。已有的 PR 记录按来源 ID 更新，已有工单投影和历史关系继续保留。只读历史不创建业务工单。

首次成功返回 `synced`、新目录修订和分支前后 OID。再次同步相同合入返回 `already_synced` 和现行目录。非快进分歧或发布期间其他操作者更新了该项目时，调用方须回读现行分支与目录再作处理。新增或变化的原生内容经校验后一次发布。其余附件沿用原目录中的内容指针。原生库采用完整 Git bundle 格式，分支推进时会在临时目录重打包，需预留相应空间。[原生存储与归档](../customizations/components/tianxuan/migration/importer.py)

## 从工作台读取评审

在天枢主屏选择 **历史工单**，填写归档项目和原 PR 链接，点击 **读取历史工单**。取回的 PR 正文下方列有原始评审链接。将其中一条放回同一个输入框再读取，即可查看多宝归档中的评审正文。也可以直接输入原评审永久链接。工作台使用当前天璇账户的项目权限，原 URL 的 PR 编号与评论归属须一致。[历史读取桥](../customizations/components/tianxuan/server/tianshu_bridge.py) · [原生控件验收](../tests/editor/daqian_merged_pull_review.gd)

## 目标接收与核对

隔离项目 `g17/replay` 从第一父提交 `5a827aa07df8b25679522bf8bd87f29ab8fb2a98` 导入 1,906 个提交。同步后 main 为 `422c07ad5eaa7585494ae063382ea147074dcf09`，多宝回读到 1,909 个提交、一个编号 1663 的 PR 和两条历史会话评论。再次运行后，发布修订、原生对象、模块头、修订、写入回执及项目发布计数均相同。

Windows 静默编辑器打开了 PR 中列出的批准评论，完整显示正文的 SHA-256 与 GitHub 原文一致。将同一评论锚点换到 #1664 后，窗口显示读取失败。来源记录的 GitHub 类型是 PR 会话评论，其中保存了实际批准决定。[逐项实测与目标回执](../data-collection/gonggong-ai-workbench-plan1-g17.json) · [重试和并发保护试验](../customizations/components/tianxuan/migration/test_sync_merged_pull.py)

G07 提供已核验的源镜像，G16 的五条仍开放 PR 按各自清单留在原平台。G17 使用已完成的 #1663 回放原仓合入事件。后继 G20 可据此核对正式代码库基线的接收范围。[G07](gonggong-ai-workbench-g07.md) · [G16](gonggong-ai-workbench-g16.md) · [G20](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1736)
