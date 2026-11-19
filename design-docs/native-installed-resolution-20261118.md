<!-- native-installed-resolution-implementation:20261118 -->

Dependency accepted: PR1525 merged main84d62281f0c7179369aec4352047a9ba414582a7, all80delivered paths match signedhead and required CI succeeded. Isolated worktree created from that exact trustedmain; intake-only passed. Root accepts source-bound audit and existing-role adapter/continuous/recovery plan. One native implementation worker owns explicit server and workflow files; root retains independent review, build inventory/proofs, actual model/server acceptance and delivery. No live providers or production changes in implementation.

---

<!-- gonggong-request:native-installed-resolution-20261118 -->

# 合契普通入口：已安装冲突消解与无重放接续

需求 ID：native-installed-resolution-20261118；父 #1499，上溯 #1444 / #1382；排障 #1445。沿用用户“开始执行／继续”和完整 AI 链路优先授权。路径以本工单仓库根解析，现有角色分工保持。

源码审计回执 native-installed-resolver-audit.json（SHA256 3137bcfea3bf7aebbcb0c634747db748bebc9611cfd96417e286929616131bbe）绑定 24 文件、9 条静态断言。普通 continuous 路径仅 reconcile 后将冲突标记阻塞；factory resolver 返回 None；安装清单与通用签名 broker 缺少合契角色。reconcile 可能返回后继 plan 字符串，现有 continuous 按字典处理；模型完成到候选落库间也缺只读恢复接线。源审计不算功能验证。

实施前依赖：#1499 的受审运行时/上下文源码 PR #1525 已通过适用 CI 并合入可信 main。完成依赖验收后从 main 隔离实现；不抢占 #951 的共享模型会话源码或 #1343 渲染工作。

实施范围：

1. 复用现有 NativeIntegration、NativeContinuous、NativeCandidates、InstalledPlannerRuntime、签名 runner 与元衡准入。增加薄的已安装合契适配器；不新建模型客户端、调度器、工单数据库或以测试回调冒充普通产品入口。
2. 安装清单当前已有版本 1/2；新版本明确 resolver 命令、身份、精确配置与角色来源，保留旧安装/历史 plan 回读。独立 reviewer 不能与 producer/resolver 共用身份或状态。仅选择实际评估兼容的模型协议；不得把通用 JSON 请求直接交给要求 native_request 的 CLI adapter 后声称多 CLI 已适配。
3. 冻结消解输入包含所有原始诉求/验收、精确产品基线、冲突路径与各贡献原始字节/摘要。严格验证模型返回的 plan/conflict 摘要、唯一编辑集合、删除、路径、字节上限及依赖不变；宿主以已安装 principal 和稳定 resolution key 接收不可变候选。不得静默截断大输入。多修订工具上下文须另有精确授权契约，不能冒用 producer token 或伪造 native task。
4. 普通 continuous lane 调用已安装 resolver，持久跟踪有效后继 plan，沿既有检查、独立审查、阎罗发布和进度闭环。锁不能覆盖模型/构建；无关模块或 main 变化不重跑生产者。真实依赖冲突不能静默自动合并。
5. 外部调用前持久 intent；同 plan 至多一次实际调用。未知/失联保持 held 和占用，不重放。已完成 broker 回执可只读恢复并幂等接收候选；候选已落库而回包丢失时直接回读原 receipt。恢复仍验证精确原始输入和当前授权，不洗白旧在途凭证。

验收矩阵：

