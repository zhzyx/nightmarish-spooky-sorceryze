# S07 工单和模块中的运行进度

在 AI 工作台选择业务模块和工单，点击「运行进度」。也可以在「工单详情」按编号读取同一工单，再点击「运行进度」。两个入口打开同一个只读窗口，显示运行号、签认的目标阶段、当前运行状态和由新到旧的工具步骤。每条回执保留天璇接收时的序号、时间、步骤、状态与详情。成功生成产物后可复制候选修订。执行失败时可查看已记录的退出码和原因。[S07 工单](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1763)

每次打开或点击「刷新进度」，窗口先以当前登录身份按项目和编号读取工单详情，对照所选工单 ID。只读账号直接查看获准返回的 `execution_progress`。其他账号以其中的运行号读取按精确 key 寻址的 `workflow/status`。返回的 `progress` 必须属于同一工单及运行。没有可读运行时显示空状态。关闭窗口、重新选择详情或退出账号会清除窗口数据并丢弃旧请求的响应。[天璇进度接口和事件持久化](gonggong-ai-workbench-s04.md)

### Windows 定向验收

从仓库根使用装有天璇依赖的 Python 和候选编辑器执行以下命令。

```powershell
python tests/editor/run_workbench_task_progress.py --godot bin/godot.windows.editor.x86_64.exe --report <本次结果.json>
```

探针复制编辑器到临时目录，用已签署设计拆出两个任务，确认并启动其中一个。在工作者尚在运行时，通过模块和工单两处读取运行号和已准备工作区的回执。真实子进程结束后，工单窗口刷新，再从展开后的完整工作台模块入口重开，两次显示均与独立读取的 SQLite 有序记录核对。成功场景还核对产物候选。失败场景核对退出码 7。另以获准阅读设计的 viewer 身份回读进行中和终态。选择未启动的兄弟任务后显示空状态，退出账号后窗口与文本均清除。[原生探针](../tests/editor/workbench_task_progress.gd) · [实测版本与接收结果](../data-collection/gonggong-ai-workbench-plan1-s07.json)

### 构建与回退

模块按钮在 `module_selector.gd`，详情按钮和共用窗口在 `issue_actions/issue_task_progress.gd`。业务会话为按运行号读取状态的端点保留无查询参数的路由。编辑器的 `SCsub` 把会话、模块、详情脚本分别写入 `BusinessSession.gen.h`、`module_selector.gen.h` 和 `IssueActions.gen.h`，由 `AIWorkbenchSidebar.cpp` 链入 Windows 编辑器。旧编辑器回归对照缺少运行控件，本次在独立工作树重建并测试。更新和回退以已验收编辑器包为单位，保留原天璇数据和服务。[嵌入脚本构建入口](../editor/SCsub)
