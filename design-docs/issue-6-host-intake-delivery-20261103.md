# 宿主工单入口与采集交付补缺

工单：https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/6

<!-- olympus-request:issue-governance-20261102 -->

用户于 2026-11-03 要求将已定位遗漏纳入框架，并将宿主使用框架时的真实数据采集视为 Git 交付内容。

根因：Godot 自动生成聊天快照需求 ID，bridge 仅核验框架与回执；创建 Issue 为显式命令，PR 关联检查晚于开始开发；Ariadne 尚无 GitHub 源，服务器保护未启用。

本次在工程定制层复用真实 Issue 门禁：新增 intake-only 回读校验；Godot 页面提供工单编号和稳定 ID，每轮发送传入宿主适配器，未绑定或回读失败拒绝。真实事件以 Issue URL 为来源，稳定需求 ID 贯穿宿主回执。所有已接入该适配器的引擎/IDE/CLI/生产工具共用检查；任意外部编辑器仍需其宿主实际接入，规则文件不能成为操作系统访问控制。

采集来源/验证/回执与文件事件共同交付。本地门禁拒绝 data-collection 目录下未进入 index 的文件、index 字节不符及删除历史；Hermes validate/git-check 延续原工具，提交后使用 require-committed 检查 HEAD。缓存、凭据不进入交付目录；数据原件保留并追加纠正。

验证：18 项宿主测试、37 项工单测试通过；受影响 ai_chat_olympus.cpp、olympus_panel.cpp 对象使用 MSVC 编译通过；正式 Olympus 校验为 approved_file_integrity。模拟测试位于临时目录，不写入生产数据。未执行真实模型调用、未将新二进制启用作为已验收事实。

边界：未修改共工或冻结/准入包；未建立 webhook、定时扫描或 Ariadne 假来源。远程分支保护仍需管理员实际配置。本次为 #6 增量候选，独立审查、真实门禁、文件事件及 Git 提交证据按实际完成补充；不自动关闭父单。

首个提交 af399d65 已通过真实工单/正式框架门禁，提交后 67 个数据文件、64 条事件与 HEAD 一致，已推送并建立 Draft PR #14。随后远程静态检查报告格式问题；使用仓库固定 ruff/clang-format、includes/copyright hooks 修正，并为测试 importlib 加入 spec/loader 守卫。55 项组件测试及变更文件完整 prek 检查再次全部通过，事实与追加纠正事件见 data-collection/issue-6-host-intake-ci-correction-20261103.json。前置治理分支尚未进入 main，PR 保持待验收。

## 用户修正：关联不符不能阻断

用户明确要求不因 Issue 不符阻断开发。本修订取代此前“缺绑定或回读失败拒绝开始”的设计：入口查询继续保留，但缺失、不符或网络不可达均变为提示及 needs-reconciliation。宿主将协调事项带入上下文，继续执行；缺稳定 ID 时使用确定性 pending-issue 临时身份，来源仍为实际宿主，不能借用未验证 Issue URL。补齐工单后追加更正/关联回执，保留原始事件。正式准入、权限、采集及提交验收边界保持各自含义。
