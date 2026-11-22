"""Confirm exact document revisions using the compiled Godot controls and a private Tianxuan service."""

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

import httpx
import uvicorn
from editor_test_isolation import copy_editor
from run_unified_settings_native import sanitized_environment
from starlette.responses import Response

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "customizations/components/tianxuan/server"))

# isort: split
from api import create_app  # noqa: E402
from tianxuan_core import Tianxuan  # noqa: E402


def exercise(root, binary):
    editor = copy_editor(binary, root / "engine")
    project = root / "project"
    project.mkdir()
    (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="D09"\n')
    shutil.copyfile(Path(__file__).with_name("workbench_design_signoff.gd"), project / "probe.gd")
    store = Tianxuan(str(root / "business.sqlite"))
    user = store.register("Design Studio", "author@example.invalid", secrets.token_urlsafe(24))
    actor = user["user_id"]
    token = store.issue_session(actor)
    reader = store.add_member(actor, "reader@example.invalid", secrets.token_urlsafe(24), role="viewer")
    viewer = {"Authorization": "Bearer " + store.issue_session(reader["user_id"])}
    doc = store.create_doc(actor, "Bridge", "One lever opens the bridge.")
    key = doc["id"]
    route = f"/api/v1/docs/{key}"
    fixture = dict(id=key, actor=actor, first="One pull opens the bridge.", second="Two pulls open the bridge.")
    modes = dict(
        TIANXUAN_AUTH_MODE="accounts",
        TIANXUAN_PUBLIC_ORIGIN="https://fixture.invalid",
        TIANXUAN_TENANT_ID=user["tenant_id"],
    )
    calls, controls, receipts = [], [], []
    with patch.dict(os.environ, modes), socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        origin = "http://127.0.0.1:" + str(sock.getsockname()[1])
        app = create_app(store)

        @app.middleware("http")
        async def observe(request, call_next):
            native_write = (
                request.method == "POST"
                and request.url.path.endswith("/signoff")
                and request.query_params.get("project") == "d09/studio"
            )
            payload = await request.json() if native_write else None
            reply = await call_next(request)
            if native_write:
                code = reply.status_code
                if not calls and code == 200:
                    reply = Response(status_code=503)
                calls.append(dict(path=request.url.path, payload=payload, server=code, client=reply.status_code))
            return reply

        service = uvicorn.Server(uvicorn.Config(app, log_level="error", access_log=False))
        thread = threading.Thread(target=service.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 15
            while not service.started:
                if not thread.is_alive() or time.monotonic() > deadline:
                    raise RuntimeError("Tianxuan did not start")
                time.sleep(0.03)
            with httpx.Client(base_url=origin, headers={"Authorization": "Bearer " + token}, trust_env=False) as client:
                for version, acceptance in enumerate([fixture["first"], fixture["second"]], start=1):
                    path = route + f"/versions/{version}/signoff"
                    if version == 2:
                        updated = client.patch(route, json={"body_md": "Pull the lever twice.", "expected_version": 1})
                        updated.raise_for_status()
                    assert client.get(path).json() == {"signoff": None}
                    assert client.post(path, headers=viewer, json={"acceptance": acceptance}).status_code == 403
                    env = {k: v for k, v in sanitized_environment(root).items() if not k.startswith("TIANXUAN_")}
                    env.update(
                        TIANXUAN_API=origin,
                        TIANXUAN_TOKEN=token,
                        TIANXUAN_PROJECT="d09/studio",
                        D09_FIXTURE=json.dumps(dict(fixture, version=version)),
                    )
                    run = subprocess.run(
                        [
                            str(editor),
                            "--headless",
                            "--single-window",
                            "--resolution",
                            "1440x960",
                            "--editor",
                            "--path",
                            str(project),
                            "--script",
                            "res://probe.gd",
                        ],
                        env=env,
                        cwd=root,
                        capture_output=True,
                        timeout=75,
                    )
                    output = (run.stdout + run.stderr).decode("utf-8", errors="replace")
                    assert token not in output, "Credential in editor diagnostics"
                    lines = [
                        line.removeprefix("D09_NATIVE=")
                        for line in output.splitlines()
                        if line.startswith("D09_NATIVE=")
                    ]
                    if run.returncode or "SCRIPT ERROR" in output or len(lines) != 1:
                        raise RuntimeError(output[-6500:])
                    controls.append(json.loads(lines[0]))
                    receipt = client.get(path, headers=viewer).json()["signoff"]
                    assert receipt["document_id"] == key and receipt["version"] == version
                    assert receipt["confirmed_by"] == actor and receipt["acceptance"] == acceptance
                    assert receipt["confirmed_at"] in controls[-1][1]["status"]
                    receipts.append(receipt)
                    assert client.post(path, json={"acceptance": "different criteria"}).status_code == 409
                assert client.get(route + "/versions/99/signoff").status_code == 404
                old = client.get(route + "/versions/1/signoff").json()["signoff"]
                assert old == receipts[0] and old["confirmed_at"] in controls[-1][-1]["status"]
            assert [c["path"] for c in calls] == [route + f"/versions/{v}/signoff" for v in [1, 1, 2]]
            assert [(c["server"], c["client"]) for c in calls] == [(200, 503), (200, 200), (200, 200)]
            assert calls[0]["payload"] == calls[1]["payload"] == {"acceptance": fixture["first"]}
            assert controls[0][0]["body"] == controls[1][-1]["body"] == doc["body_md"]
            assert controls[1][0]["body"] == "Pull the lever twice."
            assert len(store.versions(key)) == 2 and not store.list_issues(actor)
        finally:
            service.should_exit = True
            thread.join(10)
            store.db.close()
    reopened = Tianxuan(str(root / "business.sqlite"))
    try:
        assert [reopened.design_signoff(actor, key, n) for n in (1, 2)] == receipts
        count = reopened.db.execute("SELECT COUNT(*) FROM design_signoffs").fetchone()[0]
        assert count == 2
    finally:
        reopened.db.close()
    return dict(
        state="passed",
        editor_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
        native=controls,
        writes=calls,
        durable_receipts=receipts,
        database_row_count=count,
        viewer_can_read=True,
        viewer_write_status=403,
        changed_criteria_status=409,
        created_issues=0,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="d09-signoff-") as temp, patch.dict(os.environ, GONGGONG_WORKSPACE=""):
        result = exercise(Path(temp), args.godot.resolve())
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
