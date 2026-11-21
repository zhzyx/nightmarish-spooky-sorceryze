# I07　维护迭代与里程碑

在 Godot 工作台的「工单详情」读取编号后，编辑「迭代」或「里程碑」，点击「保存迭代与里程碑」。两行统计显示当前项目中自己可见、与已保存工单同属该迭代或该里程碑的工单数。清空输入框可移回未设置组。只读成员可以查看计划和数量。[I07 工单](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1789) · [设计条款](gonggong-ai-workbench-plan1.md#i07)

## 数据与并发

详情按 I02 回读的工单 ID 请求 `GET /api/v1/issues/{id}/work/plan?project=...`。服务核对访问权限与项目，在同一 SQLite 读事务内读取工作版本和两个计划字段，并按现有路线图投影统计。未设置用空串表示，与旧工单的默认计划兼容。[服务投影](../customizations/components/tianxuan/server/work_management.py) · [HTTP 入口](../customizations/components/tianxuan/server/work_management_api.py)

保存沿用 `work.plan` 的 HTTP 写入入口，只提交用户实际改动的字段以及当前工作版本和请求 ID。服务拒绝旧版本，控件重新读取归属供用户确认。保存回执未知时也先回读。读取新编号、关闭详情或退出账号时，控件通过 I02 的 `detail_changed` 清空状态并丢弃过期响应。[计划控件](../editor/docks/workbench/issue_milestone.gd)

## 构建与回退

`editor/SCsub` 将新增脚本嵌入 `IssueCreation.gen.h`，侧栏在 I02 详情节点下挂载 `WorkbenchIssueMilestone`。修改原生输入后需重新构建编辑器。部署时先更新天璇服务，再更新编辑器。可回退到先前的编辑器与服务；已写入的计划事件使用既有字段和事件格式，原服务仍能读取。[构建输入](../editor/SCsub) · [原生挂载](../editor/docks/workbench/AIWorkbenchSidebar.cpp)

## 验收与交接

静默探针从命令面板打开工作台，按编号读取四张可见工单，将其中一张从「第一轮／预览」移到「第二轮／发布」，并逐单回读。夹具还包括另一项目的同名组和一张私有工单。另开数据库连接比对移动前后的路线图、工作记录、非目标计划字段及其余五张工单。服务测试另验单字段修改、清空归属及旧版本冲突。

```sh
python tests/editor/run_workbench_issue_milestone.py --godot <候选编辑器> --report <报告路径>
python -m pytest -q customizations/components/tianxuan/server/test_work_management.py customizations/components/tianxuan/server/test_issue_flow.py
```

前置 I02 已由主线接收；I08 可从现有路线图读取保存后的计划字段。I07 的候选身份、原生接收和定向验证见实测记录。[I02 接收](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1854#issuecomment-7066884069) · [I07 实测](../data-collection/gonggong-ai-workbench-plan1-i07.json) · [I08 后继工单](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1751)
