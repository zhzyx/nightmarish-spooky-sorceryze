# 多宝（代码仓库）

复用开源 Git 实现，不重写协议；多宝负责合入编排、保护分支策略、权限边界与运维工具。

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
- 临时 worktree 预检、冲突隔离、可配置检查命令、独立 HOME/TEMP、凭据环境剥离、进程树超时与合入证据（`merge_sha`/检查输出/冲突路径/策略判定）。

`gitea_client.py`：Gitea/Forgejo HTTP 客户端（单一服务 token）。

- 仓库 list/create/get、分支 list、PR list/create/get/merge（merge/rebase/squash/fast-forward-only）、Issue 列表。
- 评审：`list_reviews`/`create_review`（APPROVED/REQUEST_CHANGES/COMMENT）。
- 仓库创建要求租户 `admin`；PR 创建与评审要求 editor/admin；合并前读取 PR 目标分支并按保护策略判定。
- `TIANXUAN_REQUIRED_APPROVALS` 设置合并所需独立批准数（默认 0）；大于 0 时合并前读取评审，按每位评审者最后一次状态统计 APPROVED。

`backup.py`：仓库根与 SQLite 状态的离线备份/恢复工具。

- `create` 生成 zip（`repos/`、`state/`、`manifest.json`），SQLite 使用在线备份 API 生成一致性快照。
- `verify`/`restore` 先校验清单、大小、SHA256 与路径（拒绝目录穿越、绝对路径、重复条目与未登记成员），验证通过后才写入；目标非空需显式 `--overwrite`。

HTTP/API（`server/api.py`）已暴露：

- 本地仓库浏览：`GET /api/v1/git/repos`、`branches`、`log`、`diff`、`tree`、`tags`。
- 本地仓库分支：`POST /api/v1/git/repos/{name}/branches`、`DELETE /api/v1/git/repos/{name}/branches/{branch}`。
- 仓库导入：`POST /api/v1/git/import`（仅 admin；`TIANXUAN_IMPORT_ALLOW_LOCAL` 控制本机来源，`TIANXUAN_IMPORT_ALLOWED_HOSTS` 限制远端主机）。
- 合入队列：`/api/v1/merge-queue` 入队、列表、处理、状态、重试、取消。
- Gitea：`/api/v1/repos` 列表/创建/读取、`branches`、`pulls` 列表/创建/合并，`pulls/{number}/reviews` 列表/提交。

Web `/repos` 已接入本地仓库浏览、合入队列面板与 Gitea PR 面板；文件树面板的后端接口已就绪，前端仍使用演示数据（见 #1188）。

```sh
python -m unittest discover -s customizations/components/tianxuan/duobao -p "test_*.py" -v
```

`test_git_service.py` 使用 `GIT_EXECUTABLE` 环境变量指定测试 Git，未设置时保留既有 Windows 路径。覆盖创建仓库与首次提交、分支与列表、log、diff、tree、分支删除、快进合并、冲突合并的干净回退，以及非法 ref/路径拒绝。`test_policy.py` 覆盖保护分支解析、匹配、角色授权与合入路径；`test_backup.py` 覆盖备份/恢复、SQLite 快照、摘要与路径校验；`test_merge_queue.py` 覆盖队列执行、策略拒绝与重试。`test_admin_paths.py` 验证管理路径拒绝、完整写入前预检和正常文件兼容；目录别名模型不代替 Windows 文件系统实测。

## 尚未实现（迁移前置）

- 每用户 Git 身份与凭据（当前 Gitea 使用单一服务 token；`X-Actor` 仍是临时身份）。
- 评审 UI（后端评审与批准数门禁已就绪）、必需检查结果回写（队列侧已有策略与证据）。
- 标签/发布页面、blame 与代码搜索、LFS/子模块；导入进度与失败恢复的可视化。
- Gitea webhook → 天璇事件、CI 结果回写、多副本合入 worker。
- TLS/域名、备份恢复演练与监控（见 #1188）。

## 状态

可运行的内部原型，不是可迁移的托管仓库：本地 Git 操作、合入队列、保护分支策略、备份工具与真实 Gitea 28.3.0 的仓库/分支/PR/合并已可用；评审、每用户身份、导入与运维闭环未完成。验收与剩余项以 #1188 为准。

仓库参数必须是实际普通工作区根或裸仓库根；linked worktree 与指向根的符号链接可用。普通子目录即使能被 Git 向上发现，也会在业务操作前拒绝。根路径探针保留合法 POSIX 换行字符。
