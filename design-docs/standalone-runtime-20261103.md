# Olympus 独立运行修复

## 最新状态：未应用的历史候选资料

2026-11-03，协调主任务已完成 Issue #7 的 148 文件新批准源正式切换。本页以下的 140 源文件／130 分发文件修复候选、测试及摘要均为旧基线上的历史记录，独立运行修复没有应用到活动 Olympus。旧候选已被新基线替代，不再请求批准或切换本页列出的旧摘要。

本轮补丁、测试、文档、审查证据及两条真实 Hermes 事件可作为“未应用历史候选资料”归档；归档不代表独立运行问题已修复，也不批准或启用旧候选。后续必须在新的 148 文件基线上完整重建组合候选，重新执行适用回归与独立审查，再申请最终精确摘要批准。不得直接应用旧补丁覆盖新版同步器，也不得复用旧批准。

`tools/test_olympus_standalone.py` 可复用于带本地运行清单的组合候选；本次仅按仓库 Ruff 规则格式化，并在旧隔离候选上复跑，结果不构成新版基线的验收。历史补丁与证据原件保持不变。此次归档不授权通过其他通道发布此前被拒绝的进度评论。

关联 [Issue #7](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/7)，稳定需求 ID `upstream-workflow-upgrade-20261102`。用户于 2026-11-03 要求立即定位修复 Olympus 对 GongGong 的运行依赖；本次属于既有工单“保持既有发布可用”的缺陷修复，未完成 #7 的新上游版本升级。

## 根因与范围

`tools/verify_framework.py` 和 `tools/agent-context.mjs` 的分发注入每次启动调用 `sync/gonggong_sync.py check`，强制访问外部源并对照当前源完整重建。默认 `sync/binding.json` 指向相邻 GongGong；源更新会让已批准的旧 Olympus 报漂移，部署时没有该目录会报 Upstream unavailable。工作区 `.olympus-local.json` 原批准源仅被部分宿主接入，不能解决通用独立运行。

实际复现：默认源的候选验证报 Framework drift；显式绑定原批准来源后，当前正式校验通过。此次不改变共工、不修改冻结纲领、不捏造新批准。

## 修复与可复现交付

从现有同步工具复制隔离适配器，保持原批准来源不变，在新目录完整重建。启动入口改为 `sync/local_runtime.py`，校验完整本地文件集合及规范化清单。构建生成 `sync/runtime-lock.json` 并将其纳入三个 Agent 候选指纹；修改文件再重写 lock 仍会触发候选指纹失败。允许变化仅限现有接入配置、构建报告、清单指定的准入记录及其本地证据。正式验证和 Node 上下文仍检查精确候选准入。

`build/check` 仍核验真实上游及确定性全量一致性；`prepare` 仍只准备候选。离线运行不声称已核对上游最新状态或远程撤销。源更新事件触发新的完整重建、复核与切换。Hermes 豁免模块逐字保留，生产数据不复制进候选。

补丁：[同步适配器补丁](patches/standalone-runtime-20261103.patch)。在隔离工作树应用补丁，使用原批准源运行 `sync/gonggong_sync.py build --source SOURCE --out NEW_DIRECTORY`；不能直接在当前批准包上应用补丁后视为已启用。

本机候选（相对仓库根）：`.godot-integration-local/standalone-candidate-20261103`。该目录为未启用候选，不纳入 Git。补丁及回归脚本是可审查的 Git 交付内容；旧生产包保留。没有执行提交、推送或合并。

验证：`project/runtime/python/python.exe tools/test_olympus_standalone.py CANDIDATE_ROOT`。10 项隔离测试覆盖无上游候选验证、缺源更新拒绝、待审正式运行拒绝、文件增删改拒绝、临时合成批准后的正式验证与 Node 上下文、重写 lock 后的指纹拒绝。合成批准和事件只存在临时测试目录，未写入生产数据。

结果与完整候选摘要：[验证记录](../data-collection/standalone-runtime-verification-20261103.json)。140 个源文件、130 个分发文件全量一致，语法与质量归属检查通过。只验证这些框架行为；没有声称真实模型供应商或整个 Godot 流程已重新验收。

## 交付边界

修改了批准指纹内的分发接入，需要对最终三个候选执行独立审查并批准后才能切换。历史精确批准保持原件，不能改摘要复用。候选摘要及审查证据以最终验证 JSON 为准。

GitHub 新建工具返回 403，本机无可用 gh/认证；随后针对现有 #7 的进度评论被自动审批拒绝，理由为未明确授权向该目标发布具体修复细节。未通过其他通道重试发布。工单远程状态没有更新，不把本地关联当作远程回执。远程回写需用户明确授权目的地和上述进度内容。

## 历史独立审查与旧候选摘要（已被新基线替代）

[独立审查](../data-collection/standalone-runtime-independent-review-20261103.json)通过，未发现阻断问题；独立复跑10项回归和额外4项负向探针通过，冻结纲领逐字未变。local_runtime.py 单独输出仅表示声明清单一致；完整运行仍需候选指纹、准入及宿主权限。

| 对象 | 历史候选精确摘要，不再请求批准 |
| --- | --- |
| Athena | `d5b42a1874d969448324f984b359a51d03bd2f46ae289fc11bd06fcb5a973885` |
| Themis | `d2f3fc5c9fa7bb5e44a05a0e038fb4ce6911e03e67fe0aee87642559479901bc` |
| Hermes | `7bd90acd78b4d6e67c05bec6978c0b8ffc1dd7e0159ace6e792a5b8fb2cbbce8` |

此前拟申请的范围仅为上述本地定义修复候选及替换当时的 Olympus；该申请现已失效。后续组合候选须另行复审和批准，宿主工具权限、真实模型调用不由此授予。独立运行修复尚未部署，不能宣称运行故障已消除。

Git 状态：本次补丁、回归脚本、文档、证据及真实事件已暂存；Hermes git-check 为 tracked（54事件/57数据文件），尚未提交。提交候选 Issue 门禁尝试因宿主缺少 gh 可执行文件失败（WinError 2），不声称门禁通过。补丁索引字节与工作区完全一致，git apply --check 通过。
