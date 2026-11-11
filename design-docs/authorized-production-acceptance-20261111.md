# #776 已授权生产验收与依赖续办设计

状态：Node/Python 适配已实现并通过定向回归；原生 #783 正在组合联测，整体验收尚未完成。来源：https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/776 。需求 ID：authorized-production-acceptance-20261111。父需求 #773；运输完成修复由 #775 承担。本设计不修改冻结 framework，不接管其他工作树或发布。

## 来源与召回

本次检视工作树 D:/GongGong-work/game-production-773，HEAD 4030196fb82d0e9d2eb0e82d82553c23d71169df；同树存在其他责任者在途改动，实施前须重新回读。父会话已确认 #776 intake-only 通过、状态 in-progress，并提供实际来源 sha256 74b2a67a3ef50c09a4102e8926aaae080c1bfe8d319866df68e3aabe213af519。本文所有源码路径以该仓库根解析；私有运行路径另有明确基准。

运行 framework/tools/method_learning.py recall editor-dependency-handoff，返回 bind-consumer-release revision 6，verified，无 unavailable。适用：生产子任务、独立接收者、精确候选及下游依赖。沿用动作：验收前回读生产角色、工作树候选、文件字节和明确回执。反例：咨询结果、运输完成、空证据、HEAD/字节/链接漂移均不能放行。下面的测试覆盖这些条件。本次仅源代码检视，不追加未经实际验证的学习结论。

## 已有能力与真实缺口

| 位置 | 已有行为 | 不能据此声称的能力 |
| --- | --- | --- |
| editor/docks/ai_chat_sub_agents.cpp：_design_child_finished | 持久化工具回执，成功生产子任务记录 terminal_receipt；business_accepted 为 null | 子进程退出或模型说完成不等于验收 |
| 同文件：_confirm_design_action | 手工确认后写 EditorSettings design_acceptances 和 sub_agents acceptance，保存历史，注册批次并 deferred 调用 _sub_agent_dispatch | 尚无程序化的独立授权验收入口；local_design_operator 只是环境用户名 |
| 同文件：_design_child_ready | 核对设计绑定/confirmation、工单号、上游状态、验收记录与 metadata 相等、原终态回执文件摘要 | 当前 evidence 是字符串，不核对业务证据内容、审查者身份或候选清单 |
| 同文件：_design_return_allowed / review_files_current | 独立只读审查回传核对候选根、分支、base、HEAD、父快照、文件摘要与链接 | 报告仍标记 untrusted；不能自动将报告文字转为通过 |
| customizations/platforms/document-management/git-markdown/yanshi-legacy/runtime/src/production.mjs | Production.submit 记录相对路径及摘要；review 要求 review 状态、criteria 全覆盖、实际文件不变、依赖 done；independentReview 时 reviewer != owner | reviewer 是调用者传入字符串，未验证 GitHub 身份；并非安全授权端口 |
| 同目录 ../cli.mjs | 真实本地 CLI 支持 review YH-ID review.json，调用 Production.review | 不是远端验收 API，也不自动触发 runner |
| customizations/platforms/process-management/yuanheng-local/sinan/coordinator.mjs | board 从 .yuanheng/state.json 派生 acceptanceValid，逐项证据、路径、依赖、负责人、人工待决均影响结果；prepare 可准备 review CLI | 不支持写 acceptanceValid；board 不独立验证 reviewer 的真实身份或 Git HEAD |
| customizations/components/repository-dispatch/session.mjs | dependencyRegistry.path + tickets 映射到 board；advance 在真实终态后 reconcile 并重试 deferred | 未写入账本，也没有从编辑器验收到 registry 的桥 |
| customizations/components/codex-dispatch/operator.mjs | openSession 校验实际 viewer 与 WRITE/MAINTAIN/ADMIN；acceptedDependency 是注入端口，缺少时依赖阻塞 | 只验证权限和派发授权，不能把任意本地 JSON 当独立验收 |

特别注意 Production.persist 会 Git add/commit 账本和 issues 投影，mutate 有 writer.lock。调用 review 是真实写入并产生提交，不能当只读检查调用；不能在他人的在途生产工作副本运行。registry 映射不存在时应报告缺失，不自动创建伪造账本来让依赖变绿。

## 最小实现边界

