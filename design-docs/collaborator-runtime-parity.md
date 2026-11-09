# 协作者已有工单的连续执行

用户要求核查本机与远端 main 的环境差异，使任意有权协作者在明确 Issue 上得到相同的持续推进和司南多 Agent 派发流程。

本次从活跃 Codex 会话入手，核实 Git 身份、运行时、宿主派发与跨安装边界；将明确派发指令放入所有克隆读取的仓库入口，修复复现的 Windows 门禁兼容问题。验收包括两代 PowerShell 默认探测及工单回读、原生派发证据与其他协作者的真实 PR。跨设备接收真实事件、统一认领、终态验收后推进依赖和另一账户端到端验收分别跟踪，未验证的生产能力保持开放。范围不含接管业务工单、扩大远端 ACL 或共享个人凭据。

## #140 的真实停点

#140 原文将授权绑定到 Codex 对话。kaiyunxue 以本人 GitHub 身份创建并合入 PR #155。#142 仍需 NodeRegistry、Provider 与 Publish 接口验收；#143–154 为 planned。#140 的后续评论记录了 plan_store 的写入/回读和缺少生产启动回执。这是可从命令行调用的本地 SQLite 接口；该次写计划的记录不能证明 Godot 正在运行。父单仍由原责任者推进，未从本工单接手业务代码。

远端 main 核对基线 be0d0a90dd355cec82afdb70aac1e24a9627167d。本机根工作树的 HEAD 与该基线一致，本机 main 引用落后 12 次提交。GitHub 回读 Sail-Li 与 kaiyunxue 均为 WRITE，zhzyx 为 ADMIN。本机 Codex 工作区受信任；当前会话有网络、可写工作树及原生子 Agent。GitHub 身份、工具权限、模型目录及可用槽位在每个宿主分别核对。Codex 派发的私有认领目录属于同一安装，另一 clone 需独立绑定并确认交接。同一协作账户以 PR 路径交付无需阎罗宿主密钥。

证据：[原始需求与交接](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/140#issuecomment-6665309133)、[首批剩余验收](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/142#issuecomment-6665047824)、[其他协作者合入](https://github.com/zhzyx/nightmarish-spooky-sorceryze/pull/155)、[跟踪工单 #158](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/158)。

## 天枢入口核查

天枢的设计定位见 design-docs/daqian-workflow.md。editor/docks/daqian/workspace.gd 展示工单状态，经 graph_host.py 读写计划或答复，调试按钮另起 debug_session.mjs 并标注本机协议夹具。graph_host.py 的 read/apply/answer 路径均未启动工作者。计划库默认在当前 Git 安装的 data-collection/daqian.sqlite，也可以通过已经配置的 SSH 计划宿主访问。框架司南、Codex 派发入口、工单提交入口均可独立运行。#140 的公开记录支持“一次主动写入大千计划”，谁决定这次移交及其当时的内部理由未知。

路径相对仓库根。核查为源码、工单和原生 Codex 运行回执复核，本次未启动 Godot。未获第二设备的实际终态回执，也未把在途业务从 kaiyunxue 转给本机。

## #160 修订为从 main 分发

2026-11-06 用户明确要求排查自动推进与生产对本机 Codex 的依赖，并将必要实现交付 main，由后续协作者自行取得。授权范围为 #160 的仓库接入与验证。保留 #158 对第二身份、实际运行及交接的溯源。

核对起点为 b9433dcabe69be1a8850a42a9fe8b9234829b867。共工司南 dispatchEvent、框架模型运行时、GitHub 工单门禁及阎罗协作者 PR 入口均可脱离 Codex。两处硬绑定分别在工单宿主的原生 spawn_agent/create_thread 回调、Godot 并行执行器的 Codex 命令行参数。CLI 模型列表、登录、原生聊天和 Codex 专属 UI 属于选择该后端时才会使用的适配功能。

交付独立仓库进程入口与通用生产命令，复用既有准入、真实来源、共享占用和回执。在干净检出以本人身份运行真实工单，验证无 Codex 情况下可启动、回读终态与进入交付流程；依赖验收、拒绝、重试及历史 Codex 兼容另做回归。框架不切换版本。没有触碰其他协作者设备或 #140 的业务交付。第二个账号、实际模型供应商和跨设备交接只采信真实回执。

## 2026-11-09 批量续办与用户修订

本次由用户授权推进 Sail-Li 创建、编号小于 #300 的全部开放工单，共 11 张：#49、#51、#56、#83、#91–95、#158、#160。用户随后明确 #160“直接自己执行确认即可”，不再等待第二身份；平台验证“收敛验证环境，模拟验证mac和win即可”，不再等待 Linux 或原 x86_64/Clang 14。原始范围与历史第二身份未知仍保留，不伪装为已执行。

本轮交付包括派发工作者迁移后的真实导入修复与历史 runtime_sha256 核验、隔离 Windows console/engine 配对修复、布局/主题/停止探针和 macOS/Windows 点火器模拟。工作者六项、点火器十五项、隔离八项（另有一个可选真实编辑器测试跳过）及独立 Node 四项通过。macOS 历史 a2a119d51 编辑器后台三阶段布局、深浅主题、延迟 HTTP 停止/恢复及真实 A/B 进程重启另行记录；没有把模拟编译或旧二进制称为最新 main 的真实构建。

验收、原始平台边界、27 项自更新接收矩阵及各单剩余项见 `data-collection/before300-20261109/validation.json` 与同目录证据。#637 跟踪本次发现的运行时迁移故障。修复后沿协作者签发、CI、main 回读及干净检出自执行确认推进；未满足原症状因果或完整开发流的工单继续保持开放。交付不修改其他工作副本、用户安装或原暂停测试队列。
