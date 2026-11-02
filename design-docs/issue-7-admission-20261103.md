# Issue #7 新候选准入

工单：https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/7

当前来源全量148文件，新候选与已审同步器保持字节匹配。旧候选因上游两份运行视图更新而过期，不能继续申请旧摘要批准。独立审查原件：`data-collection/issue-7-independent-review-20261103.json`，Git LF 副本 SHA256 `cece4db5ef6164ab7cbf218854451785670d62c0442b141669540f2e137f349f`（独立审查原件摘要 `158266e43a36c63a3d906f2cb0155f48d6063d5e333b65262b0aaf628839e931`；仅换行规范化，JSON 内容逐项相同）。

| Agent | 版本 | 本次精确摘要 |
| --- | --- | --- |
| Athena | 0.4.0 | c22520b3a20e24a8fad23d8ff6696e6c4b3bacd73e6e0bf53c6256c7b72eb35d |
| Themis | 0.4.0 | fdc392c5845ce48269debd5a7cee5766d03425d39cef841249b5a0dc6bcff8b8 |
| Hermes | 0.4.0 | 54c8acf59079e1c616f97f0e58f61b02f923913618bb0f9b88499238b7e9503d |

范围：agent_definition_change / local_definition_release / local_agent_definition_only / bound_candidate_only。

用户已通过 `call_2952cd1771324fd99b23a4543f259fb1` 明确回复“批准这三个候选并在复核通过后切换”。批准只绑定上表三个摘要，不延续到未来改动，也不授予自动派发、生产模型调用或替代宿主权限。

已先在隔离候选记录真实决定及准入通行证，正式验证通过后完成安装。切换前后重新计算三个候选摘要，均与上表一致；没有修改冻结候选正文来使批准生效。

实际证据：

- [用户批准记录](../Olympus/reviews/local-admission/issue7-user-decision-20261103.json)。
- [独立审查原件](../Olympus/reviews/local-admission/issue7-independent-review-20261103.json)。
- [精确来源锁及正式验证](../Olympus/reviews/local-admission/issue7-source-lock-20261103.json)。
- [Athena 通行证](../Olympus/reviews/athena-admission.json)、[Themis 通行证](../Olympus/reviews/themis-admission.json)、[Hermes 通行证](../Olympus/reviews/hermes-admission.json)。

切换后 `python Olympus/tools/verify_framework.py` 正式通过，模式为 `approved_file_integrity`；`python Olympus/sync/gonggong_sync.py check --root Olympus` 返回 `full_parity: true`、`source_admission_verified: true`，核验 148 个来源文件和 135 个确定性分发文件。13 项 reporting 配置验证通过，`runtime_connected: false` 仍如实保留，不以配置校验代替实际业务回执。

当前相对来源定位指向 `.godot-integration-local/issue7-20261103/approved-source/CURRENT_FRAMEWORK.json`；快照的 148 个来源文件和 16 项登记证据逐项匹配候选来源索引。没有修改全局 Gonggong 来源。快照保留在本机忽略目录，不作为本仓库源码交付内容。

旧框架及旧本机定位保存在 `.godot-integration-local/issue7-20261103/backup-before-switch/`。备份与切换前清单逐文件一致；`Olympus/extensions/hermes-files/` 原字节及根 `olympus-hermes-data/` 数据均在切换后核对为未变化。切换记录保存在 `.godot-integration-local/issue7-20261103/switch-result.json`，由主协调者关联真实需求事件和 Git 交付。

本记录只确认精确候选的本地定义发布与切换。Ariadne 本地模块仍保持禁用及分发待审状态；真实模型、宿主身份、工具权限、远端 Issue 状态和采集消费仍须各自的实际验证。此操作没有执行 Git 提交或生成 Hermes 业务事件。
