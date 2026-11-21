"""Exercise the shipped branch toolbar, a loopback account API and two actual Git checkouts."""

import argparse
import hashlib
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch

import uvicorn
from editor_test_isolation import copy_editor
from run_unified_settings_native import sanitized_environment

ROOT = Path(__file__).resolve().parents[2]
SERVER = Path("customizations/components/tianxuan/server")
sys.path.insert(0, str(ROOT / SERVER))
from api import create_app  # noqa: E402
from tianxuan_core import Tianxuan  # noqa: E402


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True, encoding="utf-8").strip()


def exercise(base, binary):
    project = base / "project"
    project.mkdir()
    git(project, "init", "-q", "-b", "main")
    git(project, "config", "user.email", "fixture@example.invalid")
    git(project, "config", "user.name", "Fixture")
    git(project, "config", "core.autocrlf", "false")
    (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="G10"\n')
    (project / ".gitignore").write_text(".godot/\n*.uid\n")
    script = project / "sample.gd"
    script.write_bytes(b"extends Node\n# baseline\n")
    git(project, "add", ".")
    git(project, "commit", "-qm", "older baseline")
    old = git(project, "rev-parse", "HEAD")
    original = b"extends Node\n# current\n"
    script.write_bytes(original)
    git(project, "commit", "-qam", "current workspace")
    latest = git(project, "rev-parse", "HEAD")
    repos = base / "repos"
    repos.mkdir()
    bare = repos / "sample.git"
    git(project, "clone", "-q", "--bare", str(project), str(bare))
    git(bare, "tag", "review/g10", latest)
    git(bare, "tag", "refs/heads/review/g10", latest)
    untracked = project / "untracked.txt"
    untracked.write_bytes(b"untracked before switch\n")
    # Provide the installed host entries beneath the private editor's discovered source root.
    (base / "SConstruct").touch()
    host = base / SERVER
    host.mkdir(parents=True)
    for name in ("branch_workspace.py", "tianshu_bridge.py"):
        shutil.copyfile(ROOT / SERVER / name, host / name)
    with patch.dict(os.environ, {"GONGGONG_WORKSPACE": ""}):
        editor = copy_editor(binary, base / "engine")
    store = Tianxuan(str(base / "business.sqlite"))
    owner = store.register("branch fixture", "owner@example.invalid", secrets.token_urlsafe(28))
    token = store.issue_session(owner["user_id"])
    modes = {
        "TIANXUAN_AUTH_MODE": "accounts",
        "TIANXUAN_PUBLIC_ORIGIN": "https://fixture.invalid",
        "TIANXUAN_REPO_ROOT": str(repos),
        "TIANXUAN_TENANT_ID": owner["tenant_id"],
    }
    checks = {}
    with patch.dict(os.environ, modes), socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        service = uvicorn.Server(uvicorn.Config(create_app(store), log_level="error", access_log=False))
        thread = threading.Thread(target=service.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 20
            while not service.started:
                if time.monotonic() > deadline or not thread.is_alive():
                    raise RuntimeError("Tianxuan fixture did not start")
                time.sleep(0.05)
            env = {k: v for k, v in sanitized_environment(base).items() if not k.startswith("TIANXUAN_")}
            env.update(
                TIANXUAN_API="http://127.0.0.1:" + str(sock.getsockname()[1]),
                TIANXUAN_ACTOR=owner["user_id"],
                TIANXUAN_TOKEN=token,
                TIANXUAN_GIT_REPO=bare.name,
                G10_PYTHON=sys.executable,
                G10_HEAD=latest,
                G10_BASE=old,
            )
            for phase in ("first", "restart"):
                command = [
                    str(editor),
                    "--headless",
                    "--editor",
                    "--path",
                    str(project),
                    "--script",
                    str(Path(__file__).with_name("workbench_duobao_branches.gd")),
                ]
                result = subprocess.run(
                    command, cwd=base, env={**env, "G10_PHASE": phase}, capture_output=True, timeout=115
                )
                output = (result.stdout + result.stderr).decode("utf-8", errors="replace")
                if token in output:
                    raise AssertionError("Credential appeared in diagnostics")
                rows = [
                    line.removeprefix("G10_CHECKS=") for line in output.splitlines() if line.startswith("G10_CHECKS=")
                ]
                if result.returncode or len(rows) != 1 or "SCRIPT ERROR" in output:
                    raise RuntimeError(output[-5500:])
                checks[phase] = json.loads(rows[0])
                assert all(checks[phase].values())
                if phase == "first":
                    assert git(bare, "show-ref", "--verify", "--hash", "refs/heads/review/g10") == git(project, "rev-parse", "HEAD") == old
                    assert git(project, "branch", "--show-current") == "review/g10"
                    assert not untracked.exists()
                    assert b"# unsaved G10" not in script.read_bytes()
            assert git(project, "branch", "--show-current") == "main" and git(project, "rev-parse", "HEAD") == latest
            assert script.read_bytes().replace(b"\r\n", b"\n") == original + b"# unsaved G10\n"
            assert untracked.read_bytes() == b"untracked before switch\n"
        finally:
            service.should_exit = True
            thread.join(timeout=10)
            store.db.close()
    return {
        "windows_or_host_editor": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "explicit_base": old,
        "original_head": latest,
        "checks": checks,
        "independent_git_and_file_readback": True,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="gonggong-g10-") as temp:
        report = exercise(Path(temp), args.godot.resolve(strict=True))
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Passed branch creation, unsaved buffer protection and restart recovery")
