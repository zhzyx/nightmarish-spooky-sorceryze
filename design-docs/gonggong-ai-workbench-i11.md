# I11　原生检索并筛选工单

在 Godot 命令面板打开 AI 工作台，登录天璇项目，点击「检索工单」。初次打开显示当前账号在项目内可读的全部工单。可以同时指定业务模块、负责人姓名或 ID、状态和关键字，点击「查询」或在输入框按回车。结果显示工单编号、模块和标题。双击结果或选中后点击「打开工单详情」即可按项目内编号进入 I02。结果为空时点击「清除筛选」恢复全部可见工单。[工单 #1754](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1754) · [方案一 I11](gonggong-ai-workbench-plan1.md#i11) · [I02 详情](gonggong-ai-workbench-i02.md)

## 查询与权限

模块选项来自当前项目的 `GET /api/v1/business-modules`，按模块 ID 查询。工单仍使用 `GET /api/v1/issues` 和原有的 `project`、`module_id`、`status` 参数。新增可选的 `assignee` 精确匹配同租户用户 ID 或姓名，同名人员可用 ID 区分。`q` 在标题、正文和验收条件中做 Unicode 大小写折叠后的字面子串匹配。查询传入负责人或关键字时，原生控件核对服务回传的生效参数。旧服务收到未知参数可能返回完整列表，此时控件提示更新服务并清空结果。服务保留原有列表字段、按编号排序及祖先需求读权核对，已有未分配工单仍可出现在全部负责人的结果内。[列表入口](../customizations/components/tianxuan/server/api.py) · [存储查询](../customizations/components/tianxuan/server/tianxuan_core.py)

检索请求由工作台会话附带凭据与当前项目。修改筛选项即清空结果，关窗、注销或切换账号和项目会使在途响应失效。再次打开时重新载入当前项目的模块与列表。[原生控件](../editor/docks/workbench/issue_search.gd)

## 构建与验收

检索脚本与建单和详情脚本一同生成 `IssueCreation.gen.h`，编辑器侧栏挂载 `WorkbenchIssueSearch`。脚本变更需要重建编辑器。先更新天璇服务，再发布原生编辑器，使负责人和关键字参数都有对应服务支持。回退可恢复原编辑器和服务版本，数据库结构沿用 I02。[构建输入](../editor/SCsub) · [侧栏入口](../editor/docks/workbench/AIWorkbenchSidebar.cpp)

在装有天璇服务依赖的 Python 环境执行以下定向验证。探针以只读成员从命令面板进入，使用两个模块的同名工单，以及负责人、状态或正文各有一项不同的干扰行。另一个项目和私有需求的同名工单在该成员的列表之外。探针分别按编号打开两张目标工单，核对其稳定 ID，清除无结果筛选，并验证注销后迟到的结果不会再次显示。[定向实测](../data-collection/gonggong-ai-workbench-plan1-i11.json)

```sh
python tests/editor/run_workbench_issue_search.py --godot <候选编辑器> --report <本地报告路径>
python -m pytest -q customizations/components/tianxuan/server/test_module_issues.py customizations/components/tianxuan/server/test_issue_number.py customizations/components/tianxuan/server/test_issue_ancestor_acl.py
```
