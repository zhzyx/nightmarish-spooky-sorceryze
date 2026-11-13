# 未提交改动与历史工作树审查清理

## 2026-11-13 后续保留项复核

本轮增量盘点34棵工作树，复用原有源码审阅，核对原保留工作树HEAD均未变化，并对未提交文件留存摘要。#828已由#852完整交付；原项目AI配置提交与主线补丁等价，原#832已被替代关闭。独立核验原工作者终态、认领、进程、打开文件和实际启动入口后，正常删除 `project-ai-config-20261112` 工作副本，未使用强制删除。

删除前后校验并保留11份必要原件（174,517,603字节），包括独有故障事件、私有回执、UI快照及旧原生程序；原非祖先分支和提交保留。4682个忽略文件均已分类，未发现未知内容。删除前该工作树占用2,320,484 KiB；此数不是实测磁盘净释放量。其余工作树原HEAD和本轮记录的独有文件摘要复验一致，有效安装及用户配置未修改。

本目标累计正常删除28棵工作树，当前登记33棵。#833原CI队列仍为queued，根因未知，保留原远端候选与诊断责任；不以#828的后继交付替代旧队列恢复。#830已收到用户明确交接，将由本会话接续准备候选的交付；父#978其他原环境验收继续保留。详见[追加清理证据](../data-collection/ai-integration-retained-worktree-cleanup-978.json)。下文按时间保留历史处置记录。

## 2026-11-13 交付验收与清理

用户明确交接后，PR #1044 已进入 main `c827551e86ad37551302a6df3dc37d4d63a3638c`，内容树与独立审查候选一致。精确 PR/main CI 均通过：Windows 1578 个测试、474797 个断言通过，3 项跳过；会话隔离、运行时中断及原请求恢复实际通过。macOS 九个原生场景、4 个 C++ 用例/74 断言和49个桥接用例通过。#838 已 done/completed，旧 #847 以被替代关闭。

本轮正常删除 `ai-chat-status-recovery-integration-20261113` 和 `tianshu-resume-status-20261112` 两棵旧工作树，以及两条已合入本地分支、两条关闭 PR 的精确远端候选分支。累计清理27棵工作树，当前保留34棵；原 f5e 源码分支不是 main 祖先，保留历史。全部改动与原失败证据已归档校验，当前原生程序和必要回退版本保留。原用户工作区、其他任务和有效安装未变。

详见[追加交付回执](../data-collection/tianshu-resume-status-838-delivery.json)。原 #827 预览与生产整体验收及父 #978 仍独立开放；受控夹具不代表真实供应商推理，未运行 CI 项不计通过。下文早期状态为历史来源，以本节为当前 #838 接收状态。

<!-- gonggong-request:workspace-review-cleanup-20261112 -->

用户于 2026-11-12 明确要求 review 主工作区未提交改动及其他任务工作树，删除非必要保留对象。Issue #973；原 AI/GitHub 全面重构目标继续，本单只完成前置工作区整理。路径以仓库根为基准；宿主私有回执的基准另在证据中注明。

## 验收与结果

- 盘点原 52 个工作树，核对 HEAD、index、工作区改动、忽略文件、主线历史、PR、工单、进程及持久认领。
- 19 个干净且已交付副本经过独立审查后用普通 `git worktree remove` 删除；对应 19 个本地分支用非强制删除。远端分支不在本轮清理范围。
- 先归档并校验 247 份必要私有回执/配置；主树 34 份未跟踪事件与远端 main 逐字节一致，确认其余事件无关联引用后私有归档并删除重复本地副本。
- 保留 33 个原工作树及其必要记录；402 份独有内容摘要复验一致，原 HEAD 未变。另新建的重构工作树用于持续目标，仍在使用。
- 本轮没有启动编辑器、改认证、切换有效安装、删除用户项目或清理在途资源。静默 Git/文件核对适用，无生产源码改动，未重复编译引擎。

## Review 发现

