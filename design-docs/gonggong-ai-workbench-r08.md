# R08 启动时打开本人的待判断事项

工作台验证天璇账号和当前业务项目后，向 `GET /api/v1/work/my-judgments?project=<项目>` 读取 H03 个人队列。收到非空列表时，编辑器打开工作台侧栏，将焦点移到第一项。行沿用 H03 的工单、问题和候选修订入口，用户可在查看原修订后决定或转交。列表为空或读取失败时延续已有布局，仍可从“我的待判断事项”手动读取。切换账号或工单详情时，旧请求的响应随原会话或页面代次失效。[工单 #1777](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1777) · [个人判断队列](../editor/docks/workbench/issue_actions/creative_judgments.gd)

同一次认证也会触发 R07 的遗留占用回读与项目恢复。独立工单使用其已有授权、原票据和已安装的生产者运行，个人队列可以在生产进程运行期间接收焦点。显示一项判断不会替用户签认该修订。[会话入口](../editor/docks/workbench/business_session.gd) · [恢复协议](gonggong-ai-workbench-r07.md)

## 运行与回退

在仓库根使用装有天璇测试依赖的 Python 和本候选的原生编辑器复跑。工装在系统临时目录创建独立项目、账号、域库、产物库和编辑器设置。观察器读取第一行焦点及其在滚动视口、编辑器窗口内的实际位置。生产者写入自己的 PID 后等待观察器确认队列已可见，随后退出，独立检查进程读取蓝色圆形预览并出具阶段回执。另一个同项目账号用自己的凭据启动，其个人队列为空。[原生验收](../tests/editor/run_workbench_startup_judgments.py) · [实测回执](../data-collection/gonggong-ai-workbench-plan1-r08.json)

```powershell
python -X utf8 -m pytest -q customizations/components/tianxuan/sinan-workorders/test_native_project_reopen.py customizations/components/tianxuan/server/test_work_management.py
python -X utf8 tests/editor/run_workbench_startup_judgments.py --godot bin/godot.windows.editor.x86_64.exe --report "$env:TEMP/r08-startup-result.json"
```

`editor/SCsub` 将两个界面脚本分别生成 `BusinessSession.gen.h`、`IssueActions.gen.h`，由 `AIWorkbenchSidebar.cpp` 编入编辑器。发布包含这两处内嵌脚本的原生候选即可使用已有 H03、R07 服务。需要回退时恢复上一已验编辑器，原服务保留持久任务和判断记录。前置验收与后续冻结均沿原工单交接。[H03 #1835](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1835) · [R07 #1803](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1803) · [F01 #1743](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1743)
