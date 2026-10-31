# 需求采集与统计口径 v2

宿主在需求发起时登记 request 和实际 Agent 快照，持续记录所有正常、失败、取消、重试与返工步骤。一个需求可关联多个会话、工作及 Agent。数据以事实来源为准，缺采集能力则记录缺口，不生成假历史。

## 时间与对话

需求首尾取 request.initiated_at 和 request_end.occurred_at，无结束事件则总耗时未知。事件 occurred_at 为发生时间，created_at 为记录生成时间；索引统一 UTC，原始时区保留。父子和并发步骤时长不能相加当需求墙钟时间。step_duration_ms 仅为观察到的步骤时长和；排队／等待可独立 phase。

消息按 conversation_id + message_id 去重，用户可见 user 消息的唯一 (conversation_id,turn_id) 为对话轮次。多条消息可属同一轮，turn_id 由实际会话来源提供，不能猜测。内部 Agent 通讯、助手消息及工具消息单列。

direction_error 保存预期／实际及原问题引用；correction 回链该错误。quality_issue 与 rework 分开，返工关联实际 step，时长／消耗通过步骤查询，不再复制加总。handoff 保留收发 Agent、通讯引用及相关工作。关联 certainty=possible/unknown 时可检索，但不当作已证实因果。

coverage 针对消息、步骤、方向、质量和用量分别记录时间窗与 observed/expected 对账。缺埋点写 partial/unavailable，计数未知用 null。没有完整覆盖证明时，只能说“未观察到”，不能说“未发生”。宿主负责源端序列／批次与落库对账，不能以模型声明替代。

## 每步 usage

必含 scope=exclusive、usage_key、provider、model、metering_ref、input_tokens、output_tokens、cache_read_input_tokens、cache_creation_input_tokens、reasoning_output_tokens、equivalents。usage_key 对应唯一实际调用／计费单元；上传重试沿用原 key，实际重新调用使用新 key。父步骤只记自身独占消耗，不重复子步骤。

每项 token 为 {value,status,reason,method}，status=measured/estimated/unavailable/not_applicable。前两者为非负整数并注明方法，估算注明方法版本；后两者 value=null 并说明原因，绝不能补零。provider/model 缺失显式写 unknown，metering_ref 指向缺失调查记录，不伪造账单。

equivalents 各项使用同样测量封套，并含 unit、formula_ref、formula_version、raw_value、raw_unit。保留原始图像数、credits、时长等，采用客户明确的分析换算公式，不假设存在跨模型通用 token 比例。未知等价值为 null；仍保留已知原始值。另记货币成本时须保留币种和计价版本。

input 包括相应缓存子集，output 包括 reasoning 子集，适配器按供应商语义标准化。总 token 只加 input + output，缓存／推理不重复加入。实测、估算和未知数量分开；等价值按 unit + formula_ref + formula_version + status 分组，不跨公式相加，也不再叠加到真实 token。

## 多维查询

list/stats 可筛 tenant、Agent 快照、agent-id/agent-version、project、request、step、work、kind、label=name=value、since（含）与 until（不含）。多值关联用存在性过滤，不通过 JOIN 放大计数。stats 按 request/agent/project/step/day 分组，Agent 组以主 Agent 归属；按相关 Agent 筛选可有交集，不能把各筛选结果之和当总体。

步骤分组使用稳定 step_key；--step 接受任一历史步骤 record_id 并解析同逻辑步骤全部版本，--step-key 可直接筛选稳定键。更正后的用量和原来的消息／问题仍归同一步骤，历史版本在统计中排除。CLI 统计同时返回 data_snapshot（选中记录 ID、内容 SHA256、有效性及整体指纹），用于追溯与重算。ingested_at 为本地实际接收时间，v1 历史无此事实则为 null。

输出保留查询条件、生成时间、metric_version、排除量、coverage 原记录。按需求返回首尾与墙钟耗时，消息／轮次，错误／纠正，质量／返工，步骤及逐类 token/等价。per_observed_step_tokens_complete 只描述已观测步骤字段，不代表全量采集。running、unknown、legacy_unmapped 显式保留；默认统计排除 superseded/stale/legacy_unmapped。未知不变成零。

窗口筛选后的统计只是所选事实；缺少需求首尾不推断完整周期。反馈支持度按独立事件簇，不能将记录数当用户数。错误率、返工率等另行分析时说明分母和覆盖，当前工具不自行生成有误导性的总体比率。生产分析需保存快照水位、查询及标签版本，支持回到原记录重算。

## 标准参照

核对日期 2026-11-01。采用通用可验证机制，而非宣称存在一项覆盖所有数据库与未来需求的统一认证：

- [CloudEvents 1.0.2](https://github.com/cloudevents/spec/blob/v1.0.2/cloudevents/spec.md)：来源、事件 ID、类型与时间参照；当前 JSONL 是奥林匹斯契约，尚非完整 CloudEvents 协议输出。
- [OpenTelemetry Traces](https://opentelemetry.io/docs/concepts/signals/traces/)：trace/span、父子步骤与关联参照；只保存字段，未部署 Collector。
- [OpenTelemetry GenAI](https://github.com/open-telemetry/semantic-conventions-genai)：供应商用量映射参照，适配器必须固定版本；[官方属性说明](https://opentelemetry.io/docs/specs/semconv/registry/attributes/gen-ai/)明确缓存和 reasoning 的子集口径，同时该页已迁移，不能当永久接口。
- [PostgreSQL 约束](https://www.postgresql.org/docs/current/ddl-constraints.html)：主键、唯一、外键及字段校验参照。当前可执行实现是 SQLite，并未部署 PostgreSQL。

生产上线需真实覆盖验收、租户权限、保留删除、备份恢复、迁移对账、索引和容量压测、数据目录维护。长期可用依赖这些运行措施与授权生命周期，不承诺无限保留或恢复从未采集的信息。
