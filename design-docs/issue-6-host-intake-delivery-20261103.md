# 宿主工单入口与采集交付补缺

工单：https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/6

<!-- olympus-request:issue-governance-20261102 -->

用户于 2026-11-03 要求将已定位遗漏纳入框架，并将宿主使用框架时的真实数据采集视为 Git 交付内容。

根因：Godot 自动生成聊天快照需求 ID，bridge 仅核验框架与回执；创建 Issue 为显式命令，PR 关联检查晚于开始开发；Ariadne 尚无 GitHub 源，服务器保护未启用。

本次在工程定制层复用真实 Issue 门禁：新增 intake-only 回读校验；Godot 页面提供工单编号和稳定 ID，每轮发送传入宿主适配器，未绑定或回读失败拒绝。真实事件以 Issue URL 为来源，稳定需求 ID 贯穿宿主回执。所有已接入该适配器的引擎/IDE/CLI/生产工具共用检查；任意外部编辑器仍需其宿主实际接入，规则文件不能成为操作系统访问控制。

采集来源/验证/回执与文件事件共同交付。本地门禁拒绝 data-collection 目录下未进入 index 的文件、index 字节不符及删除历史；Hermes validate/git-check 延续原工具，提交后使用 require-committed 检查 HEAD。缓存、凭据不进入交付目录；数据原件保留并追加纠正。

验证：18 项宿主测试、37 项工单测试通过；受影响 ai_chat_olympus.cpp、olympus_panel.cpp 对象使用 MSVC 编译通过；正式 Olympus 校验为 approved_file_integrity。模拟测试位于临时目录，不写入生产数据。未执行真实模型调用、未将新二进制启用作为已验收事实。

边界：未修改共工或冻结/准入包；未建立 webhook、定时扫描或 Ariadne 假来源。远程分支保护仍需管理员实际配置。本次为 #6 增量候选，独立审查、真实门禁、文件事件及 Git 提交证据按实际完成补充；不自动关闭父单。

## 本轮续办回读与验证

本轮真实回读确认 #6 保持 open、type:maintenance、status:in-review、workspace:olympus，稳定需求 ID 与当前工作区租户一致。PR #10 已于 2026-11-03 北京时间合并，合并提交为 `628ff28ab817311560114c8a01d44f36b46cb28b`；该合并不包含当前未提交的宿主入口增量，也不自动证明父工单验收完成。

重新执行工单组件 37 项和宿主组件 18 项测试全部通过；正式框架返回 approved_file_integrity，冻结纲领未变，Hermes 校验 64 条事件有效。scheduler 引用检查、两个聊天源文件 clang-format 及 git diff --check 通过。[原始工单快照与验证记录](../data-collection/issue6-continuation-verification-20261103.json)记录本轮覆盖范围。

当前会话 GitHub CLI 不可用，尚未运行通过受信任入口的真实 intake CLI 与完整提交门禁；GitHub 插件回读不能冒充该脚本已通过。独立审查和本轮文件事件需按实际结果追加；候选尚未提交、发布或验收，不启用新引擎或模型。

续验发现提交门禁未复用入口的 workspace 标签要求，已将该要求上移至共享 check_issue；新增回归确认缺少 workspace:olympus 时完整 gate 在正式框架执行前拒绝。最终工单组件 38 项、宿主组件 18 项通过。真实 intake-only 调用因缺少 gh 可执行文件返回 WinError 2；保留阻断，不伪造 CLI 回执。首次验证快照与 Hermes 事件保持原件，后续结果另行追加。

独立只读审查发现采集历史原件改写后重新暂存可通过，已修复为拒绝 HEAD 历史文件修改、删除和类型变化（禁用 rename 检测，避免改名掩盖删除）。新增真实临时 Git 提交后改写并暂存的拒绝回归，工单组件最终 39 项通过；来源纠正应新增文件。审查未发现宿主绑定、Issue 来源贯穿及 Godot 设置传递的其他明确阻碍，真实入口与新二进制仍待验。

## 本轮提交发布候选

用户明确授权提交并发布。候选从真实远程 main 的 628ff28a 隔离建立，仅包含 #6 宿主工单入口、采集保护与对应记录；不带入 #15 并行流程改动或已合并的 #7/#11 修复。官方 GitHub CLI 已恢复，真实 intake-only 回读通过；前述缺少 CLI 为历史状态。隔离候选重新运行工单39项、宿主18项和正式框架校验通过，聊天源格式与引用检查通过。独立审查沿用相同实现文件摘要的有效记录，当前候选未修改批准框架。最终新引擎二进制和真实模型调用仍未验收，发布分支与默认分支合入分别记录。

实现提交 `0241194c0ddd3c609a9fd692b054f1f0f326734a` 已推送并与远程分支精确回读一致；[PR #16](https://github.com/zhzyx/nightmarish-spooky-sorceryze/pull/16) 已发布，仍开放待验收，未合入 main。完整提交门禁通过，提交后 Hermes 检查为 committed：69 事件／72 数据文件。[远程发布证据](../data-collection/issue6-continuation-publication-20261103.json)与对应真实事件追加交付。后续仅新增这批发布证据，复用未变实现的行为与独立审查结果，重跑最终提交门禁及提交后数据检查。

用户要求立即合入后，实际读取PR静态失败并完成格式、测试模块spec/loader类型保护、同一头文件规范路径修复；57项回归和mypy通过。独立复核确认生产逻辑一致，头文件目标一致。仅两份已记录摘要的历史证据原件排除换行格式化，原件保护门禁继续运行。[CI修复证据](../data-collection/issue6-continuation-ci-fix-20261103.json)。以新提交远程检查为准，尚不宣称合入。
