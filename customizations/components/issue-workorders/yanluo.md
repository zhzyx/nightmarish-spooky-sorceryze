# 阎罗当前宿主入口

路径基准为仓库根。当前定义位于 `customizations/components/yanluo`，精确版本、指纹与对应批准由受信 grant 绑定的 `customizations/host-agents.json` 登记。v0.1.2 的历史批准保存在 `data-collection/yanluo-user-approval.json`。本接入在原位置加载该定义，不复制/迁移冻结框架、不改写旧批准。Git 专用执行留在 issue-workorders 接入层。

当前责任：合契交出已整合的候选、完整贡献快照和范围；阎罗负责最终核查、main 发布、发布后完成度复核、目标工单完成写入与回读；司南继续派发、依赖、父项验收和跨工单协调。已经在执行中的发布须完成原操作者交接，不能抢占或操纵其他工作树。此入口只接管新交接事件；原冻结 Agent 定义中的通用协作职责不扩展为另一位 main 发布者。

### 当前宿主的 Git 校验程序

以仓库根为基准，Git 交付检查入口为 `customizations/platforms/development/git/delivery/check_delivery.py`，提供 `--framework-root` 时沿用原清单的解析基准。提交后运行 `customizations/platforms/data-collection/git-files/storage/diting_files.py git-check --repo . --require-committed`。这两个入口对应原 HOST_PROTOCOL 第 5 项的检查。新宿主私有 grant 的 trusted_files 须包含两个脚本及原有可信依赖，注册表与旧 grant 的摘要变化后重新核验和签发。

## 协作者快速签发和自动提交

在可信工作树中使用 Git、Python 3.11+ 及[共享运行时](README.md)可解析的 GitHub CLI，以本人账号登录 github.com，具备仓库内容写入和 PR 创建权限。Windows、macOS、Linux 共用同一入口。先做业务验证并取得适用的独立审查，在基于最新 main 的任务分支仅暂存本工单内容。将验证范围、结果和必要审查引用写入 PR 说明文件；命令从仓库根运行，替换尖括号参数。

```text
python customizations/components/issue-workorders/writer_submit.py --issue <编号> --request-id <稳定ID> --title "<提交标题>" --notes-file <PR说明文件>
```

入口回读同仓库 WRITE、MAINTAIN 或 ADMIN 身份，运行正式门禁，为已暂存的树创建提交，执行提交后谛听核验并推送专属候选分支。GitHub 以当前协作者为作者签署一笔内容树完全相同的签发提交，绑定工单、原提交、树、目标和 main 基线。入口回读服务端签名、作者及唯一父提交后创建 PR，输出其 URL 与签发 SHA。此回执只用于这次 Git 候选提交。

连接中断后在同一工作树以同一账号重跑。入口按候选提交定位分支并核对已有签名及 PR。签发前若主线仅发生无路径/读取交叉的前进，可显式加 `--auto-integrate`（可选配合 `--reads-file` 声明读取依赖路径）在门禁前完成树级无冲突对齐；附加 `--supersede-prior` 可在新签发 PR 就绪后自动收口本人同工单被替代的旧开放 PR（或单独运行 `--prune-superseded`）。多人并行提交期间，可运行 `writer_submit.py --queue` 在单次 GraphQL 快照中聚合所有账号的在途 PR、审计分层、CI 状态与无冲突合入波次（`merge_waves`）。CI 等待期间若主线前进且 `overlapping_write_paths` 为空，原签发者可在独立临时工作树运行 `python customizations/components/issue-workorders/writer_submit.py --rebind-pr <PR编号> --close-superseded` 重新执行正式门禁、谛听校验与服务端签发并收口被替代旧单，出现写/读重叠时仍拒绝自动重绑并转合契整合。取得 PR 后沿下述交付路径核验精确 SHA、审查和 CI，并用本人账号合入及回读。生产工具、模型预算及宿主服务凭据仍由其各自宿主授权。

## 同一候选的交付核验与模块 CI

