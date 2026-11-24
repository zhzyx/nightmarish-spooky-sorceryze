# I15　从天璇工单详情关闭与重开

在 Godot 命令面板打开「Open AI Workbench」，登录天璇项目，按编号读取「工单详情」。当流程允许进入 `done` 时，核对界面显示的验收条件，在「工单评论」中选中记录了实际候选、观察和结果的评论。点击「确认选中评论所附的验收证据」，再点击「关闭工单」。接收者负责判断实测是否满足原条件。对于已关闭或已取消的普通工单，有写权限的操作者可从同一详情重开，操作前可查看将返回的阶段。[设计条款](gonggong-ai-workbench-plan1.md#i15) · [工单 #1756](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1756)

## 服务端验收和历史

服务以当前认证身份、项目、工单内容修订、流程版本及该工单最近一次资产提交或审批版本登记验收，引用 I05 已保存且归属本单的评论。仅发布评论时工单保持开放。存在提交过的模型或原画时，服务同时使用现有资产审批逻辑，验证每一类最新提交的人工审批及固定修订上的实际字节。之后更换内容、推进流程、重开或重新提交资产都会使原验收失效。[生命周期实现](../customizations/components/tianxuan/server/issue_lifecycle.py) · [资产审批](../customizations/components/tianxuan/server/work_management.py)

I06 属性面板继续处理负责人和普通阶段迁移，详情的关闭操作会检查允许的流程边、依赖放行及阶段的人工判断。普通工单原有的 PATCH、`issue.transition`、`flow.advance` 和 `flow.judge` 保留调用参数，已登记当期验收时可以进入 `done`。缺证据的终态迁移返回 409。因此 Web、天枢标题同步及脚本通过这些入口推进至审查后，也需要先有验收回执。未验收的托管子单或尚未取得计划回执的原生需求也会阻止父单完成。原生工作流独占其托管工单的验收；可信需求执行入口核实其映射中所有子单都有正式接收后，可以凭这些真实回执汇总父单。[共用状态迁移](../customizations/components/tianxuan/server/issue_flow.py) · [原生需求执行](../customizations/components/tianxuan/server/native_entry_factory.py)

生命周期读取和写入均从 `/api/v1/issues/{id}/lifecycle` 进入。GET 返回历史和当前可用操作。POST 到 `accept`、`close` 或 `reopen` 时检查项目、租户、角色及祖先需求 ACL。写入和操作标识回执在同一事务提交。客户端先回读再重试，相同意图沿用原标识。验收、关闭、重开分别记录实际操作者、时间、原状态与目标状态、内容修订和可用证据。已有旧关闭记录按历史事件呈现。历史事件已经过期时，服务从现行流程选择一个可以到达该终态的阶段，供操作者在重开前核对。重开沿用原工单编号、评论和内容。[服务路由](../customizations/components/tianxuan/server/work_management_api.py) · [详情控件](../editor/docks/workbench/issue_actions/issue_lifecycle.gd)

## 构建、复验与回退

沿用 I03 的内嵌脚本构建路径。SCons 从 `editor/docks/workbench/issue_actions/*.gd` 生成 `IssueActions.gen.h`，随后重新编译侧栏并链接编辑器。配套天璇服务启动时为已有数据库创建附加的生命周期表。回退时恢复上版编辑器及服务，并保留数据库与新增历史表；旧服务仍可读取原编号和状态，原版服务的完成规则同时恢复。

```sh
python -m pytest -q customizations/components/tianxuan/server/test_issue_lifecycle.py customizations/components/tianxuan/server/test_issue_flow.py
python tests/editor/run_workbench_issue_lifecycle.py --godot <候选编辑器路径> --report <报告路径>
```

Windows 探针在隔离项目运行四次真实无头编辑器，分别由关闭者、只读查看者和重开者核对同一编号。探针覆盖缺证据、缺回执、重试、历史和登录切换，退出服务后重新打开数据库核对。前置 I06 的 Mac 观察记录了只读状态写入拒绝与第二视图读取；本卡接单时没有专属 Mac 评论。[I15 验证记录](../data-collection/gonggong-ai-workbench-plan1-i15.json) · [I06 Mac 观察](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1850#issuecomment-7067781078) · [I06 主线接收](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1850#issuecomment-7069007188)