主树两处规则改动来自已交付 #954 / PR #958，用于给旧主工作区补装任务清理约定；最新 main 已有同一条款。当前主树仍供运行中编辑器使用，保留这两处补装，未 reset 或升级该工作树。

多份 dirty 工作树是历史合入候选的中间组合。对独有源码版本逐项查主线文件历史，并审阅未匹配的差异：包括旧 `find_gh` 的项目内安装查找、AI 配置恢复、Windows 安装与宿主策略、回归夹具、网络连接试验以及天枢文案。部分字节已在历史提交出现；未匹配字节不能据此称为已交付或安全废弃。旧候选不是后续重构基线，不自动应用其过期策略。`project-ai-config` 的提交补丁与主线等价，但未完成其恢复/交接核对，保留。

19 个清理候选均有主线包含、completed 工单及无占用依据。#426 已重开的两份恢复工作树、在途 PR #829/#831/#847、真实进程引用的两个工作树及当前引擎候选/启动来源保留。`protected_roots` 仅为候选准备时累积的其他工作树隔离清单；实际启动路径另行核对。

清理中一次预检查把 `.flush.lock` 错当零字节文件，安全停止后按桥接实现纠正：文件可含初始化单字节 `0`，是否活动以实际独占锁获取判断。绑定 #975，修正经过独立核查，原操作完成。此处不增加定时清理，不将锁文件存在解释为死锁。

## 每个工作树的处置

