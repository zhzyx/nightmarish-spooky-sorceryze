# U12　从编辑器页面带入通用引用

在马良或已注册的扩展页打开命令面板，选择 **Open AI Workbench**。输入框上方显示页面名、模块和可读范围。马良的模块标识为 `AINativeMainScreen`。项目插件使用其注册脚本的项目相对路径，例如 `res://addons/notes/plugin.gd`。这条页面引用仅包含名称和模块标识，页面里的未发送文本留在原控件中。点击引用即可移除。[工单 #1809](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1809) · [方案一 U12](gonggong-ai-workbench-plan1.md#u12)

侧栏先定位发起操作的停靠页。焦点在页面外时取当前主屏。场景、脚本、文件系统和检查器沿用各自的选区入口；已暂存的引用优先。页面改名、移除或编辑器重启后，失效引用会保留在草稿中，点击移除后可继续发送。[侧栏入口](../editor/docks/workbench/AIWorkbenchSidebar.cpp) · [引用生成与校验](../editor/docks/workbench/AIWorkbenchReference.cpp)

原生聊天沿用 C05 编辑器引用的 `kind`、`object_id`、`revision` 字段。`editor-page://` 定位符分别编码模块和页面名，`revision` 为定位符 UTF-8 字节的 SHA-256，表示本次可读元数据的版本。发送时将该条引用写入消息记录，并将当时的页面名、模块、范围和引用作为 JSON 快照放入该条模型消息正文。现有的排队和发送渠道消费同一条已冻结消息。[C05 消息快照](gonggong-ai-workbench-c05.md) · [原生消息发送](../editor/docks/ai_chat_dock.cpp)

## 定向复验

从候选源码根运行下列命令。测试在系统临时目录建立编辑器副本和独立工程，启用 R4 Notes 插件，通过实际命令面板和发送按钮操作。在 960、1200、1440 像素宽窗口分别检查引用和输入框的可见矩形。马良在嵌入模式下使用已有滚动容器显示较宽的工具。回环接收端独立计算两个页面引用的摘要，和原生会话中持久化的三条消息逐项比较，还核对插件私有草稿、页面改名后的拒发和移除后下一条消息的正文。[测试入口](../tests/editor/run_workbench_page_reference.py) · [候选和接收回执](../data-collection/gonggong-ai-workbench-plan1-u12.json)

```powershell
python -X utf8 tests/editor/run_workbench_page_reference.py --godot bin/godot.windows.editor.x86_64.exe --report bin/u12-pages.json
```
