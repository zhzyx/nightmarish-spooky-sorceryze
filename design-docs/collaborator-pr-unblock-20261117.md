# 协作者 PR 审查误阻塞与 Issue association 启动修复

需求 ID：collaborator-pr-unblock-20261117
用户授权：2026-11-17 当前 Codex 会话要求定位并修复其他协作者提交 PR 时被要求等待 Sail-Li 审查的问题。
责任者：当前 Codex / Sail-Li，隔离工作树从 main 6590bc7ed9fffd55a0e72d844c4c8331b25a3d4a 开始；不接管其他 PR。

事实：main protected=false，rulesets=[]；zhzyx ADMIN，kaiyunxue 和 Sail-Li WRITE。PR #1378 的审查请求由 kaiyunxue 发出，且由本人合入。运行 43922625430 为 pull_request_target 平台策略 brownout，作业数 0；不是 Issue 校验或独立审查失败。运行 43931744179 的同名作业已成功。

范围：将只读关联检查改为 pull_request 事件，保留无 checkout、无 secrets、无写 token 和全部关联条件；明确关联检查不是可信候选准入，工作流自身变更仍需独立审查与正式门禁。明确审查请求与强制审批的区别及独立审查者选择，不移除必要审查、不绕过真实保护。
验收：验证有效关联、无效关联拒绝、无工作树代码执行及只读权限；独立检查；本次 PR 的 issue-association 和适用 CI 成功，main 包含修复；记录其他操作者历史实际合入证据，不冒充其身份复验。
停止条件：真实权限拒绝或必要独立审查未通过。平台策略管理 API 当前返回 403；本修复不依赖修改管理策略。
经验召回：github-issue-delivery/reconcile-workflow-incidents revision 2；按同一作业核对，不能用其他任务或只有编译成功证明恢复。平台启动失败与业务审查分别留证。
参考：https://github.com/zhzyx/nightmarish-spooky-sorceryze/actions/runs/43922625430
官方依据：https://docs.github.com/en/actions/reference/security/securely-using-pull_request_target
