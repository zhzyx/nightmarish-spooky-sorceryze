# G19 核对全仓迁移副本的对象、字节与全部引用

在 Mac 的新目录运行 git_archive.py，冻结来源 Git 仓的全部分支、标签及可见 PR 引用。运行 customizations/components/tianxuan/migration/rehearse_repository.py CAPTURE NEW_DIRECTORY --tenant TENANT --actor ACTOR --project PROJECT，将全部可达提交导入隔离的多宝 NativeStore，再从已发布的目录修订恢复 bundle 并建立独立镜像。回执列出每个引用的来源与恢复值，核对对象类型、字节、提交记录关联和 git fsck。此次来源没有 LFS 对象和子模块。业务工单、评论等 GitHub 服务元数据使用独立的在线清单，Git 仓副本演练回执只统计 Git 范围。

[设计条款](gonggong-ai-workbench-plan1.md#g19) · [实机验收回执](../data-collection/gonggong-ai-workbench-plan1-g19.json)
