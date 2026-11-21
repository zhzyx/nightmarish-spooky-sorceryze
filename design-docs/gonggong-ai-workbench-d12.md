# D12　按工单恢复业务模块对话与未发草稿

在 AI 工作台登录天璇，选择业务模块和工单。再次打开同一编辑器工程、登录同一账号并选择模块时，编辑器从天璇读取该模块最近的工单和会话。消息与回复由服务端保存。切换到其他工单时，编辑器核对工单列表，并读取该工单上次关联的会话。首次进入的工单从空会话开始。打开或切换都不会发起模型请求。[工单 #1748](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1748) · [方案一 D12](gonggong-ai-workbench-plan1.md#d12)

编辑器在当前操作系统用户的 Godot 编辑器数据目录 `business-drafts/` 保存未发送正文、引用定位符、修订、脚本摘录和会话标识。每份草稿使用独立文件，以天璇服务地址、已核验账号 ID、业务项目、编辑器项目绝对路径、模块 ID 和工单 ID 的组合计算文件名。模块概览有自己的空工单位置。同名模块与同名工单各自保留草稿。清空正文、逐条移除引用、退出账号和重新登录均通过业务输入框生效。切换时清除输入框撤销记录。账号令牌和已配置的模型密钥在写入前脱敏，凭据仍由当前登录会话管理。文件引用在恢复和发送时校验修订，原生场景节点和临时对象仍需本次编辑器实例核实身份。[模块输入框](../editor/docks/workbench/module_selector.gd) · [草稿文件与引用恢复](../editor/docks/workbench/AIWorkbenchDraft.cpp)

用户按发送后，工作台先保存该条消息的请求 ID，再向原会话发送正文与引用快照。编辑器关闭时若服务端已经保存消息，重新打开会先根据原 ID 与编辑内容核对回执，保留期间修改过的草稿。文件经临时文件写完后替换；写入失败在模块内提示。消息与回复始终以通过当前身份回读的会话为准。

## 定向复验

从候选源码根运行以下命令。探针启动独立天璇 HTTP 服务、账号数据库和有固定回复的测试模型传输。多个后台编辑器进程依次复用同一份临时项目和私有编辑器设置，逐次记录真实工单、会话、引用修订、草稿、消息数及 HTTP 动作。验收覆盖换工单、两个同名模块的不同文件、重开、主动清空、换账号与换项目。[复验入口](../tests/editor/run_workbench_module_drafts.py) · [候选与实测回执](../data-collection/gonggong-ai-workbench-plan1-d12.json)

```powershell
python -X utf8 tests/editor/run_workbench_module_drafts.py --godot bin/godot.windows.editor.x86_64.exe --report bin/d12-checks.json
```

该改动随原生编辑器构建。原有工作台脚本通过 `editor/SCsub` 生成嵌入头文件，草稿读写由 `editor/docks/SCsub` 纳入原生目标。回退时恢复前一已验证编辑器与对应源码，保留服务端会话和本机独立的草稿目录，便于回到支持恢复的版本。
