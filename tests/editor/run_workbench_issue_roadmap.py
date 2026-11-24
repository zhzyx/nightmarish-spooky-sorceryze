"""Verify module/milestone ancestry and numbered I02 details across two native editor launches."""

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

SCOPE = "studio/game"


def seed(store):
    password = secrets.token_urlsafe(24)
    account = store.register("I08", "owner@example.invalid", password)
    owner = account["user_id"]
    viewer = store.add_member(owner, "viewer@example.invalid", password, role="viewer")["user_id"]
    art, sound = (store.create_business_module(owner, SCOPE, name, call_id=name)["id"] for name in ("场景", "音效"))
    private = store.create_requirement(owner, "private", "内部需求", "why", "scope", "done")
    store.set_visibility(owner, private["id"], "private")

    def issue(title, module, milestone, parent=None, project=SCOPE, requirement=None):
        row = store.create_issue(
            owner,
            title,
            project=project,
            module_id=module,
            parent_id=parent and parent["id"],
            requirement_id=requirement,
        )
        if milestone:
            store.dispatch_tool(
                owner,
                "work.plan",
                dict(issue_id=row["id"], expected_version=0, plan={"milestone": milestone}),
                call_id="seed-" + row["id"],
            )
        return row

    top = issue("设计", art, "预览")
    mid = issue("审阅", art, "预览", top)
    leaf = issue("审阅", art, "预览", mid)
    cross = issue("审阅", sound, "发布", top)
    blank = issue("待排期", sound, "")
    peer = issue("审阅", sound, "预览")
    issue("隔离项目", "default", "预览", project="studio/other")
    issue("内部工单", art, "预览", requirement=private["id"])
    preview = "预览（项目共 4 单）"
    release = "发布（项目共 1 单）"

    def label(row):
        return f"#{row['number']} · {row['title']}"

    targets = []
    for row, path, milestone in [
        (top, ["场景", preview, label(top)], "预览"),
        (mid, ["场景", preview, label(top), label(mid)], "预览"),
        (leaf, ["场景", preview, label(top), label(mid), label(leaf)], "预览"),
        (cross, ["音效", release, "上级 · " + label(top), label(cross)], "发布"),
        (peer, ["音效", preview, label(peer)], "预览"),
        (blank, ["音效", "未设置里程碑（项目共 1 单）", label(blank)], ""),
    ]:
        targets.append(dict(path=path, id=row["id"], number=row["number"], title=row["title"], milestone=milestone))
    return account["tenant_id"], viewer, targets


def launch(engine, base, database, tenant, viewer, targets):
    store = Tianxuan(database)
    token = store.issue_session(viewer)
    modes = dict(
        TIANXUAN_AUTH_MODE="accounts", TIANXUAN_TENANT_ID=tenant, TIANXUAN_PUBLIC_ORIGIN="https://fixture.invalid"
    )
    requests = []
    with patch.dict(os.environ, modes), socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        api = create_app(store, native_store=NativeStore(base / "native.db"), native_only=True)

        @api.middleware("http")
        async def record(request, call_next):
            response = await call_next(request)
            route = request.url.path
            if route.endswith(("/roadmap", "/detail")) or ("/issues/" in route and request.method != "GET"):
                requests.append([request.method, route, request.query_params.get("project"), response.status_code])
            return response

        server = uvicorn.Server(uvicorn.Config(api, log_level="error", access_log=False))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 20
            while not server.started:
                if not thread.is_alive() or time.monotonic() > deadline:
                    raise RuntimeError("Tianxuan fixture failed to start")
                time.sleep(0.05)
            env = {k: v for k, v in sanitized_environment(base).items() if not k.startswith("TIANXUAN_")}
            env.update(
                TIANXUAN_API=f"http://127.0.0.1:{sock.getsockname()[1]}",
                TIANXUAN_PROJECT=SCOPE,
                TIANXUAN_TOKEN=token,
                I08_TARGETS=json.dumps(targets),
            )
            run = subprocess.run(
                [engine, "--headless", "--editor", "--path", base / "project", "--script", "res://probe.gd"],
                cwd=base,
                env=env,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
            )
        finally:
            server.should_exit = True
            thread.join(10)
            store.db.close()
    output = (run.stdout + run.stderr).replace(token, "[redacted]")
    reports = [line.removeprefix("I08_REPORT=") for line in output.splitlines() if line.startswith("I08_REPORT=")]
    assert run.returncode == 0 and len(reports) == 1 and "SCRIPT ERROR" not in output, output[-5000:]
    assert requests == [
        request
        for target in targets
        for request in (
            ["GET", "/api/v1/work/roadmap", SCOPE, 200],
            ["GET", f"/api/v1/issues/by-number/{target['number']}/detail", SCOPE, 200],
        )
    ], requests
    result = json.loads(reports[0])
    assert result == targets
    return dict(details=result, requests=requests)


def exercise(binary, base):
    with patch.dict(os.environ, {"GONGGONG_WORKSPACE": ""}):
        engine = copy_editor(binary, base / "engine")
    project = base / "project"
    project.mkdir()
    (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="I08"\n', encoding="utf-8")
    shutil.copyfile(Path(__file__).with_name("workbench_issue_roadmap.gd"), project / "probe.gd")
    database = str(base / "domain.db")
    store = Tianxuan(database)
    try:
        tenant, viewer, targets = seed(store)
    finally:
        store.db.close()
    first = launch(engine, base, database, tenant, viewer, targets)
    reopened = launch(engine, base, database, tenant, viewer, targets)
    assert first == reopened
    with binary.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()

    def receipt(probe):
        return hashlib.sha256(json.dumps(probe, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()

    return dict(
        engine_sha256=digest,
        role="viewer",
        first=first,
        first_receipt_sha256=receipt(first),
        reopened_receipt_sha256=receipt(reopened),
        reopened_detail_numbers=[row["number"] for row in reopened["details"]],
        reopened_editor_and_database_matches=True,
        launches=2,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="workbench-i08-") as tmp:
        result = exercise(args.godot.resolve(strict=True), Path(tmp))
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Passed I08 native roadmap and reopen checks")
