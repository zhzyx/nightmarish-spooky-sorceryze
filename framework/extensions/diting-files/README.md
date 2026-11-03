# 谛听 Git 文件采集适配

当前数据写入仓库根 gonggong-diting-data/；Olympus 历史数据保持在 olympus-hermes-data/，只读验证和分析，不修改原始租户、事件、批准或摘要。路径以仓库根解析。

命令：diting_files.py init|record|validate|analyze|git-check --repo WORKSPACE。analyze 必须指定 --tenant；不同租户不合并计量，相同身份和字节去重，冲突拒绝。git-check 同时检查历史和当前数据。init 要求模块先提交，迁移中的隔离候选不得伪称已启用。

文件事件是 Git 接入存储适配，沿用共享谛听采集规范；数据库采集入口仍为 tools/diting-host.py。配置、文件落库、Git 提交、远端发布和实际消费分别留证。
