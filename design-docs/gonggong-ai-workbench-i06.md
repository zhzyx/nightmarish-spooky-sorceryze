# I06　维护工单负责人和状态

从 Godot 命令面板打开「Open AI Workbench」，登录天璇项目，按编号读取工单，再打开「维护负责人和状态」。选择本租户成员并点击「更新负责人」，或选择「未分配」清除分工。状态下拉框从该工单当前流程读取迁移目标，点击「迁移状态」后重新读取详情。两项操作分别保存。[方案一 I06](gonggong-ai-workbench-plan1.md#i06) · [工单 #1850](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1850)

## 服务与原生入口

负责人由 I02 的 `issue_assignees` 关系保存。`PUT /api/v1/issues/{id}/assignee?project=...` 接收 `assignee_id` 和 `expected_assignee_id`。两者都可为 `null`。写事务校验操作者的编辑角色、工单及祖先需求的写权限、项目归属和目标成员的租户。当前负责人已是目标值时返回当前详情；其他人已改派到不同值时返回 409。实际变更记录 `issue.assigned` 事件。负责人不参与内容修订摘要。[服务入口](../customizations/components/tianxuan/server/api.py) · [工单领域实现](../customizations/components/tianxuan/server/tianxuan_core.py)

原生控件通过当前业务会话读取成员目录和工单的 `work/flow`。状态提交使用 `work/flow/advance`、读取到的流程版本及操作标识，继续执行现有的依赖、流程归属及迁移校验。人工判断阶段提示等待人工判断，终态显示没有可用迁移。只读账号能查看工单。具有编辑角色、而仅获祖先需求读权限的成员尝试保存时会收到权限提示。编号、详情或账号变更会清空属性控件并忽略迟到响应。[流程接口](../customizations/components/tianxuan/server/work_management_api.py) · [属性控件](../editor/docks/workbench/issue_actions/issue_assignment.gd)

## 构建与回退

I06 使用 I03 共享的工单详情扩展。SCons 将 `issue_actions/issue_assignment.gd` 编入 `IssueActions.gen.h`，由 `AIWorkbenchSidebar.cpp` 编译并挂载到 `WorkbenchIssueDetail`。交付编辑器时配套部署新增写入路由的天璇服务。回退可换回原编辑器与服务；原 I02 服务仍能按编号查看已保存的负责人和工单状态。数据库沿用 I02 的关系表。[构建输入](../editor/SCsub) · [侧栏接收入口](../editor/docks/workbench/AIWorkbenchSidebar.cpp)

## 验收与复验

```sh
python -m pytest -q customizations/components/tianxuan/server/test_issue_assignee.py customizations/components/tianxuan/server/test_issue_number.py customizations/components/tianxuan/server/test_issue_flow.py customizations/components/tianxuan/server/test_issue_ancestor_acl.py
python tests/editor/run_workbench_issue_assignment.py --godot <候选编辑器路径> --report <本机报告路径>
```

原生探针在三个独立编辑器进程中打开真实工作台。管理员从未分配的 backlog 工单设置负责人并迁移到 planned。具有只读文档 ACL 的编辑者尝试取消分配和继续迁移，分别核对 HTTP 拒绝、原生提示和随后的详情；只读角色再从独立视图核对四个详情字段。服务退出后重开数据库逐项复核。服务测试另覆盖跨租户选择、错误项目、重新改派、清除、重复请求及冲突。[验证记录](../data-collection/gonggong-ai-workbench-plan1-i06.json)

I06 接单时没有 Mac 评论。I02 的接收回执已确认其 Windows 原生详情与独立连接一致，上游 D14 的 Mac 观察覆盖账号隔离、凭据失效和重新登录。[I02 主线接收](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1854#issuecomment-7066884069) · [D14 Mac 双账号观察](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1867#issuecomment-7060361368)
