# A03　本机执行入口的阶段授权

司南在接受 D10 拆出的工单前，从同一天璇域读取原单的签认。A01 确定阶段和到达条件，A02 记录当前负责人的逐项确认。宿主还需已有的可信安装计划、身份、输入、写入范围与检查项。设计工单的安装计划必须声明与确认阶段相同的 `stage`。阶段名称沿用 A01 的自由文本。[A03 工单](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1855) · [A01 契约](gonggong-ai-workbench-a01.md)

## 服务与本机接点

以天璇认证会话调用 `POST /api/v1/native/workflow/authorize`，正文只需 `{"issue":"<原单 ID>"}`。宿主的 `NativeWorkflow.authorize_installed` 读取安装计划。`authorize_task` 在写入执行票据的同一事务内，再次核对工单定义、来源设计 ID 和版本、目标修订、确认修订、当前负责人、签认人、阶段及到达条件。目标写入者可以是此前的负责人；改派后由新负责人签认。D10 原单指定的已签认版本在新草稿出现后仍可使用。未登记目标、目标被退回、尚未确认、已撤销、修订错配以及无来源读取权都会阻止启动。

票据是全部任务合同的 SHA-256。用 `status` 读取 `task.source.definition.stage_authorization`，其中 `issue_revision` 是原单定义摘要，`version` 是 D10 来源设计版本，`target_revision` 和 `confirmation_revision` 分别是目标与签认修订。派发时使用 `task.source.revision` 和票据共同定位这次授权的完整定义。原生页面读取同一原单详情的 `task_target` 与 `task_confirmation`。本机进入进程时，`NATIVE_CONTEXT` 里的 `stage_authorization` 带有相同的签认人、阶段和标准。A04 可沿票据与该标准记录到达结果，S01 可沿票据取得能力、安装配置和写入范围。[工作流](../customizations/components/tianxuan/sinan-workorders/native_workflow.py) · [本机接收者](../customizations/components/tianxuan/sinan-workorders/native_worker.py)

在 `inspect`、`reserve` 和 `execute` 开始执行的事务中重新读取签认。签认在本机预约后失效时，执行入口关闭尚未启动的本机票据，释放该预约。真实进程已有启动记录时沿原有终态与恢复流程处理。相同合同的重试返回同一票据，按同一签认更改安装合同会退回。显式换版需要当前票据及新签认。历史普通工单继续沿原有宿主授权。已绑定设计的历史票据须满足现行阶段准入。

## 验收

Windows 定向用例使用同一应用的认证 HTTP、SQLite、现有 NativeWorker 及隔离的本地 Python `local` 测试工具。进程读取实际收到的上下文，只在临时测试目录写入一次观测与夹具产物。验证同一设计的两单中仅已确认的一单到达实际进程、重试次数不变，以及各类失效票据调用数为零。服务重开后验证改派、新签认和旧预约的交接。产品中的安装者继续提供受信计划，S01/S03 接续能力映射与派发；A04 接续阶段到达后的停止。[定向测试](../customizations/components/tianxuan/sinan-workorders/test_native_stage_admission.py) · [候选与实测回执](../data-collection/gonggong-ai-workbench-plan1-a03.json)

上游 macOS 回执来自原生文档历史与会话打开精确设计修订的观察。本卡本机进程实测的平台为 Windows。[D03 观察](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1860#issuecomment-7067023618) · [D06 观察](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1861#issuecomment-7068555775)