阎罗核验完整候选及已有审查、测试、准入证据的责任、范围、输入摘要和结果是否适用；不按文件、账号或交付阶段另起业务审查。同一候选汇总一轮必要独立审查，各责任边界可并行核查；“一轮”不限制必要审查者数量，也不免除修复后的复验。已有证据完整且仍适用就复用，缺失补齐，新增差异、基线变化或明确风险仅复核受影响部分。

独立审查要求审查责任与实现责任独立。已授权的独立 Agent 或有权独立协作者均可执行；保存候选、范围、真实工作者及结论。实现者自评或用户验收不能代替；明确不通过须修复后复验。阎罗核验证据不替代原审查者、元衡或业务验收者作判断。

GitHub approval 是否必需，以实际分支保护、规则集或用户明确要求的 GitHub 审批为依据。用户保留的业务判断按其指定方式完成，不自动转成 GitHub approval。tier、CODEOWNERS 邀请或普通 review request 本身不产生必需审批，也不证明审查完成。没有实际人工门禁且独立审查证据适用时，协作者用本人身份交付，不要求固定账号或所有者再次签发；存在人工门禁时取得相应批准，不用 Agent 报告或管理员权限绕过。

当前 CI 以 [模块化 CI](../../../Markdown/testing/ci-modules.md) 和 `tools/ci/modules.json` 为唯一模块选择来源。`writer_submit.py` 从签发基线读取该注册表，由已安装的 `select_modules.py` 对真实差异（含新增、删除）计算模块归属；`audit_profile.module_selection` 绑定基线、候选树、逐路径归属及所选模块，另保存注册表摘要。候选自身修改注册表不能删除基线要求；未知路径或损坏注册表拒绝交付，先完成归属修复及独立核查。

阎罗核对 `issue-association`、注册表公共检查和所选模块检查的真实成功结果。任何适用必需检查缺失、跳过、失败或尚未完成均不算通过。原五级标签仅保留为审查范围与治理提示，不再叠加另一套 CI 矩阵或全仓审查；只有尚未采用模块注册表的历史基线沿用旧分级检查。`framework/`、Agent/Skill 定义与准入变更继续遵循精确候选治理，不由模块测试替代。

例如，马良工作台的 `addons/ainative/*.gd` 和非测试 `tools/ainative/*.py` 会被 `editor/SCsub` 嵌入原生资源，不能按脚本后缀豁免构建。其提交消费马良模块已声明的测试、编辑器构建和会话验证；新增独立测试或测试 Provider 不因“未登记宿主文件”另加全量 Windows 检查。多模块提交核对所选模块的并集，不扩展到未变更模块。

此外，引擎内 `complete_delivery` 与 `editor_delivery_finalize.py` 支持 `delivery_mode="slice"`（分片交付模式）：多人并发协作同一父工单时，分片 PR 合入并回读后记录阶段验收声明、保持 Issue 开放及原 `status:in-progress` 标签，避免提前关单阻塞其他账号在途工作；`yanluo_host.py` 另支持 `mode="pull_request_merge"`（零路径重叠主线前进时无需重签即可原子合入）及规范化 `scope_digest`（容忍工单顶部临时协调头更新，仍拒绝需求正文篡改）。

## 协作人以本人账号交付（PR 或合并队列）

审查与 CI 按上一节统一判断。`issue-association` 的元数据范围见[工单接入](README.md)；`startup_failure` 且零作业时先读取 Actions 注释和事件策略，不当成工单关联错误，也不靠请求固定账号审批解除。

