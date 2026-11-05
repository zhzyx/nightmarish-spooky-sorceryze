# 阎罗全仓 Issue 与提交审查

稳定需求 ID：yanluo-issue-audit-20261105。路径均相对仓库根。

用户要求：使用阎罗规则审查当前所有 Issue 内容和提交内容，对已有提交的 Issue 关单或新建剩余单处理。

范围：一次性覆盖本仓库全部开放/关闭 Issue、相关 PR、main 提交、需求文档和既有验收证据。以当前 main 为基准，逐项区分已合入、仅分支提交、已验证、未知与未完成；复用明确适用的既有测试，不重建引擎、不实施无关功能、不改其他工作树。当前有效阎罗规则适用；尚未合入的规则草稿不自动启用。

验收：全量范围清单与 Issue—PR—commit—验收证据映射；对完整交付的开放单记录依据后设置 done/completed 并回读；大部分完成或少模块尾项建立/复用稳定ID剩余单并保留来源、验收和依赖；不能因有提交或标签done就认定全完成。已关闭单检查明显遗留或重复，不未经证据重开。并发变更前后核对、保留其他标签、无重复建单。最终记录逐单决定、实际远端回执及仍待判断内容。

原始用户授权包括关单与新建剩余单；不需要逐单重复确认。缺证或外部权限仅阻断相关操作，其余继续。所有本地审查/采集产物按既有正式门禁提交。无定时扫描或后台服务。

## 审查结果

初始 42 张 Issue（15 open / 27 closed），45 个 PR、48 个本地分支头已核对；另含审查单 #88。执行期间 main 从 3afe3b0d 推进至 71ab6c28（PR89/#85），仅影响核验/框架元数据；已快进整合新 main，正式门禁按新有效框架运行。在这些远端操作时 PR87/#84 尚未合入；随后 f6deb6cb 整合其规则，已快进并复核影响。新的 unknown/必要父级验收约束仍要求六个未完成父单保持开放；#84 已由原工作者关闭，本次只回读。未提交工作树内容不计已交付。

独立复核者为 Codex /root，实际审查与远端执行为阎罗 /root/yanluo。四张完整范围工单 #55/#58/#59/#85 已 closed/completed，七张尾项/差异单 #90–#96 已创建、双向关联和回读。#52/#63 误用的 done 已改 in-review，其余业务标签保留；#64 已由用户在 #96 对应聊天明确撤销，取消决定见下方追加记录。#49 用户停止测试不重启、不记通过。

计数按列明的原业务验收组；#59 原七项逐条映射、#52 原macOS四项均unknown，#9/#47 原清单与实施/局部测试进度分开，不能解释为工作量百分比；原文和历史接受范围、当前证据、未知均在 `data-collection/yanluo-issue-audit-results.json`。历史验证为复用，没有新引擎构建或供应商请求。

