# 工单绑定与原聊天历史的中断恢复检查点

<!-- gonggong-request:issue-binding-history-checkpoint-20261114 -->

父 #830、总目标 #978；关联现有恢复 #951/#773，但不接管其原生产工作、安装或发布候选。当前用户已明确将 #830 交付移交本会话，并授权持续修复 AI 接入范围缺陷。本单由当前 root 在自己的4eacf基线候选隔离修复。

当前原生60f2d842候选运行原 run_parent_binding_restart.py/parent_binding_restart.gd，原断言未改、模型及GitHub均受控：绑定已在崩溃前落盘，冷启动保留相同Issue/request，但原conversation不在聊天history agents中，cold_exit_code=1。侧栏原63项路由/交互及模型关联重启已通过；此失败不能被历史Windows成功替代，也尚不等于已直接复现侧栏同一崩溃现场。独立审查确认共享持久层相关。_issue_guide_bind当前同步保存metadata，历史由异步timer写入；先保留现场验证时序，不预设唯一根因。

范围与验收：复用既有历史写入/恢复机制，在可持久查找原conversation和必要历史之前不发布可恢复工单绑定；并发旧快照不能覆盖新记录，普通输入的异步保存契约保留。真实存储失败有明确可重试反馈，保留原输入、已创建Issue身份和旧记录，不重复建单、不自动确认/推进，不授予额外工具权限。修复后原未放宽的强制终止/冷启动测试通过，并有写入失败、恢复重试和相关旧手动/状态引导拒绝路径的必要回归；macOS原生及适用精确CI、独立复核、main回读完成。原#830验收与#951/#773生产范围分别保留。

写入对象限定当前候选的AI Chat绑定/历史相关实现和对应定向回归；不修改冻结框架、有效安装、用户配置或他人工作树。测试使用隔离HOME和受控传输，不调用真实供应商。路径以仓库根为基准；私有失败证据在原主工作区 data-collection/receipts/ai-integration-refactor-20261112/issue830-delivery-native。

当前本地实现/复核：6069候选完成绑定前历史检查点，原始未放宽强杀/冷启测试、原输入增强断言、真实写入失败及仅本地重试均通过，三处绑定共用既有writer。独立复核无新增问题，当前1075恢复缺陷已解除但尚未交付。完整status发送另发现主线既有shell JSON参数故障，由#1077承接；不以本单通过代替830整体交付。详见 data-collection/ai-chat-binding-history-checkpoint-1075.json。
