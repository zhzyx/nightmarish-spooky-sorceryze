# 放宽工单门禁的 Diting 来源事件类型限制（已撤销）

<!-- gonggong-request:issue-gate-diting-source-event-binding-20261105 -->

原需求：[#64](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/64)；取消核对：[#96](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/96)。路径相对仓库根。

2026-11-05 用户明确撤销放宽门禁相关需求。#64 当前应为 closed/not_planned、status:cancelled；原实施候选已停止，不恢复、不合入、不另行派发。

原提案希望让同租户、同 request_id 且精确绑定 Issue 的任意已跟踪 Diting 事件替代 kind=request。本提案未合入，验收要求已随撤销取消，不能记为功能通过。当前 issue_gate.py 仍要求 kind=request，保持既有来源校验。

本文件补齐 #64 正文所引用但 main 中缺失的归档路径，仅保存撤销结论。原提案全文、旧状态与此次决定见 `data-collection/issue96-gate-relaxation-cancellation.json`；清理与交付跟踪见 `design-docs/yanluo-issue-64-closure-discrepancy-20261105.md`。不删除停止候选、旧批准或历史事件。
