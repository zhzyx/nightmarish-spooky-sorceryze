"""Q12: drop the accepted delivery response on a loopback socket, then recover from the original issue."""

import argparse
import hashlib
import json
import os
import platform
import re
import secrets
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import closing, contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import patch

import httpx
from editor_test_isolation import copy_editor
from run_unified_settings_native import sanitized_environment
from run_workbench_duobao_branches import ROOT, SERVER, Tianxuan, git


@contextmanager
def receiver(base, env):
    with socket.socket() as reserve:
        reserve.bind(("127.0.0.1", 0))
        port = reserve.getsockname()[1]
    api = f"http://127.0.0.1:{port}"
    with (base / "receiver.log").open("ab") as log:
        proc = subprocess.Popen(
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
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            deadline = time.monotonic() + 25
            with httpx.Client(base_url=api, trust_env=False) as client:
                while proc.poll() is None and time.monotonic() < deadline:
                    try:
                        client.get("/api/v1/health", timeout=1).raise_for_status()
                        break
                    except (httpx.ConnectError, httpx.TimeoutException):
                        time.sleep(0.08)
                else:
                    raise RuntimeError((base / "receiver.log").read_text(errors="replace")[-1500:])
                yield client, proc.pid
        finally:
            proc.terminate()
            proc.wait(timeout=15)


@contextmanager
def drop_confirmation(client, route):
    accepted = []

    class DropOnce(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != route.removesuffix("/deliver"):
                self.send_error(404)
                return
            result = client.get(self.path, headers={"Authorization": self.headers["Authorization"]})
            self.send_response(result.status_code)
            self.send_header("Content-Length", str(len(result.content)))
            self.end_headers()
            self.wfile.write(result.content)

        def do_POST(self):
            if self.path != route or accepted:
                self.send_error(409)
                return
            body = self.rfile.read(int(self.headers["Content-Length"]))
            response = client.post(
                route,
                content=body,
                headers={"Authorization": self.headers["Authorization"], "Content-Type": "application/json"},
            )
            response.raise_for_status()
            accepted.append(response.json())
            # The receiver completed its real request. Close the downstream socket with zero response bytes.
            self.connection.shutdown(socket.SHUT_RDWR)
            self.close_connection = True

        def log_message(self, *_):
            pass

    with HTTPServer(("127.0.0.1", 0), DropOnce) as relay:
        thread = threading.Thread(target=relay.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{relay.server_port}", accepted
        finally:
            relay.shutdown()
            thread.join(timeout=5)


def window(editor, base, env, phase, request_id, api):
    proc = subprocess.run(
        [
            str(editor),
            "--headless",
            "--editor",
            "--path",
            str(base / "project"),
            "--script",
            "res://probe.gd",
            "--quit-after",
            "2400",
        ],
        cwd=base,
        env=dict(env, Q12_PHASE=phase, Q12_REQUEST=request_id, TIANXUAN_API=str(api)),
        capture_output=True,
        timeout=90,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    output = (proc.stdout + proc.stderr).decode("utf-8", errors="replace")
    if env["TIANXUAN_TOKEN"] in output:
        raise AssertionError("Credential in editor output")
    rows = [line.removeprefix("Q12_EDITOR=") for line in output.splitlines() if line.startswith("Q12_EDITOR=")]
    if proc.returncode or len(rows) != 1 or "SCRIPT ERROR" in output:
        raise RuntimeError(phase + ": " + output[-2500:])
    return {**json.loads(rows[0]), "exit_code": proc.returncode}


def exercise(base, binary):
    project = base / "project"
    project.mkdir()
    (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="Q12"\n')
    git(project, "init", "-q", "-b", "main")
    git(project, "config", "core.autocrlf", "false")
    git(project, "config", "user.name", "Fixture")
    git(project, "config", "user.email", "q12@example.invalid")
    git(project, "add", "project.godot")
    git(project, "commit", "-qm", "baseline")
    baseline = git(project, "rev-parse", "HEAD")
    git(project, "checkout", "-qb", "feature")
    (project / "asset.txt").write_bytes(b"one accepted change\n")
    git(project, "add", "asset.txt")
    git(project, "commit", "-qm", "Q12 delivery")
    candidate = git(project, "rev-parse", "HEAD")
    bare = base / "repos/sample.git"
    bare.parent.mkdir()
    git(project, "clone", "--bare", "--quiet", str(project), str(bare))
    (base / "SConstruct").touch()
    host = base / SERVER
    host.mkdir(parents=True)
    shutil.copy2(ROOT / SERVER / "tianshu_bridge.py", host)
    for source, name in (
        ("workbench_duobao_merge.gd", "g13_probe.gd"),
        ("workbench_duobao_receipt_loss.gd", "probe.gd"),
    ):
        shutil.copy2(Path(__file__).with_name(source), project / name)
    with patch.dict(os.environ, {"GONGGONG_WORKSPACE": ""}):
        editor = copy_editor(binary, base / "engine")

    db = base / "service.sqlite"
    store = Tianxuan(str(db))
    org = store.register("Q12", "owner@example.invalid", secrets.token_urlsafe(24))
    actor = org["user_id"]
    peer = store.add_member(actor, "peer@example.invalid", secrets.token_urlsafe(24), role="editor")["user_id"]
    token = store.issue_session(actor)
    reviewer = {"Authorization": "Bearer " + store.issue_session(peer)}
    issue = store.create_issue(actor, "Recover original delivery")["id"]
    store.db.close()
    env = {k: v for k, v in sanitized_environment(base).items() if not k.startswith("TIANXUAN_")}
    env.update(
        TIANXUAN_AUTH_MODE="accounts",
        TIANXUAN_PUBLIC_ORIGIN="https://fixture.invalid",
        TIANXUAN_DB=str(db),
        TIANXUAN_REPO_ROOT=str(bare.parent),
        TIANXUAN_TENANT_ID=org["tenant_id"],
        TIANXUAN_PROTECTED_BRANCHES="main",
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONUTF8="1",
    )
    editor_env = dict(
        env, TIANXUAN_TOKEN=token, TIANXUAN_ACTOR=actor, TIANXUAN_GIT_REPO=bare.name, Q12_PYTHON=sys.executable
    )
    root = f"/api/v1/git/repos/{bare.name}/merge-requests"
    owner = {"Authorization": "Bearer " + token}
    work_order = f"/api/v1/issues/{issue}/comments"
    with receiver(base, env) as (client, first_pid):
        assert client.get(work_order, headers=owner).raise_for_status().json()["comments"] == []
        request = (
            client
            .post(root, headers=owner, json=dict(source="feature", target="main", candidate=candidate, issue_id=issue))
            .raise_for_status()
            .json()
        )
        path = root + "/" + request["id"]
        deadline = time.monotonic() + 20
        while client.get(path, headers=owner).raise_for_status().json()["check_state"] != "checked":
            if time.monotonic() >= deadline:
                raise TimeoutError("Candidate did not pass the receiver's merge checks")
            time.sleep(0.15)
        client.post(path + "/review", headers=reviewer, json={"decision": "APPROVED"}).raise_for_status()
        assert git(bare, "rev-parse", "main") == baseline
        with drop_confirmation(client, path + "/deliver") as (relay, accepted):
            dropped = window(editor, base, editor_env, "drop", request["id"], relay)
        assert len(accepted) == 1 and accepted[0]["merge_sha"] == candidate
        assert "closed connection without response" in dropped["status"], dropped
        assert dropped["target"] == "" and dropped["issue"] == issue and dropped["request"] == request["id"]

    # Reopen both participants. Recover the request ID through the issue; the lost response is test evidence only.
    with receiver(base, env) as (fresh, next_pid):
        comments = fresh.get(work_order, headers=owner).raise_for_status().json()["comments"]
        (note,) = comments
        found = re.findall(r"\bmr_[0-9a-f]{64}\b", note["body"])
        assert found == [request["id"]] and note["issue_id"] == issue and candidate in note["body"]
        recovered = window(editor, base, editor_env, "recover", found[0], fresh.base_url)
        assert recovered["request"] == found[0] and recovered["issue"] == issue
        assert "已合入目标分支" in recovered["status"] and candidate in recovered["target"]
        assert recovered["target"] == "当前目标 main @ " + candidate
        assert fresh.get(work_order, headers=owner).raise_for_status().json()["comments"] == [note]

    marker = "refs/duobao/delivered/" + found[0]
    delta = git(bare, "rev-list", baseline + "..main").splitlines()
    assert delta == [candidate] and git(bare, "rev-parse", marker) == candidate
    assert git(bare, "show", "main:asset.txt") == "one accepted change"
    with closing(sqlite3.connect(db.as_uri() + "?mode=ro", uri=True)) as disk:
        rows = disk.execute(
            "SELECT actor_id, result_json FROM tool_receipts WHERE tool='issue.comment' AND call_id=?",
            ("duobao:" + found[0],),
        ).fetchall()
    assert len(rows) == 1 and rows[0][0] == actor
    receipt = json.loads(rows[0][1])
    assert receipt == note and receipt["id"] == accepted[0]["comment_id"]
    return dict(
        request_id="gonggong-ai-workbench-plan1-q12",
        issue_number=1735,
        source_commit=git(ROOT, "rev-parse", "HEAD"),
        platform=platform.platform(),
        editor_sha256=hashlib.sha256(
            editor.with_name(editor.name.replace(".console.exe", ".exe")).read_bytes()
        ).hexdigest(),
        scenario_blobs={
            name: git(ROOT, "hash-object", "--path=" + name, name)
            for name in (
                "tests/editor/run_workbench_duobao_receipt_loss.py",
                "tests/editor/workbench_duobao_receipt_loss.gd",
            )
        },
        mode="headless editor, authenticated loopback TCP",
        status="passed",
        receiver_pids=[first_pid, next_pid],
        editor_sessions=[dropped, recovered],
        lost_confirmations=len(accepted),
        accepted_delivery=accepted[0],
        issue_comment=note,
        target_baseline=baseline,
        target_new_commits=delta,
        target_marker=marker,
        persistent_receipt_count=len(rows),
        persistent_call_id="duobao:" + found[0],
        work_order_link_count=len(comments),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="duobao-q12-") as temp:
        report = exercise(Path(temp).resolve(), args.godot.resolve(strict=True))
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Q12 passed: one dropped confirmation, one target commit and one durable work order receipt.")
