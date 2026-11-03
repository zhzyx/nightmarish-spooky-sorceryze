# 最终结论：跨模型本地定义与运行契约语义 PASS

对象0.9.0。三项初审发现均已关闭：按需skill文案、持久终态/取消恢复一致性、当前能力与待部署说明。下文保留初审记录；最终结论及状态以本节和JSON为准。本评价不批准业务运行、不认证任何真实模型。

最终读取4个runtime文件并对照规范。完成或取消已持久后只能补交对应回执，禁止反转；续期绑定旧委托且不得改变任务、框架、模型、权限或预算。独立运行报告MODEL-05/06提供对应合成故障路径证据；本审查者不重复签发其执行测试结论。

冻结纲领和元衡上游原件逐字节保持；3正式Agent和9skill入口共12个全部未改变，无模型专属角色、无新增常设Agent。局部运行器HMAC/额度/状态约束不等于企业身份与全局预算。真实模型、live证据和有效授权是实际任务入口前提；协议模拟不能算模型能力认证。谛听观测只覆盖此运行器，未监听全部Codex或引擎对话。

绑定manifest SHA256：`25d0b069d116af1eaa236f7564e596c0c9fa41f8fddaa5d9d91aa3eab3ac268d`。

- yanshi 0.4.0：`c40fe243a82ce1d850514919fa4da32644d17f3efae22e14026cba7d0d4f2f58`。
- kuafu 0.4.0：`a5b184a3a1b652cf8b302fb9b97886a760620c79c64f376722cc1e2df5d5041c`。
- diting 0.4.0：`ac953d822107a1f13c7aa18e8cb582ca5bc5ffd1fcfb5151eb7fa2ce20df0f07`。

原始发现的最终处理：

- MSEM-001：最终model-runtime说明改为“每步可按需选择一个登记skill”，与可选字段和实现一致。
- MSEM-002：_recover先检查已持久completed/cancelled；completed仅允许retry补交并收束completed，cancel仅补交cancel不能resume。代码路径复查通过；独立运行报告MODEL-05含持久终态中断恢复验证。
- MSEM-003：README明确配置真实模型、live代表任务证据及有效授权之后才能跑实际任务；GOVERNANCE区分本地签名/额度/状态控制与尚未部署的企业IAM/全局资源/分布式控制。

---

# 跨模型改造独立语义审查

獬豸·框架审查：临时独立审查职能，/root/xiezhi_review，受元衡控制。对象outputs/gonggong-v0.9。只读候选，未改实现、未向模型服务发请求。本评价不构成准入批准或真实模型认证。

当前结论：设计方向满足元衡边界；发现项等待最终候选复查。共享运行器不新增Agent/skill，不把模型协议兼容当实际业务能力，也不改变冻结纲领。

## 元衡六项

- purpose：三种执行模式适配单步、宿主计划和受限资源检索；产物是候选，业务验收仍由原责任链负责，接口通不能证明需求已满足。
- truth：协议、模型能力和生产部署分开声明；synthetic只能validation_only，live标签由操作员负责真实性；只证明样本集、未认证真实模型效果。上下文字节不是token窗口；max_calls不是总token或金额预算。
- economy：四个共享runtime实现，不复制模型专属Agent或skill；现有三Agent/九skill入口复用，按步骤按需加载方法，不按模型建立固定编制。
- authority：冻结纲领及元衡核心始终入上下文；HMAC委托绑定计划/状态目录/框架指纹/有效期；工具仅宿主资源map读取，模型JSON不是执行权限。密钥及文件ACL由可信操作员控制，非企业IAM。
- adaptation：同一任务类别只能路由至有评测依据且可容纳当前上下文的profile；无效输出受总调用额度，未知HTTP结果转对账，不自动加权限或降低验收。
- continuity：框架/模型配置或证据变化需重新准入；恢复保留原预算和历史，完成重放不调用模型；冻结上游不变，共工/元衡反馈仍为reference。

## 待复查发现

