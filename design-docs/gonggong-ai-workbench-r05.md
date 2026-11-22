# R05 重开后的任务恢复清单

认证客户端通过 `POST /api/v1/native/workflow/recovery` 传入工程 `project`，读取本账号在该工程授权且当前可见的活动契约。相同租户中的其他工程或其他授权人拥有的任务各自隔离。未能确定原工程的历史记录不自动归属。每页最多包含 100 个可见检查点，客户端可传入上一页的 `next_cursor` 作为 `after` 续读。

每项携带完整 R01 检查点和分类。已验收的交付归入 `completed`，已到达授权阶段、需要确认后续目标的任务归入 `awaiting-confirmation`。可执行的准备、预约或已产出任务归入 `resumable`。当前执行授权失效、失败、运行结果未知或需对账的任务归入 `needs-attention`，并附原因。读取清单只分类，应用已授权后续操作的工作由相应执行入口承担。

用同一工程中的真实生产、验收、阶段签认和物理进程失败记录关闭域库，随后用新进程回读。持有同租户编辑权限且能看见原工单的第二个账号读取清单为空。原账号对另一真实工程的查询只读到该工程自己的任务。另行撤回执行权后，仍可读的 ready 记录归入待处理。[定向验收回执](../data-collection/gonggong-ai-workbench-plan1-r05.json) · [签发格式修正后的精确候选复验](../data-collection/gonggong-ai-workbench-plan1-r05-format-recheck.json) · [原工单](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1821)
