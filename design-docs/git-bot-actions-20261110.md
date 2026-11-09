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
