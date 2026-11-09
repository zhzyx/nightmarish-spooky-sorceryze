# Git bot 与 Actions 故障并行修复

日期：2026-11-10（Asia/Shanghai）。所有仓库路径以仓库根解析。

关联原工单 [#426](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/426)，稳定需求 ID `daqian-direct-dfb3577984bfc0915d62`。用户在本次 Codex 会话明确要求推进和修复所有 Git bot / Actions 问题，并行处理多个任务；当前操作者 Sail-Li 的仓库权限回读为 WRITE。本次接续 Actions 和 bot 故障范围，原工单其余本地或业务验收保留原责任链。

## 范围与验收

从已回读 main `40df26164b8b6298902bfa44cedc29cf35828775` 隔离工作树，不更改其他工作副本。并行核对最新失败、bot 工作流和历史故障单；已复现缺陷直接修复、独立审查并按正式门禁交付。历史失败须对应原动作、候选和实际成功证据，不能仅凭业务 Issue 关闭或主线最新 CI 成功判定恢复。

当前实际修复目标为 Windows runtime simulation 的 C# fixture 冷启动超时：push run [42703106343](https://github.com/zhzyx/nightmarish-spooky-sorceryze/actions/runs/42703106343/job/129452946744) 在首个 fixture 的 `csc.exe` 编译超过 60 秒。将两个 fixture 编译入口的等待上限调整为 180 秒，仍有界、失败退出且不自动重试；超时和非零退出报告 fixture 阶段、编译器和失败信息。范围限定 `tests/editor/run_runtime_setup_simulation.py` 和 `tests/editor/runtime_selector_fixture.py`，不改产品权限或引擎实现。验收包含语法/格式、失败和成功分支、独立审查、实际 Windows CI、精确候选及 main 回读。

PR [#695](https://github.com/zhzyx/nightmarish-spooky-sorceryze/pull/695) 的 PR run [42703123431](https://github.com/zhzyx/nightmarish-spooky-sorceryze/actions/runs/42703123431/job/129453081279) 已通过中断及回滚用例，随后因 `framework/framework-manifest.json` 与 `tools/gonggong_runtime_policy.ps1` 的已审摘要不符而正确拒绝。此问题单独归入 [#696](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/696)：须由该候选发布者接收，在完整框架候选内审查并更新绑定，再复验宿主；当前 main 的文件与 pin 一致，不把未合入的框架摘要写入本候选，也不删除或自动刷新验证。

## 并行执行与证据边界

当前宿主实际启动三个原生子 Agent：`runtime_ci` 排查和修复上述 fixture；`bot_workflows` 核查 bot 并独立复核 fixture 差异；`historical_failures` 逐单核对历史恢复证据。原生启动及终态回执由当前宿主持有，实际用量和子 Agent 观测型号未知。司南 session 要求的继承型号核实端口尚不可用，该步骤保留未完成；本次原生工具调用不冒称已通过司南 session 的模型目录或持久认领验证，也不释放其他会话占用。

bot 核查发现历史 Kuafu 零作业失败 `42674078883`、`42673940739`、`42673606552` 与当前成功运行的工作流/脚本字节相同；API 未提供根因，保留未知。现有 bot 23 项回归通过，尚无足以修改当前 bot 实现的复现证据。关闭历史故障单须另留具体回执，原父工单和业务验收独立核对。

本次源头修复合入并取得 Windows 定向回执后，关闭其已满足验收的故障范围；其他候选的精确准入、原操作复验或交接缺失继续在原单保存责任者与恢复条件，不将阶段性提交报告为所有问题完成，不新增周期扫描。

## 交付后回读

修复 PR [#697](https://github.com/zhzyx/nightmarish-spooky-sorceryze/pull/697) 的签发 head `bbb36063af3b5e80ffba4900c8d6f9c3c7dc0e70` 在 push 和 PR 的适用检查全部通过后，由 Sail-Li 正常合入 main `392ef366255fb1815a8e1cc2a6d8b0c8ece58c84`；远端回读确认祖先关系。Windows PR run `42706022786` / MSVC job `129463174664` 的实际工件覆盖 3 个中断、5 个 journal、10 个部署场景，以及缺失 Python 配置后续接原请求，结果全部通过。编译器超时与非零退出保持失败，宿主 policy 变更/缺失拒绝测试仍通过。

按原故障范围逐张核对源修复、原动作或编译器/断言和主线验收后，#629、#513、#468、#467、#458、#396、#614、#660、#675 均已写回具体验收评论，并回读为 `closed/completed/status:done`。完整回执与工作流清单见 [采集记录](../data-collection/git-bot-actions-recovery-20261110.json)。本次九张历史故障收尾未改动其原业务父单；#426 的误关闭与纠正见下段。

#696 仍等原发布者接收完整框架候选并核验摘要；#255/#264/#278 缺原诊断或原操作复验；#662/#525/#556/#563 剩余原宿主账号、原操作或业务验收。#426 继续开放。[最新原工单进度](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/426#issuecomment-6752439146) 是本轮收尾前的状态，源头修复交付回读以本节及采集记录为准。

证据提交门禁发现 PR #697 的英文否定句仍含关闭关键字，合入时误触发父单自动关闭。已通过权威关闭事件确认来源为 #697，改写 PR 说明、重新打开 #426 并回读为 `open/reopened/status:in-progress`。之前 Diting 事件中的父单开放是未回读的预期状态，现已追加 `git-bot-parent-state-correction-20261110` 纠正并保留原件；源头修复、九张已验收故障和剩余范围没有变化。后续 PR 说明使用状态陈述，避免把关闭关键字放进否定句。

## 原发布者接续后的最终范围

原发布者已用 PR [#699](https://github.com/zhzyx/nightmarish-spooky-sorceryze/pull/699) 在完整候选内更新框架清单 pin，全部 10 个受信文件摘要一致，验证函数未变。精确 head `e19d4a6be4049240661c1ce66f5bfb2e631bdac3` 的适用检查全部通过；PR run `42708326425` / MSVC job `129471155588` 的工件确认 10 个部署、3 个中断、5 个 journal、policy 变更/缺失拒绝及原请求恢复均通过。原发布者已合入 main `9789559ac15830cb211ea6d1e122c1b8acc62cb3`，#696 已回读为 `closed/completed/status:done`。详见 [新增采集回执](../data-collection/git-bot-host-policy-recovery-20261110.json)，旧的待交接快照保留为历史。

本轮合计验收关闭 10 张故障单。仍开放的 #255/#264/#278 缺原诊断或原操作证据，#662/#525/#556/#563 保留原宿主账号、原操作或业务验收；#426 保持开放。最终资料在最新 main 上整合，替代只覆盖前九单的 PR #700，没有改动原发布者的工作树。

沿新主线的复盘入口，在 `github-issue-delivery` 能力域召回结果为空后，将父单误关闭的纠偏记录为 `explicit-parent-state` 候选方法，附下一张同类工单的可证伪试验；尚未登记为已验证或全局规则。

## 缺失证据处置的新决定（2026-11-10）

用户明确要求：缺少则判断处理方式，已认定无法处理则直接关闭。按此授权重新核对原七项，区分修复验收、终止历史追踪及当前仍可处理的业务，不把信息缺失本身判为永久不可修复。

- #255/#264/#278 无法恢复原错误、原工作树/index/环境或原事件，已逐张以 `cancelled/not_planned` 关闭，根因、修复与原候选复验保留未知；新证据或新复现可重新关联。
- #563 的长期谛听问题已有专责 #561、其余两类旧现场已有 #582/#600 验收，停止重复 bot 追踪并以 `cancelled/not_planned` 关闭。#561 草稿仍暂停且未交付，#534 业务仍未完成，没有接续或取消这些业务。
- #525 找到此前遗漏的 #526 最终验收：PR #529 主线树与验收树一致，Windows 编辑器完成 55 工单及两次启动的创建、开工、重复交互验证。已按 `done/completed` 关闭；原 #518 的 planned 不再作为这项修复未完成的证据，也未自动执行原业务。
- #556 保留写实人物、参考图、多视图和有机质量验收；#543 在本轮加上仓库 tenant 后 intake-only 实测通过，不能代替原候选或视觉验收。#662 保留真实 CodeBuddy 官方账号与时延验收，账号认证是可恢复前提，当前不能判定永久不可处理。两项继续由原业务责任链承担，明确下一动作已写回原追踪单。

本轮新增关闭五张：一张修复验收、四张停止追踪。合计 11 张验收完成、4 张终止历史追踪、2 张继续开放；#426 首页已更新本次用户决定和剩余责任。本轮逐单评论、权威状态回读、入口实测及保留范围见 [处置记录](../data-collection/git-bot-disposition-20261110.json)。
