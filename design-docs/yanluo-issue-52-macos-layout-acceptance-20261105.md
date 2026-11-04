<!-- gonggong-request:yanluo-issue-52-macos-layout-acceptance-20261105 -->

# 完成 AI Chat 全窗口在原 macOS 平台的四项验收

父单：#52；审查来源：#88。需求文档：`design-docs/yanluo-issue-52-macos-layout-acceptance-20261105.md`（路径相对仓库根）。

已交付依据：全窗口实现 b9038428 已进入 main；PR #70 的 Windows 三进程补充验证及原 macOS 构建记录保留，不能替代原四项完整平台验收。
已合入提交/审查基线：`b9038428`。

剩余验收：

- [ ] macOS x86_64 / Apple Clang 14 环境：全部侧栏/底栏/场景标签隐藏，AI Chat 使用完整内容区宽度。
- [ ] 切回 2D/3D/Script 后恢复各 Dock 及分割位置。
- [ ] 保持 distraction-free 原始状态与往返语义。
- [ ] 底栏展开时进入 AI Chat 不留空白，并核验恢复。

边界：优先复用现有实现和明确匹配的构建；本次审查不编译引擎。原 #52 保持开放并纠正 done 标签，不能将 Windows 结果称为 macOS 全通过。

证据：design-docs/ai-chat-fill-window-20261104.md; data-collection/issue52-windows-layout.json。

本单由阎罗全仓审查及独立复核形成，后续由司南按真实需求事件派发；创建不等于已执行或生产启用。原父单未满足全部验收，继续开放；本单完成后重新核对父单。

<!-- gonggong-host-git:Sail-Li -->
