# 已核实生产后的有界缺证补齐

需求 ID `editor-evidence-completion-20261112`；子 Issue [#876](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/876)，父 Issue [#773](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/773)。路径以仓库根解析。

正常产品生产完成但执行验证证据缺失时，独立审查可返回 `verdict: unknown, unknown_kind: missing_execution_evidence`。完整覆盖原标准：未知项显式 `met: null`、非空字符串 `missing_evidence` 和 evidence 数组；已知项必须布尔 met 及实际读取、绑定候选字节的证据。至少一项确属未知。普通 unknown、身份不明、运输未结束、活跃占用、候选/配置/来源/辅助读取漂移继续阻止续作。

原 unknown 决策单独保存在不可覆盖的 `.unknown-acceptance.json`，附原标准与读取清单；不得改写为 fail 或 pass。`repair_of.mode=missing_execution_evidence` 绑定原执行、终态、审查摘要及唯一 continuation。省略 mode 仍是原 fail 协议，显式 failed_review 归一为相同旧协议。票据键只使用前驱执行，两个模式不能争抢为两个作业。编辑器共用 `acceptance_repairs` 的一次自动续作预算，第二次未知或失败交还原父会话，不循环自动启动。

执行器沿原入口两次验证运输、身份、工单、候选、登记、审查、配置及持久票据；准备阶段拒绝时恢复原资源。已启动或未知后继保留占用，重放只回读。后继生成全新 execution/registration/terminal，完成后必须再创建独立审查，通过既有 pass-only 验收后才释放依赖。通用验收验证器未放宽。

本次复用 `editor-dependency-handoff` 的 await-terminal-observers、bind-consumer-release、review-context-and-source-evidence 三条已验证经验；适用条件是原生产者、接收者、实际候选及读证据均可核实；运输成功、旧候选或外部辅助文件不能作为业务通过。没有新增模块或外部依赖。原生输入为 ai_chat_sub_agents.cpp，须严格重编译对应编辑器；Node 输入为 runner.mjs/repair.mjs，由已有 Node 进程宿主加载。回退恢复旧代码/二进制并保留所有原票据及 unknown 回执，旧入口不自动接受新增模式。

验证：Node 全量工作单测试首轮 63/63 通过；追加运行中/未知后继重放测试 2/2 通过。Python 原生夹具 py_compile 与 Node --check 通过。原生新增 parallel-evidence-completion：真实工作者首次不提供所需执行证据，审查显式 unknown；后继实际写入证据，新审查读取并通过，A 两次执行、B/C 各一次、父回传一次。夹具另核对 unknown 原件、谱系及 A 的两次独立审查。新增 parallel-evidence-exhausted 验证第二次 unknown 不再自动启动且不释放 C。原有 parallel-repair、unknown、receipt-tamper、auxiliary-tamper 和 parallel-config-drift 继续回归。原生编译及同一候选实测由集成责任者串行运行，当前未宣称完成。

此实现仅覆盖受控运输加真实子进程/原生宿主路径。真实供应商组合生产、有效安装和父 Issue 全部验收仍由 #773 跟进；局部测试不替代整体验收。

集成验收的原生场景、独立审查、纠偏及保留边界集中记录于 [#773 续作候选回执](../data-collection/editor-production-followups-773.json)。路径以仓库根解析；正式交付及有效安装状态另行回读。
