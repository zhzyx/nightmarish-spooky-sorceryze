# I02　读取工单原生详情

在 Godot 命令面板打开「Open AI Workbench」，用「天璇账号」登录项目，点击「工单详情」。输入天璇工单编号，按回车或点击「读取详情」。界面显示标题、负责人、当前状态和完整的内容修订摘要。未分配的工单显示「未分配」。再次读取同一编号可刷新数据。[工单 #1854](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1854) · [方案一 I02](gonggong-ai-workbench-plan1.md#i02)

## 天璇回读

`GET /api/v1/issues/by-number/{number}/detail?project=...` 在同一 SQLite 读事务中按租户、项目和编号定位工单，核对工单及祖先需求的访问权，读取负责人和内容快照。响应包含编号接口原有字段，以及 `assignee` 和 `revision`。后者沿用 `issue_snapshot` 的 SHA-256，覆盖工单定义及关联需求内容。更新业务状态或分配负责人时保持同一内容版本。[服务实现](../customizations/components/tianxuan/server/tianxuan_core.py) · [HTTP 入口](../customizations/components/tianxuan/server/api.py)

`issue_assignees` 每张工单最多一名负责人。服务返回同租户用户的 `id` 和 `name`，没有分配记录则返回 `null`。旧库启动时创建空关系表，保留原工单和创建者。详情控件优先显示负责人姓名，姓名为空时显示用户 ID。负责人和状态的编辑入口属于 [I06 #1850](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1850)。

## 原生接收与构建

`WorkbenchIssueDetail` 隶属工作台业务会话，支持 `open_issue(number)`、`get_detail()` 和 `detail_changed`。查询新编号时立即清除旧工单。服务返回 403 时提示没有权限，404 时提示当前项目中不存在该编号。退出、切换身份或收起表单后丢弃已显示数据和迟到的请求。下游只在成功回读后取得当前详情的深拷贝。[原生控件](../editor/docks/workbench/issue_detail.gd)

`editor/SCsub` 将详情脚本与 I01 脚本嵌入 `IssueCreation.gen.h`，由侧栏编译单元挂载；更改脚本后需重新构建编辑器。部署需同时提供带详情入口的天璇服务与编辑器。可回退到原编辑器与服务版本，原服务仍可按原编号接口读取工单，新建的负责人表可保留。[构建输入](../editor/SCsub) · [控件挂载](../editor/docks/workbench/AIWorkbenchSidebar.cpp)

## 定向验证

```sh
python tests/editor/run_workbench_issue_detail.py --godot <候选编辑器> --report <本地报告路径>
python -m pytest -q customizations/components/tianxuan/server/test_issue_number.py customizations/components/tianxuan/server/test_module_issues.py customizations/components/tianxuan/server/test_issue_ancestor_acl.py
```

原生探针由命令面板进入详情，在隔离项目中以只读成员访问真实天璇 HTTP 服务。探针核对已分配和未分配的显示值，验证私有及缺失工单的反馈，重新打开工单后退出账号，再用新数据库连接核对工单、负责人和内容快照。服务测试覆盖旧工单、内容修订变化、状态变更、项目及权限隔离。[验证记录](../data-collection/gonggong-ai-workbench-plan1-i02.json)

I01 已由主线接收。D14 的两条 Mac 观察覆盖临时账号、凭据撤销及会话隔离。本卡 Windows 详情控件的接收记录单独列在定向验证中。[I01 接收](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1859#issuecomment-7065373317) · [D14 Mac 账号观察](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1867#issuecomment-7060361368) · [D14 Mac 会话复核](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1867#issuecomment-7062658872)

在接收 D04 和 C07 的主线修订 `373430fb` 上构建整合候选，同一个 Windows 编辑器通过 I02 详情、I01 建单重试和 C07 资产归属三项原生探针。[接收 C07 的主线 PR](https://github.com/zhzyx/nightmarish-spooky-sorceryze/pull/1958) · [候选及定向验证](../data-collection/gonggong-ai-workbench-plan1-i02.json)
