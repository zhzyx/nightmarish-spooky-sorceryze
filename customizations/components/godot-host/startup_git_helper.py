#!/usr/bin/env python3
"""Bounded, noninteractive startup fetch and conservative fast-forward.

CLI: python -c SOURCE PROJECT [TIMEOUT_SECONDS]. stdin accepts cancel or EOF.
Only fixed messages leave this process; Git diagnostics may contain credentials.
"""

import contextlib
import hashlib
import json
import os
import pathlib
import shutil
import signal
import subprocess
import sys
import threading
import time

MESSAGES = {
    "updated": "Git 已获取远端并快进更新当前分支。",
    "current": "Git 已获取远端，当前分支已是最新。",
    "ahead": "Git 已获取远端，本地分支领先；保留本地提交。",
    "dirty": "Git 已获取远端，存在本地修改或未跟踪文件；未更新工作区。",
    "diverged": "Git 分支已分叉；未更新工作区。",
    "no_repository": "当前项目不在 Git 工作树中。",
    "no_upstream": "当前分支没有可获取的远端上游。",
    "no_git": "未找到 Git 可执行程序。",
    "busy": "当前工作树正在执行启动同步或 Git 操作。",
    "changed": "同步期间分支、提交或上游配置已改变；未自动更新。",
    "timeout": "Git 启动同步超时，已停止后台进程；请检查当前 Git 状态。",
    "cancelled": "Git 启动同步已取消；请检查当前 Git 状态。",
    "fetch_failed": "Git 获取远端失败（网络、身份或远端配置）；未更新工作区。",
    "update_failed": "Git 快进未完成；请检查当前 Git 状态。",
    "error": "Git 状态检查失败；未继续自动更新。",
}


class Halt(Exception):
    pass


class Runner:
    def __init__(self, root, timeout, cancelled):
        self.root = root
        self.deadline = time.monotonic() + timeout
        self.cancelled = cancelled
        self.git = shutil.which("git")
        self.env = os.environ.copy()
        # Do not inherit a surrounding worktree/index override from the editor.
        for key in (
            "GIT_DIR",
            "GIT_WORK_TREE",
            "GIT_INDEX_FILE",
            "GIT_COMMON_DIR",
            "GIT_OBJECT_DIRECTORY",
            "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        ):
            self.env.pop(key, None)
        self.env.update(
            GIT_TERMINAL_PROMPT="0",
            GCM_INTERACTIVE="never",
            GIT_ASKPASS="true",
            SSH_ASKPASS="true",
            SSH_ASKPASS_REQUIRE="never",
            GCM_GUI_PROMPT="false",
            GIT_SSH_COMMAND="ssh -oBatchMode=yes -oConnectTimeout=10",
            GIT_OPTIONAL_LOCKS="0",
            LC_ALL="C",
        )

    def check(self):
        if self.cancelled.is_set():
            raise Halt("cancelled")
        if time.monotonic() >= self.deadline:
            raise Halt("timeout")

    @staticmethod
    def stop(process):
        if os.name == "nt":
            # /T also terminates SSH / credential helper descendants.
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
                check=False,
            )
        else:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=0.2)
            except subprocess.TimeoutExpired:
                pass
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
        with contextlib.suppress(subprocess.TimeoutExpired):
            process.wait(timeout=2)

    def run(self, *args):
        self.check()
        command = [
            self.git,
            "-c",
            "core.hooksPath=" + os.devnull,
            "-c",
            "protocol.ext.allow=never",
            "-c",
            "maintenance.auto=false",
            "-c",
            "gc.auto=0",
            "-c",
            "submodule.recurse=false",
            "-C",
            self.root,
            *args,
        ]
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self.env,
            start_new_session=os.name != "nt",
            creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0),
        )
        output = bytearray()
        overflow = threading.Event()

        def drain(stream, capture):
            try:
                while True:
                    chunk = stream.read(8192)
                    if not chunk:
                        break
                    if capture:
                        room = 65536 - len(output)
                        output.extend(chunk[: max(room, 0)])
                        if len(chunk) > room:
                            overflow.set()
            finally:
                stream.close()

        readers = [
            threading.Thread(target=drain, args=(process.stdout, True), daemon=True),
            threading.Thread(target=drain, args=(process.stderr, False), daemon=True),
        ]
        for reader in readers:
            reader.start()
        try:
            while process.poll() is None:
                self.check()
                time.sleep(0.025)
            for reader in readers:
                reader.join(timeout=0.25)
            if any(reader.is_alive() for reader in readers):
                self.stop(process)
                for reader in readers:
                    reader.join(timeout=1)
            self.check()
            if overflow.is_set():
                raise Halt("error")
            return process.returncode, bytes(output).decode("utf-8", errors="replace").strip()
        finally:
            if process.poll() is None or any(reader.is_alive() for reader in readers):
                self.stop(process)

    def value(self, *args):
        code, value = self.run(*args)
        if code:
            raise Halt("error")
        return value

    def identity(self):
        code, branch = self.run("symbolic-ref", "--quiet", "HEAD")
        if code or not branch.startswith("refs/heads/"):
            raise Halt("no_upstream")
        name = branch[len("refs/heads/") :]
        code, upstream = self.run("rev-parse", "--symbolic-full-name", "@{upstream}")
        if code or not upstream.startswith("refs/remotes/"):
            raise Halt("no_upstream")
        code, remote = self.run("config", "--get", "branch." + name + ".remote")
        if code or remote not in self.value("remote").splitlines():
            raise Halt("no_upstream")
        code, merge = self.run("config", "--get", "branch." + name + ".merge")
        if code or not merge.startswith("refs/heads/") or "\n" in merge:
            raise Halt("no_upstream")
        # Keep credential-bearing effective URLs only in memory. A rewrite or
        # refspec edit during fetch must invalidate this startup candidate.
        urls = self.value("remote", "get-url", "--all", remote)
        code, refspecs = self.run("config", "--get-all", "remote." + remote + ".fetch")
        if code:
            raise Halt("no_upstream")
        fingerprint = hashlib.sha256((urls + "\0" + refspecs).encode("utf-8")).hexdigest()
        return branch, self.value("rev-parse", "HEAD"), upstream, remote, merge, fingerprint

    def verify_identity(self, original):
        try:
            unchanged = self.identity() == original
        except Halt as result:
            if str(result) != "no_upstream":
                raise
            unchanged = False
        if not unchanged:
            raise Halt("changed")

    def in_progress(self, gitdir):
        return any(
            (gitdir / name).exists()
            for name in (
                "MERGE_HEAD",
                "REBASE_HEAD",
                "CHERRY_PICK_HEAD",
                "REVERT_HEAD",
                "rebase-merge",
                "rebase-apply",
                "sequencer",
                "BISECT_START",
                "index.lock",
            )
        )

    def dirty(self):
        return bool(self.value("status", "--porcelain=v1", "--untracked-files=normal", "--ignore-submodules=none"))


