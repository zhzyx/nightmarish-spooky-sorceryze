"""Exercise issue properties in separate authenticated native editor sessions."""

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


def run_editor(base, engine, env, mode):
    project = base / mode
    project.mkdir()
    (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="I06"\n', encoding="utf-8")
    shutil.copyfile(Path(__file__).with_name("workbench_issue_assignment.gd"), project / "probe.gd")
    result = subprocess.run(
        [str(engine), "--headless", "--editor", "--path", str(project), "--script", "res://probe.gd"],
        env={**env, "I06_MODE": mode},
        cwd=base,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=100,
    )
    output = result.stdout + result.stderr
    if env["TIANXUAN_TOKEN"] in output:
        raise AssertionError("Unexpected credential in editor output")
    markers = [line.removeprefix("I06_REPORT=") for line in output.splitlines() if line.startswith("I06_REPORT=")]
    if result.returncode or len(markers) != 1 or "SCRIPT ERROR" in output:
        raise AssertionError(output[-6000:])
    return json.loads(markers[0])


def exercise(base, binary):
    with patch.dict(os.environ, {"GONGGONG_WORKSPACE": ""}):
        engine = copy_editor(binary, base / "engine")
    database = str(base / "domain.db")
    store = Tianxuan(database)
    account = store.register("Studio", "admin@example.invalid", secrets.token_urlsafe())
    admin = account["user_id"]
    reader = store.add_member(admin, "reader@example.invalid", secrets.token_urlsafe(), name="陈墨", role="viewer")[
        "user_id"
    ]
    limited = store.add_member(admin, "artist@example.invalid", secrets.token_urlsafe(), role="editor")["user_id"]
    project = "studio/game"
    requirement = store.create_requirement(admin, "req", "场景", "需求", "范围", "验收")
    store.set_visibility(admin, requirement["id"], "private")
    for actor in (reader, limited):
        store.share_doc(admin, requirement["id"], actor, "read")
    issue = store.create_issue(admin, "场景检查", requirement_id=requirement["id"], project=project)
    modes = {
        "TIANXUAN_AUTH_MODE": "accounts",
        "TIANXUAN_TENANT_ID": account["tenant_id"],
        "TIANXUAN_PUBLIC_ORIGIN": "https://fixture.invalid",
    }
    writes = []
    views = {}
    with patch.dict(os.environ, modes), socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        api = create_app(store, native_store=NativeStore(base / "native.db"), native_only=True)

        @api.middleware("http")
        async def observe(request, call_next):
            result = await call_next(request)
            if request.method in {"PUT", "POST"} and "/issues/" in request.url.path:
                writes.append([request.method, request.url.path.replace(issue["id"], "{id}"), result.status_code])
            return result

        service = uvicorn.Server(uvicorn.Config(api, log_level="error", access_log=False))
        worker = threading.Thread(target=service.run, kwargs={"sockets": [sock]}, daemon=True)
        worker.start()
        try:
            deadline = time.monotonic() + 20
            while not service.started:
                if not worker.is_alive() or time.monotonic() >= deadline:
                    raise RuntimeError("Service did not start")
                time.sleep(0.05)
            for mode, actor in (("write", admin), ("acl", limited), ("viewer", reader)):
                env = {
                    k: v
                    for k, v in sanitized_environment(base / "profiles" / mode).items()
                    if not k.startswith("TIANXUAN_")
                }
                env.update(
                    TIANXUAN_API=f"http://127.0.0.1:{sock.getsockname()[1]}",
                    TIANXUAN_PROJECT=project,
                    TIANXUAN_TOKEN=store.issue_session(actor),
                    I06_NUMBER=str(issue["number"]),
                    I06_ASSIGNEE=reader,
                )
                views[mode] = run_editor(base, engine, env, mode)
        finally:
            service.should_exit = True
            worker.join(10)
            store.db.close()
    first, assigned, changed = views["write"]
    assert first["owner"] is None and first["status"] == "backlog"
    assert (assigned["owner"], assigned["status"]) == ("陈墨", "backlog")
    assert (changed["owner"], changed["status"]) == ("陈墨", "planned")
    assert views["acl"] == [changed, changed] and views["viewer"] == [changed]
    assert first["revision"] == assigned["revision"] == changed["revision"]
    assert "负责人　陈墨\n状态　planned" in changed["visible"]
    assignee = "/api/v1/issues/{id}/assignee"
    advance = "/api/v1/issues/{id}/work/flow/advance"
    assert writes == [["PUT", assignee, 200], ["POST", advance, 200], ["PUT", assignee, 403], ["POST", advance, 403]]
    reopened = Tianxuan(database)
    try:
        row = reopened.read_issue_detail(reader, project, issue["number"])
        assert (row["assignee"]["id"], row["status"], row["revision"]) == (reader, "planned", changed["revision"])
    finally:
        reopened.db.close()
    with binary.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"engine_sha256": digest, "edits": writes, "native_views": views, "reopened_database_matches": True}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="workbench-i06-") as directory:
        report = exercise(Path(directory), args.godot.resolve(strict=True))
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Passed I06 native writes, independent views and rejected mutations")
