# 多宝（代码仓库）

复用开源 Git 实现，不重写协议；多宝负责 AI 编排、权限与高并发合入优化。

## 选型

- Git 服务内核：Gitea/Forgejo（开源、成熟、含 PR/权限/Webhook）。
- 高并发：仓库分片、合入队列、分支/路径级锁、批量评审、读写分离。
- 平台只存仓库/PR/评审元数据；Git 对象由 Git 服务管理。

## 当前实现

`git_service.py`：系统 Git CLI 适配器，仓库为裸仓库；提交与合并在临时克隆中执行后推回，复用 Git 而不重写协议。

- 构造时可显式指定 `git_executable`，否则读取环境变量 `GIT_EXECUTABLE`，再回退到 `git`。
- 覆盖仓库创建、提交、分支、`log`、`diff`、`status` 与合并；合并支持 `--no-ff`、`--ff`、`--ff-only`。
- 冲突时抛出 `MergeConflict`（含冲突路径）并中止临时克隆中的合并，裸仓库保持原状。
- ref、仓库名与文件路径先校验，拒绝 `..`、绝对路径、shell 元字符；子进程固定 `shell=False`。

```sh
python -m unittest discover -s customizations/components/tianxuan/duobao -p "test_*.py" -v
```

`test_git_service.py` 显式使用 `D:\GongGong\project\runtime\git\cmd\git.exe`，覆盖创建仓库与首次提交、分支与列表、log、diff、快进合并、冲突合并的干净回退，以及非法 ref/路径拒绝。

## 规划

- 仓库创建/导入、分支/标签、文件浏览、blame/历史/diff。
- PR/评审、保护分支、合并策略。
- commit/PR ↔ 司南工单自动关联。
- AI：代码检索、PR 摘要、审查建议、冲突辅助。

## 状态

设计阶段；已完成基于系统 Git CLI 的本地服务适配器（`git_service.py`）与测试，尚未接入 Gitea／Forgejo 实例、HTTP API 与高并发合入编排。接入前需完成模块门禁与独立验收。
