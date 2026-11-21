"""Drive the compiled workbench through an ambiguous create receipt and numbered readback."""

import argparse
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
    (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="I01"\n', encoding="utf-8")
    shutil.copyfile(Path(__file__).with_name("workbench_issue_creation.gd"), project / "test.gd")
    database = str(base / "domain.db")
    store = Tianxuan(database)
    account = store.register("I01", "owner@example.invalid", secrets.token_urlsafe(32))
    actor = account["user_id"]
    scope = "studio/game"
    module = store.create_business_module(actor, scope, "场景", call_id="fixture-module")["id"]
    token = store.issue_session(actor)
    observations = []
    with (
        patch.dict(
            os.environ,
            {
                "TIANXUAN_AUTH_MODE": "accounts",
                "TIANXUAN_REQUIRE_KEYS": "0",
                "TIANXUAN_TENANT_ID": account["tenant_id"],
                "TIANXUAN_PUBLIC_ORIGIN": "https://fixture.invalid",
            },
        ),
        socket.socket() as sock,
    ):
        app = create_app(store, native_store=NativeStore(base / "native.db"), native_only=True)

        @app.middleware("http")
        async def lose_first_receipt(request, call_next):
            response = await call_next(request)
            if request.method == "POST" and request.url.path == "/api/v1/tools":
                observations.append(response.status_code)
                if len(observations) == 1 and response.status_code == 200:
                    return Response(status_code=503)
            return response

        sock.bind(("127.0.0.1", 0))
        env = {k: v for k, v in sanitized_environment(base).items() if not k.startswith("TIANXUAN_")}
        env.update(
            TIANXUAN_API=f"http://127.0.0.1:{sock.getsockname()[1]}",
            TIANXUAN_PROJECT=scope,
            TIANXUAN_TOKEN=token,
            I01_MODULE=module,
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
                [str(engine), "--headless", "--editor", "--path", str(project), "--script", "res://test.gd"],
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
    marker = next((s for s in proc.stdout.splitlines() if s.startswith("I01_REPORT=")), None)
    if proc.returncode or not marker or "SCRIPT ERROR" in output:
        raise AssertionError(output.replace(token, "[redacted]")[-4000:])
    report = json.loads(marker.split("=", 1)[1])
    assert observations == [200, 200], observations
    # Reopen the actual database after both submissions and the editor's GET.
    reopened = Tianxuan(database)
    try:
        issues = reopened.list_issues(actor, project=scope, module_id=module)
        assert len(issues) == 1
        row = reopened.read_issue_number(actor, scope, report["authority"]["number"])
        assert row == issues[0]
        assert report["authority"] == {k: row[k] for k in report["authority"]}
        receipts = reopened.db.execute("SELECT call_id FROM tool_receipts WHERE tool='issue.create'").fetchall()
        assert len(receipts) == 1
        report.update(
            call_id=receipts[0]["call_id"],
            committed_create_statuses=observations,
            reopened_module_records=len(issues),
            create_receipts=len(receipts),
        )
    finally:
        reopened.db.close()
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="workbench-i01-") as directory:
        report = exercise(Path(directory), args.godot.resolve(strict=True))
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Passed", report["visible_receipt"], "reopened module records", report["reopened_module_records"])
