<!-- gonggong-request:yanluo-issue-64-closure-discrepancy-20261105 -->

# 核对 #64 关闭意图与 Diting 来源门禁未合入差异

父单：#64；审查来源：#88。需求文档：`design-docs/yanluo-issue-64-closure-discrepancy-20261105.md`（路径相对仓库根）。

已交付依据：#64 远端已 closed/completed（2026-11-04T19:36:07Z），标签仍 in-progress；独立审查关闭/重开事件没有关联提交。PR #81 与 #46 文档明确未包含 #64。
已合入提交/审查基线：`3afe3b0dfc42464c554d91b84461be33aa8d2031`。

剩余验收：

- [ ] 确认 #64 原关闭表示撤销/停止需求，还是剩余源码应继续；保留实际决策来源。
- [ ] 如撤销，记录 not-planned 的业务决定与边界；如继续，先明确独立执行范围、必要审查和验收，再推进当前 main 上的剩余实现。

边界：当前 main issue_gate.py（旧基线 3afe3b0d 第 246 行，当前 71ab6c28 仍保持同一 kind=request 语义） 仍要求 kind=request。仅建立 needs-decision 差异单，不重开 #64，不恢复其已停止候选，不把 completed 历史改写为 cancelled 或已实现。

证据：customizations/components/issue-workorders/issue_gate.py（旧基线 3afe3b0d 第 246 行，当前 71ab6c28 仍保持同一 kind=request 语义）; Issue #64 timeline; PR #81; design-docs/requirement-8275346195acf05e0605ca999b44d868.md。

本单由阎罗全仓审查及独立复核形成，后续由司南按真实需求事件派发；创建不等于已执行或生产启用。原 #64 维持关闭，等待决策。

<!-- gonggong-host-git:Sail-Li -->
