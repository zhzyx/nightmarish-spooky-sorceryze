# 将独立写入边界与汇合条件接入实际派发

用户要求执行 #227 的所有优化。派发时识别依赖与共享写入，独立项继续、冲突项等待，并区分实际启动回执与结果。

验收：正常入口和对照回归，记录范围及未知项，核对 main 回执。
## 派发前后的可核查结果

父项为 [#246](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/246)，本设计和验收绑定 [#247](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/247)。工作者负责司南宿主与 GitHub 来源接入，最终由父项执行者接收并复核。下列路径均相对仓库根。

- 派发从 GitHub 正式读取原生 blocked_by 列表，合并正文的精确依赖标记，在重新授权、认领和启动前复核来源修订。原生依赖含跨仓库来源；缺可验证验收的依赖等待，不以关闭标签、子项个数或完成消息充当验收。
- 现有读读并行、读写和写写互斥继续在共享安装预约锁内判定。Codex 和仓库工作者均对本机路径解析符号链接或 Windows 目录联接；尚未创建的文件使用最近的实际目录祖先解析。新请求的无效路径只挂起本项；已占用范围无法解析时保留预约。Windows 新请求须指定盘内目录，历史盘根预约继续覆盖整盘，原有正斜杠 UNC 预约继续覆盖同一共享目录。旧预约在每次检查中按同一规则比对。跨不同安装仍需同一认领服务；路径必须覆盖实际共享接口，此规则没有推断未申报的外部资源。
- 实际启动、回执未知、部分失败等每项执行结果均附上原交接中的负责人和汇合验收条件。原状态、精确预约键、实际 worker 回执仍分别表达。发布给子工作者的读写边界随真实路径规范化。
- 供复核的普通入口为 `node customizations/components/repository-dispatch/session.mjs inspect NUMBER REQUEST_ID`；Windows 先以 tools/run_issue_gate.ps1 -ProbeOnly 确认可执行 Python。本子项运行 #247 flow-dispatch-20261107、#249 flow-candidate-20261107、#251 flow-recovery-20261107 均回读到对应工单，未申请新预约；真实 #151 有三个原生依赖 #146、#148、#149。该检查仅读取来源，结果保持 dispatchCandidate=false、acceptanceValid=false。
- `node --test customizations/components/codex-dispatch/adapter.test.mjs customizations/components/codex-dispatch/operator.test.mjs customizations/components/issue-workorders/github_source.test.mjs customizations/components/repository-dispatch/session.test.mjs` 通过。38 项覆盖同批次冲突与独立项继续、既有预约重启、缺启动回执占用、终态后补位、原生依赖缺页及版本漂移。路径冲突和异常使用隔离夹具；未对其他在途工单发起生产执行。
