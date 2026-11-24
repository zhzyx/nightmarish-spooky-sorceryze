"""Move one issue through its native detail and verify both group counts from a reopened domain."""

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
from collections import Counter
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

SCOPE = "studio/game"


def seed(store):
    password = secrets.token_urlsafe(24)
    account = store.register("I07", "owner@example.invalid", password)
    owner = account["user_id"]
    actor = store.add_member(owner, "editor@example.invalid", password, name="小唐", role="editor")["user_id"]
    doc = store.create_requirement(owner, "private", "保密需求", "why", "scope", "done")
    store.set_visibility(owner, doc["id"], "private")
    issues = []
    for title, project, req, iteration, milestone in [
        ("移动工单", SCOPE, None, "第一轮", "预览"),
        ("保留旧里程碑", SCOPE, None, "第一轮", "预览"),
        ("跨组核对", SCOPE, None, "第一轮", "发布"),
        ("已有发布项", SCOPE, None, "第二轮", "发布"),
        ("其他项目同名组", "studio/other", None, "第二轮", "发布"),
        ("私有同名组", SCOPE, doc["id"], "第二轮", "发布"),
    ]:
        issue = store.create_issue(owner, title, project=project, requirement_id=req)
        plan = dict(
            iteration=iteration,
            milestone=milestone,
            roadmap="角色",
            status="设计",
            estimated_minutes=70,
            custom_fields={"team": "模型组"},
        )
        store.dispatch_tool(
            owner, "work.plan", dict(issue_id=issue["id"], expected_version=0, plan=plan), call_id="seed-" + issue["id"]
        )
        issues.append(issue)
    return account, actor, issues


def observations(store, actor, issues):
    visible = {row["id"] for row in store.list_issues(actor, project=SCOPE)}
    rows = {
        row["id"]: row["plan"]
        for row in store.dispatch_tool(actor, "work.roadmap", {})["items"]
        if row["id"] in visible
    }
    assert set(rows) == {issue["id"] for issue in issues}
    iterations = Counter(plan["iteration"] for plan in rows.values())
    milestones = Counter(plan["milestone"] for plan in rows.values())
    result = []
    for issue in issues:
        state = store.dispatch_tool(actor, "work.read", {"issue_id": issue["id"]})
        assert state["plan"] == rows[issue["id"]]
        iteration, milestone = state["plan"]["iteration"], state["plan"]["milestone"]
        counts = f"迭代「{iteration}」　{iterations[iteration]} 单\n里程碑「{milestone}」　{milestones[milestone]} 单"
        result.append(dict(iteration=iteration, milestone=milestone, counts=counts))
    return result


def exercise(binary, base):
    with patch.dict(os.environ, {"GONGGONG_WORKSPACE": ""}):
        engine = copy_editor(binary, base / "engine")
    project = base / "project"
    project.mkdir()
    (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="I07"\n', encoding="utf-8")
    shutil.copyfile(Path(__file__).with_name("workbench_issue_milestone.gd"), project / "probe.gd")
    database = str(base / "domain.db")
    store = Tianxuan(database)
    account, actor, issues = seed(store)
    owner = account["user_id"]
    before = [store.dispatch_tool(owner, "work.read", {"issue_id": issue["id"]}) for issue in issues]
    expected_before = observations(store, actor, issues[:4])
    modes = dict(
        TIANXUAN_AUTH_MODE="accounts",
        TIANXUAN_TENANT_ID=account["tenant_id"],
        TIANXUAN_PUBLIC_ORIGIN="https://fixture.invalid",
    )
    writes = []
    with patch.dict(os.environ, modes), socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        app = create_app(store, native_store=NativeStore(base / "native.db"), native_only=True)

        @app.middleware("http")
        async def record(request, call_next):
            response = await call_next(request)
            if request.method == "POST" and "/work/" in request.url.path:
                writes.append([request.url.path, request.query_params.get("project"), response.status_code])
            return response

        service = uvicorn.Server(uvicorn.Config(app, log_level="error", access_log=False))
        thread = threading.Thread(target=service.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 20
            while not service.started:
                if not thread.is_alive() or time.monotonic() > deadline:
                    raise RuntimeError("Tianxuan fixture failed to start")
                time.sleep(0.05)
            token = store.issue_session(actor)
            env = {key: val for key, val in sanitized_environment(base).items() if not key.startswith("TIANXUAN_")}
            env.update(
                TIANXUAN_API=f"http://127.0.0.1:{sock.getsockname()[1]}",
                TIANXUAN_PROJECT=SCOPE,
                TIANXUAN_TOKEN=token,
                I07_NUMBERS=json.dumps([row["number"] for row in issues[:4]]),
            )
            run = subprocess.run(
                [str(engine), "--headless", "--editor", "--path", str(project), "--script", "res://probe.gd"],
                cwd=base,
                env=env,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
            )
        finally:
            service.should_exit = True
            thread.join(10)
            store.db.close()
    output = (run.stdout + run.stderr).replace(token, "[redacted]")
    assert run.returncode == 0 and "SCRIPT ERROR" not in output, output[-5000:]
    report = json.loads(
        next(line.removeprefix("I07_REPORT=") for line in run.stdout.splitlines() if line.startswith("I07_REPORT="))
    )
    assert writes == [[f"/api/v1/issues/{issues[0]['id']}/work/plan", SCOPE, 200]], writes
    reopened = Tianxuan(database)
    try:
        assert [reopened.get_issue(issue["id"]) for issue in issues] == issues
        after = [reopened.dispatch_tool(owner, "work.read", {"issue_id": issue["id"]}) for issue in issues]
        expected_after = observations(reopened, actor, issues[:4])
    finally:
        reopened.db.close()
    moved = {"iteration": "第二轮", "milestone": "发布"}
    assert before[1:] == after[1:] and before[0]["history"] == after[0]["history"][:-1]
    assert after[0]["version"] == before[0]["version"] + 1
    assert after[0]["plan"] == before[0]["plan"] | moved and after[0]["history"][-1]["plan"] == moved
    assert (
        report["before"] == expected_before
        and report["after"] == expected_after
        and report["saved"] == expected_after[0]
    )
    with binary.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return dict(
        engine_sha256=digest,
        native=report,
        work_plan_http=writes,
        other_work_states_unchanged=len(issues) - 1,
        stored_patch=moved,
        next_version=after[0]["version"],
        reopened_projection_matches=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="workbench-i07-") as tmp:
        result = exercise(args.godot.resolve(strict=True), Path(tmp))
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Passed I07 native iteration and milestone checks")
