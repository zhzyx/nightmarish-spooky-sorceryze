"""Drive I10 through the compiled issue detail against a real Tianxuan service."""

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
from fastapi.responses import Response
from run_unified_settings_native import sanitized_environment

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "customizations/components/tianxuan/server"))
from api import create_app  # noqa: E402
from native_store import NativeStore  # noqa: E402
from tianxuan_core import Tianxuan  # noqa: E402


def exercise(base, binary):
    with patch.dict(os.environ, {"GONGGONG_WORKSPACE": ""}):
        engine = copy_editor(binary, base / "engine")
    project = base / "project"
    project.mkdir()
    (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="I10"\n', encoding="utf-8")
    shutil.copyfile(Path(__file__).with_name("workbench_issue_time.gd"), project / "probe.gd")
    database = str(base / "time.db")
    store = Tianxuan(database)
    account = store.register("I10", "owner@example.invalid", secrets.token_urlsafe(32))
    actor = account["user_id"]
    scope = "studio/game"
    issue = store.create_issue(actor, "制作场景", project=scope)
    original_plan = {"milestone": "场景录制", "iteration": "W2", "custom_fields": {"团队": "场景"}}
    binding = {"issue_id": issue["id"]}
    store.dispatch_tool(actor, "work.plan", dict(binding, plan=original_plan, expected_version=0), call_id="fixture")
    token = store.issue_session(actor)
    requests = []
    modes = {
        "TIANXUAN_AUTH_MODE": "accounts",
        "TIANXUAN_TENANT_ID": account["tenant_id"],
        "TIANXUAN_PUBLIC_ORIGIN": "https://fixture.invalid",
    }
    with patch.dict(os.environ, modes), socket.socket() as sock:
        app = create_app(store, native_store=NativeStore(base / "native.db"), native_only=True)

        @app.middleware("http")
        async def lose_second_log_receipt(request, call_next):
            operation = request.url.path.rsplit("/", 1)[-1]
            if request.method != "POST" or operation not in {"plan", "log"}:
                return await call_next(request)
            body = await request.json()
            response = await call_next(request)
            requests.append({"operation": operation, "body": body, "committed_status": response.status_code})
            if operation == "log" and len(requests) == 3 and response.status_code == 200:
                return Response(status_code=503)
            return response

        sock.bind(("127.0.0.1", 0))
        env = {k: v for k, v in sanitized_environment(base).items() if not k.startswith("TIANXUAN_")}
        env.update(
            TIANXUAN_API=f"http://127.0.0.1:{sock.getsockname()[1]}",
            TIANXUAN_PROJECT=scope,
            TIANXUAN_TOKEN=token,
            I10_NUMBER=str(issue["number"]),
        )
        server = uvicorn.Server(uvicorn.Config(app, log_level="error", access_log=False))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 20
            while not server.started:
                if not thread.is_alive() or time.monotonic() > deadline:
                    raise RuntimeError("Fixture service failed to start")
                time.sleep(0.05)
            proc = subprocess.run(
                [str(engine), "--headless", "--editor", "--path", str(project), "--script", "res://probe.gd"],
                cwd=base,
                env=env,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=90,
            )
        finally:
            server.should_exit = True
            thread.join(timeout=10)
            store.db.close()
    output = proc.stdout + proc.stderr
    marker = next((line for line in proc.stdout.splitlines() if line.startswith("I10_REPORT=")), None)
    if proc.returncode or not marker or "SCRIPT ERROR" in output:
        raise AssertionError(output.replace(token, "[redacted]")[-6000:])
    report = json.loads(marker.split("=", 1)[1])
    assert [r["operation"] for r in requests] == ["plan", "log", "log", "log"], requests
    assert all(r["committed_status"] == 200 for r in requests)
    assert requests[0]["body"]["plan"] == {"estimated_minutes": 75}
    assert requests[2] == requests[3]
    assert requests[1]["body"]["call_id"] != requests[2]["body"]["call_id"]
    reopened = Tianxuan(database)
    try:
        state = reopened.dispatch_tool(actor, "work.read", binding)
        assert all(state["plan"][k] == v for k, v in original_plan.items())
        assert state["version"] == 4 and state["plan"]["estimated_minutes"] == 75 and state["logged_minutes"] == 35
        entries = [(entry["minutes"], entry["note"]) for entry in state["logs"]]
        assert entries == [(12, "核对草图"), (23, "调整模型")]
        summary = f"预计 {state['plan']['estimated_minutes']} 分钟 · 已登记 {state['logged_minutes']} 分钟"
        lines = "\n".join(f"{minutes} 分钟　{note}" for minutes, note in entries)
        assert report["before"] == "预计 0 分钟 · 已登记 0 分钟"
        assert report["after_first"] == "预计 75 分钟 · 已登记 12 分钟"
        assert report["after_retry"] == report["reopened"] == [summary, lines]
        report.update(requests=requests, reopened_authority=state)
    finally:
        reopened.db.close()
    with binary.open("rb") as stream:
        report["engine_sha256"] = hashlib.file_digest(stream, "sha256").hexdigest()
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="workbench-i10-") as directory:
        report = exercise(Path(directory), args.godot.resolve(strict=True))
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Passed I10 native time registration and replay checks")