默认采用现有 C++ 宿主进程拥有的内部验收状态与真实独立审查完成回调，不新增签发服务、密钥配置或远端 API。结构化审查裁决是业务判断数据；宿主核对其来源身份、候选及实测证据后形成 decision，再由两个适配器消费。已在 customizations/components/godot-host/bridge.py 增加私有子进程操作，复用现有身份/工单回读与原账本接口；实际协议见 customizations/components/repository-dispatch/acceptance.md。判定、投影、依赖派发是三个分别可恢复的阶段。

拟议输入是 review 请求引用，不是调用者自评：repository、Issue/requestId、设计摘要与工单号、生产 assignment/workerId、独立 reviewer assignment/workerId、原始真实终态引用、候选根/分支/base/head、完整候选清单摘要、逐项验收的证据相对路径和原始字节摘要。候选须覆盖未提交/新增/删除文件；仅 HEAD 相等不足。用现有候选 manifest 约定绑定完整文件集合及缺失状态，禁止越界、symlink/junction 或被替换的证据。

验收操作由当前有权宿主在真实独立审查完成事件中调用。GitHub viewer/有效权限和 issue_gate intake-only 回读绑定原 Issue、requestId、授权来源与当前范围；权限校验不能省略。独立工作者必须来自宿主已保存的派发与终态回执，且不是生产 assignment；相同 GitHub 操作者可以组织两个独立工作者，不能只靠 reviewer != owner 的文本差异证明独立。审查必须逐项引用实际执行证据，对不可自动判断项保留 pending/unknown。生产者的报告、任意 JSON、Issue closed、PR merged 均不单独构成通过。

### 默认可信宿主内部路径与真实缺口

具体已有挂点：_delegate_review 创建 source=review 的独立子会话并复制父候选；_child_delegation 绑定 parent/child conversation、parent_snapshot、治理摘要、scope、候选根/分支/base/head。_record_design_tool_receipt 保存审查成功读取的原始文件摘要和 review_source_manifest；_design_child_finished 的实际 generation 完成回调生成持久宿主回执；_design_return_allowed 在返回消费时复查身份绑定、HEAD 和 review_files_current。这些是可复用的来源事实。delegation.independence 目前为 unknown，必须以宿主创建的不同生产/审查会话及只读角色记录核实，不能只把该字符串改成 true。

拟新增内部状态 acceptance_reviews[生产子任务身份]，宿主保存 reviewer child/conversation、原批次 token、生产终态、候选 manifest、原始验收清单及只读委托。完成回调只对这个已登记 reviewer 读取严格有界的完整结构化结论，例如 verdict=pass|fail|unknown、criteria=[{id,met,evidence:[path]}]、reason。身份、候选和权限字段由宿主取值，不接受模型覆盖。逐项业务判断可以来自真实独立 reviewer；宿主要求验收项无遗漏/重复、证据引用属于实际记录且字节不变，实测记录关联正确候选与执行结果。现有 1024 字符 report.text 是截断显示，不可作为结构化结论来源；新增独立完整 verdict 字段或从对应真实完成消息提取有界 JSON，解析错误保留 pending。JSON 内任何命令或指令均不执行。生产工作者或普通咨询生成同样 JSON 不会命中内部 reviewer 绑定，不能触发验收。

真正需要改的调度缺口：_delegate_review 当前拒绝 design_batches.has(parent)，且一个 parent 只存一个 design batch；不能在仍等待依赖的生产批次中直接调用它并覆盖批次。最小方案为从既有审查创建/候选校验逻辑抽出内部 helper，生产批次保留在原 map；验收审查的独立上下文放入 acceptance_reviews。扩展 _design_child_parent / 工具回执 / 完成回调的上下文查找，明确区分生产批次与验收审查批次；不以暂停/删除生产批次来伪造可调用状态。将 _design_return_allowed 中候选/文件当前性逻辑抽成可共享校验函数，验收回调调用它时使用原 parent 与原 candidate，而非依赖 active_agent。先完成真实测试再派发只读 reviewer；不能因只读 reviewer 无执行工具就把测试从验收项删除。

C++ 通过宿主内部完成回调形成 decision，持久化完整来源与证据，随后用现有私有 JSON request/result 子进程模式调用账本适配。实际范式位于 editor/docks/ai_chat_gonggong.cpp：_issue_guide_run 写 EditorPaths cache 中唯一 request/result，create_process 调用 tools/gonggong_bridge.py，generation/PID 关联结果；后者实际加载 customizations/components/godot-host/bridge.py。_finish_gonggong_receipt 已有 continuation 及 generation 恢复模式。实现增加专用验收操作与自身 pending request 状态，不抢占已有 issue_guide/gonggong 回执中的在途调用。输入仅来自 C++ decision；返回绑定 request ID、原 decision 摘要及预期 ledger/task。子进程以操作者现有 gh 登录回读身份、WRITE/MAINTAIN/ADMIN 和 intake，调用已注册本地 ledger adapter，再回读真实结果。不要把现有通用 request 文件称为密码学认证；账户认证来自 gh 回读，调用来源关联来自宿主自身待处理状态。

