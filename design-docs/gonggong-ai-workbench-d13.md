# D13 在原生视图追踪偃师设计阶段

在 AI 工作台选择业务模块和咨询会话，点击「偃师设计阶段」。窗口默认选中第一个尚待确认的阶段，列出方向、策划、详设各自的当前修订和状态。选中阶段后可切换历史修订，核对原文、作者和最近一次保存、退回或确认的记录。详设同时展示标题和验收条件。旧草稿没有作者字段时显示「未记录作者」。[原工单 #1749](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1749)

对当前待确认修订，按钮标明阶段和修订号。退回需要填写意见，服务在该修订上记录意见、账号和时间。修订者保存新版后可再次提交确认，旧版仍可回读。确认沿用天璇的会话版本校验、当前阶段修订校验及前置阶段确认规则。每次决策后窗口读回服务记录，并发修改或响应丢失时可刷新核对。确认一个阶段后，下个阶段等待其单独的草稿和确认。[原生阶段控件](../editor/docks/workbench/design_progress.gd) · [天璇会话与阶段决策](../customizations/components/tianxuan/server/workspace_conversations.py)

在「设计文档」选中具体修订后，点击「查看偃师设计阶段」。窗口并列显示该版 D09 签认和发布需求时记录的三项阶段修订。查询按账号、租户、文档 ID 和版本定位到私有来源会话。新文档修订需取得自己的关联与签认，历史修订可从「版本历史 → 阅读原修订」重新打开。普通设计文档和无权读取来源会话的账号显示缺少关联。[D09 修订签认](gonggong-ai-workbench-d09.md)

## 构建和复验

已接入的编辑器脚本生成器将阶段控件编入 `BusinessSession.gen.h`。侧栏通过已有天璇账号访问会话；服务读取 `workspace_requirement_approvals`，退回意见持久化于原会话的修订对象。无需新增数据表。回退前保留数据库，编辑器和服务可作为一组退回到前一已验候选。[构建输入](../editor/SCsub) · [侧栏入口](../editor/docks/workbench/AIWorkbenchSidebar.cpp)

定向探针在临时项目运行 headless 编辑器和回环天璇服务，覆盖并发换版、退回意见、历史阅读、逐阶段确认和已发布文档版本之间的隔离。D09 引用的既有 Mac 观察覆盖上游会话追溯与版本历史。本卡候选的 Windows 实测见回执。[定向验证](../tests/editor/run_workbench_design_progress.py) · [候选和测试结果](../data-collection/gonggong-ai-workbench-plan1-d13.json)

```sh
python tests/editor/run_workbench_design_progress.py --godot <候选编辑器> --report <回执路径>
```
