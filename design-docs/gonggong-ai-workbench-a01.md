# A01　定义任务目标阶段与到达条件

打开「工单详情」，读取由已签认设计拆出的天璇工单，再点击「任务阶段目标」。分别填写要做到的阶段和可观察的到达条件。例如，程序单可指定「可运行原型」，要求拉动拉杆只触发一次开桥事件；动画单可指定「动画预览」，要求第 24 帧桥面完全展开。保存后窗口从服务重新读取该工单。当前负责人可修改目标，尚未指派的任务由建单人填写。负责用户随本次目标记录保存。

提交了阶段但未填写到达条件时，目标显示为已退回，原单评论保存退回原因。补齐并重新保存后，目标成为已定义，历史退回意见仍可在原单评论中查看。两张工单分别修订，保存阶段目标不推进工单的执行状态。[A01 工单](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1856) · [D10 已签认设计拆单](gonggong-ai-workbench-d10.md)

## 写入与回读

向 `PUT /api/v1/issues/{issue_id}/task-target?project={project}` 提交 D10 原始 `document_id` 和 `version`，以及 `stage`、`criteria` 和 `expected_revision`。阶段为 1 至 128 个字符，到达条件最多 8000 个字符。空白或省略条件会保存 `returned` 状态，返回 `return_comment_id` 和 `return_reason`。完整记录的状态为 `defined`。从租户、工单和会话取得的实际负责用户 ID 存于 `responsible_user`。第一次写入传目标修订 0，后续沿用上次读到的目标 `revision`。同一写入重试返回现存记录。并发改写或设计版本不符返回 409。

用 D10 的 `GET /api/v1/docs/{document_id}/versions/{version}/tasks?project={project}` 定位任务，再从 `GET /api/v1/issues/by-number/{number}/detail?project={project}` 读取 `design_source` 和 `task_target`。目标携带工单 ID、原设计 ID 与版本、阶段、标准、负责用户、目标修订和退回信息。普通工单、尚未填写的目标和无来源设计读取权限的详情返回空目标。原单有新指派时，下次修改必须由新负责人提交。A02 可逐项核对当前负责人、来源版本和目标修订，并单独记录启动确认。[服务实现](../customizations/components/tianxuan/server/tianxuan_core.py) · [原生工单控件](../editor/docks/workbench/issue_actions/issue_task_target.gd)

## 构建与验收

现有构建规则将工单控件编入 `IssueActions.gen.h`，加载编辑器时挂载在工单详情下。天璇启动时为旧库增加 `design_task_targets` 表，旧工单和 D10 的拆单来源保持可读。部署配套编辑器和服务。回退可恢复上一版服务和编辑器，保留数据库中的目标和工单评论。[编辑器构建规则](../editor/SCsub)

```sh
python tests/editor/run_workbench_task_targets.py --godot <候选编辑器> --report <回执路径>
python -m pytest -q customizations/components/tianxuan/server/test_task_targets.py
```

原生探针对已签认的 v1 生成程序单和动画单，发布设计 v2 后由两个账号分别在原生窗口保存各自目标。覆盖动画缺标准退回、补齐、旧修订冲突、错误负责人与项目、服务和数据库重开后的逐单回读。独立服务测试验证缺字段重试和两次并发补写。[原生探针](../tests/editor/run_workbench_task_targets.py) · [A01 实测回执](../data-collection/gonggong-ai-workbench-plan1-a01.json)

D10 的上游 macOS 观察覆盖从原生会话重开精确文档修订，以及原生设计历史和恢复。A01 的候选平台和实测范围见本卡回执。[D03 macOS 观察](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1860#issuecomment-7067023618) · [D06 macOS 观察](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1861#issuecomment-7068555775)
