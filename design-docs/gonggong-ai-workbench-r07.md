# R07 重开后接续已授权任务

工作台验证账号和当前业务工程后，先回读本机遗留占用，再在同一已验证会话中向天璇发送一次 `POST /api/v1/native/workflow/recover-project?project=<工程>`。服务分页读取 R05 持久清单，只选择本账号在该工程授权的活动票据。每一步重新核对会话、当前签认、依赖和执行状态。界面无需保存工作者游标或再次签认目标。[工单 #1803](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1803) · [恢复清单](gonggong-ai-workbench-r05.md)

| 已确认的边界 | 接续动作 |
| --- | --- |
| 已授权，等待预约 | 按原票据的固定模型和来源修订预约，沿用原生容量、写入冲突、先进先出和依赖核对。 |
| 已预约 | 对原执行号启动已预约工作，核收该执行号的终态。 |
| 已产出 | 有签认阶段时，在原候选上执行绑定的阶段检查。普通交付沿原安装目标核收，贡献的后续整合由原入口接收。 |
| 已到达阶段、已验收、已暂停或取消、授权失效、结果未知 | 保留检查点以及原有的判断或对账入口。 |

达到签认阶段后保留阶段回执、候选和确认修订。检查失败保留 `stage-unmet`。同一次重开中有其他票据释放容量时，再处理此前等待预约的票据。服务返回本次接续、停留、等待和错误计数；具体状态沿原票据读取。[恢复调度](../customizations/components/tianxuan/server/native_checkpoint.py) · [阶段检查](gonggong-ai-workbench-a04.md)

Windows 接收测试在系统临时目录内启动隔离的 headless 编辑器、认证 HTTP 服务、文件生产者和独立阶段检查进程。第一个编辑器签认预览，服务记录蓝色圆形产物后关闭 SQLite 连接。新服务打开原域库；编辑器两次重开相同工程，测试探针只观察原生会话和服务回执。两次重开后累计一个生产进程和一个成功的阶段检查，候选摘要、授权和预览字节一致。未签认的同级工单保留待确认。独立服务用例另验从等待预约、已预约和已产出开始恢复、阶段未达到、普通发布，以及暂停、取消、撤签和项目账号隔离。[实测回执](../data-collection/gonggong-ai-workbench-plan1-r07.json) · [编辑器复跑入口](../tests/editor/run_workbench_project_reopen.py)

在仓库根用安装天璇测试依赖的 Python 复跑。编辑器路径指向含本次内嵌工作台脚本的 Godot 候选，报告路径选在系统临时目录。

```powershell
python -m pytest -q customizations/components/tianxuan/sinan-workorders/test_native_project_reopen.py
python tests/editor/run_workbench_project_reopen.py --godot bin/godot.windows.editor.x86_64.exe --report "$env:TEMP/r07-editor-result.json"
```

部署时配套更新天璇服务与编辑器。工作台会话脚本参与生成 `BusinessSession.gen.h`，本次在原生构建后验证。域库沿用原检查点格式；回退可恢复之前的编辑器和服务并保留原工单、候选和回执。
