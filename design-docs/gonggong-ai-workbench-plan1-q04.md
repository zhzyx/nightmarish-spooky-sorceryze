# Windows 编辑器关闭与重开验收

[Q04 原单](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1731)要求在运行中关闭真实 Windows 编辑器，随后重开同一项目，观察本人的待判断项、独立支路恢复和提交次数。

## 实测路径

在 Windows 上直接启动 GUI 可执行文件，传入 `--headless --single-window --resolution 1440x960 --editor`。每次启动沿用同一个临时工程、私有设置、登录账号和回环业务服务。观察器通过根窗口传播正常关闭通知。临时目录退出后自动清理。

1. 签发模块 a 的预览生产任务。观察本地工作者及子进程已活跃、工作者能应答新的随机值，并从服务读回任务正在运行。保存停靠栏隐藏的 AI Chat 主屏并正常关闭。退出后发出第二个随机值，从 Windows 内核核对两个 PID 的终态，同时核对服务已持久化中断检查点。
2. 项目关闭期间，在模块 b 留下一条需要同一账号判断的草图。重开时让队列先到，随后放行保存布局的恢复。观察首行已处于编辑器视口内并获得键盘焦点。模块 a 的同一签发任务从原始不可变输入重新运行，校验器实际读取生成的 SVG。已中断工作区的草稿留在归档。
3. 再次正常打开项目，核对工作者及校验器启动数、候选接收调用、存储收据、草图提交版本和业务确认修订。首轮中断与一次必要的生产重试分别计数，实际提交以候选接收调用和持久收据共同核实。

## 复跑

构建配方、候选源树、二进制摘要、冻结版本失败记录与测试回执见[验收记录](../data-collection/gonggong-ai-workbench-plan1-q04.json)。在仓库根运行如下命令。`$src` 指向按验收记录还原的候选源目录，并包含用其编译的编辑器。`$python` 使用装有天璇服务测试依赖的 Python 3.11 或以上解释器。

```powershell
& $python -X utf8 tests/editor/run_windows_close_reopen.py --source $src --godot (Join-Path $src 'bin/godot.windows.editor.x86_64.exe') --report q04-replay.json
```

脚本需要在工作区以外的系统临时目录创建私有项目，直接传入 GUI 主程序，以便回执中的 PID 标识真实编辑器。测试账号、任务和进程每次重新创建。屏幕判据取自真实控件树的可见范围和焦点，本轮使用 Windows headless 显示驱动。
