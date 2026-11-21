# U15　本轮引用与逐项移除

在 Godot 编辑器的 AI 工作台中，上下文位于输入框上方。工单来自当前会话的编号与需求 ID，已登记的 Issue URL 优先。页面引用使用其注册模块标识；没有模块关联的普通脚本选区显示当前项目的名称。[工单 #1810](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1810) · [设计卡 U15](gonggong-ai-workbench-plan1.md#u15)

在一份脚本中选中文字，通过命令面板打开工作台。关闭侧栏，切换到另一份脚本，选中文字后再打开工作台。列表区分两份脚本的项目相对路径和行列范围，显示捕获时编辑缓冲区的完整 SHA-256 和将要发送的选段。点击一条「移除」即可删除该选段；输入文字和会话工单继续保留。顶部按钮可一次清空引用。发送时，队列与历史使用此次保留的 C05 引用，模型收到同一定位、修订及脱敏后的选段。普通绑定与咨询模式沿用当前会话的设置。

脚本选段在捕获、凭据变更后的预览、保存及发送前沿用编辑器的凭据遮蔽。测试用两个本机占位值依次配置隔离编辑器，核对已保存草稿、备份、保留行、恢复草稿和已暂停队列，再由本机 HTTP 接收器逐条比对实际发送内容。运行时修订继续对应原始缓冲区。

场景与检查器、文件系统、其他编辑器页面沿用原有来源入口。场景的运行时节点、临时资源实例和页面身份需要在原进程中核实，重开后保留失效项供移除。已捕获的脚本片段随草稿保存。单次发送重新核对有效引用；已观察到失效的项须移除或重新选择。脚本行列从 1 开始，SHA-256 对应捕获时的完整缓冲区。[引用处理](../editor/docks/workbench/AIWorkbenchReference.cpp) · [原生探针](../tests/editor/workbench_reference_removal.gd)

从仓库根目录复验以下命令。使用同一候选编辑器，将报告写入已有的本机目录。隔离探针需要使用系统临时目录，运行测试的进程应清除继承的工作区变量。

```powershell
Remove-Item Env:GONGGONG_WORKSPACE -ErrorAction SilentlyContinue
py -X utf8 tests/editor/run_workbench_reference_removal.py --godot $editor --report "$out/u15.json"
py -X utf8 tests/editor/run_tianshu_spatial.py --godot $editor --scene-selection --report "$out/u07.json"
py -X utf8 tests/editor/run_tianshu_spatial.py --godot $editor --references --report "$out/c08.json"
py -X utf8 tests/editor/run_workbench_resource_selection.py --godot $editor --report "$out/u09.json"
py -X utf8 tests/editor/run_workbench_page_reference.py --godot $editor --report "$out/u12.json"
```

[组合候选与实收回执](../data-collection/gonggong-ai-workbench-plan1-u15.json)
