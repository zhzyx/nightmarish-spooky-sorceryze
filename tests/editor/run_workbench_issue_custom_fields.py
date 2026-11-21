"""Exercise project fields and configured stages through the compiled I02 issue detail."""

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
sys.path.insert(0, str(ROOT / "customizations/components/tianxuan/server"))
from api import create_app  # noqa: E402
from native_store import NativeStore  # noqa: E402
from tianxuan_core import Tianxuan  # noqa: E402
from work_management import define_text_field  # noqa: E402


def exercise(base, binary):
    with patch.dict(os.environ, {"GONGGONG_WORKSPACE": ""}):
        engine = copy_editor(binary, base / "engine")
    project = base / "project"
    project.mkdir()
    (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="I09"\n', encoding="utf-8")
    shutil.copyfile(Path(__file__).with_name("workbench_issue_custom_fields.gd"), project / "probe.gd")
    database = str(base / "domain.db")
    store = Tianxuan(database)
    password = secrets.token_urlsafe(32)
    account = store.register("I09", "i09@example.invalid", password)
    owner = account["user_id"]
    token = store.issue_session(owner)
    cases = []
    for scope, key, label, old, new, target in [
        ("studio/game", "map", "地图", "山地", "平原", "layout"),
        ("studio/film", "shot", "镜头", "远景", "近景", "cut"),
    ]:
        define_text_field(store, owner, scope, key, label)
        issue = store.create_issue(owner, label, project=scope)
        plan = {
            "iteration": "week 2",
            "milestone": "RC1",
            "roadmap": scope,
            "status": "art",
            "estimated_minutes": 75,
            "custom_fields": {key: old, "legacyFlag": False, "legacyInteger": 2**60 + 1, "legacyNote": "历史资料"},
        }
        store.dispatch_tool(owner, "work.plan", dict(issue_id=issue["id"], expected_version=0, plan=plan), call_id=key)
        store.dispatch_tool(
            owner,
            "flow.configure",
            dict(
                issue_id=issue["id"],
                expected_version=0,
                stages=[
                    {"id": stage, "progress": progress, "human": False}
                    for stage, progress in [("backlog", 0), (target, 40), ("done", 100)]
                ],
                edges=[{"from": "backlog", "to": target}, {"from": target, "to": "done"}],
            ),
            call_id=key,
        )
        cases.append(
            dict(
                project=scope,
                id=issue["id"],
                number=issue["number"],
                key=key,
                label=label,
                old=old,
                new=new,
                target=target,
                original_plan=plan,
            )
        )
    observed_requests = []
    modes = {
        "TIANXUAN_AUTH_MODE": "accounts",
        "TIANXUAN_TENANT_ID": account["tenant_id"],
        "TIANXUAN_PUBLIC_ORIGIN": "https://fixture.invalid",
    }
    with patch.dict(os.environ, modes), socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        app = create_app(store, native_store=NativeStore(base / "native.db"), native_only=True)

        @app.middleware("http")
        async def observe(request, call_next):
            response = await call_next(request)
            if request.method == "POST":
                observed_requests.append([request.url.path, request.query_params.get("project"), response.status_code])
            return response

        server = uvicorn.Server(uvicorn.Config(app, log_level="error", access_log=False))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 20
            while not server.started:
                if not thread.is_alive() or time.monotonic() > deadline:
                    raise RuntimeError("Tianxuan fixture unavailable")
                time.sleep(0.05)
            env = {k: v for k, v in sanitized_environment(base).items() if not k.startswith("TIANXUAN_")}
            env.update(
                TIANXUAN_API=f"http://127.0.0.1:{sock.getsockname()[1]}",
                TIANXUAN_TOKEN=token,
                TIANXUAN_PROJECT=cases[0]["project"],
                I09_CASES=json.dumps(cases, ensure_ascii=False),
            )
            result = subprocess.run(
                [str(engine), "--headless", "--editor", "--path", str(project), "--script", "res://probe.gd"],
                env=env,
                cwd=base,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
            )
        finally:
            server.should_exit = True
            thread.join(timeout=10)
            store.db.close()
    output = result.stdout + result.stderr
    if password in output or token in output:
        raise AssertionError("Credential in fixture diagnostics")
    markers = [line.removeprefix("I09_REPORT=") for line in output.splitlines() if line.startswith("I09_REPORT=")]
    if result.returncode or len(markers) != 1 or "SCRIPT ERROR" in output:
        raise AssertionError(output[-6500:])
    controls = json.loads(markers[0])
    authority = []
    reopened = Tianxuan(database)
    try:
        for case, record in zip(cases, controls, strict=True):
            issue = reopened.read_issue_detail(owner, case["project"], case["number"])
            work = reopened.dispatch_tool(owner, "work.read", {"issue_id": issue["id"]})
            plan = case["original_plan"]
            expected = plan | {"custom_fields": plan["custom_fields"] | {case["key"]: case["new"]}}
            assert work["version"] == 2 and work["plan"] == expected, work
            assert issue["status"] == case["target"]
            assert record == dict(
                project=case["project"], field=case["label"], value=case["new"], stage=issue["status"]
            )
            authority.append(
                dict(project=case["project"], stage=issue["status"], version=work["version"], plan=work["plan"])
            )
    finally:
        reopened.db.close()
    expected_writes = [
        [f"/api/v1/issues/{case['id']}/work/{action}", case["project"], 200]
        for case in cases
        for action in ["plan", "flow/advance"]
    ]
    assert observed_requests == expected_writes, observed_requests
    with binary.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {
        "engine_sha256": digest,
        "controls": controls,
        "reopened_authority": authority,
        "http_writes": observed_requests,
        "switch_cleared": True,
        "logout_cleared": True,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="workbench-i09-") as directory:
        report = exercise(Path(directory), args.godot.resolve(strict=True))
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Passed I09 native project-field and stage checks")