| 工作树 | 结论 |
|---|---|
| nightmarish-spooky-sorceryze | 保留主工作区；两处规则为旧树补装，3份原需求与独有事件仍有追溯用途 |
| godot-candidate-01f4412e1ee4cd33d614c47b | 保留；引擎候选绑定及独有需求、事件 |
| nightmarish-spooky-sorceryze-daqian | 保留；实际进程引用 |
| before300-ai49-after680-20261110 | 保留；1 个独有提交，补丁等价/整体验收或交接未完整确认 |
| before300-ai49-delivery-20261110 | 保留；2 个独有提交，补丁等价/整体验收或交接未完整确认 |
| before300-ai49-eec633-20261110 | 保留；2 个独有提交，补丁等价/整体验收或交接未完整确认 |
| before300-ai49-handoff-20261110 | 保留；41 项未提交/未跟踪内容，包含独有证据或待核实历史组合 |
| before300-ai49-main35b-20261110 | 保留；65 项未提交/未跟踪内容，包含独有证据或待核实历史组合 |
| before300-ai49-main5f-20261110 | 保留；44 项未提交/未跟踪内容，包含独有证据或待核实历史组合 |
| before300-final-20261110 | 保留；110 项未提交/未跟踪内容，包含独有证据或待核实历史组合 |
| before300-final-62e450-20261110 | 已清理；main 包含精确 HEAD、Issue completed、无占用；PR #691 |
| before300-final-a681-20261110 | 保留；119 项未提交/未跟踪内容，包含独有证据或待核实历史组合 |
| before300-final-receipts-20261110 | 已清理；main 包含精确 HEAD、Issue completed、无占用；PR #694 |
| before300-main-dde25-20261110 | 保留；1 个独有提交，补丁等价/整体验收或交接未完整确认 |
| before300-main2746-20261110 | 保留；52 项未提交/未跟踪内容，包含独有证据或待核实历史组合 |
| before300-main5f018-20261110 | 已清理；main 包含精确 HEAD、Issue completed、无占用；PR #667 |
| before300-main9132-20261110 | 保留；3 个独有提交，补丁等价/整体验收或交接未完整确认 |
| before300-sail | 保留；1 个独有提交，补丁等价/整体验收或交接未完整确认 |
| before300-stop92-20261110 | 保留；1 个独有提交，补丁等价/整体验收或交接未完整确认 |
| before300-stop92-final-20261110 | 保留；105 项未提交/未跟踪内容，包含独有证据或待核实历史组合 |
| daqian-ai-entry | 保留；1 个独有提交，补丁等价/整体验收或交接未完整确认 |
| daqian-input | 保留；2 个独有提交，补丁等价/整体验收或交接未完整确认 |
| daqian-multi-issue | 保留；2 个独有提交，补丁等价/整体验收或交接未完整确认 |
| daqian-publish-readback | 已清理；main 包含精确 HEAD、Issue completed、无占用；PR #425 |
| daqian-worker-progress | 保留；152 项未提交/未跟踪内容，包含独有证据或待核实历史组合 |
| editor-layout-20261112 | 已清理；main 包含精确 HEAD、Issue completed、无占用；PR #852 |
| engine-module-build | 已清理；main 包含精确 HEAD、Issue completed、无占用；PR #742 |
| git-bot-actions-20261110 | 保留；原工单 #426 已重开，恢复职责尚未结束 |
| git-bot-disposition-20261110 | 保留；原工单 #426 已重开，恢复职责尚未结束 |
| issue-160-portable | 已清理；main 包含精确 HEAD、Issue completed、无占用；PR #171 |
| issue-195-ai-chat-animation | 保留；3 项未提交/未跟踪内容，包含独有证据或待核实历史组合 |
| macos-471-completion | 已清理；main 包含精确 HEAD、Issue completed、无占用；PR #512 |
| macos-471-native | 保留；实际进程引用，且存在未释放工作者认领 |
| macos-tianshu-493 | 保留；2 项未提交/未跟踪内容，包含独有证据或待核实历史组合 |
| project-ai-config-20261112 | 保留；1 个独有提交，补丁等价/整体验收或交接未完整确认 |
| render-auto-build | 已清理；main 包含精确 HEAD、Issue completed、无占用；PR #745 |
| runtime-compilation-20261111 | 已清理；main 包含精确 HEAD、Issue completed、无占用；PR #802 |
| runtime-native-20261111 | 已清理；main 包含精确 HEAD、Issue completed、无占用；PR #805 |
| startup-account-restore-20261112 | 已清理；main 包含精确 HEAD、Issue completed、无占用；PR #870 |
| startup-config-sync-20261112 | 已清理；main 包含精确 HEAD、Issue completed、无占用；PR #865 |
| startup-session-memory-20261112 | 已清理；main 包含精确 HEAD、Issue completed、无占用；PR #870 |
| tianshu-3d-20261112 | 已清理；main 包含精确 HEAD、Issue completed、无占用；PR #816 |
| tianshu-3d-actions-20261112 | 保留；分别对应在途 PR #831、#847、#829 |
| tianshu-3d-new-task-fix-20261112 | 已清理；main 包含精确 HEAD、Issue completed、无占用；PR #822 |
| tianshu-3d-send-20261112 | 保留；分别对应在途 PR #831、#847、#829 |
| tianshu-blue-wave-20261112 | 已清理；main 包含精确 HEAD、Issue completed、无占用；PR #839 |
| tianshu-godot-delivery | 已清理；main 包含精确 HEAD、Issue completed、无占用；PR #434 |
| tianshu-main-integration | 保留；1 个独有提交，补丁等价/整体验收或交接未完整确认 |
| tianshu-product-delivery | 保留；68 项未提交/未跟踪内容，包含独有证据或待核实历史组合 |
| tianshu-resume-status-20261112 | 保留；分别对应在途 PR #831、#847、#829 |
| tianshu-wave-with-3d-20261112 | 保留；引擎候选启动二进制引用、未提交组合及未合入父提交 |
| tianshu-workflow-labels | 已清理；main 包含精确 HEAD、Issue completed、无占用；PR #437 |

完整公开证据：[清理回读](../data-collection/workspace-review-cleanup-973.json)。私有记录保留原路径、摘要、终态回执和归档映射，不发布凭据、本机配置值或完整进程输出。Review 覆盖本轮保留/删除判断与独有改动风险；不将静态审阅表述为所有历史业务已通过验收。
