# 多任务派发与能力选模

路径相对框架根。候选入口 `modules/sinan/dispatch.mjs` 导出 `planDispatch` 和 `dispatchEvent`；原 `refresh.mjs` 仍是纯刷新，不暗中启动执行者。已准入宿主在一次实际事件刷新后调用 dispatchEvent，提供新鲜 board、来源适配及执行回调。当前交付是可测试的核心接入接口，未绑定 Codex/Godot 的生产执行器。

## 分工和模型

只拆独立交付，不为每个动作创建对话。每项 requests 提供 ticket（原来源全局 ID）、outcome、owner、acceptance、authorityRef、contextRefs、capabilities、reads、writes，可选 target=agent/chat、model。任务顺序沿用司南 ready 的优先级；硬依赖通过 board 排除，软关联不凭自然语言推断为阻塞。上下文只交接目标、授权、依据、接口、当前版本、验收和必要引用，不复制所有聊天；共享写入使用单写者或隔离工作副本。

能力由实际工作明确，例如资料归纳需要文本处理，工程实现需要编码及工具使用，复杂架构/冲突诊断增加深度推理，视觉审阅增加图像输入。高影响变更保留独立审查者，不能用模型更强代替独立审查。capabilities 为宿主定义的能力标签，无能力证据不得凭型号名称猜测。

宿主 environment 提供 capacity（真实剩余池上限，含在途占用）、active（所有运行/预留/回执不明任务的 ticket/reads/writes）、catalog（id、available、targets、capabilities、可选 preference，数字越小越优先）。目录必须来自当前宿主，可用性与模型可用工具共同核验；用户明确型号时精确匹配，无匹配返回待处理，不静默降级。符合全部必需能力后按宿主偏好排序；费用/时延未知不编造数值。按槽位隔离执行和审查，执行池默认沿用现行两个执行槽，并受真实宿主容量约束。

target 默认 agent；chat 必须 environment.chatCreationAuthorized=true，绑定明确用户要求。宿主不支持模型覆盖或某种目标时从对应目录排除，不能提交一个参数后宣称已经换型。Codex 子 Agent 指定模型时按工具约束使用独立上下文并显式传必要交接；创建独立 chat 使用宿主当前的建聊能力，复用已有目标则用对应消息工具。不能把写到文件的消息记为已送达。

## 宿主契约

`dispatchEvent(event, requests, host)` 的 event={type,reference}，只接受需求、状态、依赖、决定、完成、失败、用户查询、范围变化事件；无定时调用。

- withLock(fn)：跨聊天短事务锁，inspect/校验/预留串行，锁外并发启动。
- inspect(event)：先对账事件的真实执行回执，再返回 {snapshot,environment}；完成、失败或取消后是否释放由宿主确认，不能只相信事件标题。
- revalidate(assignment)：真实身份、元衡准入、需求与范围、源版本、预算、模型权限、槽位及读写集合均匹配才返回 true；必须按源 CLI 的版本条件保护随后 start，失效则拒绝。
- reserve(assignment,event)：启动前持久预留，按工单及修订去重，返回 true 才执行。跨版本也禁止重复执行仍在途的同一工单；持久化未知时抛错，不能启动。保存资源锁直到真实回执对账。
- startSource(assignment)：通过原来源 CLI 短事务 start，返回 reference；同一来源的修改串行并重新校验版本，不直接覆盖账本。
- launch(assignment)：实际启动 Agent/chat 并传精确 model.id 及必要上下文，返回 {workerId,reference,model,target}。多项 launch 可同时等待，不等待前项交付才启动后项。
- ack(assignment,receipt)：通过原 CLI 保存实际 worker 回执；成功仅表示运行，不能当作业务验收。
- record(record)：持久记录并按已有 reporting.json 调共享谛听；记录实际与未知状态，工具调用失败不等于对端未执行。

reads/writes 必须是宿主已解析真实路径、junction/symlink 和工作副本别名后的绝对规范资源路径。Windows 大小写及目录包含按冲突处理，读读可并发。动态写入超出集合必须重新申请资源，不能由工作者自行扩大权限。目录与模型清单是宿主可信输入，不接受子 Agent 自评作为授权。

reserve 后任何启动、ack 或记录失败都保留占用并返回 reconcile_required；宿主按 key 查询原来源和目标，取得真实回执后才更正或释放。不得因超时重派。持久预留后的崩溃在后续真实事件中对账，不增加后台扫描。无生产宿主时只用 planDispatch 输出 not_dispatched；单元模拟不计为真实生产回执。

恢复：停止调用新的 dispatchEvent，恢复原 prepare/refresh，保留来源状态、预留与回执并完成在途对账。候选准入不改变未来任务授权。

当前操作者的 GitHub 原生宿主契约由接入层 `customizations/components/codex-dispatch/HOST_PROTOCOL.md`（以仓库根为基准）维护。共享安装内认领不等于 GitHub 全局 CAS；启动前回读修订和依赖，持久 launch-intent 与确定未启动释放共用来源锁。queued chat 只有真实 setup 映射核验后才 ack；真实终态核验后才释放容量。宿主私有完整参数和来源路径不进入共享采集，公开事件仅保留必要身份、摘要和实际状态。
