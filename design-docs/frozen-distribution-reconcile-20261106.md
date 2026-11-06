# 共工工作区自检与离线分发登记

[工单 #189](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/189) 来自 [PR #187](https://github.com/zhzyx/nightmarish-spooky-sorceryze/pull/187) 的静态检查失败。用户本次要求优化当前共工框架并自检。以远端 main 的 146865d1586825f1be0ad43815b360f3e65d77ed 为基线，登记该提交中 CURRENT_FRAMEWORK.json 已选定的 0.9.2 包。路径均相对仓库根。

## 范围和来源

- 修正 integrations/gonggong/frozen-distribution.json，补全 28 个路径、更新 37 个摘要。framework/package-lock.json 提供 279 项，锁文件自身的 Git 字节另取摘要，一共 280 项。
- 全部差异的旧、新摘要、最后修改提交与作者在 data-collection/frozen-distribution-reconcile-20261106.json。作者用于溯源。当前五个 Agent 的准入对象和审查证据由 framework/framework-manifest.json 的 admission_pass 引用。历史规范、纲领、元衡原件、Agent、准入文件与有效框架指针均未修改。
- 工作区入口校验指针与登记版本，再执行与静态 CI 相同的离线检查、正式框架校验与数据 Git 检查。修正根 README 中失效的上游同步操作。登记审查只覆盖基线包的离线分发一致性，宿主执行授权仍须按实际任务核实。

## 验收与交接

运行分发回归、指针不匹配负例、司南及宿主回归、工作区自检与正式工单门禁；提交后检查已入库状态。核对独立登记审查、精确候选的远端静态 CI 与 main 接收提交，在 #177 留下可恢复的回执。Gameplay 工作副本与既有 PR 由原发布者处理。

远端静态检查 [42251779221](https://github.com/zhzyx/nightmarish-spooky-sorceryze/actions/runs/42251779221) 首先拒绝 #55 的 21 个已入库日志。仅为这 21 个精确路径补齐 Git 忽略例外，保留原始验收文件和其他日志的忽略规则。
