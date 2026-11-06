# 司南的来源与接入边界

路径以仓库根为基准。通用职责见 framework/agents/sinan/AGENT.md，所需能力见 framework/skills/work-order-coordination/runtime-ref.json。本目录实现元衡本地账本适配，由宿主按需选用。

本地工具目前读取已登记元衡账本及通过原 CLI 准备操作。其它业务系统需要实现对应来源适配后才可声称覆盖；通用 Agent 定义不等于所有后端已接通。

司南默认在适用权威来源关联本地工单，不产生必须创建外部 Issue 的指令。当前工作区 的 Git 接入由宿主绑定 git-issue 和实际权限，在该接入的 registry 中声明 issue_tracking={enabled:true,provider:"git-issue",authority_ref:"实际授权引用"}。配置只选择交接方式，不授予操作权限，也不自动调用 GitHub。

启用后 followUps 保留 issue/issueAction 供现有宿主消费，并给出通用 workItemAction；未启用时 issueAction=null，既有 issue_ref 仅作为历史关联保留，不自动启用外部操作。源故障和文档修复遵守同一规则。宿主真正操作前验证权限、目标及来源版本，写入后回读；无回执不记送达。

工具 refresh 仍返回 not_dispatched，不直接启动 Agent 或改外部工单。把实际 start/ack、业务执行和接收结果交回司南，按同一真实事件复用采集引用。
