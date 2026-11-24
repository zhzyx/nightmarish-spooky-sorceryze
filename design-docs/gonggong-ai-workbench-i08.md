# I08 展示模块路线图

在 Godot 的 AI 工作台登录天璇，打开「模块路线图」，展开业务模块与里程碑，再展开工单查看子单。选中任一工单后按「打开工单详情」，或双击该工单，即可在 I02 详情中读取原单编号、标题及当前状态，在 I07 计划区核对归属。[I08 工单](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1751) · [I08 设计条款](gonggong-ai-workbench-plan1.md#i08)

## 数据与权限

工作台调用既有 `GET /api/v1/work/roadmap?project=…`，项目取自当前业务会话。服务在同一数据库读事务中取项目模块、该成员可见的工单和已有计划事件。每行带业务模块 ID、稳定编号及同一结果集中可见的父单 ID。原有无项目参数的路线图与模型工具仍返回旧格式。新控件核对项目回显；遇到不支持项目过滤的服务会显示读取失败。关闭路线图或切换身份会清空数据并废弃在途响应。[路线图投影](../customizations/components/tianxuan/server/work_management.py) · [HTTP 入口](../customizations/components/tianxuan/server/work_management_api.py)

各工单按自身业务模块和里程碑归组。子单与父单归属不同时，在子单分组内显示带「上级」的上下文节点，仍可打开相应原单。里程碑旁的「项目共 … 单」采用 I07 的同项目、同里程碑、当前账号可见工单口径，跨组显示的父链不会重复计数。未设置里程碑的工单单独成组。只读成员使用同一路线图与详情入口。[原生控件](../editor/docks/workbench/issue_roadmap.gd)

## 构建与回退

`editor/SCsub` 将路线图 GDScript 嵌入 `IssueCreation.gen.h`，由工作台侧栏挂载。修改脚本后重新生成头文件并编译链接编辑器。部署顺序为天璇服务、原生编辑器，回退可恢复先前编辑器和服务。该功能只读既有计划与父单关系，无数据迁移。[构建输入](../editor/SCsub) · [工作台挂载](../editor/docks/workbench/AIWorkbenchSidebar.cpp)

## 验收与交接

I07 已完成。I08 探针用 viewer 身份在候选编辑器中展开三层工单，分别从同标题行和跨组父链定位 I02 原单，逐项核对稳定 ID、编号、里程碑和 I07 统计。样例同时包含其他项目和私有需求下的工单。关闭后重新打开同一数据库、服务和编辑器，重复全程并比较结果。[I07 原单](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1789) · [候选与接收回执](../data-collection/gonggong-ai-workbench-plan1-i08.json)

```sh
python tests/editor/run_workbench_issue_roadmap.py --godot <候选编辑器> --report <报告路径>
python -m pytest -q customizations/components/tianxuan/server/test_work_management.py customizations/components/tianxuan/server/test_issue_flow.py
```

F01 冻结两平台原生组合候选，Q13 核验工单和设计协作最终组合。各自在其他前置满足后领取。[F01](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1743) · [Q13](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1723)
