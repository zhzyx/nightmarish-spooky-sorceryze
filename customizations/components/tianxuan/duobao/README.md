# 多宝（原生版本与 Git 兼容接入）

原生方向由 [#1382](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1382) 定义：多宝自主保存版本、变更与组合，Git 仅作可选接入。以下原生入口与已有线上 Git 服务分别说明；当前服务尚未切换到原生存储。

## 原生模块修订（#1386）

`native_store.py` 是 Python 标准库宿主工具。每个组织拥有独立模块头、不可变修订、内容摘要与请求回执。任务引用精确模块基线和已读对象；无关模块变化不要求重新生产，同模块不相交对象可合成。改变已读或已写对象、未知读取依赖下的模块漂移以及不兼容依赖会拒绝接收。调用方必须由可信宿主提供认证身份及完整读取集合；CLI 参数本身不证明身份或依赖完整性。

`submit` 的跨模块变更和回执在同一个短事务中提交。`dependencies` 可固定精确修订，或用 `@batch` 引用本次请求内的另一模块；`compose` 校验整个依赖闭包并保存候选。`received` 和 `candidate` 都不是验收或发布批准。SQLite 写入会短暂串行，不能将本地语义试验解释为无物理等待或多副本容量承诺。大文件流式存储、服务认证、可信读集合采集、证据缓存和发布接线仍由后续子项实现。

路径以仓库根解析；`--db` 必须是宿主明确指定的绝对路径，父目录须预先存在。编辑内容采用 Base64，删除采用 `null`，对象名只作逻辑标识。示例输入：

```json
[{"module":"gameplay","base":null,"reads":[],"edits":{"rules.json":"e30="}}]
```

```text
py customizations/components/tianxuan/duobao/native_cli.py --db D:/authorized-data/native.sqlite --tenant team-a submit --actor worker-a --request-key request-1 --input change.json
py customizations/components/tianxuan/duobao/native_cli.py --db D:/authorized-data/native.sqlite --tenant team-a head --module gameplay
py -X utf8 -m unittest discover -s customizations/components/tianxuan/duobao -p test_native_store.py -v
py -X utf8 customizations/components/tianxuan/duobao/verify_native_processes.py
```

实际证据见 `data-collection/duobao-native-processes-1386.json`（路径基准仓库根）：250 次旧基线提交、最多 16 个 CLI 子进程，空 PATH、无 Git 工作目录、重启重放、历史读取和冲突反例。测试创建并清理自己的临时数据库，不访问线上数据库。该证据仅支持记录的本机环境。回退为停用新增入口并保留数据库，不修改或删除旧 Git 服务数据。

## 既有 Git 服务

以下实现保留用于现有安装与可选 Git 接入；它的队列和分支机制不作为原生多宝的协作协议。

## 选型

- Git 服务内核：Gitea/Forgejo（开源、成熟、含 PR/权限/Webhook）；本地裸仓库由系统 Git 管理。
- 合入：持久化队列、分支/路径级冲突隔离、串行合入与合入证据。
- 平台只存仓库/PR/评审元数据；Git 对象由 Git 服务或本地裸仓库管理。

## 当前实现

`git_service.py`：系统 Git CLI 适配器，仓库为裸仓库；提交与合并在临时克隆中执行后推回，复用 Git 而不重写协议。

- 构造时可显式指定 `git_executable`，否则读取环境变量 `GIT_EXECUTABLE`，再回退到 `git`。
- 覆盖仓库创建、提交、分支、分支删除、`log`、`diff`、`tree`/文件列表、`tag` 列表、`status`、单分支合并与批量合入（`merge_batch`）；合并支持 `--no-ff`、`--ff`、`--ff-only`。
- 仓库镜像导入：`import_repo` 以 `git clone --mirror` 保留分支、标签与远端引用；来源先经 `validate_import_source` 校验（仅 https/ssh/git/file，禁止密码凭据，可配主机白名单，本机路径需显式开启），失败或超时清理本次目标。
- 冲突时抛出 `MergeConflict`（含冲突路径）并中止临时克隆中的合并，裸仓库保持原状。
- 并发推送使用显式 `--force-with-lease` CAS 保护：目标分支被无交叉路径并发推进时，`commit` 与 `merge` 在同一临时克隆内自动拉取最新引用并重放；并发 `commit` 命中同路径或文件/目录前缀重叠时立即抛出 `MergeConflict` 拒绝静默覆盖；`merge_batch` 在单次克隆中合入全部无冲突分支并隔离冲突分支。
- ref、仓库名与文件路径先校验，拒绝 `..`、绝对路径、shell 元字符；子进程固定 `shell=False`。
- 提交输入拒绝 `.git` 管理路径及其代表性平台别名；全部目标预检后才写入，拒绝符号链接、可检测的 junction 和解析后的管理目录路径。Git 命令显式禁用 hooks、fsmonitor 和提交签名。

`policy.py`：保护分支与合入授权的纯函数策略。

- 保护模式来自 `TIANXUAN_PROTECTED_BRANCHES`（逗号分隔，支持 `fnmatch` 通配符，例如 `main,release/*`）；非法模式在启用保护前拒绝。
- 受保护分支只能经多宝合入队列写入，直接合并（含 Gitea PR 合并入口）返回 403；创建/删除受保护分支只允许租户 `admin`。
- 合入队列在入队和执行前分别解析操作者角色：viewer 拒绝，editor/admin 可经队列合入；角色在执行前被撤销时候选项以 `rejected` 结束并保留证据。

`merge_queue.py`：SQLite 持久化合入队列。

- 候选持久化、优先级、串行领取、stale 恢复、自动 worker、失败重试与取消。
- 候选可绑定 PR 编号与工单引用（`pr_number`/`issue_ref`），绑定写入证据并在合入结果中保留；重试与取消仅创建者或租户 `admin` 可执行。
- 可选 `event_sink` 把入队与终态写入领域事件（生产入口接 `Tianxuan.record_actor_event`）；事件通道失败不阻断合入。
- 临时 worktree 预检、冲突隔离、可配置检查命令、独立 HOME/TEMP、凭据环境剥离、进程树超时与合入证据（`merge_sha`/检查输出/冲突路径/策略判定）。

`gitea_client.py`：Gitea/Forgejo HTTP 客户端（服务 token；可选 `sudo` 代表指定用户）。

- 仓库 list/create/get、分支 list、PR list/create/get/merge（merge/rebase/squash/fast-forward-only）、Issue 列表。
- 评审：`list_reviews`/`create_review`（APPROVED/REQUEST_CHANGES/COMMENT）。
- 提交状态：`list_commit_statuses`/`create_commit_status`（pending/success/error/failure/warning），供 CI 回写。
- `sudo` 参数写入 `Sudo` 请求头，让管理员 token 以指定 Gitea 用户名执行；写操作由上层要求操作者已绑定 Gitea 身份，读操作可回退服务身份。
- 仓库创建要求租户 `admin`；PR 创建与评审要求 editor/admin；合并前读取 PR 目标分支并按保护策略判定。
- `TIANXUAN_REQUIRED_APPROVALS` 设置合并所需独立批准数（默认 0）；大于 0 时合并前读取评审，按每位评审者最后一次状态统计 APPROVED。
- `TIANXUAN_REQUIRED_CHECKS` 设置合并前必须为 `success` 的提交检查 context（逗号分隔，默认空）；缺失、失败或 pending 均拒绝合并。

`backup.py`：仓库根与 SQLite 状态的离线备份/恢复工具。

- `create` 生成 zip（`repos/`、`state/`、`manifest.json`），SQLite 使用在线备份 API 生成一致性快照。
- `verify`/`restore` 先校验清单、大小、SHA256 与路径（拒绝目录穿越、绝对路径、重复条目与未登记成员），验证通过后才写入；目标非空需显式 `--overwrite`。

HTTP/API（`server/api.py`）已暴露：

- 本地仓库浏览：`GET /api/v1/git/repos`、`branches`、`log`、`diff`、`tree`、`tags`。
- 本地仓库分支：`POST /api/v1/git/repos/{name}/branches`、`DELETE /api/v1/git/repos/{name}/branches/{branch}`。
- 仓库导入：`POST /api/v1/git/import`（仅 admin；`TIANXUAN_IMPORT_ALLOW_LOCAL` 控制本机来源，`TIANXUAN_IMPORT_ALLOWED_HOSTS` 限制远端主机）。
- 合入队列：`/api/v1/merge-queue` 入队、列表、处理、状态、重试、取消。
- 在编辑器天枢工具栏打开“多宝合入”，填写仓库、来源和目标分支。读取来源候选或填写完整提交，再发起合入请求。使用“刷新检查”读取结果，“读取目标分支”单独读取目标当前提交。编辑器重启后可凭仓库名及请求编号刷新。
- 已认证的账户在 Git 存储模式调用 `POST /api/v1/git/repos/{name}/merge-requests`，提交 `source`、`target`、`candidate`。服务核对来源分支的完整 OID，同时锁定目标基线。相同账户和精确输入对重放同一回执。
- `GET /api/v1/git/repos/{name}/merge-requests/{id}` 返回来源候选、目标基线、当前 `check_state` 和各项检查退出码。队列 worker 在这两个提交上运行合并预检及配置的检查，`checked` 表示预检通过、待合入。任一分支偏离或不可读取时返回 `stale`。独立的 `GET /api/v1/git/repos/{name}/branch-tip?branch=…` 返回实际分支尖端。
- “查看冲突差异”读取精确请求的两侧文件。逐文件选择来源、目标或编辑后的文本，再点“重建并检查候选”。服务在独立分支保留两方提交作为双亲，返回新的请求编号和检查。原来源与目标分支继续保留。
- 发起合入请求前填写天璇工单 ID。候选检查通过后，有写权限的发起人可以点击“交付并回写工单”。发起人和其他有写权限的成员都可以“批准候选”或“要求修改”。项目设置批准数时，每个账号对当前候选的批准计一次。队列核对当前分支、审批意见和必需检查，原子推进目标分支，并将确切提交与请求编号写入工单。用同一请求重新交付可找回原评论；目标已移除该提交时会提示重新核对。
- Gitea：`/api/v1/repos` 列表/创建/读取、`branches`、`pulls` 列表/创建/合并，`pulls/{number}/reviews` 列表/提交，`commits/{sha}/statuses` 列表与 `statuses/{sha}` 写入。

Web `/repos` 已接入本地仓库浏览、合入队列面板与 Gitea PR 面板；文件树面板的后端接口已就绪，前端仍使用演示数据（见 #1188）。

```sh
python -m unittest discover -s customizations/components/tianxuan/duobao -p "test_*.py" -v
```

`test_git_service.py` 使用 `GIT_EXECUTABLE` 环境变量指定测试 Git，未设置时保留既有 Windows 路径。覆盖创建仓库与首次提交、分支与列表、log、diff、tree、分支删除、快进合并、冲突合并的干净回退，以及非法 ref/路径拒绝。`test_policy.py` 覆盖保护分支解析、匹配、角色授权与合入路径；`test_backup.py` 覆盖备份/恢复、SQLite 快照、摘要与路径校验；`test_merge_queue.py` 覆盖队列执行、策略拒绝与重试。`test_admin_paths.py` 验证管理路径拒绝、完整写入前预检和正常文件兼容；目录别名模型不代替 Windows 文件系统实测。

## 首版非目标（需单独立项）

- LFS 服务端对象分发与客户端 checkout（已支持指针识别与导入时可选 `git lfs fetch`）；子模块递归克隆/更新（只读展示已支持）。
- 跨副本共享合入队列（当前依赖单 SQLite 库；已提供 worker 注册/心跳、stale 恢复与 worker 列表）。

## 外部验收（需目标宿主）

- TLS 证书、域名与反向代理的实际部署。
- 数据卷备份恢复演练回执与监控接入。
- PR 管理面板真机截图与人工验收。

## 状态

可运行的内部原型，不是可迁移的托管仓库：本地 Git 操作、代码搜索、逐行追溯、合入队列、保护分支策略、备份工具与真实 Gitea 28.3.0 的仓库/分支/PR/合并已可用；评审、每用户身份、导入与初始化工具均已落地；运维演练回执需目标宿主，多副本 worker 属后续架构项。验收与剩余项以 #1188 为准。

仓库参数必须是实际普通工作区根或裸仓库根；linked worktree 与指向根的符号链接可用。普通子目录即使能被 Git 向上发现，也会在业务操作前拒绝。根路径探针保留合法 POSIX 换行字符。

## 不可变候选接收（#1451）

需要保存旧固定输入上的生产结果且不移动模块 head 时，使用 [候选接收入口](native_candidates.md)。未知读取仍保持未知；候选保存与后续整合、验证及发布是不同阶段。
