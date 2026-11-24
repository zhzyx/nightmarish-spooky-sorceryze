# I13　从天枢旧会话和在途记录读取原单

在 AI 工作台侧栏或展开的会话中选择 **查看关联工单**，即可读取这次会话绑定的原工单。右键另一个会话标签也能查看它的关联工单，当前标签和输入草稿保留。在天枢看板选择 **筛选与跟进 → 在途工单**，还可从当前账号的已绑定草稿、开工记录或在途看板项选择 **读取原单详情**。[原工单 #1755](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1755) · [方案一 I13](gonggong-ai-workbench-plan1.md#i13)

原生弹窗显示来源、原 URL、稳定需求标识、原单标题、正文及其当前状态。来源记录包含当时的状态时，同时显示记录状态。账号作用域包含工作区、仓库 ID 和账号 ID。没有作用域的旧会话需要当前账号的私人记录以工单号、需求标识和来源相互印证。原标识过期、无权访问或缺少关联记录时，弹窗显示查证结果。[原生入口](../editor/docks/ai_chat_dock.cpp) · [天枢映射与界面](../editor/docks/daqian/workspace.gd)

读取动作复用已验证的天枢会话、看板宿主和 `bound_issue`，向原仓库发出一次 GitHub 工单 GET。宿主核对返回的工单号、规范 URL、记录类型和原始需求标识，回传前复核当前账号。C04 的天璇模块位置以及 I12 的归档原件继续由各自入口读取。[看板宿主](../customizations/components/godot-host/daqian/board.py) · [C04](gonggong-ai-workbench-c04.md) · [I12](gonggong-ai-workbench-i12.md)

部署使用同一候选的编辑器、看板包和安装宿主。回退时一并恢复上一版编辑器和对应看板包、宿主脚本。已有的会话和工作记录沿用原存储格式。[原生冷启动用例](../tests/editor/daqian_inflight_issue.gd) · [定向验收回执](../data-collection/gonggong-ai-workbench-plan1-i13.json)
