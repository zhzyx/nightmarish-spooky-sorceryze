# I09　维护工单自定义字段与阶段

从 Godot 命令面板打开 **Open AI Workbench**，在「工单详情」按编号读取当前项目的工单，再打开「字段与阶段」。选择项目定义的文本字段，修改后点「保存字段」。阶段列表显示当前阶段和流程允许的下一阶段，点「保存阶段」后详情重新读取状态和修订。只读账号可查看字段和阶段。人工裁定阶段使用天璇既有的人工裁定入口。[方案一 I09](gonggong-ai-workbench-plan1.md#i09) · [工单 #1752](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1752) · [前置 I02 #1854](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1854)

## 项目定义与兼容

原有天璇工作接口通过 JSON 对象保存自定义字段。B02 盘点记录了缺少项目字段定义的情况。本次补入文本字段定义。编辑成员通过 `PUT /api/v1/work/field-definitions/{key}?project=...` 提交 `{"label":"地图"}`。服务以账号的租户、项目、稳定字段键作为联合主键，重复设置同一字段只更新显示名。原生界面通过 `GET /api/v1/work/field-definitions?project=...` 枚举当前项目。[B02 接口盘点](gonggong-ai-workbench-b02.md)

详情使用 I02 已授权读取的工单 ID，分别通过 `GET /api/v1/issues/{id}/work` 和 `.../work/flow` 读取计划和流程版本。保存字段时，`POST .../work/plan` 发送字段键、文本值、预计版本及该次写入的调用 ID。天璇在同一写事务中检查工单权限、所属项目的字段定义与计划版本，将单一修改合入原有字段对象。已有整组计划写入调用仍按原协议处理。服务端保留未知字段及其原始类型，包括超出编辑器 JSON 精度的整数。里程碑、预计时间及其他计划键只在其各自被提交时更新。

阶段沿用工单流程的状态、边和 `POST .../work/flow/advance`。服务检查版本、依赖及流程所有权。字段和阶段各有独立保存按钮和回执。版本冲突或回执无法核实时，界面提示重新打开读取。切换账号、项目、工单编号或关闭详情会清空控件并作废旧请求。

## 原生构建与验证

`editor/SCsub` 将 `issue_custom_fields.gd` 与 I02 详情脚本生成同一个 `IssueCreation.gen.h`，由 `AIWorkbenchSidebar.cpp` 在实际详情节点下挂载。服务和数据库沿用天璇部署。回退编辑器时使用上一已验证的编辑器构建，新增数据表对旧服务兼容。修改嵌入脚本需要重新生成头文件、编译侧栏并链接候选编辑器。

```powershell
python -m pytest -q customizations/components/tianxuan/server/test_work_management.py customizations/components/tianxuan/server/test_issue_flow.py
python tests/editor/run_workbench_issue_custom_fields.py --godot bin/godot.windows.editor.x86_64.exe --report <本地回执路径>
```

原生探针在隔离编辑器中通过命令面板操作两个项目。每个项目有独立的文本字段和工单阶段。探针切换项目并检查旧控件已清空，保存后用新数据库连接逐项比较原计划、未知布尔值、大整数、文本和阶段。交付后的组合验收沿 F01 和 Q13 继续推进。[定向验收记录](../data-collection/gonggong-ai-workbench-plan1-i09.json) · [F01 #1743](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1743) · [Q13 #1723](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1723)