| Issue | 原范围 done / remaining / unknown | 当前决定 |
|---|---:|---|
| #85 | 4 / 0 / 0 | close_completed_after_explicit_handoff |
| #84 | 1 / 0 / 0 | retain_closed_by_original_worker |
| #83 | 0 / 0 / 5 | reuse_existing_followup |
| #79 | 4 / 0 / 0 | retain_closed_accepted_scope |
| #72 | 3 / 0 / 3 | retain_inflight |
| #64 | 0 / 1 / 2（原审查，未计完成） | cancelled_by_user_via_96 |
| #63 | 3 / 1 / 2 | remaining_followup |
| #60 | 0 / 0 / 7 | retain_inflight |
| #59 | 7 / 0 / 0 | close_completed |
| #58 | 4 / 0 / 0 | close_completed |
| #56 | 5 / 0 / 3 | remaining_followup |
| #55 | 5 / 0 / 0 | close_completed |
| #53 | 4 / 0 / 0 | retain_closed_accepted_scope |
| #52 | 0 / 0 / 4 | remaining_followup |
| #51 | 3 / 0 / 2 | remaining_followup |
| #50 | 4 / 0 / 0 | retain_closed_accepted_scope |
| #49 | 3 / 0 / 2 | retain_unknown_user_stopped |
| #48 | 7 / 0 / 0 | retain_closed_accepted_scope |
| #47 | 5 / 0 / 3 | remaining_followup |
| #46 | 5 / 0 / 0 | retain_closed_accepted_scope |
| #43 | 5 / 0 / 0 | retain_closed_accepted_scope |
| #41 | 3 / 0 / 0 | retain_closed_accepted_scope |
| #39 | 4 / 0 / 0 | retain_closed_accepted_scope |
| #35 | 4 / 0 / 0 | retain_closed_accepted_scope |
| #32 | 5 / 0 / 0 | retain_closed_accepted_scope |
| #27 | 4 / 0 / 0 | retain_closed_accepted_scope |
| #25 | 5 / 0 / 0 | retain_closed_accepted_scope |
| #24 | 3 / 0 / 0 | retain_closed_accepted_scope |
| #22 | 4 / 0 / 0 | retain_closed_accepted_scope |
| #15 | 3 / 0 / 0 | retain_closed_accepted_scope |
| #13 | 3 / 0 / 0 | retain_closed_accepted_scope |
| #12 | 3 / 0 / 0 | retain_closed_accepted_scope |
| #11 | 3 / 0 / 0 | retain_closed_accepted_scope |
| #9 | 3 / 0 / 2 | remaining_followup |
| #8 | 4 / 0 / 0 | retain_closed_accepted_scope |
| #7 | 3 / 0 / 0 | retain_closed_accepted_scope |
| #6 | 4 / 0 / 0 | retain_closed_accepted_scope |
| #5 | 5 / 0 / 0 | retain_closed_accepted_scope |
| #4 | 4 / 0 / 0 | retain_closed_accepted_scope |
| #3 | 4 / 0 / 0 | retain_closed_accepted_scope |
| #2 | 5 / 0 / 0 | retain_closed_accepted_scope |
| #1 | 5 / 0 / 0 | retain_closed_accepted_scope |

原 #9/#47/#51/#52/#56/#63 的剩余单依次为 #90/#91/#92/#93/#94/#95，父单仍 open；#46 的 CodeBuddy 剩余复用 #83。#63 的实际 Python artifact_path 纯函数与 C++ predicate 静态对照为 Windows true、macOS/Linux false，不声称真实跨平台运行。#85 已合入 PR89；原执行者已完成并结束，独立协调者明确交接后，本次阎罗依据新的全仓关单授权完成 done/completed 并回读，历史自动审批拒绝保留于追加证据。

提交映射除 PR 祖先外，单列 #48 044a6ca6、#50 a1b20fc7、#52 b9038428、#63 c6445d39 等直接提交；PR66/71/73/74/76/77 的整合路径记录在 containment 中，不能因原 PR closed/unmerged 判为未交付。历史 #24/#25 的本地用户接受范围与旧发布不因非祖先或 Olympus 字样重开。

实际写入证据 `data-collection/yanluo-issue-audit-remote.json` 原件保留；独立复核发现 #92 来源归属和 #96 引用路径问题，已同步远端更正并追加 `yanluo-issue-audit-corrections.json`。源操作已交付到 GitHub Issue 时间线，审查仓库文件在本候选发布前仍属未提交；Diting 文件落盘、Git 交付与消费分别记录。审查 #88 在自身候选经过正式门禁、提交核验、CI、main 回读后关闭，最终回执在其时间线追加。

后续规则漂移：最终准备基线 `f6deb6cb75bd38b8ec3c1e71bf86d8b26cd1a06f`。#90–#96 在 71ab6c28 的真实审查事件下建立，只有正文与回执关联，未声称 GitHub 原生 sub-issue 关系；新规则不追造迁移/关闭事实。#9/#47/#52 等拆单为本次明确授权的剩余追踪，不通过把实现、编译或额外局部测试塞入原验收分母满足阈值。

## 2026-11-05 #96 撤销决定追加

用户明确撤销 #64 放宽门禁需求。#64 已回读为 closed/not_planned、status:cancelled；#96 清理交付后同样以取消关闭，不再作为 needs-decision 派发。门禁 kind=request 保持，未实现范围不计完成。历史审查回执不改写；来源为 `data-collection/issue96-gate-relaxation-cancellation.json`，清理文档为 `design-docs/yanluo-issue-64-closure-discrepancy-20261105.md`（均相对仓库根）。
