# 共工统一工作区

本页保留工作区约束并定位流程；按当前任务读取下列入口，不把全部入口当成每次都要执行的步骤。

## 权限与有效来源

本人在目标仓库拥有有效 WRITE、MAINTAIN 或 ADMIN 权限（含团队继承）时，均可行使已准入共工框架的全部操作权限：发起和授权工单、调用 Agent/Skill、司南派发、夸父排障、谛听采集、合契整合、阎罗交付，以及按治理规则承担审查、批准和验收。宿主回读本人有效权限，随授予生效、随撤销终止。这是共工操作授权等同；具体 GitHub 操作仍受实际 ACL、分支规则及职责独立性约束，不按设备或账号另设门槛。模型、工具和第三方服务使用操作者有权使用的宿主凭据。

当前框架由根目录 `CURRENT_FRAMEWORK.json` 定位；生成 Agent/Skill 定义时读取其 `AGENTS.md` 与 gonggong-check。冻结纲领及元衡原件不可修改；已安装框架校验与新候选准入的区别见[术语与触发条件](../../../customizations/platforms/process-management/repository/execution-policy.md#术语与触发条件)。所有 Agent 仍受元衡治理，迁移不自动授权。

按用户平台组合的八类接入见[平台入口](../../../customizations/platforms/README.md)。Godot 源码及接入留在仓库根，不改外部引擎目录。当前框架不再与 Olympus 派生或同步；现行事件写入 `gonggong-diting-data/`，来源及回执写入 `data-collection/`。历史 `olympus-hermes-data/`、`archive/`、旧发布及批准只作证据；纠正追加记录，不启用已停止草稿。采集配置、送达和消费分别留证，不记录凭据或估算用量。持久路径注明解析基准，未经验证不切换有效发布。

## 任务执行入口

| 触发条件 | 权威规则 |
| --- | --- |
| 开始任务、已有授权后的推进与停止、并发、验证复用、等待、收尾清理 | [执行范围与验证成本](../../../customizations/platforms/process-management/repository/execution-policy.md) |
| 本租户任务开始及实际纠偏/复用事件 | [复盘与方法学习](../../../framework/specs/method-learning.md)，核对适用条件及反例 |
| 开发与 Git 交付 | [工单接入](../../../customizations/components/issue-workorders/README.md)：真实 Issue 与 `work-items.json` 关联，需求在 `design-docs/`；开发前 intake-only，提交前正式门禁，提交后 committed 核验；Windows 使用该入口的 PowerShell 启动器 |
| 候选交付、合入及交付后验收 | [阎罗入口](../../../customizations/components/issue-workorders/yanluo.md)，默认协作者本人 PR 路径；统一核验已有证据，不重复审查 |
| 父子项拆分、整体验收、尾项结转 | [Issue 生命周期](../../../customizations/components/issue-workorders/issue-lifecycle.md)，需求文档保留全部溯源映射 |
| Godot 引擎任务 | [静默验证](../../../customizations/components/godot-host/README.md#静默验证) |
| 新增模块 | [构建边界与验收](../../../customizations/module-boundaries.md#新增模块的构建边界与验收) |

Git 约定属于本仓库接入层，不是共工核心通用前提。交付遵循[框架交付规范](../../../framework/specs/delivery.md)；具体条件见以上正文。

## 多宝迁移期间的双线提交

2026-11-24 用户决定先迁移到多宝服务器，当前阶段保留 Git 与多宝双线自动提交，不切换唯一权威入口。Git 的工单、精确候选门禁、必要独立审查、PR/CI 与 main 回读继续适用；多宝原生仓库保存相同不可变内容及自己的回执，原生提交和读取不依赖 Git。原 Git 历史、现有服务和在途交付均保留。

宿主按[多宝原生仓库与双线提交](../../../customizations/components/tianxuan/duobao/README.md#服务器原生仓库与双线提交)配置目标和本人身份。`writer_submit.py` 在 Git 候选提交成功后自动提交同一固定树到多宝；合入后的 `--inspect-pr` 回读事件再次提交真实合入版本。记录 Git commit/tree、多宝修订、文件清单摘要和双方回执。任一侧失败保留已成功结果及 pending，按原稳定请求键恢复；不重复 Git 发布，不以一侧成功报告双线完成，不新增定时扫描。

本阶段多宝的 `git/<精确提交>` 是迁移／并行接收分支，`received` 仅代表内容接收，不代表多宝保护 `main` 已发布或业务工单已完成。多宝独立合入仍要求实际检查、独立审查及目标版本条件更新。后续完全接管须另有用户决定和真实切换验收；不能通过更名 remote、删 `.git` 或关闭 Git 检查自行完成。

## 从 main 取得自动推进与生产入口

可信 main 提供[仓库派发入口](../../../customizations/components/repository-dispatch/README.md)。按实际宿主选择仓库核验、框架模型或编辑器工作者路径；这些替代入口不串行叠加。只有选择 Codex 原生 Agent/chat 时才使用下节协议。各入口核对权限、在途占用和交接，不复制他人的配置或凭据。

## Codex 中已授权的 Issue

当前会话先回读 Issue、授权、已有 PR、已交付与剩余验收、责任者和在途占用，接续至本次授权范围验收。部分 PR 合入或计划登记不改变执行责任；换人或换宿主须明确交接并取得实际接收回执。天枢计划、打开 Godot、额外配置模型 API Key 均非 Codex 路径前置条件。

司南按[原生派发协议](../../../customizations/components/codex-dispatch/HOST_PROTOCOL.md)，对已授权、依赖已验收且读写可隔离的任务按真实槽位派发；同一实现可独立只读核查。只有一项可执行时由当前责任者继续；缺少子 Agent 工具只记录受影响派发，继续独立项。实际完成事件触发终态核验、依赖回读与补位。跨设备先确认认领和交接，终态未知不释放占用。协调只由需求、进度、依赖、决定、交接及完成事件触发，不新增定时扫描。

## 阻塞由夸父当次介入

用户反馈受阻或实际动作失败无法继续时，当次按[夸父接单、上报和复验](../../../customizations/components/issue-workorders/kuafu-routing.md)关联原单、故障与唯一主责，保留真实失败证据；正常依赖等待、工作者运行或槽位暂满沿原完成事件接续。排障不抢占他人候选，网络/身份/宿主不可用时保留待接单与恢复条件。
