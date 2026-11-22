# R03　Windows 编辑器关闭时归还工作者占用

在 [#1775](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1775) 的 Windows 入口，编辑器沿 R02 的退出回调写入本批次的关闭标记，最多等待 15 秒让 runner 收尾。超时沿用原有终止路径，缺少终态证据的预留交由原责任者核对。[R02 交接](gonggong-ai-workbench-r02.md)

每个已登记的 Windows 编辑器工作者有一个私有 Job Object。宿主在工作者主线程挂起时把它加入 Job，再恢复线程。工作者及后代共享该边界。工作者的标准输出和错误都进入原有 transcript，独立控制管道回传实际工作者 PID、执行号、退出码以及 Job 清空结果。

关闭时，runner 核对编辑器 PID、批次、工作者登记和当前候选，等待进程与日志收尾，写入终态、原票据与批次检查点，再归还同属本次执行的容量和工作副本占用。修复接续的工作副本恢复前序预留。取消保留业务待核对状态。身份变化或终态未知时保留占用。编辑器异常终止后的恢复由 R09 承接。

## Windows 实测与复跑

原生编辑器在临时项目中确认一张工单，启动 Windows 工作者及子进程。探针保留它们和外部对照树的四个原始句柄。确认都在运行后，通过 Godot 正常退出触发真实停靠面板回调。退出后同时检查原始句柄、Job 活动进程数、原票据和两类占用，并要求对照子进程回答刚生成的随机挑战。另两例分别替换容量占用所有者、修改工作者登记字节，以验证归还条件。

以下 PowerShell 在仓库根运行。使用当前工作树编译的 GUI 可执行文件，测试将它复制到系统 TEMP 的独立自包含目录并以 headless 模式启动。需要 Git、Node 和仓库支持的 Python，Node 的 Job Object 加载模块来自 `tools/codebuddy_cli/package-lock.json` 锁定的依赖。首次安装可运行 `npm ci --prefix tools/codebuddy_cli --ignore-scripts`。

```powershell
$python = (& ./tools/run_issue_gate.ps1 -ProbeOnly | ConvertFrom-Json).python
$receipt = Join-Path $env:TEMP ("r03-" + [guid]::NewGuid() + ".json")
& $python -X utf8 tests/editor/run_windows_worker_close.py --godot bin/godot.windows.editor.x86_64.exe --receipt $receipt
```

上面的命令使用当前 GitHub 身份只读查询 #1775，适用于工单仍在进行时。关单后在同一命令中追加 `--fixture-issue`，使用仅返回指定虚构仓库工单的本地传输。两种模式均执行实际编辑器、生产 runner 和 Windows Job。每个测试项目禁用远端推送，结束时清理临时项目及对照进程。[候选摘要、验证结果与独立对照](../data-collection/gonggong-ai-workbench-plan1-r03.json)
