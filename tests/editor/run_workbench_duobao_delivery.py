"""Exercise G14/G15 through separate authenticated workbench sessions and read back Git and Tianxuan."""

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
    (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="Merge delivery"\n')
    fixture = project / "asset.txt"
    fixture.write_text("base line\n")
    git(project, "init", "-q", "-b", "main")
    git(project, "config", "user.name", "Fixture")
    git(project, "config", "user.email", "merge@example.invalid")
    git(project, "add", ".")
    git(project, "commit", "-qm", "base")
    git(project, "branch", "feature")
    fixture.write_text("target line\n")
    git(project, "commit", "-qam", "target")
    target = git(project, "rev-parse", "HEAD")
    git(project, "checkout", "-q", "feature")
    fixture.write_text("source line\n")
    git(project, "commit", "-qam", "source")
    source = git(project, "rev-parse", "HEAD")
    repos = base / "repos"
    repos.mkdir()
    bare = repos / "sample.git"
    git(project, "clone", "--quiet", "--bare", str(project), str(bare))
    here = Path(__file__).resolve().parent
    shutil.copyfile(here / "workbench_duobao_merge.gd", project / "g13_probe.gd")
    shutil.copyfile(here / "workbench_duobao_delivery.gd", project / "delivery.gd")
    host = base / SERVER
    host.mkdir(parents=True)
    (base / "SConstruct").touch()
    shutil.copyfile(ROOT / SERVER / "tianshu_bridge.py", host / "tianshu_bridge.py")
    with patch.dict(os.environ, {"GONGGONG_WORKSPACE": ""}):
        editor = copy_editor(binary, base / "engine")
    database = base / "server.sqlite"
    domain = Tianxuan(str(database))
    org = domain.register("Merge delivery", "owner@example.invalid", secrets.token_urlsafe(24))
    owner = org["user_id"]
    peer = domain.add_member(owner, "review@example.invalid", secrets.token_urlsafe(24), role="editor")["user_id"]
    issue = domain.create_issue(owner, "Merge receipt")["id"]
    tokens = {user: domain.issue_session(user) for user in (owner, peer)}
    domain.db.close()
    check = [sys.executable, "-c", "raise SystemExit(open('asset.txt').read() != 'resolved line\\n')"]
    env = {k: v for k, v in sanitized_environment(base).items() if not k.startswith("TIANXUAN_")}
    env.update(
        TIANXUAN_AUTH_MODE="accounts",
        TIANXUAN_PUBLIC_ORIGIN="https://fixture.invalid",
        TIANXUAN_DB=str(database),
        TIANXUAN_REPO_ROOT=str(repos),
        TIANXUAN_TENANT_ID=org["tenant_id"],
        TIANXUAN_MERGE_CHECKS=shlex.join(check),
        PYTHONDONTWRITEBYTECODE="1",
    )
    history = []
    # Reopen the service before delivery so checks and review receipts must survive restart.
    for phases in (("resolve", "reject", "denied", "approve"), ("deliver",)):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        api = f"http://127.0.0.1:{port}"
        with (base / "service.log").open("ab") as log:
            process = subprocess.Popen(
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
                deadline = time.monotonic() + 25
                while True:
                    if process.poll() is not None or time.monotonic() > deadline:
                        raise RuntimeError((base / "service.log").read_text(errors="replace")[-2000:])
                    try:
                        with urllib.request.urlopen(api + "/api/v1/health", timeout=1):
                            break
                    except OSError:
                        time.sleep(0.1)
                for phase in phases:
                    actor = peer if phase in ("reject", "approve") else owner
                    child = dict(
                        env,
                        TIANXUAN_API=api,
                        TIANXUAN_ACTOR=actor,
                        TIANXUAN_TOKEN=tokens[actor],
                        TIANXUAN_GIT_REPO=bare.name,
                        DUOBAO_ISSUE=issue,
                        DUOBAO_PHASE=phase,
                        DUOBAO_REQUEST=history[0]["id"] if history else "",
                        G13_PYTHON=sys.executable,
                    )
                    probe = subprocess.run(
                        [
                            str(editor),
                            "--editor",
                            "--path",
                            str(project),
                            "--script",
                            "res://delivery.gd",
                            "--quit-after",
                            "15000",
                        ],
                        cwd=base,
                        env=child,
                        capture_output=True,
                        timeout=85,
                    )
                    output = (probe.stdout + probe.stderr).decode(errors="replace")
                    if any(token in output for token in tokens.values()):
                        raise AssertionError("Credentials appeared in editor output")
                    reports = [
                        line.split("=", 1)[1] for line in output.splitlines() if line.startswith("DUOBAO_DELIVERY=")
                    ]
                    if probe.returncode or len(reports) != 1 or "SCRIPT ERROR" in output:
                        raise RuntimeError(
                            phase + ": " + output[-4000:] + (base / "service.log").read_text(errors="replace")[-1500:]
                        )
                    history.append(json.loads(reports[0]))
                    if phase != "deliver":
                        assert git(bare, "rev-parse", "main") == target
            finally:
                process.terminate()
                process.wait(timeout=15)
    actual = git(bare, "rev-parse", "main")
    assert actual == history[0]["candidate"] and git(bare, "show", actual + ":asset.txt") == "resolved line"
    parents = git(bare, "show", "-s", "--format=%P", actual).split()
    assert parents == [source, target] and git(bare, "rev-parse", "feature") == source
    domain = Tianxuan(str(database))
    notes = domain.list_issue_comments(owner, issue)
    assert len(notes) == 1 and actual in notes[0]["body"] and history[0]["id"] in notes[0]["body"]
    domain.db.close()
    return dict(
        editor_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
        real_editor=True,
        service_restart=True,
        issued=issue,
        target=actual,
        parents=parents,
        histories=history,
        issue_comment=notes[0]["id"],
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--godot", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="duobao-g14-g15-") as temp:
        report = exercise(Path(temp).resolve(), args.godot.resolve(strict=True))
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print("Verified native conflict resolution, independent review and work-order delivery")