- MSEM-001（low）：“每步显式选择一个登记skill”与实现及plan字段的可选skill不一致。建议：改为“每步可按需选择一个登记skill及相关引用”。
- MSEM-002（medium）：completed journal已写但投影失败后recover cancel：最早completed仍可投影request_end completed，同时jobs cancelled。建议：让完成事件与取消恢复的最终状态保持一致并保留可追溯原事件；由运行独立审查实测此故障路径。
- MSEM-003（low）：旧全未部署描述与新本地执行约束不一致；“实际任务可运行”须标明真实模型/评测/授权前提。建议：区分本地运行器已实现、模拟验证、真实模型效果待验收、企业宿主未部署。

## 独立规范与代码前向核对

以下是规范/代码路径推演，未调用真实模型，不是模型行为通过率。

- MS01：更换为不支持原生system角色的协议模型。转角色标签文本且明确不等同原生隔离；元衡和纲领保留，不能截断。 依据：runtime/adapters.py; specs/model-runtime.md。
- MS02：模型无法输出合法信封。保留失败记录，转已评测候选且计入同一额度，无合格者needs_attention。 依据：runtime/runner.py。
- MS03：模型输出shell或未授权tool。只接受授权lookup_resource；候选被拒绝，不执行模型生成代码。 依据：runtime/runner.py。
- MS04：profile仅有synthetic证据却是正常业务任务。validate_plan拒绝，必须validation_only。此机制不认证人工把scope标live的真实性。 依据：runtime/runner.py; runtime/evaluate.py。
- MS05：模型响应超时/HTTP错误，可能已经消费。TransportUnknown转needs_reconciliation，操作员核对后retry/cancel，已用调用预算不重置。 依据：runtime/adapters.py; runtime/runner.py。
- MS06：供应商缺usage或cache/reasoning是总量子集。unknown保持unavailable不填0，子集不重复累加；不宣称跨模型通用价值换算。 依据：runtime/adapters.py; runtime/diting.py。
- MS07：用户要求无条件把完成JSON当游戏交付成功。runtime完成仅candidate_requires_business_validation，夸父不代签业务测试，谛听不批准。 依据：runtime/runner.py; specs/model-runtime.md。
- MS08：外部Codex对话发生纠偏，但不经本运行器。coverage明示只覆盖运行器，外部对话/语义纠偏不推断；需宿主提交真实事件。 依据：runtime/diting.py; specs/model-runtime.md。
- MS09：上下文超模型声明字节限额。跳过候选或转人工，不截断核心治理；不把字节值称为实际模型token窗口。 依据：runtime/runner.py; specs/model-runtime.md。
- MS10：任务完成后相同授权重放。任务/授权摘要一致则返回持久结果，不再次调用或重复计量；真实回执与任务状态应一致。 依据：runtime/runner.py; runtime/diting.py。
- MS11：任务过期或改状态目录绕调用额度。签名/有效期/状态位置检查拒绝；不同目录的总预算仍由外部宿主治理。 依据：runtime/runner.py。
- MS12：跨模型新增常设角色或绕过谛听框架修改边界。本方案仅共享运行代码，3正式Agent不变；框架/元衡数据仍仅reference，不能由模型自采纳。 依据：README.md; specs/model-runtime.md。

## 限制

- 无真实服务配置、真实模型代表任务或业务效果验收，本报告不认证任何实际模型。
- HMAC执行边界依赖操作员保管密钥和本地目录ACL，不是企业IAM、恶意本机进程沙箱或全局预算。
- 当前仅文本、非流式、JSON信封和宿主资源map读取，不认证多模态/原生工具/引擎写操作。
- 谛听自动记录范围仅此运行器；外部会话/语义纠偏/业务质量不自动推断。
- 运行功能和故障恢复的执行证据由另一独立运行审查负责；本审查不重复签发其测试结论。

最终候选manifest及3Agent完整候选指纹待冻结后绑定；当前不是最终PASS记录。

## 发布前状态元数据复查

PASS：host_loader_implemented=true仅指local_trusted_operator_runtime_only；local_runtime_instrumented=true仅指本地调用链。runtime_deployed=false明确限定enterprise_or_external_host_deployment。此区分与README及已读代码一致，不宣称企业宿主或全部Codex事件已接通。已核对全部已审源文件与三Agent候选指纹未变，仅更新manifest绑定，未重复无关测试。
