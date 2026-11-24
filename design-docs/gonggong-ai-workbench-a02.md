# A02 让对应用户逐项确认启动

从有已签认设计来源的「工单详情」打开「逐项确认启动」。窗口列出同项目、同设计修订的可见工单，逐项显示阶段、到达条件和确认状态。勾选可同时核对多项；每行的「确认启动本项」只写入该行。成功后行内显示天璇回读的确认身份。当前负责人可在同一行撤销。关闭并重开窗口会从服务重新读取。[原始工单](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1847) · [A01 阶段目标](gonggong-ai-workbench-a01.md)

## 天璇接口

用 `GET /api/v1/issues/by-number/{number}/detail?project={project}` 读取 `task_target`、当前指派和 `task_confirmation`。原设计不可见或尚未定义过目标时，确认对象为 `null`。返回的确认对象包含工单 ID、设计 ID 和版本、工单定义摘要 `issue_revision`、当前阶段、目标修订 `target_revision`、确认修订 `revision`、当前负责人 `responsible_user`、状态和确认人 `confirmed_by`。待确认及撤销状态的确认人为空。初始确认修订为 0。定义同一工单的后续目标、改变工单定义、改派负责人均使旧确认失效。

向 `PUT /api/v1/issues/{issue_id}/task-confirmation?project={project}` 提交 `document_id`、`version`、`issue_revision`、`target_revision`、`expected_revision` 和状态 `confirmed` 或 `revoked`。服务校验认证用户、编辑权限、工单与原设计可见范围、当前工单定义和目标修订。当前指派人可对已定义目标确认，未指派时由建单人确认。原设计已发布后续版本时，工单仍指向拆单时的签认版本。更新在同一 SQLite 事务中完成并记录身份事件。相同写入重试可重复取得同一回执，撤销后重放过期确认返回 409。工单执行状态由后续流程维护。

A03 消费者须按当前负责人、目标、阶段、工单定义摘要和确认修订复核本机请求。当前确认对象是天璇按现有工单投影的记录。同一个用户可以先撤销、再重新确认，消费者依确认修订区分两次授权。[天璇服务](../customizations/components/tianxuan/server/tianxuan_core.py) · [原生控件](../editor/docks/workbench/issue_actions/issue_task_confirmation.gd)

## 构建和验证

原生控件沿用工单详情动作的内嵌构建规则；修改 GDScript 后重建编辑器。服务启动时为现有数据库新增 `design_task_confirmations`。回退时恢复原编辑器和服务，保留数据库记录。[构建入口](../editor/SCsub)

```sh
python -m pytest -q customizations/components/tianxuan/server/test_task_confirmations.py
python tests/editor/run_workbench_task_confirmations.py --godot <候选编辑器> --report <回执文件>
```

原生探针连接临时天璇账户服务，在同一窗口向两项复选框发送实际鼠标按压与释放，再点击第一项的启动确认。独立 HTTP 客户端回读两项的状态和身份。重新打开服务、数据库和编辑器后再次核对，并通过原生按钮撤销第一项。[实测回执](../data-collection/gonggong-ai-workbench-plan1-a02.json)

I06 的早期 Mac 观察记录了只读状态写入被拒及当时的负责人接口缺口。其后的 macOS 集成回执覆盖 I03–I06。A02 的平台和候选以本卡回执为准。[I06 Mac 观察](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1850#issuecomment-7067781078) · [后续 Mac 集成](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1861#issuecomment-7068555775)
