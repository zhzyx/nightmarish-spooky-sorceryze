# U05　展开工作台并返回原编辑页

从原生侧栏选择 **Expand AI Workbench**。现有输入框、草稿和聊天记录会显示在完整工作台。在完整视图选择 **Return to Sidebar**，或再次从命令面板打开 **Open AI Workbench**，即可返回原编辑页与侧栏。[U05 设计](gonggong-ai-workbench-plan1.md#u05) · [工单 #1840](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1840)

完整视图保留输入框选区及光标，也允许继续录入、改变选区或滚动。返回后显示最新的选区与滚动位置。收起侧栏可继续在来源脚本选区键入。若来源主屏已被扩展移除，仍可返回侧栏继续输入。

macOS arm64 的六个隔离编辑器进程使用原生按钮、命令及滚轮，覆盖 12 次脚本往返、来源释放和旧布局。执行方式、候选摘要和每轮读数见[验收记录](../data-collection/gonggong-ai-workbench-plan1-u05.json)。