@contextlib.contextmanager
def worktree_lock(gitdir):
    # The OS releases the advisory lock even after a killed helper. Keep the inode
    # in place: unlinking it would allow two different lock holders.
    with open(gitdir / "gonggong-startup-sync.lock", "a+b") as handle:
        try:
            if os.name == "nt":
                import msvcrt

                handle.seek(0)
                handle.write(b"0")
                handle.flush()
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise Halt("busy")
        try:
            yield
        finally:
            if os.name == "nt":
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def synchronize(project, timeout=45.0, cancelled=None):
    try:
        runner = Runner(os.path.abspath(project), min(max(float(timeout), 0.05), 45.0), cancelled or threading.Event())
        if not runner.git:
            raise Halt("no_git")
        code, inside = runner.run("rev-parse", "--is-inside-work-tree")
        if code or inside != "true":
            raise Halt("no_repository")
        runner.root = runner.value("rev-parse", "--show-toplevel")
        gitdir = pathlib.Path(runner.value("rev-parse", "--absolute-git-dir"))
        with worktree_lock(gitdir):
            original = runner.identity()
            if runner.in_progress(gitdir):
                raise Halt("busy")
            branch, head, upstream, remote, merge, _ = original
            # Fetch only the configured upstream into its remote-tracking ref.
            # No forced ref updates, tags, submodules, FETCH_HEAD or local branches.
            code, _ = runner.run(
                "fetch",
                "--no-tags",
                "--no-recurse-submodules",
                "--no-write-fetch-head",
                "--",
                remote,
                merge + ":" + upstream,
            )
            if code:
                raise Halt("fetch_failed")
            runner.verify_identity(original)
            if runner.in_progress(gitdir):
                raise Halt("busy")
            if runner.dirty():
                raise Halt("dirty")
            target = runner.value("rev-parse", upstream)
            if head == target:
                raise Halt("current")
            code, _ = runner.run("merge-base", "--is-ancestor", head, target)
            if code:
                if code != 1:
                    raise Halt("error")
                reverse, _ = runner.run("merge-base", "--is-ancestor", target, head)
                raise Halt("ahead" if reverse == 0 else "diverged" if reverse == 1 else "error")
            runner.verify_identity(original)
            if runner.value("rev-parse", upstream) != target:
                raise Halt("changed")
            if runner.in_progress(gitdir):
                raise Halt("busy")
            if runner.dirty():
                raise Halt("dirty")
            # User branch mergeOptions may include --squash or other behavior
            # outside startup policy; disable them for this invocation only.
            code, _ = runner.run(
                "-c",
                "branch." + branch[len("refs/heads/") :] + ".mergeOptions=",
                "merge",
                "--ff-only",
                "--no-edit",
                "--no-autostash",
                "--no-squash",
                "--no-overwrite-ignore",
                target,
            )
            if code:
                raise Halt("update_failed")
            if runner.value("rev-parse", "HEAD") != target or runner.value("symbolic-ref", "HEAD") != original[0]:
                raise Halt("changed")
            raise Halt("updated")
    except Halt as result:
        status = str(result)
    except (OSError, ValueError, subprocess.SubprocessError):
        status = "error"
    return {"status": status, "message": MESSAGES[status]}


def main():
    cancelled = threading.Event()

    def monitor():
        try:
            # Closing the editor closes the pipe and cancels descendant Git/SSH.
            os.read(sys.stdin.fileno(), 128)
        finally:
            cancelled.set()

    threading.Thread(target=monitor, daemon=True).start()
    if os.name != "nt":
        signal.signal(signal.SIGTERM, lambda *_: cancelled.set())
        signal.signal(signal.SIGINT, lambda *_: cancelled.set())
    result = synchronize(sys.argv[1] if len(sys.argv) > 1 else ".", sys.argv[2] if len(sys.argv) > 2 else 45, cancelled)
    try:
        print(json.dumps(result, ensure_ascii=True), flush=True)
    except BrokenPipeError:
        # Cancellation can close both directions of Godot's stdio pipe.
        os._exit(0)


if __name__ == "__main__":
    main()