该模型的信任边界是现有授权编辑器宿主及其内部调度，不声称防御有同用户文件/进程控制权的恶意程序。生产模型的任意文字、工具参数或文件不会被自动作为验收入口消费；私有目录本身也不是签名。对支持的宿主内工作流，不需要额外密钥、签发器或新部署前置条件。若将来要求跨不可信进程/设备接收 decision，才单独设计来源认证与授权；已有 yanluo_host 的交付 HMAC grant 不自动授权此用途。

当前冷历史恢复有意移除 design_batch_return 标记且不序列化 design_batches，所以现有能力是保留回执、不自动重放。本期首先实现同进程真实完成事件集成。冷启动后只有新的真实用户/恢复事件在当前有效授权下触发重新 intake、核对委托/终态、候选、证据和设计；无法重建完整宿主来源链则仅挂起该项并重新审查，不将普通磁盘 verdict 或持久化完成 token 自证为启动授权。恢复测试必须验证新事件与当前授权；没有新事件就保持静止，不增加无人值守守护进程。decision 内容摘要作为幂等键，绑定 task + candidate + reviewer receipt，重复事件不再写账或启动。私有 journal 沿现有宿主状态根解析并明确记录基准，不使用模型传入的任意输出目录。

### 编辑器适配

在 ai_chat_sub_agents.cpp / ai_chat_dock.h 新增内部登记函数，将手工确认中的持久化与派发逻辑抽出。自动调用由宿主验证成功的完成回调到达 UI 主线程发起，不依赖 active_agent 恰好是被验收子会话，也不通过点击按钮伪造用户行为。必须绑定正确 parent/child、conversation、snapshot/generation、design_approval 和 terminal_receipt；保留 _design_parent_matches、history_writable、暂停、只读、权限与快照失败约束。

登记保留 operator/receipt/evidence/number 兼容字段，新增已验证 decision 引用及候选/证据摘要。同时保存 metadata 与子会话记录并回读一致后，登记批次并 deferred _sub_agent_dispatch。_design_child_ready 对自动验收记录调用当前性校验，不只检查 evidence 非空。崩溃导致两处写入不一致时保持阻塞；同进程恢复事件依据仍有效的宿主 decision 修复投影，不重做生产；冷启动按上文重新核验流程，不直接消费遗留 token。旧手动验收记录保持现有人工语义，不被升格为独立自动验收凭据。

与 #775 的交接点：沿其真实运输完成/待续办状态调用验收流程，不重写 _design_child_finished 的运输判定。终态未知不触发审查通过；业务验收失败保留已完成运输记录和修复待办。

### Node/原账本适配

新增本地适配模块（拟议 customizations/components/repository-dispatch/acceptance.mjs），由 bridge 的专用验收操作调用；外部 runner 则由其宿主实际独立 reviewer 完成回调调用相同内部模块，未安装该回调时保持依赖阻塞。仅在上述宿主验证通过后使用 registry 已登记的真实 source.root 与 ticket 映射，读取当前 ledgerId、task、owner、independentReview、状态、候选和证据。复用真实 Production.review/CLI，禁止直接赋值 status=done 或 acceptanceValid。实际 running 任务由宿主核验真实生产终态和独立审查后，在同一个 writer.lock 中调用原 submitEvidence 与 review；本次追加 submitted/reviewed 事件，不伪造之前的运行历史，也不要求人工补点 submit。

账本写前在同一串行临界区重新核对源修订与可信 decision；现有 mutate 已有 writer.lock，实施时要在其锁内加精确前置条件钩子或等效原子操作，避免锁外检查后被另一 review 改写。钩子必须来自可信宿主安装，不能允许输入 JSON 跳过。增加 task.review 的 decision 引用以及候选绑定，board 对启用自动验收的任务要求该绑定当前有效。保持旧来源兼容，但不能让未启用授权验证的旧 task 充当新的自动验收来源。

