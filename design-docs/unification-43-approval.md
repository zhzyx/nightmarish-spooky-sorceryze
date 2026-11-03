# 共工 0.9.2 本地定义批准材料

工单：https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/43

独立审查：codex_subagent_/root/migration_review；五项框架审查、元衡六项、精简、适用验证均通过。此处尚无批准。

范围：仅批准下面五个精确候选的本地 Agent 定义发布；不授予任意宿主、工具、模型或未来任务权限。Windows交付、远端main和工作区切换仍按本次已授权迁移方案验收。

| Agent | 版本 | SHA256 |
| --- | --- | --- |
| yanshi | 0.4.0 | `750061f390b05b9ce21ad22264115f1e0ec724235bdc14ac160016f84a8a4763` |
| kuafu | 0.4.0 | `baf867dad0e50d734e3ae9d756f032674c91520c818a0315b9bab48db7ddb10a` |
| diting | 0.4.0 | `77233fd9af63852e3beb34d5b5cef3d54d33bcd187e19fc20f0d766b37323768` |
| heqi | 0.3.1 | `6f10ba216707673aa4a6706bdfae62b81b5955d1532516aa84fb19b7ad4cb6cb` |
| sinan | 0.1.1 | `eaf1e100dbb71ba9b9e39fc8018c5a9122f8e1946e5e2d5dc73c30cbcfbedda5` |

候选行为回归：48宿主、41工单、9独立运行/防篡改、10模拟模型、10迁移数据测试通过；4项分发回归通过。新Windows编辑器已经编译，原生安装验收继续进行；不把待验证写成通过。

旧批准及历史数据保留原件。批准拒绝或尚未收到时不切换现行框架。
