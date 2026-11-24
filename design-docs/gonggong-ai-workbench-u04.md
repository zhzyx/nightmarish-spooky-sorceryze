# U04　可重绑定的工作台快捷键

在编辑器按 **Ctrl+Shift+M**，macOS 使用 **Cmd+Shift+M**，即可打开工作台侧栏并聚焦当前会话的输入框。在编辑器设置的 **Shortcuts** 中搜索 **Open AI Workbench** 可修改或清除绑定。命令面板里的同名命令和快捷键共用原有侧栏，收起后焦点回到发起操作的控件。[U04 工单](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1808) · [原设计](gonggong-ai-workbench-plan1.md#u04)

原生工作台向 EditorSettings 注册 `editor/open_ai_workbench`。编辑器先派发 GUI 输入，再匹配工作台快捷键，因此输入框可优先处理全选等文本操作。命令面板引用同一 Shortcut 资源，在设置变更后显示当前绑定。[原生实现](../editor/docks/workbench/AIWorkbenchSidebar.cpp)

## 定向复验

从源码根运行下列命令，指定本次编译的编辑器。先清空测试进程继承的 `GONGGONG_WORKSPACE`，运行器会创建临时的独立设置和工程。

```powershell
$env:GONGGONG_WORKSPACE = ''
$repo = (Get-Location).Path
Push-Location $env:TEMP
try {
    py "$repo/tests/editor/run_ai_chat_tab_order.py" --godot "$repo/bin/godot.windows.editor.x86_64.exe" --report "$repo/bin/u04-layout.json" --workbench-command
} finally {
    Pop-Location
}
```

探针依次派发默认键和改绑后的 Alt+Shift+P，检查打开的侧栏、输入框实例与焦点，验证旧键失效。再临时把工作台绑定到 Ctrl/Cmd+A，检查聊天输入框和单行输入框均能选中原文。原卡所附 macOS 观察覆盖命令面板；本卡的候选及实测平台见[验证记录](../data-collection/gonggong-ai-workbench-plan1-u04.json)。[探针](../tests/editor/ai_chat_tab_order.gd)
