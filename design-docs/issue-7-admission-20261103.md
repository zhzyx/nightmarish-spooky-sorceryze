# Issue #7 新候选准入

工单：https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/7

当前来源全量148文件，新候选与已审同步器保持字节匹配。旧候选因上游两份运行视图更新而过期，不能继续申请旧摘要批准。独立审查原件：`data-collection/issue-7-independent-review-20261103.json`，Git LF 副本 SHA256 `cece4db5ef6164ab7cbf218854451785670d62c0442b141669540f2e137f349f`（独立审查原件摘要 `158266e43a36c63a3d906f2cb0155f48d6063d5e333b65262b0aaf628839e931`；仅换行规范化，JSON 内容逐项相同）。

| Agent | 版本 | 本次精确摘要 |
| --- | --- | --- |
| Athena | 0.4.0 | c22520b3a20e24a8fad23d8ff6696e6c4b3bacd73e6e0bf53c6256c7b72eb35d |
| Themis | 0.4.0 | fdc392c5845ce48269debd5a7cee5766d03425d39cef841249b5a0dc6bcff8b8 |
| Hermes | 0.4.0 | 54c8acf59079e1c616f97f0e58f61b02f923913618bb0f9b88499238b7e9503d |

范围：agent_definition_change / local_definition_release / local_agent_definition_only / bound_candidate_only。独立审查通过，用户批准尚未收到。旧运行来源与当前安装保持有效。批准后再次核对来源及精确候选，通过后才能发布定义与切换；不批准自动派发、生产模型调用或替代宿主权限。
