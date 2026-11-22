# S05　根据已验收的依赖启动后继

一张生产票据结束时，司南把 `execution.finished` 中的票据号交给天璇。生产者退出后，验收尚未通过的上游仍阻塞后继。上游完成独立检查、审查和发布并取得验收回执后，已签认后继可在本次事件中获得自己的执行票据。后继抵达签认阶段后，工作台按 A04 保存阶段检查结果。[S05 工单](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1812) · [阶段签认](gonggong-ai-workbench-a04.md) · [工单依赖](gonggong-ai-workbench-i04.md)

## 事件与执行

`POST /api/v1/native/workflow/advance` 接受可选字段 `completion`，值为完成事件中的 64 位十六进制票据号。原生 Node 派发器和宿主管道使用同一消费逻辑。单张完成票据只匹配本租户当前有效的上游执行。集成一次验收多张票据，沿依赖变化事件读取已提交的验收队列。宿主恢复也可沿原入口回读待消费记录。每个安装入口只消费本入口负责的工单。

天璇回读上游实际发布的精确验收记录，按安装计划或 I04 直接依赖找到后继。签认仍有效、全部直接依赖都已验收、目标仍在授权范围内时，天璇把上游原生产物修订和验收回执固定在后继票据中。在写入授权的同一事务内再次核对适用的依赖和来源，再由原有预约、执行、阶段检查入口启动工作。自定义普通流程仍由其已有状态机负责。[授权与消费](../customizations/components/tianxuan/sinan-workorders/native_workflow.py) · [司南事件入口](../customizations/components/tianxuan/sinan-workorders/native_dispatch.mjs)

同一上游票据在 `native_outbox_consumed` 只有一条消费记录。重放已经消费的回执时，接收者仍可发现已授权但尚待运行的原票据。预约和物理执行沿用原票据身份。任务成功退出、签认阶段到达、整项交付验收分别保存在各自的业务记录中。[工单进度](gonggong-ai-workbench-s04.md)

## Windows 接收与复跑

实测通过认证 HTTP 运行随仓库交付的 Node 派发器；每次投递都新启一个接收进程。上游进程实际生成模块 b 的输出文件。已签认后继在模块 a 内产生输出，阶段检查读取固定的两个模块并核对字节。下表为子进程自身启动记录的累计条数；另用持久进程退出记录核对每个执行号及退出码。

| 上游回执 | 首次到达 | 第一次重放 | 第二次重放 | 后继接收结果 |
| --- | ---: | ---: | ---: | --- |
| 生产结束，缺少交付验收 | 0 | 0 | 0 | 工单无后继运行 |
| 真实候选已独立验收 | 1 | 1 | 1 | 原运行到达 `stage-reached`，阶段检查通过 |

两组中的未签认同级任务均保持零次启动。定向用例同时检查另一个前置仍未验收、旧来源票据、其他票据和其他宿主入口的回读，以及自定义流程的所有权。Godot 侧另用 #2042 已验收的 Windows 包，以 `copy_editor` 启动隔离 headless 工作台，验证签认、运行、断线重连与撤回。该编辑器回归与上述完成事件实测的候选、票据和结果分别记录。[定向用例](../customizations/components/tianxuan/sinan-workorders/test_native_successor_events.py) · [接收与版本](../data-collection/gonggong-ai-workbench-plan1-s05.json)

在仓库根用具备天璇依赖的 Python、Node 与受验的编辑器包执行以下命令。

```powershell
python -m pytest -q customizations/components/tianxuan/sinan-workorders/test_native_successor_events.py
python tests/editor/run_workbench_confirmed_native_stage.py --godot <编辑器路径> --report <实测结果.json>
```

本次交付随天璇服务与司南 Node 宿主更新。安装时按原流程固定配套代码版本，再启动服务。已有数据库由原生工作流在一个 SQLite 写事务内更新所有权触发器。回退前先等候已启动的工作者终止，保留原数据库备份和所有候选、回执；还原先前服务、派发器及配套数据库快照后再接续旧版本能识别的任务。
