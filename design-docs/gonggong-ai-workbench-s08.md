# S08　按资产写入范围预约本机工作者

两张已授权工单可以同时写同一模块中的不同对象。两张工单写同一对象时，先取得预约的工作者占用该资产，后一张保留在持久队列中。认证服务的 `POST /api/v1/native/workflow/inspect` 返回等待票据的 `snapshot.items[].key`、`dispatchCandidate: false` 与 `waitReason: resource_conflict`。票据可通过 `status` 回读原工单。占用方不可见时，服务只返回匿名槽位和调用者有权读取的等待票据。[S08 工单](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1792)

安装计划把声明的产物路径映射为租户原生模块与对象名，`authorize_task` 将这个范围固化在任务契约的 `writes` 中。司南使用 `/native-assets/<tenant>/<module>/<object>` 作为逻辑地址，沿用可移植工作区的大小写折叠规则。整模块写入占用模块根，对象与其上下级路径互斥。工作者从独立目录读取已钉住的不可变输入修订，可以与产出新候选的工作者并发。已存在的异常路径声明在调度期间保守地占用整模块。[安装计划](../customizations/components/tianxuan/server/native_entry_factory.py) · [预约实现](../customizations/components/tianxuan/sinan-workorders/native_workflow.py)

服务在同一个 SQLite 写事务里重读原契约、占用、可运行队列与容量，随后写入预约。客户端提交的范围不会改变已授权契约。调度器保留可运行工单的先进先出顺序，遇到正在等资产的队首时允许独立任务使用空槽。`reserved`、`running` 和 `held` 票据持续占用其资源。工作者产生终态后，原来的执行结束事件触发重新读取与接续。按工单限定的入口也会订阅可见的冲突占用方，即使此时还有空槽。[入口适配](../customizations/components/tianxuan/server/native_execution_host.py) · [司南驱动](../customizations/components/tianxuan/sinan-workorders/native_dispatch.mjs)

## Windows 接收实测

在隔离的本地项目中，三项已签认工单分别运行有界的 Python 子进程。前两项声明写 `a/preview.svg`，第三项写 `a/peer.svg`。测试通过实际 Node 司南、认证 HTTP、SQLite 任务库和原生资产库完成派发。子进程自行记录运行号、PID 及高分辨率开始和结束时间。首项与第三项运行区间重叠；第二项当时只出现在等待队列。首项完成后，第二项实际启动，第三项仍在运行。三项进程退出码均为 0，各自的候选通过已授权的 SVG 内容检查，达到签认的阶段。

另一次实测只把等待工单交给带身份检查的共享 Node 入口。占用者从另一个认证入口启动。两槽中尚有一槽空闲时，等待入口订阅占用者终态，随后仅启动自己的工单。跨数据库连接的预约、通配范围、大小写别名、父子对象路径和不可见占用者另有定向测试。S03 的原生断线重连流程也在同一版本服务上复验，原工作者只有一次实际启动。[定向用例](../customizations/components/tianxuan/sinan-workorders/test_native_asset_reservations.py) · [实测回执](../data-collection/gonggong-ai-workbench-plan1-s08.json)

## 复跑与交接

从仓库根目录使用已安装的天璇 Python 依赖和 Node 运行。第一条命令把进程区间、候选和等待回读写入 JUnit 属性。第二条命令经 `copy_editor` 复制已核对的 Windows 编辑器和配套资源，执行 headless 签认与重连检查。

```powershell
python -m pytest -q -o junit_family=legacy -o tmp_path_retention_policy=none customizations/components/tianxuan/sinan-workorders/test_native_asset_reservations.py --junitxml=<本次报告路径>
python tests/editor/run_workbench_confirmed_native_stage.py --godot <已验收编辑器> --report <本次原生报告路径>
```

本次变更由天璇服务及 Node 派发程序加载，保留已有任务数据库。发布者从相同候选取得服务、派发及入口适配文件后一并部署。需要回退时先结清物理占用，再切回此前已验收的服务与派发程序。前置为已验收的 I04 和 S03，下游 H06、K03、R09 各自核对其余前置。[I04 工单](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1831) · [S03 工单](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1845)
