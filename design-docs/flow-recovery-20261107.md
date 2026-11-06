# 夸父解阻与原操作复验

当前目标是让负责原工单的人能看出哪一步受阻、谁接手、哪项工作可以继续，以及原操作是否已经在相同候选复验成功。对应 [#251](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/251)，父项为 [#246](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/246)，用户授权来自本次「执行所有优化内容」。适配器及命令按仓库根解析。

## 执行入口与回读

1. 检测、接单沿用 [夸父接入](../customizations/components/issue-workorders/kuafu-routing.md)。同一工作树、工单、动作、失败证据和候选下的重复观察共用首次失败时间。完成原操作复验后，同一故障再次发生会建立新的事件。
2. 处理人使用现有 `assess` 命令时，可传 `--attempted`（已试操作及结果）、`--repair-owner`（可解除的责任人）和 `--continuable`（可继续子项）。只填写可公开的事实；原单评论和谛听判断事件保留最新一次判断及依据。
3. 原先受阻的前置条件实际具备后，已接单的处理人使用同一工单绑定、实际工作者及授权，运行 `kuafu_incident.py --repo . condition INCIDENT --bug N --worker WORKER --authority REF --evidence REF`。证据应指向实际交付、权限恢复回读或独立验证。本机保存处理人观察时点；尚无此回执时保留未知。判断和条件观察分别记录。
4. 原工作者重跑实际门禁或交付命令。成功后现有入口记录动作与结果摘要。原动作、工作树、HEAD、暂存差异及适用的验证基线一致时才写原操作通过；其他候选成功留下单独回执，原操作保持待验。`status INCIDENT` 提供 `recovery.first_failure_at`、`condition_observed_at`、`reverified_at` 及条件来源。统计每次事件时使用确定的首个匹配回执。缺失任一端点时，对应阶段耗时保持未知。私有目录位于 Git common-dir 下。
5. GitHub CI 事件复用原有运行归属、失败作业与步骤覆盖检查，成功时在原单回读夸父机器人 JSON。三个同名时间字段分别来自首次失败运行、独立条件证据、相同候选成功运行。本接入未观测独立条件时为 null。后继候选的回执按候选分别记录，保留原事件的复验机会。历史回执保留当时证据精度。

## 验收

实际接入路径涵盖提交/门禁的成功回调、受绑定夸父接单和 GitHub workflow_run 处理。定向运行 `python -m unittest discover -s customizations/components/issue-workorders -p "test_kuafu*.py"` 共 25 项通过。覆盖失败去重、缺回执、条件回执重放、移动基线、后继候选成功、原候选恢复、恢复后复发和旧 CI 标记。Ruff 0.17.1 检查通过。测试使用隔离宿主和 GitHub 回执夹具；未来真实阻塞的等待时长留待当时的三个时间点核实。

历史接续与时间口径：旧宿主若只为后继候选留了回执并已删除 pending 索引，接单者在原工作树使用 condition 并回读真实解除证据后，会恢复该事件的原动作索引。缺原验证基线时，即便同名分支或 HEAD 相同，也只能记录候选复验。GitHub 后继候选以运行 head 和该次 PR head 共同索引；复验 JSON 保留两者各自的原值与新值。既有回执按当时记录读取。first_failure_at 在本地是首次检测记录时间；GitHub 运行取首次接收的失败 attempt 所带 updated_at，旧记录可回读取该失败 attempt 的 updated_at，缺失保留 null。这是失败完成的提供方时间代理，实际步骤第一次出错时刻未知。
