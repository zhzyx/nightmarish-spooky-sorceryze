"""多宝 Git 服务适配器。

复用系统 Git 实现，不重写 Git 协议：仓库以裸仓库（bare repository）保存，
提交与合并在临时克隆中执行后推回裸仓库，进程调用固定 ``shell=False``。

安全边界：

- ref、仓库名与文件路径先做本地校验，拒绝 ``..``、绝对路径和 shell 元字符；
- 提交输入不得指定 Git 管理路径或平台别名；写入前拒绝路径中的符号链接；
- 子进程清理继承的 ``GIT_DIR`` 等环境变量，统一关闭交互提示、签名与钩子；
- 合并冲突在临时克隆中检测并 ``--abort``，裸仓库不会停留在半完成状态，
  失败时以 :class:`MergeConflict` 返回冲突路径；
- 并发推送采用显式 ``--force-with-lease`` CAS 校验：无路径交叉的并发提交或合并
  在同一临时克隆内自动拉取最新目标并重放；存在路径/目录前缀交叉的并发直接提交
  拒绝覆盖并抛出 :class:`MergeConflict`，批量合入（``merge_batch``）在单次克隆中
  合并无冲突分支并隔离冲突分支。

本模块只负责 Git 操作与无冲突并发合入编排；权限、评审与 PR 元数据由多宝
上层承担，Git 对象始终由 Git 服务管理。
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
import unicodedata
from bisect import bisect_left
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

__all__ = [
    "DEFAULT_CONCURRENCY_RETRIES",
    "DEFAULT_GIT_EXECUTABLE",
    "GIT_EXECUTABLE_ENV",
    "GitCommandError",
    "GitService",
    "GitServiceError",
    "MergeConflict",
    "ValidationError",
]

DEFAULT_GIT_EXECUTABLE = "git"
GIT_EXECUTABLE_ENV = "GIT_EXECUTABLE"
DEFAULT_CONCURRENCY_RETRIES = 16
_EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"

#: 允许的合并策略（同时限制为白名单，避免把任意参数交给 git）。
MERGE_STRATEGIES = ("--no-ff", "--ff", "--ff-only")

_LOG_FORMAT = "%H%x1f%an%x1f%ae%x1f%aI%x1f%s%x1e"

_CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")
_REF_FORBIDDEN = re.compile(r"[~^:?*\[\\]")
_DRIVE_LETTER = re.compile(r"^[A-Za-z]:")
_SHELL_METACHARACTERS = frozenset("|&;<>()$`\\\"'*?[]{}~!#^%")
_PSEUDO_REFS = frozenset({
    "HEAD",
    "FETCH_HEAD",
    "ORIG_HEAD",
    "MERGE_HEAD",
    "CHERRY_PICK_HEAD",
    "REVERT_HEAD",
    "BISECT_HEAD",
    "REBASE_HEAD",
})

#: 固定传给每条 git 命令的配置：Unicode 路径、禁用自动 gc。
_BASE_CONFIG_OPTIONS = (
    "-c",
    "core.quotepath=false",
    "-c",
    "gc.auto=0",
    "-c",
    "advice.detachedHead=false",
    "-c",
    f"core.hooksPath={os.devnull}",
    "-c",
    "core.fsmonitor=false",
    "-c",
    "commit.gpgsign=false",
)

#: 写入类操作固定 LF 换行，保证不同宿主上结果一致。
_LINE_ENDING_CONFIG_OPTIONS = (
    "-c",
    "core.autocrlf=false",
    "-c",
    "core.eol=lf",
)

#: 这些变量会把命令重定向到调用者的仓库，进入服务前必须清理。
_ISOLATED_ENVIRONMENT = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_COMMON_DIR",
    "GIT_NAMESPACE",
    "GIT_PREFIX",
)


class GitServiceError(RuntimeError):
    """多宝 Git 服务的基础错误。"""


class ValidationError(GitServiceError, ValueError):
    """输入（ref、路径、仓库名等）未通过校验。"""


class GitCommandError(GitServiceError):
    """git 子进程以非零状态退出。"""

    def __init__(
        self,
        command: list[str] | tuple[str, ...],
        returncode: int,
        stdout: str = "",
        stderr: str = "",
    ) -> None:
        self.command = tuple(command)
        self.returncode = returncode
        self.stdout = stdout or ""
        self.stderr = stderr or ""
        detail = self.stderr.strip() or self.stdout.strip() or "no output"
        detail = detail.replace("\r\n", "\n")
        if len(detail) > 2000:
            detail = f"{detail[:2000]}…"
        super().__init__(f"git command failed with exit code {self.returncode}: {' '.join(self.command)}: {detail}")


class MergeConflict(GitServiceError):
    """合并产生冲突；``paths`` 保存冲突文件路径。"""

    def __init__(
        self,
        paths: list[str] | tuple[str, ...],
        *,
        source: str | None = None,
        target: str | None = None,
    ) -> None:
        self.paths = list(dict.fromkeys(paths))
        self.source = source
        self.target = target
        joined = ", ".join(self.paths) if self.paths else "unknown paths"
        super().__init__(f"merge of {source!r} into {target!r} failed with conflicts: {joined}")

    @property
    def conflicts(self) -> list[str]:
        """冲突路径的副本（便于调用方按路径处理）。"""
        return list(self.paths)


def _overlapping_paths(left: Iterable[str], right: Iterable[str]) -> list[str]:
    """检测路径集合交集（含文件与目录前缀碰撞，如 ``a`` 与 ``a/b``）。"""
    ordered_right = sorted(set(right))
    members = set(ordered_right)
    matches: set[str] = set()
    for name in left:
        parts = name.split("/")
        if any("/".join(parts[:end]) in members for end in range(1, len(parts) + 1)):
            matches.add(name)
            continue
        position = bisect_left(ordered_right, name + "/")
        if position < len(ordered_right) and ordered_right[position].startswith(name + "/"):
            matches.add(name)
    return sorted(matches)


def _reject_control_characters(value: str, label: str) -> None:
    if _CONTROL_CHARACTERS.search(value):
        raise ValidationError(f"{label} contains control characters: {value!r}")


def _reject_shell_metacharacters(value: str, label: str) -> None:
    found = sorted({character for character in value if character in _SHELL_METACHARACTERS})
    if found:
        raise ValidationError(f"{label} contains unsupported shell metacharacters ({''.join(found)}): {value!r}")


def _validate_repo_name(name: str) -> str:
    """校验仓库名并返回落盘目录名（带 ``.git`` 后缀）。"""
    if not isinstance(name, str):
        raise ValidationError("repository name must be a string")
    if not name or name != name.strip():
        raise ValidationError(f"invalid repository name: {name!r}")
    if "/" in name or "\\" in name:
        raise ValidationError(f"repository name must be a single path segment: {name!r}")
    if name in (".", "..") or ".." in name:
        raise ValidationError(f"invalid repository name: {name!r}")
    directory_name = name if name.endswith(".git") else f"{name}.git"
    if directory_name == ".git":
        raise ValidationError(f"invalid repository name: {name!r}")
    _validate_file_path(directory_name, label="repository name")
    return directory_name


def _validate_file_path(path: str, *, label: str = "file path") -> str:
    """校验仓库内相对路径；仓库根由调用方固定，路径不得逃逸。"""
    if not isinstance(path, str):
        raise ValidationError(f"{label} must be a string")
    if not path or path != path.strip():
        raise ValidationError(f"invalid {label}: {path!r}")
    _reject_control_characters(path, label)
    _reject_shell_metacharacters(path, label)
    if ":" in path:
        raise ValidationError(f"{label} must not contain ':': {path!r}")
    if PurePosixPath(path).is_absolute() or PureWindowsPath(path).is_absolute() or _DRIVE_LETTER.match(path):
        raise ValidationError(f"{label} must be relative: {path!r}")
    parts = path.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise ValidationError(f"{label} must not contain empty, '.' or '..' segments: {path!r}")
    if any(part != part.strip() for part in parts):
        raise ValidationError(f"{label} has leading/trailing whitespace: {path!r}")
    for part in parts:
        # Reserve case, trailing-dot/space and format-character aliases too.
        # This deliberately applies on every host, including case-sensitive ones.
        portable = "".join(char for char in part if unicodedata.category(char) != "Cf")
        if portable.rstrip(" .").casefold() == ".git":
            raise ValidationError(f"{label} targets Git administration: {path!r}")
    return path


def _validate_ref_name(name: str, *, label: str = "ref") -> str:
    """校验 Git ref（分支名、日志/差异引用）；只接受简单 ref 或提交 SHA。"""
    if not isinstance(name, str):
        raise ValidationError(f"{label} must be a string")
    if not name or name != name.strip():
        raise ValidationError(f"invalid {label}: {name!r}")
    _reject_control_characters(name, label)
    _reject_shell_metacharacters(name, label)
    if any(character.isspace() for character in name):
        raise ValidationError(f"{label} must not contain whitespace: {name!r}")
    if name.startswith("-"):
        raise ValidationError(f"{label} must not start with '-': {name!r}")
    if name == "@" or "@{" in name:
        raise ValidationError(f"invalid {label}: {name!r}")
    if name.startswith("/") or name.endswith("/") or "//" in name:
        raise ValidationError(f"invalid {label}: {name!r}")
    if ".." in name or name.endswith("."):
        raise ValidationError(f"invalid {label}: {name!r}")
    if _REF_FORBIDDEN.search(name):
        raise ValidationError(f"invalid {label}: {name!r}")
    if name.startswith("refs/"):
        raise ValidationError(f"{label} must be a short name, not a full ref: {name!r}")
    for part in name.split("/"):
        if part.startswith(".") or part.startswith("-") or part.endswith(".lock"):
            raise ValidationError(f"invalid {label}: {name!r}")
    return name


def _validate_branch_name(name: str) -> str:
    name = _validate_ref_name(name, label="branch name")
    if name in _PSEUDO_REFS:
        raise ValidationError(f"reserved ref name cannot be used as a branch: {name!r}")
    return name


def _validate_message(message: str) -> str:
    if not isinstance(message, str) or not message.strip():
        raise ValidationError("commit message must be a non-empty string")
    if "\x00" in message:
        raise ValidationError("commit message must not contain NUL")
    return message


def _validate_identity(author_name: str, author_email: str) -> tuple[str, str]:
    for value, label in ((author_name, "author name"), (author_email, "author email")):
        if not isinstance(value, str) or not value.strip():
            raise ValidationError(f"{label} must be a non-empty string")
        if _CONTROL_CHARACTERS.search(value):
            raise ValidationError(f"{label} contains control characters")
        if "<" in value or ">" in value:
            raise ValidationError(f"{label} must not contain '<' or '>'")
    if "@" not in author_email:
        raise ValidationError("author email must contain '@'")
    return author_name.strip(), author_email.strip()


def _validate_limit(limit: int) -> int:
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise ValidationError("log limit must be an integer")
    if not 1 <= limit <= 1000:
        raise ValidationError("log limit must be between 1 and 1000")
    return limit


def _validate_retries(max_retries: int) -> int:
    if isinstance(max_retries, bool) or not isinstance(max_retries, int) or not 0 <= max_retries <= 64:
        raise ValidationError("max_retries must be an integer between 0 and 64")
    return max_retries


class GitService:
    """通过系统 git CLI 提供多宝所需的仓库操作。

    ``git_executable`` 显式指定 Git 可执行文件；未指定时依次读取环境变量
    ``GIT_EXECUTABLE`` 和默认值 ``git``。所有仓库操作都使用绝对路径、
    参数数组与临时克隆，可安全并发调用。
    """

    def __init__(self, git_executable: str | None = None) -> None:
        if git_executable is None:
            candidate = os.environ.get(GIT_EXECUTABLE_ENV) or DEFAULT_GIT_EXECUTABLE
        else:
            if not isinstance(git_executable, str) or not git_executable.strip():
                raise ValidationError("git executable must be a non-empty string")
            candidate = git_executable.strip()
        self.git_executable = candidate

    # ------------------------------------------------------------------
    # 仓库
    # ------------------------------------------------------------------
    def create_repo(self, root: str | os.PathLike[str], name: str, default_branch: str = "main") -> str:
        """在 ``root`` 下创建裸仓库并返回其路径。

        已存在同名仓库时拒绝覆盖，避免误删数据。
        """
        directory_name = _validate_repo_name(name)
        branch = _validate_branch_name(default_branch)
        try:
            root_path = Path(os.fspath(root)).expanduser()
        except TypeError as error:
            raise ValidationError("root must be a string or os.PathLike") from error
        root_path = root_path.resolve()
        if root_path.exists() and not root_path.is_dir():
            raise GitServiceError(f"repository root is not a directory: {root_path}")
        root_path.mkdir(parents=True, exist_ok=True)
        destination = root_path / directory_name
        if destination.exists():
            raise GitServiceError(f"repository already exists: {destination}")
        self._run([
            "init",
            "--bare",
            "--quiet",
            f"--initial-branch={branch}",
            str(destination),
        ])
        return str(destination)

    def commit(
        self,
        repo: str | os.PathLike[str],
        branch: str,
        message: str,
        files: Mapping[str, str],
        author_name: str,
        author_email: str,
        *,
        max_retries: int = DEFAULT_CONCURRENCY_RETRIES,
    ) -> str:
        """在临时克隆中写入文件并提交，使用 CAS 校验推回裸仓库后返回提交 SHA。

        若远端目标分支在写入期间被其他并发协作者推进：
        - 写入路径与远端新增变更无重叠时，自动拉取最新分支并重放提交；
        - 写入路径与远端新增变更存在文件或目录前缀重叠时，拒绝覆盖并抛出 :class:`MergeConflict`。
        """
        branch = _validate_branch_name(branch)
        message = _validate_message(message)
        name, email = _validate_identity(author_name, author_email)
        retries = _validate_retries(max_retries)
        if not isinstance(files, Mapping):
            raise ValidationError("files must be a mapping of relative paths to text")
        staged: dict[str, str] = {}
        for relative, content in files.items():
            relative = _validate_file_path(relative)
            if not isinstance(content, str):
                raise ValidationError(f"content for {relative!r} must be a string")
            staged[relative] = content
        if not staged:
            raise ValidationError("commit requires at least one file")
        # Reject the entire input before even probing a repository with Git.
        repo_path, _ = self._repo_path(repo, require_bare=True)

        with tempfile.TemporaryDirectory(prefix="duobao-commit-") as temporary:
            worktree = Path(temporary) / "worktree"
            self._clone(repo_path, worktree)
            worktree_root = worktree.resolve()
            remote_ref = f"refs/remotes/origin/{branch}"

            for attempt in range(retries + 1):
                self._checkout_branch(worktree, branch)
                if attempt > 0:
                    self._run(["-C", str(worktree), "clean", "-fd", "--quiet"])
                destinations: dict[str, Path] = {}
                for relative in staged:
                    destination = worktree.joinpath(*relative.split("/"))
                    current = worktree
                    for part in relative.split("/"):
                        current = current / part
                        if current.is_symlink() or getattr(current, "is_junction", lambda: False)():
                            raise ValidationError(f"file path follows a link: {relative!r}")
                    resolved = destination.resolve()
                    if not resolved.is_relative_to(worktree_root):
                        raise ValidationError(f"file path escapes the worktree: {relative!r}")
                    _validate_file_path(resolved.relative_to(worktree_root).as_posix())
                    destinations[relative] = destination
                base_sha = self._rev_parse(worktree, remote_ref)
                # Check all destinations before writing any input into the clone.
                for relative, content in staged.items():
                    destination = destinations[relative]
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with open(destination, "w", encoding="utf-8", newline="\n") as handle:
                        handle.write(content)
                self._run(["-C", str(worktree), "add", "--", *staged])
                self._run([
                    "-C",
                    str(worktree),
                    "-c",
                    f"user.name={name}",
                    "-c",
                    f"user.email={email}",
                    "-c",
                    "commit.gpgsign=false",
                    "commit",
                    "--allow-empty-message",
                    "--no-verify",
                    "-m",
                    message,
                ])
                sha = self._rev_parse(worktree, "HEAD")
                if sha is None:
                    raise GitServiceError("commit succeeded but HEAD cannot be resolved")
                lease = f"refs/heads/{branch}:{base_sha or ''}"
                pushed = self._run(
                    [
                        "-C",
                        str(worktree),
                        "push",
                        "--quiet",
                        "--no-verify",
                        f"--force-with-lease={lease}",
                        "origin",
                        f"HEAD:refs/heads/{branch}",
                    ],
                    check=False,
                )
                if pushed.returncode == 0:
                    return sha

                self._run(
                    ["-C", str(worktree), "fetch", "--quiet", "origin", f"refs/heads/{branch}:{remote_ref}"],
                    check=False,
                )
                latest_sha = self._rev_parse(worktree, remote_ref)
                if latest_sha is None or latest_sha == base_sha:
                    raise GitCommandError(pushed.args, pushed.returncode, pushed.stdout, pushed.stderr)
                upstream_changed = self._changed_paths(worktree, base_sha or _EMPTY_TREE, latest_sha)
                conflicts = _overlapping_paths(staged.keys(), upstream_changed)
                if conflicts:
                    raise MergeConflict(conflicts, source=branch, target=branch)
                if attempt >= retries:
                    raise GitCommandError(pushed.args, pushed.returncode, pushed.stdout, pushed.stderr)

            raise GitServiceError("unreachable commit retry state")

    def branch(self, repo: str | os.PathLike[str], name: str, start: str = "HEAD") -> str:
        """基于 ``start`` 创建分支并返回其提交 SHA。

        已存在且指向同一提交时幂等返回；指向其他提交时不覆盖并报错。
        """
        repo_path, _ = self._repo_path(repo)
        name = _validate_branch_name(name)
        start = _validate_ref_name(start, label="start revision")
        target = self._rev_parse(repo_path, start)
        if target is None:
            raise GitServiceError(f"unknown start revision: {start!r}")
        existing = self._rev_parse(repo_path, f"refs/heads/{name}")
        if existing is not None:
            if existing == target:
                return target
            raise GitServiceError(f"branch already exists with a different commit: {name!r}")
        self._run(["-C", str(repo_path), "branch", name, target])
        return target

    def list_branches(self, repo: str | os.PathLike[str]) -> list[str]:
        """返回仓库内的本地分支名。"""
        repo_path, _ = self._repo_path(repo)
        output = self._run(["-C", str(repo_path), "for-each-ref", "--format=%(refname:short)", "refs/heads"]).stdout
        return [line.strip() for line in output.splitlines() if line.strip()]

    # ------------------------------------------------------------------
    # 读取
    # ------------------------------------------------------------------
    def log(self, repo: str | os.PathLike[str], ref: str = "HEAD", limit: int = 20) -> list[dict[str, Any]]:
        """按时间倒序返回提交记录；空仓库的 ``HEAD`` 返回空列表。"""
        repo_path, _ = self._repo_path(repo)
        ref = _validate_ref_name(ref, label="log ref")
        limit = _validate_limit(limit)
        if self._rev_parse(repo_path, ref) is None:
            if ref == "HEAD":
                return []
            raise GitServiceError(f"unknown revision: {ref!r}")
        output = self._run([
            "-C",
            str(repo_path),
            "log",
            f"--format={_LOG_FORMAT}",
            f"--max-count={limit}",
            "--no-color",
            ref,
            "--",
        ]).stdout
        entries: list[dict[str, Any]] = []
        for record in output.split("\x1e"):
            record = record.strip("\r\n")
            if not record:
                continue
            fields = record.split("\x1f")
            if len(fields) != 5:
                continue
            sha, author, email, date, subject = fields
            entries.append({
                "sha": sha,
                "author": author,
                "email": email,
                "date": date,
                "message": subject,
            })
        return entries

    def diff(self, repo: str | os.PathLike[str], a: str, b: str) -> str:
        """返回 ``a`` 到 ``b`` 的统一 diff 文本。"""
        repo_path, _ = self._repo_path(repo)
        a = _validate_ref_name(a, label="diff left revision")
        b = _validate_ref_name(b, label="diff right revision")
        return self._run([
            "-C",
            str(repo_path),
            "diff",
            "--no-color",
            "--no-ext-diff",
            "--unified=3",
            a,
            b,
            "--",
        ]).stdout

    def read_file(self, repo: str | os.PathLike[str], ref: str, relative: str) -> str:
        """读取裸仓库指定 ref 下的文件文本，精确保留换行。"""
        repo_path, _ = self._repo_path(repo, require_bare=True)
        if not isinstance(ref, str) or not ref.strip() or any(ch in ref for ch in "\0\r\n"):
            raise ValidationError("ref must be a non-empty single-line string")
        revision = ref.strip()
        file_path = _validate_file_path(relative)
        completed = self._run(
            ["-C", str(repo_path), "show", f"{revision}:{file_path}"],
            preserve_newlines=True,
        )
        return completed.stdout

    def status(self, repo: str | os.PathLike[str]) -> dict[str, Any]:
        """返回仓库状态摘要。

        裸仓库没有工作区，返回 ``head``/``head_sha``/``branches`` 等元数据；
        非裸仓库额外返回 ``clean`` 与 ``changes``。
        """
        repo_path, bare = self._repo_path(repo)
        head_sha = self._rev_parse(repo_path, "HEAD")
        result: dict[str, Any] = {
            "path": str(repo_path),
            "bare": bare,
            "head": self._symbolic_head(repo_path),
            "head_sha": head_sha,
            "branches": self.list_branches(repo_path),
            "empty": head_sha is None,
        }
        if not bare:
            output = self._run(
                [
                    "-C",
                    str(repo_path),
                    "status",
                    "--porcelain",
                    "--untracked-files=all",
                ],
                check=False,
                # 读取外部工作区时沿用仓库自身的换行配置，避免把仅换行差异
                # 误报为修改。
                line_endings=False,
            ).stdout
            changes = [line for line in output.splitlines() if line.strip()]
            result["clean"] = not changes
            result["changes"] = changes
        return result

    # ------------------------------------------------------------------
    # 合并
    # ------------------------------------------------------------------
    def merge(
        self,
        repo: str | os.PathLike[str],
        source: str,
        target: str,
        strategy: str = "--no-ff",
        *,
        max_retries: int = DEFAULT_CONCURRENCY_RETRIES,
    ) -> str:
        """将 ``source`` 合入 ``target`` 并推回裸仓库，返回结果提交 SHA。

        发生冲突时在临时克隆中执行 ``merge --abort``，裸仓库保持原状，并抛出
        携带冲突路径的 :class:`MergeConflict`。若 ``target`` 在合并期间被无冲突
        并发更新推进，在同一临时克隆内自动拉取最新 ``target`` 并重试合并。
        """
        repo_path, _ = self._repo_path(repo, require_bare=True)
        source = _validate_branch_name(source)
        target = _validate_branch_name(target)
        retries = _validate_retries(max_retries)
        if strategy not in MERGE_STRATEGIES:
            raise ValidationError(
                f"unsupported merge strategy {strategy!r}; expected one of {', '.join(MERGE_STRATEGIES)}"
            )
        if self._rev_parse(repo_path, f"refs/heads/{source}") is None:
            raise GitServiceError(f"unknown source branch: {source!r}")
        if self._rev_parse(repo_path, f"refs/heads/{target}") is None:
            raise GitServiceError(f"unknown target branch: {target!r}")

        with tempfile.TemporaryDirectory(prefix="duobao-merge-") as temporary:
            worktree = Path(temporary) / "worktree"
            self._clone(repo_path, worktree)
            target_remote = f"refs/remotes/origin/{target}"

            for attempt in range(retries + 1):
                base_sha = self._rev_parse(worktree, target_remote)
                if base_sha is None:
                    raise GitServiceError(f"unknown target branch: {target!r}")
                self._checkout_branch(worktree, target)
                if attempt > 0:
                    self._run(["-C", str(worktree), "clean", "-fd", "--quiet"])
                completed = self._run(
                    [
                        "-C",
                        str(worktree),
                        "-c",
                        "user.name=Duobao Merge",
                        "-c",
                        "user.email=duobao@gonggong.local",
                        "merge",
                        "--no-verify",
                        strategy,
                        "-m",
                        f"Merge branch '{source}' into {target}",
                        f"refs/remotes/origin/{source}",
                    ],
                    check=False,
                )
                if completed.returncode != 0:
                    conflicts = self._conflicted_paths(worktree)
                    in_progress = self._merge_in_progress(worktree)
                    if in_progress:
                        self._run(
                            ["-C", str(worktree), "merge", "--abort"],
                            check=False,
                        )
                    if conflicts or "CONFLICT" in f"{completed.stdout}\n{completed.stderr}":
                        raise MergeConflict(conflicts, source=source, target=target)
                    raise GitCommandError(
                        completed.args,
                        completed.returncode,
                        completed.stdout,
                        completed.stderr,
                    )
                sha = self._rev_parse(worktree, "HEAD")
                if sha is None:
                    raise GitServiceError("merge succeeded but HEAD cannot be resolved")
                if sha == base_sha:
                    return sha
                pushed = self._run(
                    [
                        "-C",
                        str(worktree),
                        "push",
                        "--quiet",
                        "--no-verify",
                        f"--force-with-lease=refs/heads/{target}:{base_sha}",
                        "origin",
                        f"HEAD:refs/heads/{target}",
                    ],
                    check=False,
                )
                if pushed.returncode == 0:
                    return sha

                self._run(["-C", str(worktree), "fetch", "--quiet", "--prune", "origin"], check=False)
                latest_sha = self._rev_parse(worktree, target_remote)
                if latest_sha is None or latest_sha == base_sha or attempt >= retries:
                    raise GitCommandError(pushed.args, pushed.returncode, pushed.stdout, pushed.stderr)

            raise GitServiceError("unreachable merge retry state")

    def merge_batch(
        self,
        repo: str | os.PathLike[str],
        sources: Sequence[str],
        target: str,
        strategy: str = "--no-ff",
        *,
        max_retries: int = DEFAULT_CONCURRENCY_RETRIES,
    ) -> dict[str, Any]:
        """在单次临时克隆中批量合入多个源分支并原子推回裸仓库。

        与目标或已接收前序分支冲突的源分支会被 ``merge --abort`` 干净隔离到
        ``isolated`` 列表中，其余无冲突分支继续在同一批次合入，消除逐笔克隆与
        串行推送争用。
        """
        repo_path, _ = self._repo_path(repo, require_bare=True)
        target = _validate_branch_name(target)
        retries = _validate_retries(max_retries)
        if strategy not in MERGE_STRATEGIES:
            raise ValidationError(
                f"unsupported merge strategy {strategy!r}; expected one of {', '.join(MERGE_STRATEGIES)}"
            )
        if isinstance(sources, (str, bytes)) or not isinstance(sources, Sequence) or not sources:
            raise ValidationError("sources must be a non-empty sequence of branch names")
        validated_sources = [_validate_branch_name(item) for item in sources]
        if len(set(validated_sources)) != len(validated_sources):
            raise ValidationError("sources must not contain duplicate branch names")
        if self._rev_parse(repo_path, f"refs/heads/{target}") is None:
            raise GitServiceError(f"unknown target branch: {target!r}")
        for item in validated_sources:
            if self._rev_parse(repo_path, f"refs/heads/{item}") is None:
                raise GitServiceError(f"unknown source branch: {item!r}")

        with tempfile.TemporaryDirectory(prefix="duobao-batch-merge-") as temporary:
            worktree = Path(temporary) / "worktree"
            self._clone(repo_path, worktree)
            target_remote = f"refs/remotes/origin/{target}"

            for attempt in range(retries + 1):
                base_sha = self._rev_parse(worktree, target_remote)
                if base_sha is None:
                    raise GitServiceError(f"unknown target branch: {target!r}")
                self._checkout_branch(worktree, target)
                if attempt > 0:
                    self._run(["-C", str(worktree), "clean", "-fd", "--quiet"])

                merged: list[dict[str, Any]] = []
                isolated: list[dict[str, Any]] = []
                for source in validated_sources:
                    source_ref = f"refs/remotes/origin/{source}"
                    ancestor = self._run(
                        ["-C", str(worktree), "merge-base", "--is-ancestor", source_ref, "HEAD"],
                        check=False,
                    )
                    if ancestor.returncode == 0:
                        merged.append({
                            "source": source,
                            "status": "already_included",
                            "sha": self._rev_parse(worktree, "HEAD"),
                        })
                        continue
                    completed = self._run(
                        [
                            "-C",
                            str(worktree),
                            "-c",
                            "user.name=Duobao Merge",
                            "-c",
                            "user.email=duobao@gonggong.local",
                            "merge",
                            "--no-verify",
                            strategy,
                            "-m",
                            f"Merge branch '{source}' into {target}",
                            source_ref,
                        ],
                        check=False,
                    )
                    if completed.returncode != 0:
                        conflicts = self._conflicted_paths(worktree)
                        if self._merge_in_progress(worktree):
                            self._run(["-C", str(worktree), "merge", "--abort"], check=False)
                        combined = f"{completed.stdout}\n{completed.stderr}"
                        if conflicts or "CONFLICT" in combined:
                            isolated.append({
                                "source": source,
                                "reason": "merge_conflict",
                                "conflicts": conflicts,
                            })
                            continue
                        if strategy == "--ff-only":
                            isolated.append({
                                "source": source,
                                "reason": "non_fast_forward",
                                "conflicts": [],
                            })
                            continue
                        raise GitCommandError(
                            completed.args,
                            completed.returncode,
                            completed.stdout,
                            completed.stderr,
                        )
                    merged.append({
                        "source": source,
                        "status": "merged",
                        "sha": self._rev_parse(worktree, "HEAD"),
                    })

                final_sha = self._rev_parse(worktree, "HEAD")
                if final_sha is None:
                    raise GitServiceError("batch merge succeeded but HEAD cannot be resolved")
                if final_sha == base_sha:
                    return {
                        "target": target,
                        "base_sha": base_sha,
                        "head_sha": final_sha,
                        "merged": merged,
                        "isolated": isolated,
                        "attempts": attempt + 1,
                    }

                pushed = self._run(
                    [
                        "-C",
                        str(worktree),
                        "push",
                        "--quiet",
                        "--no-verify",
                        f"--force-with-lease=refs/heads/{target}:{base_sha}",
                        "origin",
                        f"HEAD:refs/heads/{target}",
                    ],
                    check=False,
                )
                if pushed.returncode == 0:
                    return {
                        "target": target,
                        "base_sha": base_sha,
                        "head_sha": final_sha,
                        "merged": merged,
                        "isolated": isolated,
                        "attempts": attempt + 1,
                    }

                self._run(["-C", str(worktree), "fetch", "--quiet", "--prune", "origin"], check=False)
                latest_sha = self._rev_parse(worktree, target_remote)
                if latest_sha is None or latest_sha == base_sha or attempt >= retries:
                    raise GitCommandError(pushed.args, pushed.returncode, pushed.stdout, pushed.stderr)

            raise GitServiceError("unreachable batch merge retry state")

    # ------------------------------------------------------------------
    # 子进程与辅助
    # ------------------------------------------------------------------
    def _run(
        self,
        arguments: list[str],
        *,
        check: bool = True,
        line_endings: bool = True,
        preserve_newlines: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        config_options = list(_BASE_CONFIG_OPTIONS)
        if line_endings:
            config_options.extend(_LINE_ENDING_CONFIG_OPTIONS)
        command = [self.git_executable, *config_options, *arguments]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=not preserve_newlines,
                encoding=None if preserve_newlines else "utf-8",
                shell=False,
                env=self._environment(),
            )
        except FileNotFoundError as error:
            raise GitServiceError(f"git executable was not found: {self.git_executable}") from error
        except OSError as error:
            raise GitServiceError(f"failed to start git executable {self.git_executable!r}: {error}") from error
        if preserve_newlines:
            completed = subprocess.CompletedProcess(
                completed.args,
                completed.returncode,
                completed.stdout.decode("utf-8"),
                completed.stderr.decode("utf-8"),
            )
        if check and completed.returncode != 0:
            raise GitCommandError(
                command,
                completed.returncode,
                completed.stdout,
                completed.stderr,
            )
        return completed

    def _environment(self) -> dict[str, str]:
        environment = os.environ.copy()
        for name in _ISOLATED_ENVIRONMENT:
            environment.pop(name, None)
        environment["GIT_TERMINAL_PROMPT"] = "0"
        environment["GIT_PAGER"] = ""
        environment["GIT_MERGE_AUTOEDIT"] = "no"
        return environment

    def _repo_path(
        self,
        repo: str | os.PathLike[str],
        *,
        require_bare: bool = False,
    ) -> tuple[Path, bool]:
        try:
            path = Path(os.fspath(repo))
        except TypeError as error:
            raise ValidationError("repository path must be a string or os.PathLike") from error
        if not path.exists():
            raise GitServiceError(f"repository does not exist: {path}")
        if not path.is_dir():
            raise GitServiceError(f"repository is not a directory: {path}")
        resolved = path.resolve()
        probe = self._run(
            ["-C", str(resolved), "rev-parse", "--is-bare-repository"],
            check=False,
        )
        if probe.returncode != 0:
            raise GitServiceError(f"not a git repository: {resolved}")
        bare = probe.stdout.strip().lower() == "true"
        # rev-parse discovers parent repositories too; the caller must supply
        # the actual bare root or worktree root, not one of its subdirectories.
        root_probe = self._run(
            ["-C", str(resolved), "rev-parse", "--absolute-git-dir" if bare else "--show-toplevel"],
            check=False,
            preserve_newlines=True,
        )
        root = root_probe.stdout.removesuffix("\n")
        if root_probe.returncode != 0 or not root or Path(root).resolve() != resolved:
            raise GitServiceError(f"not a git repository root: {resolved}")
        if require_bare and not bare:
            raise GitServiceError(f"repository is not bare: {resolved}")
        return resolved, bare

    def _rev_parse(self, repo: str | os.PathLike[str], revision: str) -> str | None:
        completed = self._run(
            ["-C", str(repo), "rev-parse", "--verify", "--quiet", revision],
            check=False,
        )
        if completed.returncode != 0:
            return None
        output = completed.stdout.strip()
        return output.splitlines()[0] if output else None

    def _changed_paths(self, repo: str | os.PathLike[str], before: str, after: str) -> list[str]:
        completed = self._run(
            ["-C", str(repo), "diff", "--no-renames", "--name-only", "-z", before, after, "--"],
            check=False,
        )
        if completed.returncode != 0:
            return []
        return sorted({path for path in completed.stdout.split("\x00") if path})

    def _symbolic_head(self, repo: str | os.PathLike[str]) -> str | None:
        completed = self._run(
            ["-C", str(repo), "symbolic-ref", "--quiet", "--short", "HEAD"],
            check=False,
        )
        return completed.stdout.strip() or None

    def _remote_branches(self, repo: str | os.PathLike[str]) -> list[str]:
        output = self._run([
            "-C",
            str(repo),
            "for-each-ref",
            "--format=%(refname)",
            "refs/remotes/origin",
        ]).stdout
        prefix = "refs/remotes/origin/"
        return [line.strip()[len(prefix) :] for line in output.splitlines() if line.strip().startswith(prefix)]

    def _clone(self, repo_path: Path, destination: Path) -> None:
        self._run([
            "clone",
            "--quiet",
            "--no-hardlinks",
            str(repo_path),
            str(destination),
        ])

    def _checkout_branch(self, worktree: Path, branch: str) -> None:
        remote_ref = f"refs/remotes/origin/{branch}"
        if self._rev_parse(worktree, remote_ref) is not None:
            self._run([
                "-C",
                str(worktree),
                "checkout",
                "--quiet",
                "--force",
                "-B",
                branch,
                remote_ref,
            ])
            return
        if self._rev_parse(worktree, "HEAD") is not None:
            self._run([
                "-C",
                str(worktree),
                "checkout",
                "--quiet",
                "--force",
                "-B",
                branch,
            ])
            return
        # 空仓库：保留未诞生的分支，不凭空制造根提交。
        if self._symbolic_head(worktree) == branch:
            return
        remote_branches = self._remote_branches(worktree)
        if remote_branches:
            self._run([
                "-C",
                str(worktree),
                "checkout",
                "--quiet",
                "--force",
                "-B",
                branch,
                f"refs/remotes/origin/{remote_branches[0]}",
            ])
            return
        self._run(["-C", str(worktree), "checkout", "--quiet", "-b", branch])

    def _conflicted_paths(self, worktree: Path) -> list[str]:
        completed = self._run(
            [
                "-C",
                str(worktree),
                "diff",
                "--name-only",
                "--diff-filter=U",
                "-z",
            ],
            check=False,
        )
        if completed.returncode != 0:
            return []
        return [path for path in completed.stdout.split("\x00") if path]

    def _merge_in_progress(self, worktree: Path) -> bool:
        return self._rev_parse(worktree, "MERGE_HEAD") is not None