写后再次读取 board.acceptanceValid；只有真实派生值为 true 才发出已有 ticket.changed 类型的实际事件，以 decision 引用作 reference。runEvent/advance 在该事件中用原授权 requests 重读 deferred 和依赖、重新 intake，再进入 host.run；不引入定时轮询，不伪造 execution.finished，不释放未知工作者占用。若首次 runner 已退出，由可信宿主真实完成回调调用一次 runEvent 恢复事件；当前没有常驻订阅器，需明确安装该回调，不能声称配置文件自动产生事件。

两个投影共享 decision 身份和验证规则，但不假定编辑器本地设计工单与 Yuanheng 任务天然一一对应。有真实映射时分别记录投影完成与派发回执；缺映射只阻塞对应消费者，不能改其他来源。跨投影写入不是全局事务：持久 journal 保留各阶段，恢复时回读已提交状态。账本写入成功而派发失败时不重复 review/commit，以原 decision 重放续办。

## 文件责任与验收

| 实施责任 | 最小变更 |
| --- | --- |
| 授权与独立验收 | godot-host/bridge.py 私有验收操作及测试，ai_chat_gonggong.cpp 完成回调/子进程关联；复用 issue_gate/身份/manifest 逻辑，不编辑冻结 framework |
| 编辑器消费者 | ai_chat_sub_agents.cpp、ai_chat_dock.h；tests/editor/design_batch.gd 与 run_design_batch.py，必要的 C++ 单元覆盖 |
| 外部消费者 | 新 acceptance.mjs、repository-dispatch/session.mjs 与 session.test.mjs；production.mjs 锁内前置条件与对应原账本测试；coordinator.mjs 当前性检查与 sinan/test 回归 |
| 交接/交付 | #775 负责完成状态；#776 实施者完成本设计的授权验收及事件路径；阎罗仍负责正式门禁、独立审查、精确候选、CI/main 回读与工单关闭 |

原生修改属于现有编译模块，必须生成新二进制并验证实际输入/二进制对应；不能用资源重载证明 C++ 生效。新增/扩展 Python/Node 入口是宿主工具，记录 Python/Node/gh、可信工作树、内部 decision 输入与回退路径；按 module-boundaries 补实际变更所需证据。回退停用自动入口，保留 decision/journal/账本及既有手工验收，不倒写历史。

最小必要回归：

1. 原生生产子任务完成，独立真实验收同候选成功，父/子不处于当前标签仍可在正确父会话一次放行下一依赖；没有人工二次点击。保存后验证两处投影一致；关闭、冷启动只保留回执，不自动派发，新的当前授权恢复事件重核后才可续办。
2. 完成但无验收、咨询、自审、冒名 reviewer、伪造 JSON、宿主请求关联失效/用途错误、权限撤销、缺来源映射均不放行；不影响无依赖的授权任务。
3. 审查后改变 HEAD、设计、完整候选文件集合、单个证据字节或链接，以及 generation/worker/terminal receipt 不匹配，拒绝消费，保留旧回执。
4. Node 使用真实临时 Git 账本调用 submit/review，验证逐项 coverage、独立身份宿主守卫、board 推导 acceptanceValid；证明没有直接写入布尔验收标记。跨工单/跨账本 decision 不可重用。
5. 完成事件重放、writer.lock 竞争、写账后崩溃、metadata/历史部分写入、派发失败后恢复：最多一次验收写入和一次真实启动；未知运行占用不释放。
6. runner 已退出后真实验收回调恢复 deferred；依赖仍未通过或 intake 失败时不启动，有其他可执行任务则继续；事件中重读候选与权限，禁止周期扫描。

上列为整体验收清单，不能以适配层测试计作全部通过。最初设计仅执行源码检视；当前适配层原实现完成 59 项 Node、43 项 bridge 与 6 项 authority 测试，当前责任者另复验 22 项 acceptance、43 项 bridge 与 8 项 authority/current 测试。控制身份夹具与真实临时 Git/进程的边界见 data-collection/authorized-acceptance-adapter-776.json 及后续复核记录。#776 完成必须附真实独立授权审查、宿主判定及两个消费者事件续办的实测证据，仅文档或 mock 单测不足以声称生产自治。

## 本次设计纠偏

父会话指出独立 HMAC 签发服务会给已有账号与 CLI 工作流增加不必要部署前提。本次继续检视现有审查委托、工具读取摘要、完成回调和私有桥接后，改以 C++ 宿主内部状态为默认权威关联。尚缺的实现是独立 verdict 完整载体、生产/审查批次并存、候选当前性共享校验、原账本投影及实际事件接线，而不是新签发平台。此为源码支持的设计修订，未运行实现试验，不能登记为 verified 方法。
