# Olympus 残留与当前链路死锁排查

稳定需求 ID：olympus-residue-deadlock-20261104。

产物为当前有效入口残留修复及功能检查证据。平台为 Windows x64 / Python / Node，必要时验证现有 Godot 编辑器；未修改原生代码时不重建引擎。覆盖框架正式准入、工单回读、桥接、需求入口、采集、包完整性及已有代表测试。历史 archive、Olympus 数据、冻结纲领和元衡原件保持不变。与 #49 实际 UI 调试、#48 子会话功能保持独立。验收为直接故障有复现与回归，所有检查逐项区分通过、失败和未验证；真实供应商不可用不算模拟通过。路径均相对仓库根。

2026-11-04 扩大验证：实际安装页签返回乱码，定位 ai_chat_dock.cpp 的窄字符串。修复 Unicode 字面量后选择 Windows x64/MSVC 现有编辑器配置增量构建（tests=yes、accesskit/d3d12/angle=no），仅用于验证当前候选，不切换有效发布。既有运行包先保留。

## 当前验证结果（Issue #51）

真实工单：https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/51；intake-only 回读通过。基线 b123479a。当前其他聊天的 samples/gonggong-workbench/project.godot、design-docs/ai-chat-debug-20261104.md 和项目缓存不属于本单。

- 正式框架准入、243 文件离线快照检查通过；冻结纲领和元衡原件未改。
- 工单 42、宿主 49、框架单测 19、运行场景 10、迁移 10、Git Issue 8、司南 16、CLI 52、独立包 9 项通过。编辑器 Python 测试 31 通过、1 个符号链接权限场景跳过。
- 当前专用 Godot 链路 13 项检查、真实准入配本地模型的需求建单、仅咨询越权拒绝均通过。自更新模拟构建与实际隔离重启交接通过；60 MB 历史性能场景通过。
- 两秒回执延迟下的失败、重试、取消、恢复失败均通过，最大采样帧间隔 0.015591 秒，未复现运行时死锁。
- 清理的是有效验证入口中的旧豁免、待批准假设、固定两页假设、自更新旧定位方式以及 CLI 子进程清理竞态。archive、历史发布、Olympus 历史数据和审批原件保留。
- 旧通用 UI 验证仍有未通过项：安装包共工页签乱码；旧测试还把 Stop 按钮禁用当成整个会话完成，无法覆盖新增的异步需求建单阶段，部分场景在发模型请求前就退出。因此不能声称所有当前功能通行，也不能把用户报告的死锁标为解决。

同一候选文件摘要与结果见 data-collection/issue51-validation-summary.json；原始扩展失败见 issue51-extended-checks.json；专用链路、需求、仅咨询报告分别为 issue51-flow-verification.json、issue51-requirements.json、issue51-consultation.json（均相对 data-collection/）。本次未调用真实模型供应商，未提交或切换有效发布。谛听已实际落库两条本单事件；Git 提交与消费未确认。原生候选构建另附实际回执。

## 新候选构建回读

Windows x64 / Visual Studio 14.5 构建成功，SCons 实际用时 421.65 秒。17 项原生 AIChat 测试与 171 个断言通过。新二进制实际返回 Agents／定时器／共工，页面切换测试通过，正式定义准入到模拟模型答复及回执通过。精确源码与二进制摘要见 data-collection/issue51-candidate-verification.json；该文件追加补充先前摘要，不改写旧记录。

通用 UI 测试现已越过页面断言，随后在“Enter 后立即进入模型忙碌态”旧断言失败（异步需求阶段尚未结束），未发出模型请求；仍不能将这批旧场景算通过。用户报告的死锁未在本单覆盖场景中复现，保留待定位。新构建保存在 bin/，未覆盖 project/godot/bin 的运行安装、未提交或发布。本单真实事件已落库，尚未完成 Git 交付门禁、提交和消费确认。

