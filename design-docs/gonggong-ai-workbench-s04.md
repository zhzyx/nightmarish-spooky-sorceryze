# S04　把执行进度写回天璇

签认一项设计任务后，工单详情的 `execution_progress` 返回当前授权的运行号、工作者引用、工单来源修订、目标阶段、运行状态、候选和事件。需要核对历史运行时，用该次 S03 运行号调用 `POST /api/v1/native/workflow/status`，读取同格式的 `progress`。两处都校验操作者当前对工单、固定设计和输入的读取权限。原单详情与当前运行取自同一个数据库快照。未启动原生工作流的工单和无权读取绑定设计的操作者，在已安装工作流的详情端点得到空进度。[S04 工单](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1842) · [S03 运行号](gonggong-ai-workbench-s03.md)

### 生产回执

每个运行号的 `events` 按 `sequence` 升序排列。`recorded_at` 是天璇接收时间，`state` 是接收当时的运行状态。工单所属阶段来自这张票据的签认设计。工作流状态转移与对应事件处于同一 SQLite 事务，覆盖本机预约与执行、工作者终态、阶段复验和最终接收。升级前已有的运行保留原票据与终态，从首次观察到的 `snapshot` 开始记录。

| 已完成的工具步骤 | 工单可读回的引用 |
| --- | --- |
| `workspace.materialize` | 本机已准备好的模块及固定修订 |
| `context.manifest`、`context.read`、`context.delta` | 已授权上下文工具返回的结果 ID 和响应摘要 |
| `process.closed` | 物理进程退出码和已关闭输出日志的摘要 |
| `workspace.collect` | 验证写入范围后实际采集的变更模块 |
| `candidate.compose` | 已生成的候选及各模块产物修订 |

同一次工具回执重投时，接收者核对原引用并保留原序号。内容不同的同标识回执会报错。调度器的延迟状态通知回读数据库中的现状。同一工作者的终态在并发核对或阶段复验之后才返回时，同样保留已提交的较新状态。模型名和用量只取经工作者核实的公开观察字段；本次本机进程直接产出文件，这两个字段均为 null。[工作流与回执存储](../customizations/components/tianxuan/sinan-workorders/native_workflow.py) · [上下文工具](../customizations/components/tianxuan/server/native_entry_context.py)

### 目标接收

Windows 原生编辑器打开已签署设计并确认「程序」。一个真实子进程在授权工作区内生成产物，另一项「动画」保持待确认。原连接关闭后，新认证连接按工单号取得同一运行的 4 条进行中回执。放行进程后，详情返回 8 条回执、退出码 0 和候选修订。把第 4 条回执附在旧的 running 通知上重投，天璇返回 produced，随后回读的完整事件序列与候选均相同。[原生测试](../tests/editor/run_workbench_confirmed_native_stage.py) · [实测版本与结果](../data-collection/gonggong-ai-workbench-plan1-s04.json)

独立服务测试用蓝色圆形 SVG 的实物检查证明到达签认阶段。另一个天璇实例在同一 SQLite 数据库上启动后，沿原票据回读相同历史，并向工具接收者重投原始回执。另测失去设计权限、同回执内容冲突、真实退出码 7、旧库升级和阶段已验收后迟到的工作者终态。上下文工具用本机与已登记远端节点两种认证连接核对结果引用。[进度定向回归](../customizations/components/tianxuan/sinan-workorders/test_native_issue_progress.py)

### 复跑与更新

从仓库根使用已装天璇依赖的 Python、Node 和受验编辑器包执行。原生脚本用 `copy_editor` 复制编辑器及配套资源，以隔离项目和配置运行 headless 确认，并在进程终止后清理夹具。

```powershell
python tests/editor/run_workbench_confirmed_native_stage.py --godot <编辑器路径> --report <本次结果.json>
python -m pytest -q customizations/components/tianxuan/sinan-workorders/test_native_issue_progress.py
```

本次修改由天璇 Python 服务与已安装工作者加载。更新时同时切换对应源文件，保留天璇和产物数据库。已签认程序的工作者安装摘要随实现更新，待执行的旧安装按原工作流核验。回退前待在途进程结束或保留未知占用，恢复已核实的原服务和工作者版本，保留已落库的运行与产物回执。原生输入与 #2039 编辑器包一致，包文件和实际运行摘要均在实测记录中。
