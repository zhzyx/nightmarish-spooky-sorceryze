# GitHub Issue 工单适配

宿主执行约束见 [执行范围与验证成本](execution-policy.md)：任务入口固定边界，交付阶段按变更选择验证，等待阶段合并真实状态事件，效果沿用 Diting 记录。它是本组件的流程约定，不改变共享 Agent 定义或声称已实现自动预算控制。


宿主开发入口使用同一脚本的 `--intake-only --tenant <配置租户>` 模式，仍需提供 `--repo`、`--issue`、`--request-id`。此模式只回读真实工单并验证仓库 origin、稳定 ID、类别、有效状态、租户及 workspace:gonggong，不执行模型、不代替正式框架准入。没有 Issue 时先经已授权需求入口创建/复用；聊天入口拒绝绕过，不以本地预览替代发布。

data-collection 内公开的业务来源与交付回执也是交付内容：本地提交门禁逐文件比较 index 当前字节，拒绝未跟踪、被忽略、未暂存或删除的采集原件。宿主私有 inbox/、outbox/、receipts/ 及采集根目录 *.local.json、SQLite 和标准旁文件必须保持忽略且未跟踪，强制暂存会被拒绝；公开交付证据放在其他明确路径。任意业务证据不因被忽略而豁免。缓存、凭据和本机绝对源路径不得发布；纠正追加记录。Diting 仍按既有规则校验并在提交后核对 HEAD。服务器 required check、分支保护及 Sinan 事件来源仍需各自真实启用，入口校验不冒充这些能力。
Git 工作流接入子模块见 [git-workflow.md](git-workflow.md)。新建工单记录当前认证的 GitHub login；显式事件记录事件操作者与 Issue 修订标记，供并发更新核对。共工后续需在自身框架中实现相应来源适配和回读，本组件不修改 Sinan 分发包。

适用 GongGong 工程层；共工共同框架、Sinan 源状态和准入不变。本文路径均相对仓库根。工作区配置为 `work-items.json`，类别定义为 `.github/labels.json`，七种状态另列 `.github/status-labels.json`。每个类别表单携带唯一 `type:*` 和默认 `status:needs-decision`；开始生产前明确范围、授权及依赖并转为 `status:in-progress`，待验收时为 `status:in-review`。

Git 本身不提供 Issue，本工程采用现有 GitHub 远程仓库的 Issue。Issue 状态是权威；本地文档、创建计划和数据索引不是另一套工单账本。所有远程操作需要实际 GitHub 权限；已验证本机现有 GitHub CLI 登录及仓库写权限；若 `gh` 不在 PATH，将实际 CLI 的 bin 目录加入本机会话 PATH。账号凭据不进入仓库。GitHub 插件状态不影响已验证的本机 CLI 通道。

```powershell
# 预览标签，不进行远程写入
python customizations/components/issue-workorders/work_items.py labels
# 在安装并登录 gh 后创建缺失的标签，不覆盖现有标签
python customizations/components/issue-workorders/work_items.py labels --apply
# 预览首张实际需求工单
python customizations/components/issue-workorders/work_items.py issue --document design-docs/issue-workflow-20261102.md --title "工单 Issue 化与需求及采集目录" --type development --request-id issue-workflow-20261102
# 同一命令添加 --apply 后执行创建；收到真实 URL 后回填文档
# 对已有真实事件生成谛听来源索引
python customizations/components/issue-workorders/work_items.py collect --request-id issue-workflow-20261102
```

`issue --apply` 创建前分页检查所有开放/关闭 Issue 中的稳定需求标记，已有单张则返回其 URL，多张则拒绝。该检查避免串行重试重复创建；GitHub 不提供此客户端操作的事务锁，禁止并发创建同一需求。网络超时后先重新查询，不直接假定失败。创建不会自动派工、修改权限、关闭其他 Issue 或修改原文档。

发布顺序：准备并审查本地配置 → 连接 GitHub → 创建缺失类别标签 → 将模板发布到默认分支 → 创建 Issue 并回填链接 → 记录真实回执。远程发布仍按任务授权执行；不会因为本地脚本或模板存在而声称已上线。

采集前调用现有 Diting 验证工具；无实际事件、校验失败则拒绝生成成功索引。来源记录身份保持不变，采集索引只包含路径与摘要，不把历史记录重新上报为谛听自产事件。

提交前使用已审查、受信任的工程入口；不得执行未知 PR 提供的脚本：

```powershell
# gh 不在 PATH 时，GONGGONG_GH 可指向宿主已登录的 gh.exe；不存储令牌。
# 暂存本次交付和真实 Diting 事件，再运行（仓库根路径按实际环境传入）：
python customizations/components/issue-workorders/issue_gate.py --repo . --issue 6 --request-id issue-governance-20261102
```

