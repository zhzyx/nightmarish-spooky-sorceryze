# A04　在签认的阶段停止

从设计拆出的任务完成生产后，在 `POST /api/v1/native/workflow/status` 用执行票据读取 `stage_result`。达到标准时返回 `stage-reached`、原因 `authorized_stage_criteria_met`、完整阶段签认、候选和模块修订，以及每项检查的结果和证据 ID。原始进程回执、产物接收记录和可读的模块版本保存在同一票据的 `terminal`。签认和产物继续受原工单、来源设计和模块的读取权限保护。[A04 工单](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1841) · [A03 阶段准入](gonggong-ai-workbench-a03.md)

## 安装计划与阶段检查

安装者为阶段指定能检验其到达条件的 `checks`，并在受信计划中写入对应的 `stage_criteria` 文本。例如，目标要求 SVG 预览中有一个半径 12 的蓝色圆时，检查需要读取候选修订中的 SVG，验证圆的数量、半径和颜色。该字段须与用户签认的完整 `criteria` 相同。检查 ID、安装上下文、目标修订、签认修订和阶段一并进入票据。确认或安装计划发生变化时沿 A03 的换版规则重新核对。现存计划省略该字段时仍可领取、产出并重放，候选显示 `stage_criteria_check_unbound`，等待有依据的核验。

生产进程结束后，司南沿完成事件读取 `inspect.stage_checks`，调用 `POST /api/v1/native/workflow/verify-stage`，正文为 `{"key":"<执行票据>"}`。天璇在精确候选上运行多宝的已安装检查，写回前重读当前签认，并在同一原生存储写锁下核对通过证据。失败检查以 `stage-unmet` 和 `authorized_stage_check_failed` 保留实物和结果。证据撤销、检查仍在运行或签认失效时，已产出的候选仍能按原权限查看。阶段结果按票据唯一写入，重开服务及重复投递均可读回。[工作流实现](../customizations/components/tianxuan/sinan-workorders/native_workflow.py) · [司南驱动](../customizations/components/tianxuan/sinan-workorders/native_dispatch.mjs)

阶段检查与普通工单的交付入口独立调度。受阶段限制的候选在独立审查、发布、完成、贡献合入和已验收依赖的入口都受到执行上限约束。阶段到达时原工单保持可查看，整体业务交付留给后续显式授权。[A05 续授工单](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1762)

## 复验

从仓库根在已装天璇依赖、Python 和 Node 的环境运行以下命令。用例通过认证 HTTP 启动随仓库交付的 Node 司南驱动、本地预览进程和解析 SVG 的检查，第二次驱动覆盖冷启动回读。蓝色与红色预览各生成一个实际候选，前者满足标准，后者保留失败证据。两次调度都逐项记录交付调用。定向用例还覆盖撤回签认、撤销检查证据、旧安装计划、贡献路径和并发结算。普通任务、集成与联合交付沿原回归组验证。[定向验证](../customizations/components/tianxuan/sinan-workorders/test_native_stage_stop.py) · [候选、产物和接收回执](../data-collection/gonggong-ai-workbench-plan1-a04.json)

```sh
python -m pytest -q customizations/components/tianxuan/sinan-workorders/test_native_stage_stop.py customizations/components/tianxuan/sinan-workorders/test_native_stage_admission.py
```

本次候选在 Windows 上使用隔离安装的本机测试工具，通过天璇任务服务完成阶段实测。此前 macOS 原生观察涵盖从会话重开精确文档修订，以及设计历史的差异与恢复。[D03 macOS 接收回执](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1860#issuecomment-7067023618) · [D06 macOS 接收回执](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1861#issuecomment-7068555775)
