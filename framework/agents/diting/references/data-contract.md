# 数据契约 v2

每条新记录必含 schema_version=2、record_id、tenant_id、kind、created_at（带时区）、evidence_refs、payload；更正可带 supersedes。ID 在租户内唯一，同内容重放幂等，不同内容拒绝。原文保留于受控来源，模型只收必要脱敏片段。实际授权、保留和删除由宿主控制。

除 source、agent_snapshot 外，必有 context：request_ref、primary_agent_ref、related_agent_refs、work_items、linkage_state、linkage_note。request_ref 指向 request，request 自身指向自己。Agent 引用必须指向实际版本快照。work_items 各项为 {id,kind,relation,certainty}，涵盖 Feature、工单、资产、接口或通讯等相关与可能相关工作；certainty=confirmed/possible/unknown。linkage_state=complete/partial/unknown，未知不能省略原因，空关联不能声明 complete。

## 基础与分析

| kind | payload 必填字段 |
| --- | --- |
| source | source_key, authority_ref, purpose, retention, allowed_fields |
| agent_snapshot | agent_id, version, definition_digest, definition_ref, origin, role_kind |
| feedback | source_key, external_id, source_revision, occurred_at, collected_at, batch_id, content, original_ref, context |
| annotation | labels, schema_version, method, reviewer, uncertainty |
| classification | taxonomy_version, categories, candidate_layer, reason, event_cluster, target |
| analysis | question, method, sample, findings, counterevidence, limitations, target |
| optimization | target_layer, target, problem, proposed_change, metrics, validation_plan, rollback, owner_ref, status |
| reference | title, statement, applicability, limitations, review_after, status, target |

agent_snapshot 引用 source，definition_digest 为实际定义 SHA256；origin=registered/generated/external，role_kind=subagent/framework/governance。登记快照不等于准入。feedback 引用匹配 source，payload.context 保存原环境，顶层 context 保存工作关联。annotation 引用反馈或执行事件，labels 含 name/value/evidence_span；缺片段写原因。classification 引用反馈或标注。analysis 引用反馈、标注、分类或执行事实；样本写时间窗、独立事件数、分母、缺失及筛选。

target={scope,agent_ref}，scope=feature/project/module/agent/framework/yuanheng/unknown，agent_ref 须在 context 中。分类和优化层级与 target.scope 一致。framework 必须有 cross_agent_evidence（已列入 evidence_refs 的记录 ID，覆盖多个实际 Agent）或 handoff 证据，不靠名称推断框架根因。共工／元衡仅可形成 proposed reference；其他子 Agent 可形成 proposed optimization。两者均引用 analysis，不自动生效；reference.review_after 为 YYYY-MM-DD。

## 执行事实

下表事件都包含 source_key、event_key、source_revision，evidence_refs 含匹配 source。来源 + 事件 ID + 版本去重，更正保留逻辑身份。除非明确可空，必填字段不能省略。

| kind | 其他 payload 字段 |
| --- | --- |
| request | request_key, project_id, initiated_at, intent |
| request_end | status（completed/cancelled/failed）, occurred_at |
| step | step_key, phase, started_at, ended_at, duration_ms, status, attempt, trace_id, span_id, parent_step_ref, usage |
| message | conversation_id, message_id, turn_id, role, visibility, content_ref, step_ref, occurred_at |
| direction_error | error_id, expected, actual, issue_ref, step_ref, occurred_at |
| correction | error_ref, action, resolution, step_ref, occurred_at |
| quality_issue | issue_id, issue_ref, severity, step_ref, occurred_at |
| rework | issue_ref, action, step_ref, occurred_at |
| handoff | from_agent_ref, to_agent_ref, communication_ref, step_ref, occurred_at |
| coverage | category, state, observed, expected, reason, window_start, window_end |

request 是不可改的需求身份，目标变化另记事件。step 每次实际尝试独立 step_key 和 usage_key；running 的 ended_at/duration_ms 为 null，succeeded/failed/cancelled 必有结束时间和相符时长。根 parent_step_ref、未归入步骤的 step_ref 可空，不捏造步骤。correction.error_ref 指向方向错误；rework.issue_ref 指向 quality_issue；这些关系须同需求并列入 evidence_refs。quality_issue.issue_ref 指原质量主记录，问题确认程度与检查结论来自原系统，谛听不另签结论。

message.role=user/assistant/tool/system，visibility=user_visible/internal。handoff 两个实际 Agent 必须在 context 中。coverage.category=messages/steps/directions/quality/usage，state=complete/partial/unavailable；未知计数为 null，complete 必有可对账 observed=expected。具体统计及 usage 字段见 telemetry.md。

## 版本与生命周期

更正不覆盖历史。原始事件在后来步骤完结后仍保留当时事实；自身被替代标记 superseded。派生标注、分类、分析、优化、reference 在证据祖先被替代时为 stale，必须重评。上下文归属是历史引用，不因步骤结束把所有消息算成失效。请求错误、纠正、返工均留存，不能为美化指标删除。

字段、标签与统计口径分别版本化，索引从原记录事务生成。历史按 Agent 当时版本保存，升级使用映射，不反写旧归因。保留、撤回和必要删除覆盖原始、缓存、索引、派生及备份策略。权限与保留范围外不承诺永久数据；源端未提供的事实不能通过标签恢复。无效批次整体拒绝，连接器负责隔离、重试及补证，不建立第二套质量账本。
