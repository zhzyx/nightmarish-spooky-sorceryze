# I10　登记预计和实际工时

打开工作台的「工单详情」，读取天璇工单，再展开「工时」。输入非负整数分钟数并点击「保存预计工时」可调整预计值。每次实际工作填入正整数分钟数，可选填工作内容，点击「登记本次工时」。界面显示预计分钟数、累计实际分钟数和按登记顺序排列的记录。[工单 #1753](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1753) · [方案一 I10](gonggong-ai-workbench-plan1.md#i10)

## 数据与重试

控件从详情取天璇工单 ID，经业务会话发起当前身份的工时读取。界面使用工作快照中的 `plan.estimated_minutes`、`logged_minutes` 和 `logs`。保存预计值时仅发送 `plan.estimated_minutes`；天璇按字段合并，保留迭代、里程碑和自定义字段。实际登记发送 `minutes` 和 `note`。[工作记录服务](../customizations/components/tianxuan/server/work_management.py)

两类写入都使用最近读取的工作版本和本次操作的随机请求编号。提交期间锁定控件。回执未知时保留请求编号、参数和版本，允许重试同一请求。版本冲突时重新读取工作快照，待使用者核对后再次提交。切换工单、收起详情或退出账号会清除控件状态，迟到的回执按详情代次丢弃。重开详情会从天璇读取已提交的条目。[详情控件](../editor/docks/workbench/issue_detail.gd) · [工时控件](../editor/docks/workbench/issue_time.gd)

## 构建与验收

`editor/SCsub` 将工时脚本嵌入 `IssueCreation.gen.h`，侧栏在已挂载的 I02 详情下创建 `WorkbenchIssueTime`。脚本更新随编辑器重新编译、链接。部署或回退时切换编辑器二进制；服务沿用已有的工时表、事件和接口。[构建输入](../editor/SCsub) · [原生挂载](../editor/docks/workbench/AIWorkbenchSidebar.cpp)

```powershell
python tests/editor/run_workbench_issue_time.py --godot bin/godot.windows.editor.x86_64.exe --report <本地报告路径>
python -m pytest -q customizations/components/tianxuan/server/test_work_management.py
```

定向探针从命令面板进入实际详情，在隔离项目和真实天璇 HTTP 服务上点击保存预计、连续登记两次工时。服务在第二次登记写入成功后模拟回执丢失。探针点击重试，再关闭并重开详情，比较界面与重新打开的 SQLite 数据库，核验旧计划字段、工时累计、记录顺序及重试请求内容。[目标接收记录](../data-collection/gonggong-ai-workbench-plan1-i10.json)
