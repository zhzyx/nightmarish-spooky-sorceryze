"""Verify exact merge requests through the shipped editor toolbar and production queue service."""

import argparse
import hashlib
import json
import os
import secrets
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from unittest.mock import patch

from editor_test_isolation import copy_editor
from run_unified_settings_native import sanitized_environment
from run_workbench_duobao_branches import ROOT, SERVER, Tianxuan, git


def exercise(base, binary):
    project = base / "project"
    project.mkdir()
    (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="G13"\n')
    git(project, "init", "-q", "-b", "main")
    git(project, "config", "user.name", "Fixture")
    git(project, "config", "user.email", "g13@example.invalid")
    git(project, "add", "project.godot")
    git(project, "commit", "-qm", "target base")
    target = git(project, "rev-parse", "HEAD")
    repos = base / "repos"
    repos.mkdir()
    bare = repos / "sample.git"
    git(project, "clone", "--quiet", "--bare", str(project), str(bare))
    git(project, "checkout", "-qb", "feature/g13")
    (base / "SConstruct").touch()
    host = base / SERVER
    host.mkdir(parents=True)
    shutil.copyfile(ROOT / SERVER / "tianshu_bridge.py", host / "tianshu_bridge.py")
    with patch.dict(os.environ, {"GONGGONG_WORKSPACE": ""}):
        editor = copy_editor(binary, base / "engine")
    database = base / "service.sqlite"
    store = Tianxuan(str(database))
    owner = store.register("合入测试", "merge@example.invalid", secrets.token_urlsafe(24))
    token = store.issue_session(owner["user_id"])
    store.db.close()
    # The configured check actually reads the candidate's preflight worktree.
    check = [sys.executable, "-c", "raise SystemExit(open('candidate.txt','rb').read() != b'pass')"]
    env = {k: v for k, v in sanitized_environment(base).items() if not k.startswith("TIANXUAN_")}
    env.update(
        TIANXUAN_AUTH_MODE="accounts",
        TIANXUAN_PUBLIC_ORIGIN="https://fixture.invalid",
        TIANXUAN_DB=str(database),
        TIANXUAN_REPO_ROOT=str(repos),
        TIANXUAN_TENANT_ID=owner["tenant_id"],
        TIANXUAN_MERGE_CHECKS=shlex.join(check),
        PYTHONDONTWRITEBYTECODE="1",
    )
    observations = []
    for content in (b"pass", b"fail"):
        (project / "candidate.txt").write_bytes(content)
        git(project, "add", "candidate.txt")
        git(project, "commit", "-qm", content.decode())
        git(project, "push", "--quiet", str(bare), "HEAD:refs/heads/feature/g13")
        candidate = git(bare, "show-ref", "--verify", "--hash", "refs/heads/feature/g13")
        with socket.socket() as reserved:
            reserved.bind(("127.0.0.1", 0))
            port = reserved.getsockname()[1]
        api = f"http://127.0.0.1:{port}"
        with (base / "service.log").open("ab") as log:
            service = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                    "--log-level",
                    "error",
                    "--no-access-log",
                ],
                cwd=ROOT / SERVER,
                env=env,
                stdout=log,
                stderr=log,
            )
            try:
                until = time.monotonic() + 20
                while True:
                    if service.poll() is not None or time.monotonic() > until:
                        raise RuntimeError((base / "service.log").read_text(errors="replace")[-3000:])
                    try:
                        with urllib.request.urlopen(api + "/api/v1/health", timeout=1):
                            break
                    except OSError:
                        time.sleep(0.05)
                previous = observations[0] if observations else {}
                child_env = dict(
                    env,
                    TIANXUAN_API=api,
                    TIANXUAN_TOKEN=token,
                    TIANXUAN_ACTOR=owner["user_id"],
                    TIANXUAN_GIT_REPO=bare.name,
                    G13_SOURCE=candidate,
                    G13_TARGET=target,
                    G13_OLD_ID=previous.get("id", ""),
                    G13_OLD_SHA=previous.get("source", ""),
                    G13_PYTHON=sys.executable,
                )
                result = subprocess.run(
                    [
                        str(editor),
                        "--headless",
                        "--editor",
                        "--path",
                        str(project),
                        "--script",
                        str(Path(__file__).with_name("workbench_duobao_merge.gd")),
                    ],
                    cwd=base,
                    env=child_env,
                    capture_output=True,
                    timeout=100,
                )
                output = (result.stdout + result.stderr).decode(errors="replace")
                if token in output:
                    raise AssertionError("Credential appeared in diagnostics")
                rows = [
                    line.removeprefix("G13_RESULT=") for line in output.splitlines() if line.startswith("G13_RESULT=")
                ]
                if result.returncode or len(rows) != 1 or "SCRIPT ERROR" in output:
                    raise RuntimeError(output[-5500:] + (base / "service.log").read_text(errors="replace")[-1800:])
                row = json.loads(rows[0])
                assert all(row["checks"].values())
                assert git(bare, "show-ref", "--verify", "--hash", "refs/heads/main") == target
                assert git(bare, "show-ref", "--verify", "--hash", "refs/heads/feature/g13") == candidate
                observations.append({**row, "source": candidate, "service_pid": service.pid})
            finally:
                service.terminate()
                service.wait(timeout=15)
    assert observations[0]["id"] != observations[1]["id"]
    return {
        "editor_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "target": target,
        "native_editor_headless": True,
        "service": "uvicorn main:app, accounts, Duobao Git backend",
        "service_restarted": True,
        "independent_bare_target_readback": True,
        "observations": observations,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--godot", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="gonggong-g13-") as folder:
        report = exercise(Path(folder).resolve(), args.godot.resolve(strict=True))
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Passed native merge requests, exact checks, stale candidate and target readback")
