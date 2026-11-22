# 已保存布局冷开时显示本人待判断项

本单承接 #1709 的关闭重开验收 #1732 和首屏要求 #1777。原 Mac arm64 Cocoa 记录在 #2125。编辑器读到了正确的 `b @ 48a0ca56…`，首行已有焦点，但行和停靠侧栏在控件树中均不可见。[故障原单](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/2125)

## 恢复顺序

项目的首次文件扫描完成时，EditorNode 恢复保存的停靠布局和主屏。已保存的全屏工作台可能在这个步骤关闭停靠侧栏。若本人队列更早返回，立即打开的侧栏会被随后的恢复覆盖。待判断控件现在照常请求并绑定条目，等首次布局恢复后才打开侧栏，下一帧聚焦首行。登录身份或工单变化使等待中的请求失效。空队列沿用保存的布局。独立工作的恢复继续由原生会话发起。

## 验收和复跑

在仓库根使用 Python 3.11+ 和可直接启动的候选编辑器。脚本会复制编辑器到临时目录，启动隔离账号、回环服务和确定性工作者。在 Windows 传入原生 `.exe` 主程序，在 macOS 传入 arm64 独立可执行文件。macOS 的 Cocoa 验收需要可用图形登录会话。

```sh
python -m pip install -r customizations/components/tianxuan/server/requirements.txt
python tests/editor/run_workbench_startup_judgments.py --godot <editor> --display-driver macos --report r08-cocoa.json
python tests/editor/run_workbench_startup_judgments.py --godot <editor> --display-driver macos --judgments-first --report r08-cocoa-ordered.json
```

两轮都可追加 `--saved-layout <Q05工程/.godot/editor/editor_layout.cfg>`，将关闭后保存的原布局复制到两个隔离工程，按 SHA-256 核对实际重开字节。未传入原布局时，测试使用与设计批次样例相同的渲染配置，正常关闭 AI Chat 主屏并记录生成的布局。Windows 后台验证省略 `--display-driver macos`。

普通轮在正常调度下观察首屏。受控轮等本人行从真实 HTTP 响应绑定后才放行首次扫描的布局回调。两轮均在独立工作者实际启动时核对首行文字、修订、可见性、焦点、滚动视口和编辑器边界，并在工作恢复后再次核对。无待办账号单独冷开，保留关闭前的主屏和隐藏侧栏。观察器只在准备布局时可以导航，重开期间的首屏结论完全来自自动行为。输出包含各次窗口的关闭/重开进程回执、布局摘要、控件观测、工作者及检查进程回执。

Windows 后台回执见 [本单验证记录](../data-collection/macos-cocoa-reopen-pending-judgment-sidebar-windows.json)。原 Mac 样例的可见 Cocoa 窗口须由 Mac 候选实测确认。

## Windows 原版对照

Q06 从 F01 提交 `35a233f2a6910ad0ec19931bd1db12e3d4b28fa6` 重建的 Windows 编辑器 SHA-256 为 `2147dfb85d4b03a1d088c7e738301f1b81c7f74fa2509d19e15dcbbff494891f`。该程序的普通轮通过。相同程序在队列先到时退出 1，侧栏隐藏，首行已绑定正确修订，独立工作者已启动，焦点落在 ChatInput。该次日志 SHA-256 为 `c6c1049bcf3d7d144fe67b456a4569e9290b118ed556a7dcf9e7cac7a29f79e0`。Windows 验证记录中的 `5b30bbfe…` 为另一份 #2121 已验收对照包，两者在相同顺序下都复现了隐藏侧栏。
