# 已绑定生产父任务的阶段结束检查与自动接续

稳定需求 ID：bound-production-continuation-20261113。路径以仓库根解析。

工单：[#1024](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1024)，原生父项 #953，需求溯源 #978。

来源：父 #953 的生产宿主接入尾项，以及用户 #978 全工程 AI/GitHub 接入重构、修复阻塞并持续交付的授权。责任 Sail-Li 当前 Codex 会话。源码审计基于 main 1c8124dc；本次从已接收证据的 main ad79c25d 隔离实现。不接管 #971/#830/#838/#948/#951 的候选或工作副本，不修改冻结 Agent/Skill，不新增后台服务或定时扫描。

## 问题与本次结果

真实生产父会话从工单绑定和已安装 bridge 的 intake 进入模型，HTTP、Codex CLI、CodeBuddy 的最终回执统一进入 AIChatDock::_request_completed。当前完整终答结束当前聊天回合；这不等于错误关闭工单，但没有一般父任务的原始完整验收与下一动作检查。已存在设计子项的独立验收、精确候选核查、实际完成事件和有界修复，不复制一套替代账本。

本次交付一个实际接入生产回调的阶段结束检查：对于完整任务契约已经由宿主确认、验收与执行映射可核实的父会话，在模型准备结束时核对真实状态，仍有已授权且可执行动作时自动推进现有执行入口。必须实际完成“阶段 A → 核验 → 自动推进 B → 独立验收”的链路；只增加提示词、返回 pending 或建立尚未消费的配置不算完成。

普通咨询、未绑定聊天、仅解释、独立审查者和子工作者维持各自已授权语义；不能把所有完整终答都变成续跑。缺少完整验收映射时明确保留未接通状态，不猜测任意自然语言 Issue 已被完全覆盖。本子项不关闭父 #953/#978 的其他宿主、模型行为、真实供应商、平台与完整业务验收。

## 必需的绑定与实现边界

1. 在被接受的生产任务开始时，由真实宿主保有任务绑定：仓库/操作者/Issue/request/来源修订，原完整验收定义与稳定 ID，候选/产物范围，原验收到已登记任务及现有执行路由的完整映射，会话/snapshot/generation/取消状态，现有工具与模型授权和有界无进展预算。复用当前已确认设计和登记账本。定义、覆盖或来源不全时不启用自动完成判断；生产者自己写的 done JSON 或仅 closed Issue 不形成验收。
2. 在共同终答回调的清理和 terminal 发出前启动独立的异步安装宿主检查，保留本轮答案与动作回执。独立 nonce/generation，不能复用或覆盖正在运行的 intake/acceptance 作业。当前 source/criteria/candidate/actor 漂移使旧证明失效；执行前再次检查需要的当前权限。
3. 结果使用有限的宿主动作：已验证全部验收与必要交付、当前可执行的既有动作、等待已知事件、必要决定、取消/撤权/预算停止、未知副作用需要回读、无进展排障。不得让模型输出任意 shell 命令或自报完成作为控制依据。acceptance-current 只证明候选当前性，不能当作账号授权或业务通过。
4. 真实接续复用已存在的独立验收/修复、受配置约束的派发，或原父会话入口；父会话重新请求前重新读取真实工单与治理上下文。CLI 继续保持本机工具边界，不安装全局 Stop hook，不修改 Codex 桌面调度。
5. 等待已有工作者/CI 时保留准确标识与占用，由对应实际事件唤起本次活跃宿主；没有事件传输就如实待处理，不能承诺已停止进程自行唤醒。副作用回执未知先回读原命令/候选，不重新执行。
6. 相同权威证据下的重复终止须有界，聊天文本变化不算进展；重复事件幂等，不重复模型/工具/PR动作。取消、暂停、预算耗尽、权限撤销与迟到回执处理保持原边界。超出有界恢复时向既有夸父路径报告一次具体故障，保留证据，不无限续跑或切换模型。

## 验收与交付

- C1：可信完整任务绑定真实生成并由共同回调消费；绑定不足、部分覆盖、同名其他 Issue/候选、生产者伪造 done、closed-not-planned 均不能被当完整验收。
- C2：至少一个真实已登记父任务在第一阶段结束后，无人工“继续”自动执行一个已授权下一动作，独立验收覆盖原完整定义后才结束。隔离测试可用受控模型/远端接口，但必须运行实际原生回调和安装宿主链；受控证据不泛化为所有真实模型成功率。
- C3：原 HTTP 与 CLI 归一化终答均消费同一控制逻辑；普通咨询、只读、子工作者/独立审查、人工保留决定、排队 steering、工具拒绝与显式停止不会被错误续跑。
- C4：当前权限、来源、验收定义、候选及会话代次变化拒绝旧动作；检查后/启动前及异步等待中的取消阻止后续执行，保留已发生或未知副作用。
- C5：有界无进展、重复事件、真实等待/完成回调及冷重启的可信状态边界经有区分力的测试验证；不把磁盘文件自行恢复为 live reviewer/owner。
- C6：原始故障与修复结果分开留证；必要 Python/Node/C++ 和私有 headless 原生验证、独立审查、正式门禁、精确候选 CI、main 回读和本子项验收关闭。未经验证不切换有效安装。

实现可调整内部文件划分以复用现有能力，但不得缩成仅策略函数或 pending-only UI。若某个平台/宿主确实没有完成事件能力，记录真实缺口并继续可实现路径；本子项与父项不得据局部成功误报全完成。目标平台先覆盖当前 macOS 原生宿主及仓库适用 Windows CI，真实供应商/跨模型效果沿父 #953 的原范围保留。

## 具体实现与验证约束

完整绑定的可用生产入口是既有设计定版原生确认；操作者在原 Issue 中按 Godot 宿主 README 的 `gonggong-parent-contract` 格式明确列出完整原始验收映射，设计以 `gonggong-parent-completion:v1` 标记明确选择该契约。安装 chat intake 回传当前真实账户/原始来源摘要，原生确认将其与最终设计的完整字节及全部已登记工单一起绑定。原生会话内另持有确认对象，持久化的 approval 不能重建该对象。不存在从自然语言自动推断完整覆盖的默认行为。

确认后实际启动父生产准备阶段；正常模型请求仍经过原工单/框架上下文与模型、工具权限。共同完成回调先保留答案，再通过独立 nonce、live 文件和 generation 发起安装宿主 check/authorize。可执行动作只调用既有 `_sub_agent_dispatch`，实际子会话/独立验收完成回传后，保留活的原完整映射再次核对。验收 currentness 检查单独等待其实际回执，不能把其首次返回 false 当作已拒绝的验收。每次父终答使旧 currentness 缓存失效，最终完成需要原完整映射中的全部 live 独立验收，包括明确的 delivery 项。

来源比较包含 Issue 标识、正文、标题、状态及 authenticated actor，正文/验收/身份变化使原确认失效；评论计数或更新时间本身不是需求修订。候选在 check 与 authorize 间必须一致；执行状态由原生已登记子会话、真实 terminal receipt 和 live reviewer 得出，模型终答不进入控制判断。真正进展只取已登记执行和验收事实，不取聊天文本、审计新增或未验收的代码变化。

构建归属：C++ 修改属于既有 editor 原生构建输入，需要重新编译及私有 headless 原生验证；新增 `customizations/components/godot-host/parent_completion.py` 属既有 **host_tool**，由安装 bridge 内部 action 实际消费，依赖已安装 issue_gate、acceptance candidate 捕获和 owned_process。未增加 Agent/Skill 定义、独立运行包或新任务账本。测试文件不属于生产模块。回退恢复上一已验证二进制与相应宿主文件，保留真实工单和原回执。

本次已召回本租户 `editor-dependency-handoff`：`await-terminal-observers` rev5、`bind-consumer-release` rev15、`review-context-and-source-evidence` rev4 均 verified。前两项分别对应真实进程/回执观察后释放、精确候选与独立验收后放行依赖；第三项仅在原生独立审查读取上游上下文时复用，普通咨询不套用该契约。沿已有方法追加测试，不建立新治理门禁。

受控原生 fixture 使用原生确认、实际共同终答回调、安装适配器、真实临时 Git 候选、真实命令/读取及既有 live 独立验收；仅模型与远端 GitHub 传输受控。其完整范围是 fixture 已声明的命令执行/文件交付，不证明真实供应商效果、任意 Issue 自然语言覆盖、GitHub main 交付或父 #953/#978 完成。真实跨平台、构建、原生场景和交付结果以本单 evidence 实际回执为准。

已绑定父任务的 `complete_delivery` 复用相同检查，不允许准备阶段以生产者清单绕过独立完整验收。通过后原生宿主根据原始映射和 live decision 生成清单，保留原工具批准；批准后适配器再次验权、核对候选及独立证据，实际调用原 journaled finalizer。受控 Python 集成运行真实 Node 验证器、真实 finalizer/journal 与既有 activation retry，GitHub/main/signed 读回为受控边界；这与原生 fixture 的非 Git 交付范围分别报告。

关闭 Issue 后丢失回执的恢复使用显式安装命令 `parent-delivery-readback` 及保留的原始 request，而不再要求 open intake。它仅核对同一原账户、nonce、完整交付 scope、已观察 attempt、main/CI 与原契约，不重放副作用，也不还原 live owner/reviewer。原账户失去 WRITE 后仍可在实际读取权限允许时回读。已核实的 activation_pending 沿现有 delivery-retry；未知激活不擅自重试。

交付验证范围：原生 fixture 的完整任务是命令/读取及文件交付，实际覆盖 native callback、安装适配器、独立验收、早期交付绕过拒绝及交付暂存时取消；Python 集成运行真实 Node 验证器与真实 journaled finalizer，远端 signed/main/CI 为受控接口。追加的 post-acceptance 原生场景已实际运行 C++ 重建 guard/清单、原工具授权、安装 parent-delivery、独立子进程 finalizer 及 journal，成功路径取得原生 complete；执行中 Stop 和编辑器销毁路径确认子进程退出且释放延迟写入条件后没有追加写入。远端账户、signed/main/CI、Issue 写入和 activation 端口为隔离受控接口，不等于真实 GitHub 交付。真实 600 秒超时已通过：native timed_out=true、live request 撤销、内层进程退出且无迟到写入；不根据 outer guard 的 cancelled=false 推断信号先后。活跃 source 检查要求原 Issue open，故要求该 Issue 已关闭才能独立验收的循环契约不受支持；原 Issue 最终关闭沿既有 finalizer，在独立业务/main 证据之后执行。

模块边界实测由父责任者执行：同一二进制 `725f339115fbb462ed4d36b47ae2d3823d10ea4bc4366a1ad05bdbeca759adcf`，私有安装源码快照原 adapter 正常接续通过；仅私有 adapter 明确拒绝后，原生实际回读 `PRIVATE_HOST_TOOL_REFUSAL`，状态 decision_required、Stop 已释放、无子任务或业务验收；恢复原 adapter 精确字节后再次正常接续通过。生产 adapter 与二进制未变，私有快照已清理。最初拒绝实验发现 Stop 残留启用，原始失败保留；修复清理后 v2 才通过。详见本单 data-collection 记录所指向的原始报告，不把私有拒绝探针当作业务实现。

有界停止的追加实测：受控模型连续提出提前 `complete_delivery`，旧二进制在实际调用一次夸父后仍发出第四次模型请求，原生复现报告保留。修复仅让 `dispatch_registered` 的提前拒绝继续模型；wait/decision/readback/Kuafu 状态将未执行提案记录为取消，关闭工具协议条目后沿既有 held/terminal 路径停止。新二进制 `b12fdd311dac10bf36954e17a909f53f76cbce126e2fc43ba22f57c2f2de740c` 的同场景恰好三次模型请求，实际已有 Kuafu local-only consumer 一次、持久 incident 一份、36 条真实事件，无子任务、无业务验收、控件释放；local-only 的接单仍是 pending，不声称远端夸父已处理。C++ 与 fixture 的精确增量及受影响场景复验分别留证。

实现工作者交接时验证归属（修复前的历史范围）：本地 Python/Node 套件共 129 个测试通过（parent 23、bridge 48、Python acceptance 8、Node acceptance 22、既有 finalizer 15、既有 retry 13）。13 个受控原生场景在已记录二进制上分别通过：最后 b12f 二进制重跑全部五个受影响场景（有界停止、normal、提前交付拒绝、两种暂存交付工具撤权）；其余普通 CLI、Stop/consultation/currentness、冷启动与模块 update/revert 沿未变代码路径复用 725f 的精确报告，不声称它们全在 b12f 重跑。CLI 使用可执行私有 provider，经真实安装 Codex bridge 与原生 CLI 回调；模型终态之后才恢复 fixture 的 HTTP 子任务配置，不把人主动切换连接的行为当本场景。原始 fixture 解析/配置失败与实际产品缺陷分别保留。独立产品审查、精确候选 CI 与 main/工单交付属于父责任者 C6，不能由本次源实现报告代替。


## 独立审查后的进程收尾修复

独立审查 R1 实际复现：外层 provenance owner 取消时，内部 finalizer 使用另一个 owned process group；原 bridge 默认信号退出使该组继续运行并产生迟到写入。原生取消入口现先撤销本次 mapped delivery 的 live request，保留 `.original.json` 回读证据；adapter 的 SIGTERM/SIGINT 只置取消标记，让现有 owned_process finally 完成组/Job 收尾，再恢复原信号处理。原始复现与修复后的独立复验均保留，不把外层退出当作内部已停。

补齐实际原生成功链时发现第二个实测缺陷：macOS 保护进程不能执行带 setuid 的 `/bin/ps`，导致正常短命令收尾拒绝。现有 owned_process 改用系统 libproc 读取同一进程组，以显式 zombie 查询、未回收 leader、完整有界成员及第二次一致枚举确认收尾；信息缺失、截断、活成员或成员变化均保留未知。未取消保护 profile，也未忽略 EPERM。Apple 内核接口定义与本机 SDK 对照，独立核查另留证。

owned_process 同时是安装宿主工具和现有 AINative 的嵌入输入。此次真实增量构建重生成 bundle.gen.h、重编译 ainative_editor_plugin 并重新链接；新 binary `62b6d319096f4677f05e48715a31d71bac40de71008a27fd18448e568bc4e1f4` 再次通过完整受控原生交付成功路径。v4 Stop/销毁使用前一原生 binary `61d83b6a66558ef20aaabdfc31d3039aac19f444f5954ae98f97912cea55fe44`，其实际安装 owned_process 与当前字节一致；两次构建的 native 完成/取消代码不变，新增差异是嵌入资源，准确消费范围分别记录。

当前去重后的必要 Python/Node 验证共 142 项：parent 25、owned_process 11，以及 unchanged bridge 48、Python acceptance 8、Node acceptance 22、finalizer 15、retry 13。parent25 的首次追加调用漏配 Node PATH，在 setup 阶段失败；原始日志保留，配置正确重跑 25 项通过。真实保护环境短命令及 pinned zombie/活成员测试通过；独立审查继续核对最终精确字节；600 秒超时原始 history 与追加显式超时断言后验核查均通过。历史 same-binary update/refusal/revert 只证明旧 adapter `1b976…`，不冒充 R1 修复后 adapter 的回执。

主线在验收期间接收 PR #1028 的 15 个 Gameplay 文件，与本候选无交叉；当前责任者归档全部 39 个任务文件后快进到 `d5a77b1d539a9b92a1b81fc84c4df447dab82a7d`，恢复 index 并逐项核对 SHA256 完全相等。该基线真实增量构建通过，新 binary `605ef761816555036198d0112f32eb5f204c4cd2418b2e58a137e4343fa3abae` 再次通过原生受控交付成功路径。实际 CI/main 交付仍须绑定最终候选，不用此前基线的成功代替。
