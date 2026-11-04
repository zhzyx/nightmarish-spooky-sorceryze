<!-- gonggong-request:yanluo-issue-64-closure-discrepancy-20261105 -->

# #64 放宽门禁需求撤销与 #96 清理

工单：[核对单 #96](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/96)；被撤销需求：[#64](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/64)；审查来源：#88。本文持久化路径相对仓库根解析。

## 决定与范围

2026-11-05 用户明确指示：“#96，撤销放宽门禁相关需求。清理并关闭相关内容”。据此撤销 #64，结束 #96 的关闭意图待决分支，不再继续门禁放宽实现，不建立承接需求。实际执行者为 Codex /root；独立工作树仅更新需求、审查视图及追加事件和来源。不操作其他工作副本或停止候选，不改门禁源码、冻结原件或历史采集记录。

本次交付为取消决定及文档/事件，无 Godot 运行包或编译目标。验证使用当前 Windows/Python 工具链：核对门禁仍要求同租户、同 request_id、kind=request 且精确 Issue 来源；检查文档和路径、Diting validate、正式 issue gate、提交后 git-check --require-committed；远端回读取消状态和仓库提交。停止条件为清理交付和状态同步完成，不追加引擎构建或无关测试。

## 清理验收

- [x] 用户已选择撤销，#64 剩余源码停止，不再等待继续/撤销决定。
- [x] #64 保持关闭，修正为 status:cancelled / not_planned，原 closed/completed/in-progress 在追加来源中保留。
- [x] 严格来源门禁保留；原需求归档说明、#88 当前视图同步，旧证据保留。
交付程序：文档与事件通过正式门禁及精确候选 CI 后由阎罗发布；远端接收和 #96 的 cancelled/not_planned 关闭回读由同次真实事件追加到 Issue 时间线，提交前不声称已交付。

## 证据与边界

审查基线 d4c9a9183d38a2e4bd12ac56ef40c892b65a99bf。此前 #64 于 2026-11-04T19:36:07Z closed/completed，标签仍 in-progress，PR #81 及 #46 文档均未包含该功能；此次依据新的用户撤销决定更新当前处置，不把未实现功能记为完成。

来源与远端 #64 回读：`data-collection/issue96-gate-relaxation-cancellation.json`。原需求归档：`design-docs/issue-gate-diting-source-event-binding-20261105.md`。门禁：`customizations/components/issue-workorders/issue_gate.py`。原 #88 数据和 Diting 原件保持不变；文件落盘、Git 提交、远端接收、实际消费分别记录，消费未知。
