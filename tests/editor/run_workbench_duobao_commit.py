"""Headless native controls, authenticated loopback API and independent Git readback."""

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
from fastapi.responses import JSONResponse
from run_unified_settings_native import sanitized_environment
from run_workbench_duobao_branches import ROOT, SERVER, Tianxuan, create_app, git


def run_controls(editor, project, base, env, token):
    result = subprocess.run(
        [
            str(editor),
            "--headless",
            "--editor",
            "--path",
            str(project),
            "--script",
            str(Path(__file__).with_name("workbench_duobao_commit.gd")),
        ],
        cwd=base,
        env=env,
        capture_output=True,
        timeout=160,
    )
    output = (result.stdout + result.stderr).decode("utf-8", "replace")
    assert token not in output
    lines = [line.removeprefix("G11_CHECKS=") for line in output.splitlines() if line.startswith("G11_CHECKS=")]
    if result.returncode or "SCRIPT ERROR" in output or len(lines) != 1:
        raise RuntimeError(output[-5500:])
    checks = json.loads(lines[0])
    assert all(checks.values())
    return checks


def exercise(base, binary):
    project = base / "project"
    project.mkdir()
    git(project, "init", "-q", "-b", "work/g11")
    git(project, "config", "user.email", "fixture@example.invalid")
    git(project, "config", "user.name", "G11 Fixture")
    git(project, "config", "core.autocrlf", "false")
    (project / "project.godot").write_bytes(b'config_version=5\n[application]\nconfig/name="G11"\n')
    (project / ".gitignore").write_bytes(b".godot/\n*.uid\n")
    for name in ["A.txt", "B.txt"]:
        (project / name).write_bytes(b"original\n")
    git(project, "add", ".")
    git(project, "commit", "-qm", "before selection")
    baseline = git(project, "rev-parse", "HEAD")
    repos = base / "repos"
    repos.mkdir()
    bare = repos / "sample.git"
    git(project, "clone", "-q", "--bare", str(project), str(bare))
    (project / "A.txt").write_bytes(b"chosen\n")
    (project / "B.txt").write_bytes(b"staged B\n")
    git(project, "add", "B.txt")
    (project / "B.txt").write_bytes(b"working B\n")
    (base / "SConstruct").touch()
    host = base / SERVER
    host.mkdir(parents=True)
    for name in ("selected_commit.py", "tianshu_bridge.py"):
        shutil.copyfile(ROOT / SERVER / name, host / name)
    with patch.dict(os.environ, {"GONGGONG_WORKSPACE": ""}):
        editor = copy_editor(binary, base / "engine")
    store = Tianxuan(str(base / "business.sqlite"))
    owner = store.register("commit fixture", "owner@example.invalid", secrets.token_urlsafe(28))
    token = store.issue_session(owner["user_id"])
    modes = {
        "TIANXUAN_AUTH_MODE": "accounts",
        "TIANXUAN_PUBLIC_ORIGIN": "https://fixture.invalid",
        "TIANXUAN_REPO_ROOT": str(repos),
        "TIANXUAN_TENANT_ID": owner["tenant_id"],
    }
    received = []
    lookups = []
    with patch.dict(os.environ, modes), socket.socket() as sock:
        app = create_app(store)

        @app.middleware("http")
        async def lose_first_receipt(request, call_next):
            response = await call_next(request)
            if "/selected-commits/" in request.url.path and response.status_code == 200:
                lookups.append(git(bare, "rev-parse", "refs/heads/work/g11"))
            if request.url.path.endswith("/selected-commits") and response.status_code == 200:
                received.append(git(bare, "rev-parse", "refs/heads/work/g11"))
                if len(received) == 1:
                    return JSONResponse({"detail": "fixture lost first receipt"}, status_code=503)
            return response

        sock.bind(("127.0.0.1", 0))
        service = uvicorn.Server(uvicorn.Config(app, log_level="error", access_log=False))
        thread = threading.Thread(target=service.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 20
            while not service.started:
                if time.monotonic() > deadline or not thread.is_alive():
                    raise RuntimeError("Loopback service did not start")
                time.sleep(0.05)
            env = {k: v for k, v in sanitized_environment(base).items() if not k.startswith("TIANXUAN_")}
            env.update(
                TIANXUAN_API="http://127.0.0.1:" + str(sock.getsockname()[1]),
                TIANXUAN_ACTOR=owner["user_id"],
                TIANXUAN_TOKEN=token,
                TIANXUAN_GIT_REPO=bare.name,
                G11_PYTHON=sys.executable,
            )
            checks = run_controls(editor, project, base, env, token)
        finally:
            service.should_exit = True
            thread.join(timeout=10)
            store.db.close()
    head = git(bare, "rev-parse", "refs/heads/work/g11")
    assert received == [head] and lookups == [baseline, head]
    assert git(project, "rev-parse", "HEAD") == head
    assert git(bare, "rev-list", "--count", baseline + ".." + head) == "1"
    assert git(bare, "diff", "--name-only", baseline, head) == "A.txt"
    assert git(bare, "show", head + ":A.txt") == "chosen" and git(bare, "show", head + ":B.txt") == "original"
    assert git(project, "show", ":B.txt") == "staged B" and (project / "B.txt").read_bytes() == b"working B\n"
    return {
        "editor_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "baseline": baseline,
        "branch": "work/g11",
        "authoritative_receipts": received,
        "lookup_branch_tips": lookups,
        "additional_commits": 1,
        "changed_paths": ["A.txt"],
        "B": {"remote": "original", "index": "staged B", "working_tree": "working B"},
        "checks": checks,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="gonggong-g11-") as folder:
        result = exercise(Path(folder), args.godot.resolve(strict=True))
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Passed selected-file native control, lost receipt retry and independent readback")
