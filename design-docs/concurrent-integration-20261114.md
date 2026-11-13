# 多协作者高并发合入优化

需求 ID：concurrent-integration-20261114

Issue：https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1151
排障关联：https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1154

用户授权：2026-11-14 当前 Codex /goal，探索整个仓库并优化代码与依赖，使多个协作者、内容产出方和模型能够快速并发合入。

## 验收

- 对全部 Git 跟踪路径建立可复现分类清单，识别代码、第三方、生成物、运行时包、治理及历史证据边界；不以抽样审查声称逐行审查全部代码。
- 回读实际 PR、CI、分支规则与发布入口，区分共享文件冲突、依赖验证、容量排队和主线漂移，并记录基线。
- 在现有接入层优化可验证的瓶颈；以机器可读契约、确定性输入及冲突关系支持并行计划，未知依赖保守处理。保留精确候选、独立审查和真实权限。
- 验证独立变更并发、重叠变更隔离、依赖顺序、失败恢复和主线漂移；报告吞吐证据及未覆盖限制。
- 按正式门禁、独立核查、CI、main 回读及工单验收交付；逐项记录剩余范围。

## 实施原则

源代码本来多数为可读文本。仅转换格式不能消除共享状态与发布串行点；数学用于明确不变量、读写集合与依赖关系，不取代可执行程序。第三方、冻结框架及历史证据保持各自边界，依实际瓶颈选择修改，不进行没有消费者验证的全仓重写。

从 origin/main 65e1fdc9f004bdf0a945f1ea4568b91d5bc4c1c4 隔离开发，不使用主工作区其他任务修改。已有 #1085 发布协调和 #1080 CI 事故作为排查来源，原任务候选保持原责任。

召回 github-issue-delivery/reconcile-workflow-incidents revision 2：实际失败作业必须与修复后的同一验证步骤对应；其他任务或仅编译成功不能证明恢复。本任务适用这一证据约束，尚未声明复用验证完成。

## 固定基线的初步审计

全量对象枚举：28,191 个 Git 跟踪文件，415,868,876 字节。其中 thirdparty 4,893 个、modules 4,374 个、editor 1,905 个、gonggong-diting-data 9,071 个、data-collection 1,535 个。摘要见 data-collection/concurrent-integration-inventory-1151.json；可通过 integration_plan.py 对记录的 revision 重建完整对象清单。这是目录/对象覆盖，不是全部源代码逐行审计。

- 发布：#1085 的实际协调记录描述候选通过 CI 后 main 推进、旧候选被拒绝及人工发布窗口；不等于本任务已复现所有发布故障。
- 构建：tools/build_engine_modules.py 已支持原生实现改动对应目标构建、文档与采集记录跳过引擎编译，未知输入回退 full。runner.yml 已有 merge_group 入口，不能宣称完全没有队列支持；远端保护查询返回 404、规则列表为空，不能据此断言已启用服务端合并队列。
- 文本不等于运行时：editor/SCsub 将部分 Godot/Python 脚本生成头文件；天枢部分 UI 是独立包；Tianxuan build-impact 声明 host_tool，需沿实际消费者逐项验证。不按后缀批量豁免引擎构建。
- 合契：现有并发整合规范已要求固定贡献、真实 merge-base、独立副本和组合验证。本次在其宿主目录补只读自动清单与准备批次，保持原有职责和准入，不另建中心状态账本。

## 尚未验收

第二批候选减少签发分支 staging/signature 两次 push 与 PR 的重复静态检查：仅跳过 `push` 到 `refs/heads/codex/submit/`，PR/main/manual/merge_group/tag 仍沿原有启用条件。实际旧 push 运行 43522243343 的静态作业耗时 21 秒；这是一个样本，不外推总吞吐。

已核对 SConstruct、SCsub 和 builders 中的实际 customizations 引用。仅四个明确独立的合契 CLI/测试/说明/专用 workflow 路径加入引擎构建排除，未知新增路径、混合原生实现、头文件和嵌入脚本仍按原规则验证。该路由修改自身仍触发完整 CI，不用待审排除绕过自身验收。7 项构建路由测试及 9 种 workflow 表达式条件通过；独立核查者 /root/sinan_b39efaa5c949ae7c 未发现阻断缺陷。远端优化结果尚待回读。

当前已认证身份 viewerPermission=WRITE，GitHub GraphQL main mergeQueue=null。尚无已启用服务端合并队列的证据；本任务未修改远端分支保护或假定具备管理权限。准备并行不取消最终分支更新的串行约束。

当前工具不自动合入、不证明语义兼容、不证明提升真实 CI 吞吐。剩余：完整依赖消费审计、真实并发/排队基准、受影响构建路由优化、发布接入与恢复试验、精确候选 CI、main 回读和整体验收。不得以本工具通过测试关闭整体需求。

## 原生缓存与宿主代码边界

本批次对两套缓存身份同时加入精确宿主输入清单，限定已核对的 43 个 Tianxuan/合契路径；清单自身始终计入身份，未知文件继续保守计入。SCons 的实际消费者优先级高于排除清单，因此脚本日后被生成器消费会重新触发失效。本地缓存读取工作树，hosted artifact 读取 HEAD blob，未提交策略不会改变后者身份。损坏策略回退普通构建或完整树身份。

Windows 实际图 dry-run 得到 9,362 个原生输入，与 43 个路径交集为空；小型真实 SCons 夹具验证新增消费者时失效。12 项本地缓存、2 项宿主边界及 8 项 artifact 测试通过，1 项 POSIX 夹具在 Windows 跳过。独立审查者 /root/sinan_bf2b42c978b32940 额外验证构建中修改清单拒绝发布；真实 symlink 夹具因 WinError 1314 未验证。新增 Windows/Linux CI 持续执行这些测试，尚待本候选远端结果。证据见 data-collection/concurrent-native-cache-1151.json。

PR #1170 的 Windows 完整构建、路由及 planner 检查已成功，两个签发 push 的重复作业确实 skipped；它尚未合入，main 已变化。这是减少重复工作的实际证据，不是全链路吞吐提升百分比。发布协调已获得用户明确授权；#1080 当前发布者请求优先窗口，本任务不抢占其候选。#951 的等待安排已解除。

剩余验收继续包括：精确新候选的 CI 与 main 回读、真实缓存复用和并发发布收益、其他消费条件及失败恢复；父 Issue 保持进行中。
