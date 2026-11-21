# D06 审阅设计差异与恢复版本

在 AI 工作台打开「设计文档」，选择文档，再打开「版本历史」。两个下拉菜单可按修订号选择原修订和对比修订，差异区域显示天璇返回的逐行变化。「阅读原修订」在同一文档窗口打开所选修订的正文和段落。文档以 ID 定位，同名文档各有自己的历史。[需求 #1861](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1861) · [方案一 D06](gonggong-ai-workbench-plan1.md#d06)

选择要恢复的原修订，将对比修订设为列表中最新的版本。审阅差异后，恢复按钮显示将采用的原修订和新修订号，例如「将 v1 恢复为新修订 v3」。保存 A、编辑为 B 再恢复 A 后，当前正文为 v3 的 A。v1 的 A 与 v2 的 B 均可通过历史窗口重新打开。[前置 D04](gonggong-ai-workbench-d04.md)

## 读取与恢复

历史控件使用文档窗口的天璇业务会话发送请求。版本列表来自 `GET /api/v1/docs/{id}/versions`。比较请求向 `/diff` 传入两个选定修订号。恢复向 `/versions/{原修订}/restore` 提交已审阅的最新修订号 `expected_version` 和该操作的 `call_id`。成功后核对服务返回的文档 ID 与新修订号，再通过 D04 的修订读取入口显示新正文。[文档版本控件](../editor/docks/workbench/document_history.gd) · [天璇接口](../customizations/components/tianxuan/server/api.py)

回执丢失时，「重试此次恢复」沿用原请求的文档、目标修订、预期修订和操作 ID。发生并发冲突时可重新打开历史，查看新修订和差异，再决定是否恢复。切换文档或退出账号会清空历史窗口及其在途选择。

## 构建与复验

工作台侧栏将历史脚本与业务会话生成到 `BusinessSession.gen.h`，并随编辑器编译链接。回退使用先前已验证的编辑器。文档及修订继续保存在原天璇服务中。[构建入口](../editor/SCsub)

在仓库根使用已安装天璇依赖的 Python 运行 `python tests/editor/run_workbench_documents.py --history --godot <候选编辑器> --report <验证报告>`。探针从原生工作台入口驱动 D04 的新建、编辑与 D06 的比较、恢复和历史阅读。临时天璇数据库与回环服务记录每次写入和返回状态，包括已写入后丢失回执、同一请求重试、外部修订插入后的冲突。[验证记录](../data-collection/gonggong-ai-workbench-plan1-d06.json)
