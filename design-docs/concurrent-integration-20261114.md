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

## 全仓可读性／数学形式化核对与四层并发优化（基线 `1593063c`）

1. **可读文本与数学形式化的真实边界（`integration_plan.py` 扩展审计）**：
   - 对 `1593063c4ea197be23f40b81f987b8cf068f6dff` 全量枚举 28,234 个 Git 跟踪对象（416,268,237 字节）：其中 **28,110 个文件（99.56%，400,935,755 字节）本身已是 UTF-8 可读文本**，仅 124 个文件（0.44%，15,332,482 字节）为二进制图标、字体、测试夹具与历史截图；八类架构边界（`engine_native` 9,355、`thirdparty` 4,893、`telemetry_and_evidence` 10,924、`documentation_and_specs` 1,208、`tests_and_samples` 609、`host_adapters_and_apps` 519、`ci_and_repo_config` 465、`framework_governance` 261）均可由 `integration_plan.py` 按任意固定提交重建。
   - 近期并发排队的全部 PR 修改的均是纯文本源码与 JSON/Markdown，证明**仅靠文本化无法消除 `refs/heads/main` 单引用 CAS 串行点、过宽 C++ 全量 CI 触发与基线漂移拒绝**；同时，C++／Python／TypeScript 编译器、Godot ABI 与 `frozen-distribution.json` 字节锁定的元衡／共工框架需要可执行源码而非纯数学符号重写。
   - 数学的正确落点是**以前缀闭包集合代数与 DAG 偏序形式化并发合入不变量**：令贡献 $c_i$ 在共同基准 $b_i$ 上的写集为 $W_i = \Delta(b_i, t_i)$、显式读集为 $R_i$（未知记为 $\bot$），路径前缀闭包交集满足 $\overline{W}_i \cap \overline{W}_j = \overline{W}_i \cap \overline{R}_j = \overline{W}_j \cap \overline{R}_i = \emptyset$ 且 $R_i, R_j \neq \bot$ 时，树变换在对象层满足交换律且互不覆盖。
2. **合契内存态无锁批次合成（`integration_plan.py --compose`）**：
   - 默认在 Git 隔离对象目录（`GIT_OBJECT_DIRECTORY` quarantine）内用 `git merge-tree --write-tree` 折叠跨不同历史基线的无冲突贡献，核验每步树差异精确等于 $W_i$ 且目标 blob/mode 与源候选逐项一致，自动隔离路径冲突或前置受阻项，且对 `.git/objects`、index 与工作树零写入（16 份跨三代基线的合成贡献在 223.87 ms 内完成 1 批合成）。
3. **签发入口基线漂移无重叠快速重绑（`writer_submit.py --rebind-pr` / `--auto-integrate`）**：
   - 针对 CI 期间 `main` 被无关提交推进导致的重复建单与排队：原签发者可通过 `--rebind-pr <PR> --close-superseded`（或签发前 `--auto-integrate`，支持 `--reads-file` 读取依赖核验）在独立临时工作树内用 `git merge-tree --write-tree` 对齐最新 `main`，重跑完整 `issue_gate.gate`、`diting_files.py git-check --require-committed` 与 GitHub 服务端签名，并在新单就绪后关闭被替代旧单；存在任何写/读路径重叠时立即拒绝自动重绑并保留合契人工/语义整合边界。
4. **引擎构建路由与原生缓存统一收敛（`tools/native_host_inputs.json`、`build_engine_modules.py`、`editor_native_cache.py`、`tianxuan-tests.yml`）**：
   - 经 Linux 实测 SCons dry-run probe（9,379 个 `native_sources`）与 Windows SCons probe（9,362 个 `native_sources`）双重核验，将已审查无原生消费者的天璇前后端、部署配置、Markdown 规范与合契工具共 **121 个精确路径**纳入 `tools/native_host_inputs.json`（排除 `build-impact.json`、`module.json`、`component.json` 等边界声明文件）。
   - `build_engine_modules.py` 仅从比较基准修订（`revision:tools/native_host_inputs.json`）读取已合入策略，因此任何修改 `tools/native_host_inputs.json` 自身或新增未审查文件的 PR 仍强制走 `full` 引擎验证；已审查宿主文件的常规修改跳过 15 分钟 Windows C++ 编辑器重编，改由扩展后的 `tianxuan-tests.yml`（Python pytest + Next.js `tsc --noEmit` & `next build`）与 `integration-plan.yml` 快速验证。
5. **多宝裸仓库乐观 CAS 重试与单克隆批量合入（`duobao/git_service.py`）**：
   - `GitService.commit` 与 `GitService.merge` 改为显式 `--force-with-lease` CAS 推送：目标分支被无路径交叉的并发提交推进时在同一临时克隆内自动拉取重放（16 线程并发写 `main` 实测 16/16 全部成功，耗时 1,516.79 ms）；并发 `commit` 命中同一路径或目录前缀时立即抛出 `MergeConflict` 防止静默覆盖丢失更新。
   - 新增 `GitService.merge_batch`，在单次克隆中批量合入多个无冲突分支并将冲突分支干净隔离到 `isolated` 回执（15 个无冲突项 + 1 个冲突项单次克隆合入耗时 266.28 ms，对比 14 次串行 `merge` 702.52 ms）。

实测与代码摘要见 `data-collection/concurrent-integration-throughput-1151.json`。剩余验收：精确新候选的远端 CI 与 `main` 合入回读、生产环境跨会话缓存命中与远端合并吞吐持续观测；父 Issue #1151 保持开放直到整体验收回读完成。
