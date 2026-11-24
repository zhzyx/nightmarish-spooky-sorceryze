# U01　从任一主屏打开同一工作台

在 Godot 编辑器打开命令面板（默认 Ctrl+Shift+P，macOS 为 Cmd+Shift+P），选择 **Open AI Workbench**。原生命令键为 `editor/open_ai_workbench`。重复执行会显示当前编辑器会话已经挂载的 AI Chat。此入口沿用原主屏与布局键 `AIChatMainScreen`。[U01 工单](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1871) · [方案一 U01](gonggong-ai-workbench-plan1.md#u01)

`EditorNode` 在原注册位置创建主工作台、加入停靠管理器，将命令面板中的键绑定到该对象的 `force_focus_dock` 操作。绑定保留实例身份，可从限制自动切换的主屏显式打开工作台。U02 可以沿用此命令键接入原生侧栏；现有布局仍按原键和原页签顺序加载。[注册点](../editor/editor_node.cpp) · [停靠管理器](../editor/docks/editor_dock_manager.cpp) · [U02 工单](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1869)

## Windows 候选验收

构建使用本工作树的 C++ 源码和清单校验过的 WebView2 SDK，生成独立编辑器并打包天枢 UI 和看板 sidecar。回退时退出候选进程，使用上一套已验收的编辑器和匹配的 sidecar 打开原项目。[B06 构建与回退](gonggong-ai-workbench-b06.md)

从候选仓库根可重跑定向验收。在测试进程环境中清除继承的 `GONGGONG_WORKSPACE`，为探针使用系统临时目录。命令可从 PowerShell 执行。

```powershell
$runner = (Resolve-Path tests/editor/run_ai_chat_tab_order.py).Path
$editor = (Resolve-Path bin/godot.windows.editor.x86_64.exe).Path
$report = Join-Path (Resolve-Path bin).Path 'u01-candidate-order.json'
Remove-Item Env:GONGGONG_WORKSPACE -ErrorAction SilentlyContinue
Push-Location $env:TEMP
try { py -X utf8 $runner --godot $editor --report $report --workbench-command } finally { Pop-Location }
```

探针对初始布局、四种旧布局和重启布局各启动一次真实 headless 编辑器。在每个进程内，从 2D 和 Script 主屏分别在原生命令面板按键查找并执行，再在已打开的工作台重复执行。每次都核对当前可见实例、整棵编辑器节点树中同布局键的实例集合，以及主屏页签数。六个进程共执行 24 次，各自始终只有一个工作台，原有十个页签在正常保存并重新加载后顺序一致。首轮四次调用的实例 ID 均为 `596748830801`。候选摘要、六轮逐次回读、构建与原生测试结果见[验证回执](../data-collection/gonggong-ai-workbench-plan1-u01.json)。
