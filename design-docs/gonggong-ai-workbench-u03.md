# U03　在编辑器顶栏打开工作台侧栏

在 2D、3D 或 Script 主屏，点击编辑器顶栏右侧的 **AI Workbench**。当前主屏保持可见，右侧打开已有会话，输入框立即接收键盘输入。侧栏已经打开时，再点同一按钮会重新聚焦输入框。[设计条款 U03](gonggong-ai-workbench-plan1.md#u03) · [工单 #1807](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1807)

编辑器创建顶栏时注册一个按钮。按钮按下时记录来源焦点，激活时调用 U02 的侧栏打开方法，与命令面板共用同一会话、输入框和停靠控件。旧页签迁移由 U13 承接。[顶栏注册](../editor/editor_node.cpp) · [侧栏实现](../editor/docks/workbench/AIWorkbenchSidebar.cpp) · [U13](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1791)

## 定向复验

在 Windows 候选源码根运行以下 PowerShell 命令。运行器把编辑器复制到系统临时目录，创建隔离项目，以 headless 模式将鼠标事件发给编辑器视口。每轮分别从三个主屏点击按钮，移走输入焦点后再次点击。探针核对按钮可命中、当前主屏、侧栏和输入框实例，以及每次点击后的焦点。[测试入口](../tests/editor/run_ai_chat_tab_order.py) · [控件断言](../tests/editor/ai_chat_tab_order.gd)

```powershell
$runner = (Resolve-Path tests/editor/run_ai_chat_tab_order.py).Path
$editor = (Resolve-Path bin/godot.windows.editor.x86_64.exe).Path
$report = Join-Path (Resolve-Path bin).Path 'u03-button.json'
Remove-Item Env:GONGGONG_WORKSPACE -ErrorAction SilentlyContinue
Push-Location $env:TEMP
try { py -X utf8 $runner --godot $editor --report $report --workbench-button } finally { Pop-Location }
```

此前的 macOS 对照记录中，点击旧 AI Chat 页签能找到同一会话，但三次都未聚焦输入框。U03 的候选记录分别保存侧栏及输入框身份和实际焦点读数。[macOS 原始观察](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1807#issuecomment-7059217521) · [U03 候选记录](../data-collection/gonggong-ai-workbench-plan1-u03.json)
