"""Git-compatible Duobao transfer. File content travels only for the checked paths."""

import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

MAX_BYTES = 16 * 1024 * 1024
OID = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")


def git(root, *args, data=None, index=None):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    if index is not None:
        env["GIT_INDEX_FILE"] = str(index)
    try:
        run = subprocess.run(
            [
                os.environ.get("GIT_EXECUTABLE") or "git",
                "--no-replace-objects",
                "--literal-pathspecs",
                "-C",
                str(root),
                *args,
            ],
            input=data,
            capture_output=True,
            env=env,
            timeout=90,
        )
    except subprocess.TimeoutExpired as error:
        raise ValueError("Git 操作超时，请回读状态后重试") from error
    if run.returncode:
        raise ValueError(run.stderr.decode("utf-8", "replace").strip() or "Git 操作失败")
    return run.stdout


def oid(root, *args, **kwargs):
    value = git(root, *args, **kwargs).decode("ascii").strip()
    if not OID.fullmatch(value):
        raise ValueError("需要完整的 Git 对象标识")
    return value


def checked_oid(value):
    if not isinstance(value, str) or not OID.fullmatch(value):
        raise ValueError("修订无效")
    return value


def workspace(project):
    if not project.is_absolute() or not (project / "project.godot").is_file():
        raise ValueError("请选择当前打开的 Godot 项目")
    root = Path(git(project, "rev-parse", "--show-toplevel").decode().rstrip("\r\n")).resolve()
    branch = git(root, "symbolic-ref", "HEAD").decode().strip().removeprefix("refs/heads/")
    git(root, "check-ref-format", "refs/heads/" + branch)
    return root, branch, oid(root, "rev-parse", "HEAD")


def changed(root, base, tree):
    records = git(root, "diff-tree", "-r", "--no-renames", "--name-status", "-z", base, tree).split(b"\0")[:-1]
    return [{"status": status.decode(), "path": path.decode()} for status, path in zip(records[::2], records[1::2])]


def working_tree(root, base, index):
    git(root, "read-tree", base, index=index)
    git(root, "add", "-A", "--", ".", index=index)
    return oid(root, "write-tree", index=index)


def diff(project) -> dict[str, Any]:
    root, branch, base = workspace(project)
    if git(root, "ls-files", "-u", "-z"):
        raise ValueError("请先处理工作副本冲突")
    with tempfile.TemporaryDirectory() as temp:
        tree = working_tree(root, base, Path(temp) / "index")
    return {"branch": branch, "base": base, "tree": tree, "files": changed(root, base, tree)}


def preview(project, base, tree, path) -> dict[str, Any]:
    root, _, _ = workspace(project)
    data = git(
        root, "diff", "--no-ext-diff", "--no-textconv", "--no-renames", checked_oid(base), checked_oid(tree), "--", path
    )
    return {"diff": data[:65536].decode("utf-8", "replace") + ("\n…（预览截断）" if len(data) > 65536 else "")}


def pathspec(paths):
    return b"".join(p.encode() + b"\0" for p in paths)


def changes(root, base, tree):
    rows = git(root, "diff-tree", "-r", "--no-renames", "--raw", "--no-abbrev", "-z", base, tree).split(b"\0")[:-1]
    for metadata, path in zip(rows[::2], rows[1::2]):
        _, mode, _, obj, _ = metadata.decode().split()
        yield mode, obj, path


def selected_tree(root, base, snapshot, paths, index):
    git(root, "read-tree", base, index=index)
    selection = set(paths)
    entries = [
        (mode + " " + obj + "\t").encode() + path + b"\0"
        for mode, obj, path in changes(root, base, snapshot)
        if path.decode() in selection
    ]
    # Process removals before adding a path that replaces a directory or vice versa.
    git(root, "update-index", "-z", "--index-info", index=index, data=b"".join(sorted(entries)))
    tree = oid(root, "write-tree", index=index)
    if sorted(f["path"] for f in changed(root, base, tree)) != paths:
        raise ValueError("选择的路径已变化，请刷新并重新确认")
    return tree


