# I01　通过天璇创建工单

在 Godot 命令面板打开「Open AI Workbench」，用「天璇账号」登录目标项目。打开「新建天璇工单」，输入标题，从服务返回的业务模块中选择目标，点击「创建工单」。天璇写入后，工作台按权威编号重新查询，在控件中显示编号、模块和标题。另建同名工单时点击「另建工单」。[工单 #1859](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1859) · [设计条款 I01](gonggong-ai-workbench-plan1.md#i01)

## 请求、重试与回读

原生控件 `WorkbenchIssueCreation` 挂在 D14 的 `WorkbenchBusinessSession` 下。模块来自当前项目的 `GET /api/v1/business-modules`。创建适配器 `create_issue(request_id, title, module_id)` 将当前会话的项目和模块发给 `POST /api/v1/tools` 的 `issue.create`，以 `request_id` 作为显式 `call_id`。自动化消费者应沿用同一逻辑请求的稳定标识。天璇在同一写事务中分配编号、写工单与记录回执，并按租户、操作者、工具和调用标识重放。相同标识更改内容会返回 409。[C02 模块关系](gonggong-ai-workbench-c02.md) · [天璇领域实现](../customizations/components/tianxuan/server/tianxuan_core.py)

原生表单为本次建单生成随机请求标识。收到未知回执时，表单保留原始标题、模块和标识，点击「重试同一请求」可以取回同一工单。收起面板保留草稿，退出账号、切换项目或关闭编辑器会释放此会话内的草稿。工作台在身份切换时丢弃上次请求的迟到回执。[会话契约 D14](gonggong-ai-workbench-d14.md) · [原生建单适配器](../editor/docks/workbench/issue_creation.gd)

`read_issue(number)` 调用 `GET /api/v1/issues/by-number/{number}?project=...`。天璇在同一读事务中按当前租户、编号和项目定位，沿用现有工单及祖先需求的可见性检查。返回的 `id`、`number`、`module_id` 和 `project` 可供下游定位原件。创建回执与按编号回读的工单 ID 一致时，原生表单才显示完成结果。[HTTP 入口](../customizations/components/tianxuan/server/api.py)

## 构建与验证

I01 扩展既有工作台与天璇服务。编辑器构建将 `issue_creation.gd` 生成到 `IssueCreation.gen.h`，侧栏编译单元据此创建原生控件。部署需要配套的编辑器和含编号读取接口的服务。回退可使用上一版本的编辑器及天璇服务，已创建的工单、编号和回执均沿用既有表结构。[编辑器构建输入](../editor/SCsub)

```sh
python tests/editor/run_workbench_issue_creation.py --godot <候选编辑器> --report <本地报告路径>
python -m pytest -q customizations/components/tianxuan/server/test_issue_number.py customizations/components/tianxuan/server/test_module_issues.py customizations/components/tianxuan/server/test_business_modules.py
```

定向探针从命令面板打开工作台，使用隔离账号与真实天璇 HTTP 服务，改写首次已提交请求的响应为 503，在同一表单点击重试，回读编号并重开数据库核对行数与幂等回执。Mac 上已有观察涉及前置账号会话，I01 的原生建单验收对应本卡 Windows 候选。[D14 的 Mac 会话记录](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1867#issuecomment-7060361368) · [I01 定向验证与候选摘要](../data-collection/gonggong-ai-workbench-plan1-i01.json)

合入 C06、D02、G10 与 U06 后，同一 Windows 候选分别复跑建单、模块切换、账号会话、文档读取、分支操作和辅助窗口。[整合候选与六项原生复验](../data-collection/gonggong-ai-workbench-i01-integration.json)