本地门禁查询 `work-items.json` 对应仓库的真实开放 Issue，要求 origin 同仓库、唯一已知类别、唯一 `in-progress` 或 `in-review` 状态，稳定需求 ID 支持 `<!-- gonggong-request:ID -->` 或 Issue 表单的 `### 稳定需求 ID` 字段，歧义拒绝。它直接执行 `framework/tools/verify_framework.py` 正式模式（无 `--candidate`）与包含结构/摘要/关联验证的 Diting 提交前 `git-check`（不再重复运行 `validate`），拒绝历史事件删除或改写，并检查该需求已有真实文件事件且已被 Git 跟踪。`work-items.json` 必须显式绑定 `tenant_id`；只选取该租户和需求的事件，且至少一个 `kind=request` 事件的 `source_ref` 必须精确等于 Issue URL 或 `github:owner/repo:issue:N`。正式框架校验使用已安装包内完整性清单和精确准入，不访问外部共工。无外部框架同步来源；正式校验和实际采集缺失仍阻断。

输出摘要绑定当前 HEAD、index 与 tracked/nonignored 文件内容，检查前后内容和 Issue 状态须一致。修改后重新绑定候选并回查受影响证据；提交时复核 Git 内容，提交后另运行 Diting `git-check --require-committed`。此摘要不是签名、准入通行证、消费回执或可跨版本复用的成功证明；工具核验事件结构、摘要和关联；静态 tenant/source/actor 字段及 SHA256 不能认证操作者身份或证明事件叙述真实，也不替代宿主独立权限或业务验收。纠正已有事件时追加新事件及 supersedes，保留历史原件。

PR 正文必须有且仅有以下两行关联字段：

```text
GongGong-Issue: #6
GongGong-Request: issue-governance-20261102
```

`.github/workflows/gonggong-issue-gate.yml` 使用 PR 创建、编辑、同步等事件，无定时任务；`pull_request_target` 仅运行可信 base 工作流的固定 github-script，权限只读，绝不 checkout 或运行 PR 代码。CI 查询本仓库真实 Issue、类别/状态及需求 ID；无外部共工源时不冒称执行完整准入或业务验收。Issue 后续独立改标签/关闭不会自动刷新已有 PR 检查，合入前须重跑并复核最新状态。管理员需另将 `issue-association` 配置为分支保护必需检查；工作流存在不表示远程已强制，也无法约束仓库外直接修改 Godot。

回退：停止调用该适配器，保留既有 Issue、文档、事件和采集索引；不要删除远程标签或历史数据。恢复旧入口不能消除已经创建的 Issue。

接口依据：[GitHub Issue 表单](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms)、[gh issue create](https://cli.github.com/manual/gh_issue_create)、[gh label create](https://cli.github.com/manual/gh_label_create)。

普通引擎会话复用现有 Yanshi／ClarifyFeature 自动整理需求并建单，受限需求阶段与开发门禁分开，见 [宿主协议](../godot-host/HOST_PROTOCOL.md)。工单适配器不因此授予模型、工具或设计定版权限。

## 核验复用与成本（Issue #85 候选）

门禁仍前后核对 HEAD、index 对象及工作区精确字节；index 对象已绑定内容，不重复生成 staged binary diff。工作区字节流式哈希，不用 mtime/size 代替内容验证。整仓前后读取仍保留，不能声称已经消除全部磁盘读取。

Git 跟踪、忽略和 blob 内容使用 NUL 分隔路径与批量对象读取；Git 异常、合并冲突、链接对象仍失败。Diting 一轮只加载一次当前与历史数据。框架完整性扫描的实时摘要供候选和报告检查共享；正式准入状态和有效期每次检查。

通常一次门禁调用即可。宿主确有连续显式请求时，可运行 `issue_gate.py --repo . --session`，逐行通过 stdin 提交 `{"issue":85,"request_id":"verification-efficiency-20261105"}`。每行返回一个成功/失败 JSON；EOF 退出，不扫描、不轮询、不设后台任务。宿主必须检查每行 `state`，不能以进程仍存活或最后退出码代替门禁结果。

session 仅在同一进程内复用成功事件的结构/摘要校验，精确字节改变会失效；仓库、Diting validator 字节或 Python 版本改变清空缓存，失败清空缓存。门禁自身或已加载 Git helper 字节改变时拒绝继续，必须重启会话。关联图、Git 当前状态、Issue 状态、框架准入和候选前后一致性始终重新核对；磁盘上的旧成功文件不被当作缓存。普通一次性 CLI 不跨进程复用证据。

此节描述隔离候选能力，精确准入完成前不代表有效发布已切换。回退为使用原已批准版本；保留历史事件、测试与实测证据。