def make_candidate(root, target, branch, base, tree, message):
    # The immutable local ref survives a lost POST response or editor restart.
    binding = json.dumps([target, branch, base, tree, message], ensure_ascii=False).encode()
    ref = "refs/gonggong/selected/" + hashlib.sha256(binding).hexdigest()
    existing = git(root, "for-each-ref", "--format=%(objectname)", ref).decode().strip()
    if existing:
        return checked_oid(existing)
    candidate = oid(
        root, "-c", "commit.gpgSign=false", "commit-tree", tree, "-p", base, "-F", "-", data=(message + "\n").encode()
    )
    try:
        git(root, "update-ref", ref, candidate, "0" * len(base))
    except ValueError:
        # An equivalent click in another editor may have won the reservation.
        return oid(root, "rev-parse", "--verify", ref)
    return candidate


def transfer(root, branch, base, candidate):
    files = []
    size = 0
    for mode, obj, path in changes(root, base, candidate):
        content = None
        if mode != "000000":
            if mode not in ("100644", "100755", "120000"):
                raise ValueError("所选变更包含不支持的子模块条目")
            size += int(git(root, "cat-file", "-s", obj))
            if size > MAX_BYTES:
                raise ValueError("所选文件内容超过 16 MiB")
            content = base64.b64encode(git(root, "cat-file", "blob", obj)).decode()
        files.append({"path": path.decode(), "mode": mode, "content": content})
    return {
        "branch": branch,
        "base": base,
        "sha": candidate,
        "files": files,
        "commit": base64.b64encode(git(root, "cat-file", "commit", candidate)).decode(),
    }


def finish(root, branch, base, candidate, paths):
    # Use Git's normal index lock. Only entries still matching the old base are
    # advanced. An explicitly staged, different version survives the receipt.
    index = Path(git(root, "rev-parse", "--path-format=absolute", "--git-path", "index").decode().rstrip("\r\n"))
    lock = Path(str(index) + ".lock")
    installed = False
    with lock.open("xb") as stream:
        try:
            if git(root, "symbolic-ref", "HEAD").decode().strip() != "refs/heads/" + branch:
                raise ValueError("当前分支已切换，保留多宝回执并核对本地工作区")
            current = oid(root, "rev-parse", "HEAD")
            if current == candidate:
                return
            if current != base:
                raise ValueError("多宝已接收，当前本地分支已前移，请核对工作区")
            staged = git(root, "diff", "--cached", "--no-renames", "--name-only", "-z", base).decode().split("\0")[:-1]
            # A file-to-directory transition can make an otherwise literal Git
            # pathspec cover staged descendants (or replace their staged ancestor).
            reset = [
                p for p in paths if not any(p == s or p.startswith(s + "/") or s.startswith(p + "/") for s in staged)
            ]
            if index.is_file():
                with index.open("rb") as source:
                    shutil.copyfileobj(source, stream)
            stream.close()
            if reset:
                git(
                    root,
                    "reset",
                    "-q",
                    candidate,
                    "--pathspec-from-file=-",
                    "--pathspec-file-nul",
                    index=lock,
                    data=pathspec(reset),
                )
            git(root, "update-ref", "refs/heads/" + branch, candidate, base)
            try:
                os.replace(lock, index)
                installed = True
            except OSError:
                git(root, "update-ref", "refs/heads/" + branch, base, candidate)
                raise
        finally:
            stream.close()
            if not installed:
                lock.unlink(missing_ok=True)


def submit(project, target, body, publish, lookup) -> dict[str, Any]:
    root, branch, head = workspace(project)
    base, snapshot = checked_oid(body["base"]), checked_oid(body["tree"])
    paths = sorted(set(body["paths"]))
    message = body["message"].strip()
    if not paths or not message or len(paths) > 1024 or len(message.encode()) > 8192 or branch != body["branch"]:
        raise ValueError("请核对当前分支、提交说明与选择的文件（最多 1024 项）")
    with tempfile.TemporaryDirectory() as temp:
        index = Path(temp) / "index"
        tree = selected_tree(root, base, snapshot, paths, index)
        candidate = make_candidate(root, target, branch, base, tree, message)
        readback = lookup(branch, base, candidate)
        if readback.get("branch") != branch or readback.get("sha") != candidate:
            raise ValueError("无法确认多宝候选状态，请重新回读")
        if readback.get("state") == "advanced":
            raise ValueError("多宝分支已前移，请同步后重新选择")
        if readback.get("state") == "received":
            result = readback
        elif readback.get("state") != "pending":
            raise ValueError("多宝候选状态未知，请重新回读")
        else:
            if head != base and head != candidate:
                raise ValueError("工作区已变化，请刷新差异并重新确认")
            if head == base:
                current = working_tree(root, base, index)
                if selected_tree(root, base, current, paths, index) != tree:
                    raise ValueError("工作区已变化，请刷新差异并重新确认")
            result = publish(transfer(root, branch, base, candidate))
    if result.get("sha") != candidate or result.get("branch") != branch:
        raise ValueError("多宝回执与候选不符，请核对后重试")
    finish(root, branch, base, candidate, paths)
    return {"branch": branch, "sha": candidate}


