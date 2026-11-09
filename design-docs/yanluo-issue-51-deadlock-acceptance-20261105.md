<!-- gonggong-request:yanluo-issue-51-deadlock-acceptance-20261105 -->

# 补齐 AI Chat 原始卡死复现与真实停止交互验收

父单：#51；审查来源：#88。需求文档：`design-docs/yanluo-issue-51-deadlock-acceptance-20261105.md`（路径相对仓库根）。

已交付依据：PR #61/#78/#82 已整合工具清理与 HTTP 取消；关联 #47 的 PR #67 已交付 modal 修复；取消信号毫秒级回归及断线恢复已有证据，原始真实死锁尚无唯一根因证明。
已合入提交/审查基线：`e7b217340281c0ce14511b7961959be72eeaa469`。

剩余验收：

- [ ] 在用户允许继续的代表环境补充原始卡死复现与因果证据，无法复现则记录 unknown，不能猜定唯一根因。
- [ ] 验收真实鼠标/键盘停止交互与 UI 响应、取消后恢复，以及迟到结果不恢复旧轮；信号调用或网络断开不能替代全部交互证据。

边界：仅待补复现/验收及证据指向的必要修复；不重做已合入取消/modal，不在本审查中恢复用户停止的调查或构建。

证据：data-collection/issue51-pr61-integration-20261105.json; data-collection/issue59-integration-validation-20261105.json。

本单由阎罗全仓审查及独立复核形成，后续由司南按真实需求事件派发；创建不等于已执行或生产启用。原父单未满足全部验收，继续开放；本单完成后重新核对父单。

<!-- gonggong-host-git:Sail-Li -->

## 2026-11-09 续办

本次后台回环头部延迟+1MiB gzip 恢复通过，Stop 3.256ms，恢复发生在被取消服务器释放前，无迟到回复。修复测试被自动模型目录刷新锁住 Send 的准备步骤。此为控件 pressed 信号、历史 a2a119d51 二进制的模拟服务验证，不是原死锁因果或物理点击证明。

本轮源修订、实测与模拟边界统一引用 `data-collection/before300-20261109/validation.json` 及同目录各项报告（路径相对仓库根）。
