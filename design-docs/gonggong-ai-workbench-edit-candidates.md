# 脚本候选合并与动画区间回放

在「继续当前工作」中发送脚本选区。模型答复可提供选区的对象 ID、修订、原文和替换文本。工作台在当前脚本窗口展示差异。点击「接受并保存」时，工作台再次核对会话、文件、磁盘摘要、编辑缓冲区与选区，再调用原生脚本保存。其余位置的人工修改保留。选区移动或出现重叠编辑时可在新修订上重新发起接续。[E12 验收](../data-collection/gonggong-ai-workbench-plan1-e12.json)

脚本接续验收用两个独立的 Mac 工程打开相同脚本。对人工保存的函数签名应用调用点建议后，重开并执行新版本；若用户又改写并保存同一行，旧建议的确认按钮禁用，重开后执行人工版本。分别运行 `tests/editor/run_workbench_edit_candidates.py --godot <编辑器路径> script` 和 `script-conflict` 模式，回执包含各次文件摘要、关联的选区修订与 GDScript 检查结果。[Q15 验收](../data-collection/gonggong-ai-workbench-plan1-q15.json)

在动画时间线选中落地键，打开 Animation Tools 的 **Halve Approach Before Selected Keys** 并为候选命名。最早选中的键固定所有轨道的边界。候选把位于零秒与边界之间的键时间减半，保留边界及之后的时间、键值和过渡。原片段和候选均可保存并重开。[E11 验收](../data-collection/gonggong-ai-workbench-plan1-e11.json)

选中候选后使用 **Replay Source and Candidate Approach**，在原生时间线依次观看两份修订。面板标明当前片段、内容摘要与区间；两次播放都短暂停留在终点。时间线随后恢复到进入回放前的候选与光标。也可以在另一原片段中选两个键，使用 **Mark Selected Keys as Replay Source** 固定区间，再选择候选回放；只选一个结束键时从零秒开始。在回放期间再次点回放命令或停止按钮会恢复编辑位置。[V06 验收](../data-collection/gonggong-ai-workbench-plan1-v06.json)
