# E01 任务打开时固定编辑目标与起始修订

原生任务的授权事务固定工程及业务模块。目标文件取自任务的写入范围，文件摘要由授权时固定的不可变模块修订得出。认证工作流的 edit-baseline 读回指定目标的初始与当前修订和 SHA-256。路径删除后仍能读回起始摘要。历史任务缺少可核实的业务归属时返回空值。

[设计条款](gonggong-ai-workbench-plan1.md#e01) · [验收工单](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1834)
