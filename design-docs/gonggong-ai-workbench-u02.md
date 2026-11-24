# U02　打开原生侧栏并恢复编辑焦点

在 2D 或脚本编辑器中打开命令面板，选择 **Open AI Workbench**。命令把现有会话的消息和输入框显示在右侧停靠区。编辑器继续显示发起操作的主屏，草稿随原输入框保留。再次调用同一命令会聚焦同一输入框。[U02 工单](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1869) · [方案一 U02](gonggong-ai-workbench-plan1.md#u02)

使用侧栏内的关闭按钮或原生停靠操作收起侧栏。编辑器将会话控件放回原处，待停靠区完成页签切换后恢复最初发起操作的控件焦点。若原控件已释放或不可见，编辑器跳过该次恢复。主动选回 AI Chat 主屏会把会话带回原页签。[原生实现](../editor/docks/workbench/AIWorkbenchSidebar.cpp)

## 定向复验

从候选源码根运行下列命令。将 `MAC_EDITOR` 指向构建所得的 arm64 裸编辑器，其目录中应有匹配的天枢 UI 和看板包。运行器会建立隔离的编辑器副本和临时项目。

```sh
python3 tests/editor/run_ai_chat_tab_order.py --godot "$MAC_EDITOR" --report "$TMPDIR/u02-layout.json" --workbench-command
```

六轮启动覆盖初始、旧版及重开布局。在脚本中保留未保存文本并继续录入，在 2D 视口中对原选中节点继续操作，同时核对重复打开、原页签切换、源控件已释放等路径。实际二进制、探针和各轮结果见[macOS 验收记录](../data-collection/gonggong-ai-workbench-plan1-u02.json)。[测试入口](../tests/editor/run_ai_chat_tab_order.py)
