# 门禁与交付故障修复

稳定需求 ID：gate-reliability-20261105。路径以本工作树仓库根解析。

用户在排查后授权“全量推进修改”。本次在当前 main 的隔离工作树修复同一提交链：本地提前验证 CI 的变更证据关联；提供可验证 Python 入口；准确区分未暂存、Git 权限、网络、验证超时及发布阶段；保留旧工作区与在途修改。此链需要整体集成验收，使用单 Issue，不修改 Agent/skill、冻结框架、历史原件或放宽门禁。

目标 Windows/PowerShell/Python，CI 关联契约同时用 Node 验证。验收包括：缺证据和错误 Issue 在本地拒绝；同 PR 范围的已提交与暂存证据均正确处理；诊断无凭据泄露；无效 WindowsApps 别名不被采用；脏工作树不能误报批准失败；已有正式校验保持有效。局部回归、正式门禁、提交后数据核验、远端精确候选 CI/main 回读完成后关闭。本任务不编译 Godot，不自动修改其他工作树或托管权限；权限失败使用宿主许可通道恢复，发布回读失败先核对远端，不重复发布。

基线 c76f8988；原始故障证据为 PR #104/#105 的 issue-association 失败、根工作区未暂存 diff 拒绝、WindowsApps Python 无法执行及受限网络回读失败。既有批量优化已经在基线内复用，不重复修改冻结框架。

真实工单：[Issue #106](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/106)，intake-only 已回读通过。交付为源码与 PowerShell 入口，不涉及编辑器安装或模型服务。66 项工单/交付回归通过，其中新用例执行真实 CI JavaScript 对照相同正反例；Ruff 0.17.1 检查通过。实际入口自动探测仓库 Python；明确指定 WindowsApps 别名正确拒绝；脏候选正确返回 WORKTREE_UNSTAGED 和非零退出码。采集器生成同租户精确 Issue 绑定，歧义拒绝，原始记录不改写。

沙箱临时目录及原子硬链接权限失败分别通过宿主许可的同一测试/落库命令恢复，不将环境拒绝当作业务校验失败。未改变托管权限，未声称已有后台恢复服务。正式门禁、提交、CI/main 回读按本次发布阶段继续核实；公开证据为 data-collection/gate-reliability-verification-20261105.json，最终远端回执记录于本工单。