- 正常注册/需求 API 发起两项实际冲突贡献，经已安装确定性 broker 和真实派发完成一次合契调用、联合条件检查、独立审查及一次发布，双方贡献和父需求进度正确；不得手工注入 resolver 回调替代该验收。
- 非冲突贡献不调用 resolver；无关需求/评论/状态/模块更新不触发重做或重复模型调用，相关验收变化正确拒绝旧候选。
- 并发重复事件、冷重启、后继 plan 接续及已知 CAS 变更保留原贡献和幂等身份；无 string.get 错误。
- 在 intent 后、模型调用中、已完成 broker 未 intake、已 intake 未回包等窗口注入中断；分别证明未知不重放、已知回执可恢复、物理资源真实关闭。
- 撤销任一原任务授权/合契授权/安装时停止受影响操作，不发布、不假完成，不阻塞独立 lane。
- 错误摘要、额外/缺失/重复路径、路径穿越、越界二进制和依赖偷换拒绝；有效删除可正确处理；独立审查覆盖全部原始验收。
- 新模块实际输入、宿主接口、回退、精确候选独立审查与适用 CI/main 留底完整；不降低原生渲染能力。

根责任者核对实际源码和接口后可在此范围内继续实施，无需再次询问用户。实现者不运行真实 provider、不切换生产、不修改共享冻结定义；真实安装/模型及父级 250 多用户完整验收由根责任者另行接续。小输入消解通过不能声称大上下文、多 CLI、整个 #1499 或父目标已完成。保留原始失败和未知。

授权：codex:01a1e578-49b3-77f3-a3c4-6b284a5e688f:user-start-execution-20261117

<!-- gonggong-host-git:Sail-Li -->


## #1526 实施契约与边界（2026-11-18）

新增模块 `server/native_entry_resolver.py` 是现有 Python 宿主工具/运行包的一部分，不引入新的调度器、客户端或数据库。实际输入为冻结 integration plan、原始任务与验收、绑定历史验收、产品基线和每项贡献的精确冲突文件字节。宿主接口为 `InstalledResolver.__call__/recover/binding`、`InstalledPlannerRuntime.run` 和 `NativeCandidates.receive`。安装清单 v3 增加 resolver 命令与独立 principal；v1/v2 格式不重定义。新 plan 冻结 installation digest、resolver principal 和命令；旧 plan 保持原格式。

解析器仅接受已评估 generic JSON profile（chat-completions、ollama-chat、gonggong-json）；生产校验要求合契定义，reviewer 与 resolver/producer 使用独立角色和状态目录。当前 native-proposal CLI 协议不接受此输入，执行前拒绝。单文件原始字节上限 32768，总读取/输出 65536，完整请求 100000 字节，最多 64 冲突路径；不截断。不支持依赖冲突、多修订工具上下文、大输入或通用 native CLI，不能以此宣称整个父目标完成。

普通 continuous lane 对路径冲突发起一次持久 intent，再运行已安装解析器；模型/检查等待不持有领域数据库锁。后继 plan 写入 batch，重启继续同一有效计划。未知调用保留 held；已完成 broker/runtime 结果只读恢复，保留原签名 grant，再按精确 principal/request_key 幂等入库。完整冷协调器启动显式回读 held resolver batch。已解析 CAS 后继在精确冲突摘要和依赖未变时仅重放既有不可变字节到新基线；变更冲突输入保留阻塞，要求新的显式授权，不重新调用模型。

回退：历史 v1/v2 安装继续按旧行为拒绝自动消解；回退前须等待/保留已有 resolver 物理占用，不能通过移除安装把 held 标成完成。v3 源码、配置、模板和 executable 归入既有安装清单/构建输入；实际包更新/回退及生产安装回执由根责任者负责，单元/普通 API 验证不是生产启用。

本工单验证使用普通 requirement API、真实 installed producer/checker/reviewer/dispatcher 子进程，以及实际 native_entry_runtime 签名 subprocess + 已评估 loopback 确定性 generic profile。隔离复制的框架准入均为 synthetic fixture，未改变有效框架或真实服务。测试覆盖正常冲突/无冲突、四种中断窗口、冷协调器恢复、原始验收撤销、无关更新时间、严格输出拒绝、删除、小输入边界和 CAS 字节复用；既有 integration/continuous 回归另行运行。精确结果与限制在 `data-collection/native-installed-resolution-implementation-1526.json`。