本人交付使用同一认证通道的 `gh api user --jq .login` 和 `gh repo view OWNER/REPO --json viewerPermission` 核对身份与有效权限；OWNER/REPO 取自 `work-items.json` 并与 origin 核对。提交作者、Issue 创建者和本地 Git 用户名不是权限证明。只有任务确需完整协作者名单时才分页查询；读不到名单不等于本人无权。共工操作授权见[工作区权限](../../../Markdown/workflow/repository/README.md#权限与有效来源)，不维护账号白名单。

1. 每位协作人可提交自己的候选。先按正式工单门禁提交，再运行 git-check --require-committed。可写者推送任务分支；只读或 triage 协作人按仓库允许的 fork/PR 流程贡献，无权写入上游或自行合入。贡献资格不改变仓库 ACL。
2. 当前有合入权限的人是本次发布执行者，可在自己的认证通道中承担阎罗的交付职责。接收合契交接，核对 PR 目标为本仓库 main、完整贡献和验收范围、必要独立审查、正式门禁、交付证据及精确候选 CI。固定已审查的 PR head 和预期 main，核对候选包含该基线。合入前核对最新状态；并发发布须交接。基线变化时更新候选并复验，或使用按最新基线验证的合并队列。
3. 使用仓库允许的 PR 合入方式，例如 `gh pr merge PR --repo OWNER/REPO --merge --match-head-commit SHA`；要求队列时按队列流程提交。PR 为真实编号，SHA 为通过核查的完整 head。遵守分支保护、审批和 CI，不用 admin 绕过，不直推 main。必要审查仍由独立审查者提供。本人 PR 路径不调用 yanluo_host.py，不需要宿主密钥、私有 grant 或固定账号代办。
4. 回读 PR 的 mergedAt、mergedBy、mergeCommit、headRefOid 和远端 main，验证交付提交已进入主线及交付内容对应；排队或请求成功不算已交付。按下文对完整验收清单复核进度，记入实际操作者、候选及回执，满足整单验收才按生命周期更新并回读 Issue。权限被撤销、检查未过或回执未知时，只保留受影响步骤待处理，不借用他人账号。

## 交付后验收与人工判断

交付接收触发以下验收；当前执行者持续持有责任，移交须取得实际接收回执。

1. 阎罗回读目标交付版本，与业务验收者按原设计逐项列出通过、失败或尚待验证的内容。对尚待验证项立即调用已有工具或有权验收者执行；出现可修复的失败即交回原主责修复，沿正式交付流程推进新候选，并复验受影响项。
2. 司南对照完整需求核实目标、子项和父项各自的验收及依赖。阎罗把证据写回每个已满足条件的关联 Issue，设置 done、以 completed 关闭并回读状态、原因与标签。部分完成依原生命周期处理，承接单也纳入后续追踪。中断从最后真实回执继续；所有范围内结果均有对应结束回执才报告全部完成。
3. 权限、准入、环境等实际阻塞当次按[夸父入口](kuafu-routing.md)接单排查，可恢复失败由有权主责处理。仅当当前手段确实用尽，或遇到必须由人决定的取舍，才暂停受影响步骤。司南用原工单的稳定问题键记录受影响验收项、已试方法与结果、所需决定或操作、负责人及恢复条件。当前宿主通过已有的用户对话或授权待决通道向该负责人发出一次提醒，说明可选方案与影响；只有登记而未送出的提醒须保留待送状态。其他验收项继续推进。负责人答复、权限恢复或外部回执到达后，按原工单核对并续办；同一未变化问题不重复提醒。

## 宿主自动快进发布

本节仅适用于选择宿主授权发布的路径；本人 PR 交付不执行本节。`yanluo_host.py --repo REPO --grant PRIVATE_GRANT --apply` 是 GitHub CLI 接入，默认不带 `--apply` 只校验授权。它从调用者已经认证的 gh 通道回读账号、Issue 和远端，使用同一通道更新 main、状态和记录。宿主必须在自身可信进程中提供 GONGGONG_HOST_KEY（至少 32 字符），沿用当前运行时 HMAC-SHA256/canonical JSON 约定。密钥不进日志、源码、工单或模型上下文；接入没有签发授权的命令。grant 由有权宿主签发，至少包括：

- payload：candidate（closure.Candidate 全部字段）、绝对 repo_root、expires_at（Unix 秒）、authority_ref、account_login、target=main、mode=fast_forward、adapter_sha256、approval_sha256、candidate_manifest_sha256、host_registry_sha256、definition_digest、trusted_files（可信安装全部执行依赖及framework文件摘要）、checks、required_ci_names、acceptance_items。
- checks：REQUIRED 中每项的真实证据路径（相对仓库根）、sha256、status=passed、同一 candidate。检查记录必须来自实际执行，独立审查由独立评价者承担；签名不把未知变成通过。交付核验先执行既有 check_delivery.py，结果列入 delivery 证据。
- acceptance_items：完整原 Issue 验收清单，每项 id、module、acceptance、state(done/remaining/unknown)、evidence。done 必须有真实验证依据；remaining 说明尚未支持内容；unknown 说明缺失证据。原始清单范围由宿主核对，不能删掉难项以提高完成度。
- signature：对 payload canonical JSON 的 HMAC-SHA256；代码/定义/候选/范围/权限漂移均需复核相应证据与签发，不跨任务复用。

仅此宿主授权路径可请求自动快进：先把精确候选推送到任务分支并取得精确 SHA 的 CI，宿主回查正式门禁和 committed-data，再向 main 请求 `force=false`。不会调用 admin 绕过或构造未测的新合并树。保护分支要求 PR/合并队列时由保护规则拒绝此路径，保留待处理，不自动降级保护。多个工作树共用 Git common-dir 内的 OS 文件锁；这不是分布式全局锁，其他宿主仍需按交接规则串行发布。

实际执行状态使用 Git 私有目录的持久 journal；它不是 Diting 已落库或已消费的证明。main/工单完成/进度复核状态同时记录到真实 Issue 时间线，供现有 GitHub 来源适配消费；消费未知时保持 null，不声称司南已经处理。任务的公开测试/来源与实际 Diting 文件事件仍按原门禁提交；运行结束新增的来源事件按实际采集回执追加，不改写本次源提交。

## 合入后的完成度与拆单

每次实际 main 合入后，阎罗对照完整验收清单复核，记录已完成项数/总项数、未完成项、未知项及远端提交。不用代码行数、PR 数量、主观工时或 token 估计进度。

剩余范围的拆单阈值、查重、承接及结转关闭统一按[Issue 生命周期](issue-lifecycle.md)执行。多数通过、创建 follow-up 或旧单关闭均不等于全部完成；未知项保留未知。新单本身不增加生产授权，已有授权范围内的剩余项仍按原授权继续，由司南按实际事件与容量协调；祖先工单须另核对整体验收。

故障恢复：先读真实 main 和 Issue，再用同候选的持久 verification 回执恢复。已发布不重复发布；缺回执不关闭；主线推进或范围变化只挂起受影响动作。权限失败、CI 失败和未完成项均保留准确状态。

宿主子进程环境移除签名密钥，门禁从可信安装加载；候选框架必须逐文件匹配宿主签名的可信框架清单。框架升级需独立安装审查，不能让待审候选自带门禁或替换进度实现来复用旧授权。状态标签只添加 done、删除本次已核对的旧 status；本机 journal 保存中断过渡，不覆盖其他业务标签。

当前宿主注册表为 customizations/host-agents.json，绑定上述已批准定义与元衡治理。customizations/registry.json 中原候选条目随批准对象保留，不将它的历史 pending 字段误当成当前宿主注册状态；此注册不改变 framework 的通用 Agent 清单，也不伪造后台进程。CLI签名同时绑定宿主注册表摘要。

## 子项交付与尾项结转衔接

按 [Issue 生命周期](issue-lifecycle.md) 区分正常完成与结转关闭。现有自动适配器只实现完成关单及剩余单创建，未实现原生父子关系迁移和 not_planned 结转关闭；这部分由实际有权操作者按文档逐项核实后执行。迁移进行中保持原单开放，不把创建 follow-up 当作承接已完成，不修改已批准 Agent 定义或将文档契约声称为自动实现。
