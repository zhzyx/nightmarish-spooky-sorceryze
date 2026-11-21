"""Verify I15 using four isolated headless editor sessions and an authenticated local service."""

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
from starlette.responses import Response

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "customizations/components/tianxuan/server"))
import issue_lifecycle  # noqa: E402
from api import create_app  # noqa: E402
from native_store import NativeStore  # noqa: E402
from tianxuan_core import Tianxuan  # noqa: E402


def launch(engine, project, env):
    result = subprocess.run(
        [str(engine), "--headless", "--editor", "--path", str(project), "--script", "res://probe.gd"],
        env=env,
        cwd=project,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=90,
    )
    output = result.stdout + result.stderr
    if env["TIANXUAN_TOKEN"] in output:
        raise AssertionError("Credential in editor output")
    reports = [line[len("I15_REPORT=") :] for line in output.splitlines() if line.startswith("I15_REPORT=")]
    assert result.returncode == 0 and len(reports) == 1 and "SCRIPT ERROR" not in output, output[-7000:]
    return json.loads(reports[0])


def exercise(base, binary):
    with patch.dict(os.environ, {"GONGGONG_WORKSPACE": ""}):
        engine = copy_editor(binary, base / "engine")
    project = base / "project"
    project.mkdir()
    (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="I15"\n', encoding="utf-8")
    shutil.copyfile(Path(__file__).with_name("workbench_issue_lifecycle.gd"), project / "probe.gd")
    db = str(base / "domain.db")
    store = Tianxuan(db)
    account = store.register("验收", "owner@example.invalid", secrets.token_urlsafe(), name="林川")
    owner = account["user_id"]
    editor = store.add_member(owner, "editor@example.invalid", secrets.token_urlsafe(), name="白辰")["user_id"]
    viewer = store.add_member(owner, "read@example.invalid", secrets.token_urlsafe(), role="viewer")["user_id"]
    scope = "studio/game"
    issue = store.create_issue(owner, "验收附件", project=scope, acceptance="核对附件的 SHA-256")
    for status in ("in-progress", "in-review"):
        store.transition_issue(owner, issue["id"], status)
    asset = base / "asset.txt"
    asset.write_bytes(b"I15 candidate\n")
    assert asset.read_bytes() == b"I15 candidate\n"
    evidence_text = "已逐字节回读 asset.txt，SHA-256 " + hashlib.sha256(asset.read_bytes()).hexdigest()
    comment = store.add_issue_comment(editor, issue["id"], evidence_text)
    settings = dict(
        TIANXUAN_AUTH_MODE="accounts",
        TIANXUAN_TENANT_ID=account["tenant_id"],
        TIANXUAN_PUBLIC_ORIGIN="https://fixture.invalid",
    )
    observed, writes, reopen_keys = {}, [], []
    try:
        with patch.dict(os.environ, settings), socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            app = create_app(store, native_store=NativeStore(base / "native.db"), native_only=True)

            @app.middleware("http")
            async def observe(request, call_next):
                operation = request.url.path.rsplit("/", 1)[-1]
                if request.method != "POST" or "/lifecycle/" not in request.url.path:
                    return await call_next(request)
                if operation == "reopen":
                    reopen_keys.append((await request.json())["call_id"])
                    if len(reopen_keys) == 1:
                        writes.append([operation, None, 503])
                        return Response(status_code=503)
                response = await call_next(request)
                lost = operation == "close" and response.status_code == 200
                writes.append([operation, response.status_code, 503 if lost else response.status_code])
                return Response(status_code=503) if lost else response

            service = uvicorn.Server(uvicorn.Config(app, log_level="error", access_log=False))
            runner = threading.Thread(target=service.run, kwargs={"sockets": [sock]}, daemon=True)
            runner.start()
            try:
                deadline = time.monotonic() + 20
                while not service.started:
                    assert runner.is_alive() and time.monotonic() < deadline, "server initialization"
                    time.sleep(0.05)
                for phase, actor in [
                    ("close", owner),
                    ("viewer_closed", viewer),
                    ("reopen", editor),
                    ("viewer_open", viewer),
                ]:
                    env = {
                        k: v for k, v in sanitized_environment(base / phase).items() if not k.startswith("TIANXUAN_")
                    }
                    env.update(
                        TIANXUAN_API=f"http://127.0.0.1:{sock.getsockname()[1]}",
                        TIANXUAN_PROJECT=scope,
                        TIANXUAN_TOKEN=store.issue_session(actor),
                        I15_NUMBER=str(issue["number"]),
                        I15_PHASE=phase,
                        I15_EVIDENCE=evidence_text,
                    )
                    observed[phase] = launch(engine, project, env)
            finally:
                service.should_exit = True
                runner.join(10)
                assert not runner.is_alive()
    finally:
        store.db.close()
    assert observed["close"] == observed["viewer_closed"] and observed["close"]["status"] == "done"
    assert observed["reopen"] == observed["viewer_open"] and observed["reopen"]["status"] == "in-review"
    assert writes == [
        ["close", 409, 409],
        ["accept", 200, 200],
        ["close", 200, 503],
        ["reopen", None, 503],
        ["reopen", 200, 200],
        ["close", 409, 409],
    ]
    assert len(reopen_keys) == 2 and reopen_keys[0] == reopen_keys[1]
    restored = Tianxuan(db)
    try:
        state = issue_lifecycle.read(restored, viewer, issue["id"], scope)
        assert state["status"] == "in-review" and state["accepted"] is None
        assert [(e["kind"], e["actor"], e["evidence"]) for e in state["history"]] == [
            ("accepted", owner, comment["id"]),
            ("closed", owner, comment["id"]),
            ("reopened", editor, None),
        ]
        assert [r["id"] for r in restored.list_issue_comments(viewer, issue["id"])] == [comment["id"]]
        assert all(
            view["id"] == issue["id"] and view["number"] == issue["number"] and view["revision"] == state["revision"]
            for view in observed.values()
        )
    finally:
        restored.db.close()
    with binary.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return dict(
        engine_sha256=digest,
        views=observed,
        writes_server_client=writes,
        same_retry_key=True,
        verified_history_after_restart=state["history"],
        evidence_comment=comment,
        passed=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="workbench-i15-") as directory:
        report = exercise(Path(directory), args.godot.resolve(strict=True))
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Passed I15 native close, lost-receipt reconciliation, reopen and independent readback")
