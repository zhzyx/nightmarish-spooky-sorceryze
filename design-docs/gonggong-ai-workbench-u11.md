# U11　从工单详情打开咨询

在统一侧栏的「工单详情」读取天璇工单，点击「咨询此工单」。输入框上方显示「只咨询」、工单编号、标题、稳定 ID、详情读取时的内容修订及会话 ID。仅查看详情时，正在编写的会话保持原位。更改编号、登出或读取失败后，详情入口随旧记录一起清除。[U11 工单](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1811) · [Mac 先前观察](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1811#issuecomment-7067766533)

天璇在同一事务中核实工单读权、当前项目和模块，按租户、账号和工单恢复个人咨询。旧版模块位置有匹配会话时，核对历史消息的工单上下文后保留原会话。首次绑定后，同模块的另一张工单有独立会话。当前编辑器按模块、工单和会话索引未发送草稿。账号切换清除本地草稿及预览。[天璇会话](../customizations/components/tianxuan/server/workspace_conversations.py) · [模块对话](../editor/docks/workbench/module_selector.gd)

点击「发送」后，C05 消息快照包含项目、模块、工单及 `kind=issue` 引用。引用的 `object_id` 为 I02 详情中的工单 ID，`revision` 为当次读取的内容摘要。模型同时收到本次引用的标题、负责人和状态。重新读取并从详情进入，会为下一条消息绑定新修订。咨询沿用发送消息接口。详情入口由原生 `IssueActions.gen.h` 内嵌脚本挂载，修改脚本后需重新构建编辑器。[详情操作](../editor/docks/workbench/issue_actions/issue_consultation.gd) · [C05 快照](gonggong-ai-workbench-c05.md)

## 定向复验

从候选源码根运行以下命令。测试启动隔离的无窗编辑器和本机天璇服务，在同一模块、两个同名模块分别建立同名 A、B 工单。编辑器从正在编写的 B 打开 A，发送后返回 B，再切换模块核对草稿。测试在 A 首次发送前改动其内容修订，同时核对发送前预览、模型夹具收到的内容、持久会话及执行记录。[测试入口](../tests/editor/run_workbench_issue_consultation.py) · [候选与回执](../data-collection/gonggong-ai-workbench-plan1-u11.json)

```powershell
python -X utf8 tests/editor/run_workbench_issue_consultation.py --godot bin/godot.windows.editor.x86_64.exe --report bin/u11.json
```