def receipt(repo, branch, base, sha) -> dict[str, str]:
    base, sha = checked_oid(base), checked_oid(sha)
    ref = "refs/heads/" + branch
    git(repo, "check-ref-format", ref)
    if git(repo, "rev-parse", "--is-bare-repository").strip() != b"true":
        raise ValueError("目标必须是多宝裸仓库")
    direct = git(repo, "for-each-ref", "--format=%(refname) %(symref)", ref).decode().splitlines()
    if ref + " " not in direct:
        raise ValueError("目标不是直接分支引用")
    tip = oid(repo, "show-ref", "--verify", "--hash", ref)
    state = "pending" if tip == base else "advanced"
    if state == "advanced":
        try:
            parents = git(repo, "show", "-s", "--format=%P", sha).decode().strip()
            if parents == base and oid(repo, "merge-base", sha, tip) == sha:
                state = "received"
        except ValueError:
            pass
    return {"state": state, "branch": branch, "sha": sha}


def receive(repo, branch, base, sha, commit, files) -> dict[str, str]:
    # Rebuild the candidate exclusively in a temporary index, without a checkout.
    result = receipt(repo, branch, base, sha)
    ref = "refs/heads/" + branch
    raw = base64.b64decode(commit, validate=True)
    if oid(repo, "hash-object", "-t", "commit", "--stdin", data=raw) != sha:
        raise ValueError("提交摘要不匹配")
    if result["state"] == "received":
        return {"branch": branch, "sha": sha}
    if result["state"] == "advanced":
        raise ValueError("多宝分支已前移，请同步后重新选择")
    if len({f["path"] for f in files}) != len(files):
        raise ValueError("路径重复")
    entries = []
    size = 0
    for f in files:
        name = f["path"]
        if "\x00" in name or "\\" in name or any(p in ("", ".", "..", ".git") for p in name.casefold().split("/")):
            raise ValueError("无效的仓库相对路径")
        mode = f["mode"]
        if mode == "000000" and f["content"] is None:
            obj = "0" * len(base)
        elif mode in ("100644", "100755", "120000") and isinstance(f["content"], str):
            value = base64.b64decode(f["content"], validate=True)
            size += len(value)
            if size > MAX_BYTES:
                raise ValueError("所选文件内容超过 16 MiB")
            obj = oid(repo, "hash-object", "-w", "--stdin", data=value)
        else:
            raise ValueError("文件类型无效")
        entries.append((mode + " " + obj + "\t" + name).encode() + b"\0")
    with tempfile.TemporaryDirectory() as temp:
        index = Path(temp) / "index"
        git(repo, "read-tree", base, index=index)
        git(repo, "update-index", "-z", "--index-info", index=index, data=b"".join(sorted(entries)))
        tree = oid(repo, "write-tree", index=index)
    header = raw.split(b"\n\n", 1)[0].splitlines()
    if (
        len(header) != 4
        or header[:2] != [b"tree " + tree.encode(), b"parent " + base.encode()]
        or not header[2].startswith(b"author ")
        or not header[3].startswith(b"committer ")
    ):
        raise ValueError("提交父项或树与所选文件不一致")
    if sorted(f["path"] for f in changed(repo, base, tree)) != sorted(f["path"] for f in files):
        raise ValueError("候选实际改动与所选文件不一致")
    oid(repo, "hash-object", "-t", "commit", "-w", "--stdin", data=raw)
    try:
        git(repo, "update-ref", "--no-deref", ref, sha, base)
    except ValueError:
        if oid(repo, "show-ref", "--verify", "--hash", ref) != sha:
            raise
    return {"branch": branch, "sha": sha}
