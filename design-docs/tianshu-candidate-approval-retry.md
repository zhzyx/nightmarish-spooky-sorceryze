# 天枢候选命令确认与重试推进

关联工单 [#582](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/582)。来源为 [#534](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/534) 的 Windows 工作者现场，关联 [#562](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/562)。稳定需求 ID 为 `tianshu-candidate-approval-retry`。路径以仓库根为基准。

## 操作身份与展示

原生批准记录分别绑定执行候选根与天枢看板工作区。绑定和确认时核对当前候选所有者、工单、Git 分支与基线，再按看板工作区、仓库 ID 和用户 ID 核对对话归属。看板只展示同账号、同工单 URL、同需求 ID 和来源摘要的当前步骤。执行前重新读取工单版本并校验单次 token。

在天枢工单选择「查看待确认操作」应定位到实际卡片。聊天中单独输入「执行」或「确认」只提示返回卡片核对。旧 token、已变更的工单和重复确认都应拒绝。正常确认后，命令只在候选工作树执行一次。

## 延续原工单

工作者报错后，「重试推进」应重新核对身份并接回原工单。原生层将单独的无附件「执行」识别为继续当前直达工单，对既有候选也读取该工单的原推进回执。实质性需求补充仍走偃师范围判断。新版 Python 适配器核对已开工的直达工单来源、协作者及开工回执，再发布补充内容。缺少有效回执时暂停。

## 验收证据

`tests/editor/run_daqian_node_approval.py` 用独立 Windows 编辑器、临时 Git 工作树与本地测试传输验证卡片、手动确认及后续交互。`customizations/components/godot-host/test_requirements_agent.py` 验证需求补充的转发、拒绝和恢复。在原用户可见编辑器复验属于独立业务验收，由原工单责任者记录原会话和实际反馈。验证记录位于 `data-collection/tianshu-candidate-approval-retry-582.json`。
