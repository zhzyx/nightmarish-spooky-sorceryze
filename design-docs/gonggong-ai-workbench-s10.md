# S10　按工单运行号暂停、恢复与取消本机工作者

打开 AI 工作台的「工单详情」，读取当前天璇工单。已授权本机运行的负责人可以看到运行号，以及当前状态允许的操作。点击后，工作台重新读取同一项目、同一工单的进度。正在等待进程退出时可点击「重新读取运行」。来源见 [S10 工单](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1814) 和 [S04 进度验收](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1842#issuecomment-7077025073)。

| 操作 | 接收条件与实际效果 |
| --- | --- |
| 完成当前步骤后暂停 | 等待派发或仅完成本机预约时立即暂停。运行中的本机生产步骤先完成进程退出、日志关闭和候选保存。天璇随后把运行置为已暂停，暂停期间阶段检验和交付保持关闭。 |
| 已核对，恢复运行 | 面板显示原授权、来源修订及已发生的副作用。服务重读当前工单的活动运行号、原确认、依赖、工作者安装与持久进程和产物回执。尚未启动的任务重新等待预约，已完成的工作者沿原候选进入后续阶段。 |
| 取消此运行 | 服务先持久记录运行号和取消意图。该运行的本机进程监督器终止自己持有的进程树，关闭输出后释放预约。已保存的步骤和候选可按原运行号回读。重新打开工单只读取记录，取消状态保留。 |

服务的三个动作位于 `POST /api/v1/native/workflow/{pause,resume,cancel}`。请求包含工单 ID、运行号及操作者看到的最后一个进度序号。服务验证认证身份、当前项目、工单写权限和原运行责任者。每项决定与一条带序号的审计事件同事务提交。相同决定重投时返回当前状态，新决定必须基于当前进度。暂停时仍在执行的生产步骤继续占用原有资产与工作槽；取消效果也以工作者的实物关闭回执为准。[实现与控制端点](../customizations/components/tianxuan/sinan-workorders/native_workflow.py) · [原生面板](../editor/docks/workbench/issue_actions/issue_run_control.gd)

## 复验

从仓库根使用已安装天璇依赖的 Python，并传入本候选的 Windows 编辑器。验证程序经 `copy_editor` 在用户临时目录建立隔离副本，通过 headless 编辑器的实际按钮连接认证服务，本机进程自行写出运行号和 PID。三个工作者分别覆盖暂停后继续已有候选、并行正常结束、运行中取消。每个成功按钮请求均再经 HTTP 原样重投一次，核对重复接收、审计事件和物理启动次数。恢复负例另覆盖签认已撤销、安装前出现未知工作区、工作者终态与已读回执不一致、陈旧序号及跨工单误投。[原生验证](../tests/editor/run_workbench_task_controls.py) · [服务回归](../customizations/components/tianxuan/sinan-workorders/test_native_run_controls.py) · [候选、执行与接收回执](../data-collection/gonggong-ai-workbench-plan1-s10.json)

```powershell
python tests/editor/run_workbench_task_controls.py --godot bin/godot.windows.editor.x86_64.exe --report <本次原生报告.json>
python -m pytest -q -o tmp_path_retention_policy=none customizations/components/tianxuan/sinan-workorders/test_native_run_controls.py
```

普通天璇安装入口还用两名用户的独立需求复验。一个本机工作者进入暂停后，另一个用户的需求完成交付。服务重新接收恢复操作后唤醒原任务，完成审查和交付。复验通过正常 ASGI 应用和安装的 Node 司南执行。[安装入口回归](../customizations/components/tianxuan/server/test_native_entry_normal.py)

## 安装与回退

工单详情现有的脚本收集器将 `issue_run_control.gd` 嵌入 `IssueActions.gen.h`，由 `AIWorkbenchSidebar.cpp` 安装在已认证的工单详情下。更换脚本须重新编译编辑器。天璇 Python 服务加载工作流、工作者与控制路由，在原 SQLite 库中增加按运行号索引的意图，既有阶段及进度记录继续沿原端点读取。此次控制覆盖本机生产工作者，远端节点继续使用其原有传输适配。

更新或回退时先核对在途工作者和待执行控制。保留数据库、已关闭日志、候选和原始工作者安装，待在途工作核实后配套切换编辑器与服务。已暂停或取消的运行在启用兼容服务并重新核对前应保持原记录。