## Git 仓库剩余残留续清
本轮复用 #51 并完成 intake 回读。范围为离线校验器旧扩展豁免逻辑与项目缓存忽略规则，验证扩展内锁定证据、缺失/篡改拒绝及当前正式包。使用 .worktrees/issue51-cleanup 隔离修改，回填前核对主工作区原始摘要；不碰其他聊天文件，不改 framework/、批准原件或历史数据，不重建引擎。

续清结果：隔离候选检查通过并按原始摘要防并发覆盖回填主工作区。tools/check_gonggong_distribution.py 不再误把已锁定的谛听扩展当作未锁定豁免区；准入与证据仍逐文件验证，新增覆盖旧豁免恢复、扩展证据篡改/缺失、许可缺失的回归。12 项通过、1 项因 Windows 符号链接权限跳过；243 文件快照与正式框架校验通过。新增 **/.godot/ 忽略生成缓存，不删除其他聊天的状态。全仓旧名剩余命中为历史证据、只读兼容及第三方文本，保留不改。精确摘要和回执：data-collection/issue51-repository-cleanup.json。隔离工作树核对已回填后移除；本轮未提交、未发布，未改变上一轮尚待定位的死锁状态。

## 2026-11-05 隔离交付候选

本轮基于 origin/main `1b0a33fd`，仅交付验证工具、测试及缓存忽略差异；Windows x64 / Python 3.14 / Node，原生执行使用摘要匹配该基线的安装副本，不重建、不切换安装。UI cpp 及乱码修复由 #56 独立交付。移植摘要见 issue51-isolation-20261105.json（相对 data-collection）；通用 UI 脚本与历史摘要不同，旧通过结论不复用。

分发12通过1跳过、243文件快照、独立包9项及桥接35项通过。独立审查发现测试 teardown 在 ACP 不响应 EOF 时可挂起，已加入两秒强制结束所属子进程及 finally 清理，复核通过，非发布批准。新候选完整摘要及执行结果见 data-collection/issue51-verification-20261105.json。

二秒回执延迟的 retry/cancel/recovery_failure 三场景通过，最大采样帧间隔0.031758秒，模型及上下文使用隔离夹具。自更新实际重启回执成功，但 RuntimeSetup 与 EngineBuildApproval 争抢独占窗口，整体仅部分通过，已向 #56 交接；不能视为死锁根因已证实。通用 UI 的异步需求夹具尚未适配，不声称通过。停止条件：工具候选通过局部回归与提交门禁后交协调者；运行时死锁仍需真实场景复现及修复回归，Issue保持开放。

历史 summary 原件包含本机临时路径，仅保存在本地 issue51-validation-summary.local.json；可提交派生件为 data-collection/issue51-validation-summary-public.json，记录原件摘要且仅去除本机目录值。此前旧证据中的 summary 引用解析为该历史原件，不代表本轮执行。未调用真实供应商；不声称远端发布、有效安装切换或谛听消费确认。


# Issue #51 HTTP 取消阻塞续查

稳定需求 ID：olympus-residue-deadlock-20261104。
真实工单：https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/51。

本轮基于 origin/main c6445d3961f9de835b823a1529fd0a2d9f3ff478，独立分支 codex/issue51-http-cancel。此前残留清理及关联纠正候选 e1570456 / PR #61 保留独立，不重写其证据。路径相对仓库根；本文件为该独立续查候选的需求说明，整合时须保留此前阶段记录。

新触发为 #59 冻结源码94b0cfb534c209436b18fd724c690bcdb3e55f1f、exe SHA256 c8eb6a676d9f596fe833391cf0f5c7531a37b800b1bda915f11eff80a7131768：本地HTTP夹具延迟100秒，原生Stop后画面直到服务响应才恢复，点击准确墙钟未独立记录。该复现与最初用户死锁是否同因仍未知。

