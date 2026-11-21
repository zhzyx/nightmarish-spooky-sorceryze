"""Run the compiled I04 control against real Tianxuan work and independent native acceptance."""

import argparse
import asyncio
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest
import uvicorn
from editor_test_isolation import copy_editor
from run_unified_settings_native import sanitized_environment

ROOT = Path(__file__).resolve().parents[2]
COMPONENT = ROOT / "customizations/components/tianxuan"
sys.path[:0] = [str(COMPONENT / path) for path in ("sinan-workorders", "duobao", "server")]
import test_native_workflow as native  # noqa: E402
from api import create_app  # noqa: E402
from tianxuan_core import Tianxuan  # noqa: E402

native_environment = native.fixture


def test_editor_dependency_acceptance(native_environment, tmp_path, monkeypatch):
    workflow, actor, tenant, _, _, _ = native_environment
    source = Path(os.environ["I04_GODOT"]).resolve(strict=True)
    with patch.dict(os.environ, {"GONGGONG_WORKSPACE": ""}):
        engine = copy_editor(source, tmp_path / "engine")
    project = tmp_path / "project"
    project.mkdir()
    (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="I04"\n', encoding="utf-8")
    shutil.copyfile(Path(__file__).with_name("workbench_issue_dependencies.gd"), project / "probe.gd")

    key, upstream = native.task(native_environment, "a")
    native.reserve(native_environment, key)
    assert workflow.execute(actor, key)["state"] == "produced"
    downstream = workflow.domain.create_issue(actor, "接收成果")
    other = workflow.domain.create_issue(actor, "同时编辑的上游")
    expected_revision = workflow.domain.issue_snapshot(actor, downstream["id"])["revision"]

    monkeypatch.setenv("TIANXUAN_AUTH_MODE", "accounts")
    monkeypatch.setenv("TIANXUAN_TENANT_ID", tenant)
    monkeypatch.setenv("TIANXUAN_PUBLIC_ORIGIN", "https://fixture.invalid")
    database = str(tmp_path / "domain.sqlite")
    server_store = Tianxuan(database)
    token = server_store.issue_session(actor)
    app = create_app(server_store, native_store=workflow.worker.store, native_only=True)
    receipts = {}
    edits = []

    @app.middleware("http")
    async def observe(request, call_next):
        response = await call_next(request)
        if request.method == "POST" and request.url.path.endswith("/dependencies"):
            edits.append(response.status_code)
        if request.url.path.endswith("/advance") and response.status_code == 409:
            assert workflow.status(actor, key)["state"] == "produced"
            assert workflow.domain.get_issue(downstream["id"])["status"] == "backlog"
            release = await asyncio.to_thread(native.accept, native_environment, key)
            receipts.update(release=release["id"], candidate=release["candidate"])
        return response

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        service = uvicorn.Server(uvicorn.Config(app, log_level="error", access_log=False))
        thread = threading.Thread(target=service.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 15
            while not service.started:
                assert thread.is_alive() and time.monotonic() < deadline, "Fixture failed to start"
                time.sleep(0.05)
            env = {k: v for k, v in sanitized_environment(tmp_path).items() if not k.startswith("TIANXUAN_")}
            env.update(
                TIANXUAN_API=f"http://127.0.0.1:{sock.getsockname()[1]}",
                TIANXUAN_PROJECT=downstream["project"],
                TIANXUAN_TOKEN=token,
                I04_ISSUES=json.dumps(
                    dict(downstream=downstream["number"], upstream=upstream["number"], other=other["id"])
                ),
            )
            result = subprocess.run(
                [str(engine), "--headless", "--editor", "--path", str(project), "--script", "res://probe.gd"],
                env=env,
                cwd=tmp_path,
                capture_output=True,
                timeout=90,
                encoding="utf-8",
                errors="replace",
            )
        finally:
            service.should_exit = True
            thread.join(timeout=10)
            server_store.db.close()
    output = result.stdout + result.stderr
    assert token not in output, "Credential in editor output"
    assert result.returncode == 0 and "SCRIPT ERROR" not in output, output[-6000:]
    markers = [
        line.removeprefix("I04_REPORT=") for line in result.stdout.splitlines() if line.startswith("I04_REPORT=")
    ]
    assert len(markers) == 1, output[-3000:]
    assert edits == [200, 409, 200, 200]
    assert receipts["release"] and receipts["candidate"]
    persisted = Tianxuan(database)
    try:
        flow = persisted.dispatch_tool(actor, "flow.read", {"issue_id": downstream["id"]})
        assert flow["status"] == "in-progress" and flow["version"] == 4
        assert [(d["id"], d["accepted"]) for d in flow["dependencies"]] == [(upstream["id"], True)]
        assert persisted.issue_snapshot(actor, downstream["id"])["revision"] == expected_revision
    finally:
        persisted.db.close()
    with source.open("rb") as stream:
        engine_sha = hashlib.file_digest(stream, "sha256").hexdigest()
    report = {
        "engine_sha256": engine_sha,
        "upstream_terminal": "produced",
        "release": receipts,
        "ui": json.loads(markers[0]),
        "edit_http_statuses": edits,
        "persisted_downstream": {
            "status": flow["status"],
            "version": flow["version"],
            "content_revision": expected_revision,
        },
    }
    Path(os.environ["I04_REPORT"]).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    os.environ["I04_GODOT"] = str(args.godot.resolve(strict=True))
    os.environ["I04_REPORT"] = str(args.report.resolve())
    with tempfile.TemporaryDirectory(prefix="workbench-i04-") as directory:
        sys.exit(
            pytest.main(["-q", "-p", "no:cacheprovider", "--basetemp", str(Path(directory) / "fixture"), __file__])
        )
