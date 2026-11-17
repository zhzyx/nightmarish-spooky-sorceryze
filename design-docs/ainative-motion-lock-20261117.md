# AINative 动作任务文件锁并发修复

对应工单为 [#1440](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1440)，父工单为 [#1343](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1343)。

## 目标与授权

修复 M4.3 父工单 #1343 全量 AINative 回归中发现的 Windows 文件锁竞争。用户已授权完成相关修复、验证、提交、推送与合入，当前修复由 Codex 独立工作树承担。父工单保留原验收范围。

## 原始故障

`MotionRecoveryTests.test_concurrent_same_key_launches_once` 在四线程同时提交同一动作任务时，于 `motion_jobs.exclusive` 初始化空锁文件的 `write/flush` 阶段触发 `PermissionError`。文件句柄随后未关闭，临时目录清理再次失败。原回归执行 437 项测试，出现两项错误。

锁初始化发生在保护句柄生命周期的 `try/finally` 之前。竞争线程可以在另一线程已锁住第一个字节后尝试写入同一区间。

## 修改范围

仅修改 `tools/ainative/motion_jobs.py` 的锁生命周期和相关确定性回归。保留阻塞、非阻塞、异常传播及 POSIX 独占锁行为。先验证 Windows 支持空文件 EOF 之后的字节区间锁，再去除无必要的初始化写入。

## 验收

- 新建空锁文件的并发竞争可确定性复现原问题，修复后没有初始化写入竞争或句柄泄漏。
- 相同任务键的并发提交只启动一个子进程。
- 阻塞锁等待、非阻塞锁冲突、异常释放和文件可删除均有回归覆盖。
- Windows 实测和 Linux CI 语义测试通过，相关 AINative 全量回归通过。
- 独立审查、正式工单门禁、精确候选 CI 及 main 回读完成后关闭本修复工单。

## 验证方法复用

已召回本租户 `native-storage-resource-boundary`，当前没有已验证方法。交付阶段复用 `github-issue-delivery/reconcile-workflow-incidents`，核对失败运行与修复后同一步骤的实际结果，保留父工单与故障单的独立状态。

## 本地验证结果

Windows 实测支持零字节文件的 EOF 区间锁。修复后 14 项动作任务回归、150 次重复锁竞争检查、445 项 AINative 回归和 9 项打包回归均通过。后两组分别有 36 项和 2 项显式跳过。Ruff 和 mypy 检查通过，独立审查无新增问题。具体输入摘要和结果保存在 [验证记录](../data-collection/ainative-motion-lock-verification-20261117.json) 与 [独立审查](../data-collection/ainative-motion-lock-review-20261117.json)。Linux 平台的实际结果由精确候选 CI 回读。
