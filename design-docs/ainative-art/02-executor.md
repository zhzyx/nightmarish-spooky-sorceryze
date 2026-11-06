# 02-executor 工作流执行与持久任务

稳定需求 ID：ainative-art-02-executor-20261106

父设计：[AINative 美术与人物工作流](../ainative-art-pipeline-20261106.md)。父工单见总设计回执；本页仅用于本子项身份。

范围：DAG 执行、Provider 能力协商、持久任务、缓存失效、取消、重试及凭据隔离。

验收：重启恢复；取消不发布迟到结果；重试不重复计费提交；改图片/模型版本/骨架规格使相关缓存失效。

前置：01-contracts。

非目标：其他子项的完整实现；任务登记不表示功能通过。

主责：Codex / kaiyunxue（当前操作者）；目标 main；先 intake-only，交付通过正式门禁和精确候选 CI。必要检查：契约单使用单元测试，其余使用该范围内真实资产、编辑器回放或目标工具回读；保留失败证据。

## #143 实现与 #144 接入

`tools/ainative/executor.py` 提供 Python 3.11+ 标准库 SQLite 库；`executor_cli.py` 是 JSON 子进程桥。数据库路径以调用进程 cwd 解析为绝对路径；宿主应传绝对路径，父目录须已存在。SQLite WAL + FULL synchronous 保存运行、不可变 `(artifact.id, revision)` 和成功缓存。输入/输出内容相同版本不可改写；闭合 manifest 的同 id 不同内容不能合并。

库入口 `Executor(database, registry, providers)`；Provider 是运行时对象，不序列化。`create(graph, manifest, run_id=None)` 返回运行 id；`status(id)` 只读；`step(id)` 最多推进一个节点；`cancel(id)` 持久取消；`retry(id, node_id)` 只允许已有 Provider 明确 failed 回执的节点重试；`export(id)` 仅在整图成功且未取消时返回 `{manifest, outputs}`，供 #144 的 PublishAdapter 消费。Provider cancelled 是运行终态；后续节点不具备依赖成功条件，不能发布整图。

图是数组，每项 `{id, provider, request, links}`。request 沿用 #142 的 `{node, version, inputs, parameters, context}`；links 格式 `{目标输入端口: {node: 上游节点id, port: 上游输出端口}}`，不能与 inputs 重复绑定。图拒绝循环、缺失节点/端口、类型不相容和 optional 上游输出连线。源输入、参数、上下文和能力在创建时校验；动态输入解析后再次完整校验。上游输出 manifest 与当前闭合包合并后传入下游。

CLI 示例（在仓库根运行；factory 为宿主的受信任本地 Python 模块，不接受用户上传代码）：

```text
python tools/ainative/executor_cli.py --db /absolute/jobs.sqlite --factory host_provider:build create
python tools/ainative/executor_cli.py --db /absolute/jobs.sqlite --factory host_provider:build step --run RUN_ID
python tools/ainative/executor_cli.py --db /absolute/jobs.sqlite status --run RUN_ID
python tools/ainative/executor_cli.py --db /absolute/jobs.sqlite cancel --run RUN_ID
python tools/ainative/executor_cli.py --db /absolute/jobs.sqlite retry --run RUN_ID --node NODE_ID
python tools/ainative/executor_cli.py --db /absolute/jobs.sqlite export --run RUN_ID
```

create 从 stdin 读取 `{graph, manifest}`；成功 stdout 为 `{ok:true,result:...}`，失败为固定安全错误码且退出码 1。factory 的 `build()` 返回 `(NodeRegistry, {provider_name: provider_instance})`，从环境或宿主安全存储读取凭据；status/cancel/retry/export 不加载 factory。#144 在后台子进程调用 create/step，UI 只轮询 status；不得在编辑器主线程等待 Provider。CLI 不含真实 Provider 或通用网络重试。调用方不得把凭据放进请求、上下文、资产或 Provider manifest。

Provider 沿用 describe/submit/poll/cancel，并须提供 `result_manifest(job_id)` 返回闭合资产交换包；也可由注入适配器调用专用解析器实现此方法。成功必须同时通过 validate_job、validate_outputs、内容摘要及不可变仓库检查；空 refs/空结果清单不能替代产物。可选 `lookup(idempotency_key)` 只能查询已存在提交并返回合法回执或 None，**不得隐式创建任务**。

提交前事务先保存 reconcile 意图和稳定 idempotency_key，再释放 SQL 锁调用 submit。并发驱动同一 run/node 不重复 submit；不同运行的缓存 miss 不承诺全局提交合并。收到 job_id 后重启仅 poll 已知任务；提交回执丢失或进程在提交边界崩溃时保持 reconcile，通过明确 lookup 恢复。无 lookup、lookup 返回 None 或无法确认失败时保持待核对，绝不盲重试。确认 failed 后显式 retry 增加 attempt 并产生新 key；不承诺外部服务未计费。Provider 异常和失败消息只持久固定码，不记录原始异常、URL 或 token。节点定义与 Provider/模型版本被钉住；恢复时漂移不接收结果，保留已知 job 供正确配置恢复。

取消标记与结果发布检查均使用数据库事务，跨进程取消后迟到成功不能写入运行结果/缓存或 export。远端 cancel 由后续 step 尽力发送，不能保证服务停止计费；未知 job 必须外部核对。已取消运行不会再次恢复或重试。取消前已经成功写入的共享缓存可被其他运行使用。

文件输入使用 `snapshot_file(path)`，其返回 `{content_base64, content_sha256}` 应放入 artifact.payload。文件路径相对调用方 cwd，内容一次读取后存入不可变 manifest；摘要验证保证缓存使用的是快照内容。执行器拒绝 manifest 中 uri/url/path/source_path 字段，避免把可变文件位置当作内容。内容变化须新 revision 并更新引用。缓存键包含完整包、节点定义、参数、上下文语义、Provider/模型版本；因此图片、骨架 Profile 和上下文变化均失效，甚至无关附带资产也保守失效。

支持边界：仅单机受信任 SQLite 文件和 JSON/base64 小型资产；不包含 blob 流式存储、分布式队列、自动重试/配额、任务清理、图编辑器、真实模型 API、真实几何/骨架验证或 Godot 发布适配器。Provider 调用时限由适配器负责；status/cancel 不调用 Provider，SQL 竞争最多等待连接 timeout 10 秒。输入 id/version 与 Provider manifest 必须由受信任配置提供。直接编辑 SQLite 不属于支持接口。

## 验证证据

运行 `python -m unittest discover -s tools/ainative -p "test_*.py"`。`test_executor.py` 仅使用显式 SyntheticProvider（no-generation-fixture），覆盖已知任务关闭/重开数据库、模拟进程死亡（SystemExit）和回执丢失后核对、未知提交不重放、确认失败重试、独立连接并发驱动、独立 CLI 进程取消及迟到隔离、坏回执/坏结果、类型 DAG 合并/循环/optional 连线拒绝、定义漂移、模型/上下文/真实临时文件内容快照/骨架 Profile 的缓存失效。测试不调用真实服务，不证明真实生成、外部幂等计费或真实工具回读；产物与测试结果仍须由主代理独立审查及工单验收。
