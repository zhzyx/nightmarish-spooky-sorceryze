# 从 main 使用共工派发

从可信的 main 检出运行。Git、Node.js（22+）、Python 3.11+ 和已用本人账号登录的 GitHub CLI 需要在 PATH 中。可用 GONGGONG_GH 和 GONGGONG_PYTHON 指向已有工具。以下命令从仓库根运行，均由一次真实业务事件触发。无需打开 Codex 或 Godot、导入个人提示词或安装插件。

## 验证独立检出

先确认其他安装的实际工作者已经终止或交接。选择已授权、进行中的专用 type:test 工单，使用真实编号和稳定需求 ID。例如在 #160 的验收期运行：

```sh
node customizations/components/repository-dispatch/session.mjs inspect 160 collaborator-runtime-second-host
node customizations/components/repository-dispatch/session.mjs verify 160 collaborator-runtime-second-host
```

inspect 返回 GitHub 来源修订和依赖。verify 核实本人写权限、origin、租户、工单及框架准入，再通过司南实际启动仓库自带的 Python 核验进程。框架校验成功退出、启动回执和终态绑定一致后才释放该预留。验证不使用模型。每个来源修订最多认领一次，保留失败或未知回执，禁止通过修改标签制造重试。查看返回的 results 和 deferred；完整录入与来源回执按既有谛听门禁提交。其他协作者可以在自己的独立检出运行，记录本人、来源修订、实际终态与 PR 回读。不要复制个人配置、旧认领或登录资料。

## 运行模型生产

宿主沿用 framework/templates/model-plan.json 与 customizations/platforms/ai-access/host-http/runtime/runner.py 签发和执行计划。在可信运行环境中提供自己的模型授权、实际评测及签名密钥。使用 inspect 提供的 sourceSnapshot.sha256 填写 task.source_revision，task.work_items 中的 id 使用同一 github:OWNER/REPO#N，task.tenant_id 填 gonggong-workspace。任务与宿主授权引用一致，指定一个经过 live 评测的 profile，validation_only 为 false；grant 与状态目录使用宿主的绝对私有路径。候选结果写入签发时绑定的运行时账本，可由授权接收方验收。用下面的命令交给同一事件入口：

```text
node customizations/components/repository-dispatch/session.mjs model ISSUE REQUEST_ID ABSOLUTE_SIGNED_GRANT
```

运行前和实际调用时核对签名、期限、预算、候选框架、工单修订、结果目标与 profile。仓库只发布代码、模板和协议。由宿主保管凭据并决定资源权限。文件修改类生产沿用 [独立工作树执行器](../../../tools/godot_parallel/README.md)，其 workerCommand 接受授权的其他 CLI。Git 交付沿用 [协作者签发入口](../issue-workorders/yanluo.md)。

## 多工单与中断

可传一个可信的绝对 JSON 配置文件，沿用 [现有来源、事件与容量字段](../codex-dispatch/HOST_PROTOCOL.md)；所有 requests 显式给出 target=agent、model 和实际规范化读写路径。另以 workers 的工单键绑定对应的 kind（framework-model 加绝对 grant，或 framework-integrity）。多任务共享私有模型状态目录时须将其登记为写资源。框架模型的实际能力以签发 profile 的评测为准。dependencyRegistry.path 指定绝对司南来源注册表，dependencyRegistry.tickets 将 GitHub 依赖键绑定到经宿主核实的原账本任务键。每次准备启动都回读原账本的验收标准和产物哈希。缺证据的任务保留 deferred。真实终态触发当轮补位，之后新增的验收以 dependency.changed 事件再次进入。

仓库入口与 Codex 原生适配器共享同一 Git 安装的持久认领根（git common directory 的父目录下的 data-collection/receipts/codex-dispatch）。来源启动前二次核对修订。独立 clone 各有自己的认领根，跨设备须先交接或使用同一认领服务。回执未知时保留占用；已保存真实终态且来源已 ack 时，配置 action=reconcile、reservationKey、原 workerReceipt、execution.finished 及终态 reference，requests 只列待补位项。用已有回执恢复，禁止重发模型调用。模型完成后还需独立业务验收。当前交付由显式事件启动，进程以外的常驻监听与跨设备统一认领服务需要单独部署和验证。

进程终态同时记录实际退出码和信号。核验进程的失败可回收并保留失败结果。模型进程缺少有效完成回执时保持占用；经授权宿主核实原调用后使用框架原有 recover 处理。已 ack 的原工作者可用其 reference 加 `:ledger` 作为恢复事件引用，由入口只读核对原签发任务、预算和 SQLite 终态。账本 completed 对应 execution.finished，cancelled 对应 execution.failed，其他状态继续占用。签发续期只能沿用原计划，所有路径相对本仓库根解析，私有路径按文中所示传绝对值。

只读终态核验可使用已到期的原 grant，仍须通过该 grant 的历史签名、框架摘要、原计划绑定及数据库精确摘要检查。任何实际生产与重试继续检查有效期。
