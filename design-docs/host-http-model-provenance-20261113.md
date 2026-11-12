# 宿主 HTTP 模型回执来源

<!-- gonggong-request:host-http-model-provenance-20261113 -->

Issue #1004（父需求 #978）。授权 `codex-user-ai-github-integration-refactor-20261112`，责任人 Sail-Li，执行工作者 `/root/sinan_03552b5b08deb741`。路径以仓库根为基准。基线 `308bc83c19ae7cd1811496cca0e7062e6b30dab0`。

独立审计 R3 复现了供应商返回不同 model 而宿主丢弃该字段。本单只改已有 host-http 运行包、宿主测试与文档；不新增模块，不修改冻结框架、历史批准、个人模型库或其他工作树。根会话负责独立审查、候选准入和交付。夸父 incident `329eaa08125cebc761bb613d09dbdae28c235e99e755fbb0edf90c78a333a084` 由本工作者接单并记录根因。

## 契约与消费链

沿用 adapters.call 唯一三协议解析路径，增加共用有界身份解析函数。请求型号必须是非空、无首尾空白且可打印的字符串，UTF-8 最多 512 字节；不合法请求在网络前拒绝。返回 `requested_model`、`observed_model`、宿主 `protocol`、`observed_model_source`、`observed_model_status` 与恒 false 的 `model_identity_verified`。有效 observed_model 来自顶层 response.model；缺失或 null 为 unavailable，其他畸形值为 invalid，身份与来源均为 null。畸形可选元数据不抹掉有效的结果与用量，不增加重试。不同型号或合理别名不自动拒绝；没有独立供应商身份认证。

evaluate 将整个回执保存至 results[].response；runner 将整个回执持久化至 call_end。未知传输与恢复中断记录只保存已知的请求身份及 null observed_model。完成重放和恢复不重新请求或覆写回执。谛听固定 usage.model 表示配置值，metering_ref 引用 state/runtime.sqlite 中同租户与 task-id 经 runner.jid_for 得到 job 后、再联合 event-seq 读取的原调用。集成测试实际用该引用查询 SQLite，核对原调用与型号，而非只检查引用文本。冻结 schema 不嵌入 observed_model，单独下游导出仍有缺口，必须保留宿主 journal；不假称所有消费者已得到独立认证身份。

## 验收与验证

三个协议都覆盖相同型号、不同型号、快照别名、本地名称、边界长度、多字节长度、缺失/null/非字符串/控制字符/空白/非法 Unicode。供应商伪造宿主 provenance 字段不能覆盖真实请求、协议和验证状态。集成覆盖真实本地 HTTP → evaluate → journal → 谛听引用回读 → replay/recover，以及无效模型元数据与整体畸形响应。运行原有 runtime 全套行为回归及 scoped ruff/mypy；证据在 `data-collection/host-http-model-provenance-1004.json`。

任务开始已召回本租户方法域：editor-diagnostic-consumption 当前无已验证方法；human-model-acceptance 仅有人形几何经验，不适用于本 HTTP 来源任务，未强行套用。

本次仅合成测试，无真实付费调用或凭据读取，不构成账号、远端路由、实际权重、流式/工具/其他协议验收。既有运行委托绑定 runtime 摘要，代码更新后需按原授权重签；回退可恢复旧宿主版本，但旧回执仍没有观测身份。原父单 #978 的其他验收保持独立。
