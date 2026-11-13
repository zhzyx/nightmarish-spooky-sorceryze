<!-- gonggong-request:agent-docs-routing-submit-notes-20261114 -->

# 文档提交说明的关联字段重复

稳定需求 ID：`agent-docs-routing-submit-notes-20261114`。

关联 Issue：[Issue #1084](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1084)。

类别：`type:bug`。

## 故障与授权

交付 `agent-docs-routing-20261114` 时，首次调用 `writer_submit.py` 的说明文件手工包含了 `GongGong-Issue` 与 `GongGong-Request`；入口按契约拒绝该输入并报告 `Provide a title and PR validation notes`。用户已授权本次文档需求连续完成提交、推送和 main 交付，当前责任者在同一事件中接收并修复本次调用故障。

## 修复范围

只修正本次 PR 说明输入，移除由提交入口自动添加的两行关联字段，不修改提交工具、门禁、权限或其他候选内容。整合最新 main 后重新执行受影响文档检查与正式交付入口。

## 验收

- 说明文件不再含手工关联字段，标题和验证说明非空。
- 原提交动作在修正输入后取得明确结果；若产生新的失败，保留新证据并继续排障。
- 本故障不扩大为引擎或框架代码修改，不以故障关闭替代原需求 #1082 的业务验收。
