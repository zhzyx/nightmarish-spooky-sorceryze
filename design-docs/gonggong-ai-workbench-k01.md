# K01 从脚本编辑现场抵达模块对话

角色移动与角色动画共享 B05 样例中的 `models/suzanne.glb`。在引用这份模型的脚本中选中其路径，按 Windows 的 `Ctrl+Shift+M` 打开 AI 侧栏。通过“查看现有归属”查找模型的多宝来源、版本和对象路径。两个模块都可读时，侧栏要求明确选择；选择角色移动后，引用进入该模块的输入框。[样例清单](../samples/gonggong-workbench/fixtures/b05/sample.json) · [K01 工单](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1717)

发送一次咨询后，在角色移动留下未发草稿。再为同一资产选择角色动画，写入第二份草稿。通过模块选择器往返时，角色移动显示原稿和一轮问答，角色动画保留自己的草稿和资产引用。展开完整工作台，返回侧栏并关闭，原脚本应重新获得焦点，保留原选区，接收下一次键入。

## Windows 快捷键修复

在修复前的真实编辑器中，脚本输入控件将 `Ctrl+Shift+M` 当成 `Ctrl+M`，切换了 Tab 输入模式。命令面板在同一基线上可以走通上述路径。修复让 TextEdit 用原始按键修饰符匹配 Tab 输入模式，沿用原有光标移动和焦点处理顺序。探针同时检查 `Ctrl+M` 的两次切换及 `Shift+Right` 的扩选。[源头修复](../scene/gui/text_edit.cpp) · [故障记录](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1995)

## 复验

从仓库根、使用已安装天璇服务依赖的 Python 执行以下命令。每次执行都会创建并清理临时项目、编辑器副本、天璇和多宝数据库。通过回环天璇服务进入模型适配器，模型传输返回固定测试答复。

```powershell
python tests/editor/run_workbench_context_milestone.py --godot <候选编辑器> --report <本机报告.json>
```

默认入口使用工作台快捷键，追加 `--entry palette` 可复验命令面板入口。一次验证使用同一编辑器进程。报告保留两个归属选项、实际选择、历次草稿与可见答复、编辑前后选区及控件标识、天璇回读和模型收到的消息快照。[原生探针](../tests/editor/workbench_context_milestone.gd) · [本次分项结果及十二张前置接收回执](../data-collection/gonggong-ai-workbench-plan1-k01.json)

前置 D12 已在 PR #1989 的 macOS arm64 集成候选验证跨启动草稿并回读主线，本次 K01 实测平台为 Windows x86-64。[D12 验收](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1748#issuecomment-7068555654)
