"""Checked branch changes for the open Godot project, with recoverable local edits."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
import uuid
from pathlib import Path


def _git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [os.environ.get("GIT_EXECUTABLE") or "git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=check,
    )


def _read(root: Path, *args: str) -> str:
    return _git(root, *args).stdout.strip()


def _receipts(root: Path) -> Path:
    common = Path(_read(root, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    return common / "gonggong-workbench" / "restored-stashes"


def _recovery(root: Path, branch: str, head: str, *, capture: str = "") -> str:
    restored = _receipts(root)
    marker = f"workbench-g10/{branch}/{head}"
    # Earlier editors could capture "heads/main" when a tag was also named main.
    legacy = {marker, f"workbench-g10/heads/{branch}/{head}"}
    for entry in _read(root, "stash", "list", "--format=%H%x09%gs").splitlines():
        oid, _, subject = entry.partition("\t")
        prefix = f"On {branch}: "
        if not subject.startswith(prefix):
            continue
        message = subject[len(prefix) :]
        if capture:
            matches = message == capture
        else:
            matches = message in legacy or (
                message.startswith(marker + "/")
                and re.fullmatch(r"[0-9a-f]{32}", message[len(marker) + 1 :]) is not None
            )
        if matches and not (restored / oid).is_file():
            return oid
    return ""


def _require_project_manifest(root: Path, project: Path, revision: str) -> None:
    path = (project.resolve().relative_to(root) / "project.godot").as_posix()
    entry = _read(root, "ls-tree", "--full-tree", revision, "--", ":(literal)" + path)
    if entry.partition(" ")[0] not in {"100644", "100755"}:
        raise ValueError(f"修订 {revision} 未包含当前项目文件 {path}，工作副本未切换")


def branch_state(project: Path) -> dict[str, str | bool]:
    if not project.is_absolute() or not (project / "project.godot").is_file():
        raise ValueError("请选择当前打开的 Godot 项目")
    root = Path(_read(project, "rev-parse", "--show-toplevel")).resolve()
    project.resolve().relative_to(root)
    ref = _git(root, "symbolic-ref", "-q", "HEAD", check=False).stdout.strip()
    if not ref.startswith("refs/heads/"):
        raise ValueError("工作副本处于分离 HEAD，请先选择本地分支")
    branch = ref.removeprefix("refs/heads/")
    head = _read(root, "rev-parse", "HEAD")
    return {
        "root": str(root),
        "branch": branch,
        "head": head,
        "dirty": bool(_read(root, "status", "--porcelain", "--untracked-files=all")),
        "recovery": _recovery(root, branch, head),
    }


def change(
    project: Path, action: str, branch: str, head: str, expected: str, preserve: bool, recovery: str = ""
) -> dict[str, str | bool]:
    state = branch_state(project)
    root = Path(str(state["root"]))
    if action == "status":
        return state
    if expected != f"{state['branch']}@{state['head']}":
        raise ValueError("工作副本已变化，请刷新后重试")
    if action == "restore":
        if state["dirty"] or not state["recovery"]:
            raise ValueError("请在原分支及原修订的干净工作副本上恢复")
        if recovery != state["recovery"]:
            raise ValueError("保全记录已变化，请刷新后确认恢复的 OID")
        receipts = _receipts(root)
        receipts.mkdir(parents=True, exist_ok=True)
        # Never drop a stash by reflog index. Another worktree can push a new entry
        # while this checkout is applying its identified snapshot.
        with tempfile.NamedTemporaryFile(dir=receipts, delete=False) as pending:
            receipt = Path(pending.name)
        try:
            _git(root, "stash", "apply", "--index", recovery)
            if (
                _read(root, "symbolic-ref", "HEAD") != "refs/heads/" + str(state["branch"])
                or _read(root, "rev-parse", "HEAD") != state["head"]
            ):
                raise ValueError("恢复期间工作副本已变化，请核对修改，原保全记录仍在")
            receipt.replace(receipts / recovery)
        finally:
            receipt.unlink(missing_ok=True)
        return branch_state(project)
    if not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", head):
        raise ValueError("需要多宝回读的完整提交")
    if not branch or branch.startswith("-") or branch in ("HEAD", "@"):
        raise ValueError("分支名无效")
    _git(root, "check-ref-format", "refs/heads/" + branch)
    if _read(root, "rev-parse", "--verify", head + "^{commit}") != head:
        raise ValueError("请先在工作副本同步该提交，再切换")
    existing = _git(root, "show-ref", "--verify", "--hash", "refs/heads/" + branch, check=False)
    if existing.returncode == 0 and existing.stdout.strip() != head:
        raise ValueError("本地分支与多宝修订不同，请先同步")
    if branch == state["branch"]:
        return state
    _require_project_manifest(root, project, head)
    if _read(root, "ls-files", "--unmerged"):
        raise ValueError("请先处理工作副本的未合入条目")
    if state["dirty"]:
        if not preserve:
            raise ValueError("有未提交编辑，请选择保全或取消切换")
        _require_project_manifest(root, project, str(state["head"]))
        marker = f"workbench-g10/{state['branch']}/{state['head']}/{uuid.uuid4().hex}"
        _git(root, "stash", "push", "--include-untracked", "--message", marker)
        captured = branch_state(project)
        captured_oid = _recovery(root, str(state["branch"]), str(state["head"]), capture=marker)
        if captured["dirty"] or not captured_oid or captured["recovery"] != captured_oid:
            raise ValueError("未确认完整保全，切换已停止")
    args = (branch,) if existing.returncode == 0 else ("-c", branch, head)
    result = _git(root, "switch", "--no-guess", "--no-overwrite-ignore", *args, check=False)
    if result.returncode:
        raise ValueError("Git 拒绝切换。请刷新检查当前分支及其保全记录：" + result.stderr.strip())
    final = branch_state(project)
    if final["branch"] != branch or final["head"] != head:
        raise ValueError("切换回读不一致，请刷新工作副本")
    return final


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("status", "switch", "restore"))
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--branch", default="")
    parser.add_argument("--head", default="")
    parser.add_argument("--expected", default="")
    parser.add_argument("--preserve", action="store_true")
    parser.add_argument("--recovery", default="")
    parser.add_argument("--result", required=True, type=Path)
    args = parser.parse_args()
    try:
        data = change(args.project, args.action, args.branch, args.head, args.expected, args.preserve, args.recovery)
        reply = {"ok": True, "data": data}
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        reply = {"ok": False, "error": str(error)}
    args.result.write_text(json.dumps(reply, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