交付范围：AIChatDock聊天和模型列表HTTP取消路径的最小源码修复、Windows x64/MSVC候选构建、旧失败到新通过的隔离夹具证据。仅将两处线程式阻塞HTTP改为HTTPRequest非阻塞逐帧poll；保留通用HTTP核心、超时、大小限制、重定向、代理、generation guard、真实provider配置及共同框架。#59只改控制器状态边界，不共写本单cpp。不得替换有效安装。

验收：服务器明确进入延迟后触发Stop；头部、正文停顿及模型列表均记录同步Stop耗时和主线程最大帧间隔（本机阈值0.25秒），取消返回须早于服务端释放；随后新请求成功，迟到结果不写回；正常响应、模型列表与压缩响应有代表回归。沿用同一隔离输入比较旧失败和新通过，退出警告单列。验证平台仅Windows x64，不扩展多平台/真实服务认证。停止条件为本候选源码、实际构建、针对性回归、独立审查及交付门禁通过；原#51整体保持开放，除非另有证据完成原验收。

首次构建理由：仅修改原生HTTP请求配置，需真实编辑器验证Stop响应。复用#59只读复制到本工作树的对象缓存，SCons在本候选重新判定依赖并构建；缓存不代表候选已经验证。配置platform=windows target=editor arch=x86_64 tests=yes accesskit=no d3d12=no angle=no；不写其他工作树。

旧版已使用三秒延迟、相同服务器握手夹具重现：Stop调用2.782884秒，主线程帧间隔2.784506秒，均越过0.25秒；最终恢复和旧响应丢弃成功，但不能代替即时取消。源码链为threaded HTTP blocking read → cancel flag不能中断当前读取 → 主线程wait_to_finish。

性能适用边界：这里只解决所测网络等待引发的同步join；非阻塞网络不等于所有CPU帧耗时有界。TLS初始化/证书、解压和body复制回主线程，chunked大块及header解析没有逐帧预算，本候选不宣称所有TLS/异常大头/chunk均小于250ms，不扩展通用HTTP核心重构。

本轮最终结果：同一最终夹具下旧三场景Stop2.755–2.763秒失败；新三场景及1MiB gzip通过，Stop0.503–2.441毫秒。100秒头部延迟新候选Stop1.757毫秒、主线程gap6.325毫秒，恢复在旧服务释放前完成，实际观察旧服务释放后无陈旧回复。原生可见实点因computer-use两次无法激活窗口未执行，不计通过；已结束仅本单程序并核验窗口释放。测试退出RID/ObjectDB警告另列。源码与证据独立审查通过不等于发布批准。精确输入、构建与失败→通过证据见 data-collection/issue51-http-cancel-verification-20261105.json；未更新安装、未关闭原Issue。

## 2026-11-09 续办

关联 #92 新增 macOS 后台停止信号与恢复证据：Stop 3.256ms，旧请求释放前成功接收恢复回复，迟到结果未污染。原用户死锁的唯一根因与真实鼠标/键盘仍未知，不将新代表测试当成原症状复现。

本轮源修订、实测与模拟边界统一引用 `data-collection/before300-20261109/validation.json` 及同目录各项报告（路径相对仓库根）。


## 2026-11-09 当前候选补验与交付结论

当前候选补齐需求→开发、原生读文件与回执，以及停止/取消后双进程恢复；实际SCons编译期间的短时导航/焦点/取消也通过。现行框架有效入口与历史只读数据边界保持不变。关联#92的代表HTTP延迟取消及迟到回复隔离通过，但没有复现用户最初卡死，唯一根因保持unknown。

宿主静默验证要求不驱动用户鼠标或键盘；本轮控件信号与gui_input证明程序路径，不等于真实OS指针/键盘响应。#51/#92继续开放，明确缺的是原症状的因果证据和原文要求的物理停止交互。可执行代表场景已完成，不重复原暂停调查或把新模拟成功算成旧症状修复。证据见`data-collection/before300-20261109-followup/validation.json`（路径以仓库根为基准）。
