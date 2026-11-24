"""Verify I17 through embedded native controls against an isolated Tianxuan deployment."""

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
from fastapi.responses import JSONResponse
from run_unified_settings_native import sanitized_environment

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "customizations/components/tianxuan/server"))
from api import create_app  # noqa: E402
from native_store import NativeStore  # noqa: E402
from tianxuan_core import Tianxuan  # noqa: E402

LABEL = "声音 & 音效"


def native_probe(base, engine, origin, token, ticket):
    project = base / "project"
    project.mkdir(parents=True)
    (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="I17"\n', encoding="utf-8")
    shutil.copyfile(Path(__file__).with_name("workbench_issue_classification.gd"), project / "probe.gd")
    env = {k: v for k, v in sanitized_environment(base).items() if not k.startswith("TIANXUAN_")}
    env.update(
        TIANXUAN_API=origin, TIANXUAN_PROJECT=ticket["project"], TIANXUAN_TOKEN=token, I17_TICKET=json.dumps(ticket)
    )
    result = subprocess.run(
        [str(engine), "--headless", "--editor", "--path", str(project), "--script", "res://probe.gd"],
        env=env,
        cwd=base,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=100,
    )
    output = result.stdout + result.stderr
    if token in output:
        raise AssertionError("Credential in editor diagnostics")
    markers = [line.removeprefix("I17_REPORT=") for line in output.splitlines() if line.startswith("I17_REPORT=")]
    if result.returncode or "SCRIPT ERROR" in output or len(markers) != 1:
        raise RuntimeError(output[-6000:])
    record = json.loads(markers[0])
    assert record["reopened_id"] == ticket["id"] and record["project"] == ticket["project"]
    assert record["type"] == "bug" and record["label"] == LABEL
    return record


def exercise(base, binary):
    with patch.dict(os.environ, {"GONGGONG_WORKSPACE": ""}):
        engine = copy_editor(binary, base / "engine")
    database = str(base / "domain.db")
    password = secrets.token_urlsafe(32)
    store = Tianxuan(database)
    account = store.register("I17", "owner@example.invalid", password)
    owner = account["user_id"]
    reader = store.add_member(owner, "reader@example.invalid", password, role="viewer")["user_id"]
    tokens = {user: store.issue_session(user) for user in (owner, reader)}
    projects = ["studio/audio", "studio/video"]
    tagged = [
        store.create_issue(owner, "同名原单", project=p, body_md="保留正文", acceptance="保留验收") for p in projects
    ]
    untagged = [store.create_issue(owner, "同名原单", project=p, type="feature") for p in projects]
    # Reopen an actual pre-I17 schema containing populated issue rows.
    store.db.execute("DROP TABLE issue_labels")
    store.db.close()
    store = Tianxuan(database)
    modes = {
        "TIANXUAN_AUTH_MODE": "accounts",
        "TIANXUAN_TENANT_ID": account["tenant_id"],
        "TIANXUAN_PUBLIC_ORIGIN": "https://fixture.invalid",
    }
    native, writes = [], []
    with patch.dict(os.environ, modes), socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        origin = f"http://127.0.0.1:{sock.getsockname()[1]}"
        api = create_app(store, native_store=NativeStore(base / "native.db"), native_only=True)

        @api.middleware("http")
        async def observe(request, call_next):
            if request.url.path == "/api/v1/issues" and request.query_params.get("label") == "legacy":
                # The pre-I17 server ignored label= and returned the ordinary project listing.
                project = request.query_params["project"]
                return JSONResponse({"issues": [i for i in tagged + untagged if i["project"] == project]})
            response = await call_next(request)
            if request.method == "PUT" and request.url.path.endswith("/classification"):
                writes.append({"project": request.query_params.get("project"), "status": response.status_code})
            return response

        server = uvicorn.Server(uvicorn.Config(api, log_level="error", access_log=False))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 20
            while not server.started:
                if not thread.is_alive() or time.monotonic() > deadline:
                    raise RuntimeError("Fixture failed to start")
                time.sleep(0.05)
            for user in (owner, reader):
                for ticket in tagged:
                    native.append(native_probe(base / f"run-{len(native)}", engine, origin, tokens[user], ticket))
            with httpx.Client(
                base_url=origin, headers={"Authorization": "Bearer " + tokens[reader]}, trust_env=False
            ) as client:
                ticket = tagged[0]
                route = f"/api/v1/issues/{ticket['id']}/classification"
                params = {"project": ticket["project"]}
                update = {"type": "task", "labels": [], "expected_type": "bug", "expected_labels": [LABEL]}
                assert client.put(route, params=params, json=update).status_code == 403
                client.headers["Authorization"] = "Bearer " + tokens[owner]
                assert client.put(route, params={"project": projects[1]}, json=update).status_code == 404
                stale = {**update, "expected_labels": []}
                assert client.put(route, params=params, json=stale).status_code == 409
                # Replaying the acknowledged desired state causes no duplicate bindings.
                replay = {"type": "bug", "labels": [LABEL], "expected_type": "task", "expected_labels": []}
                assert client.put(route, params=params, json=replay).status_code == 200
                for index, project in enumerate(projects):
                    rows = client.get("/api/v1/issues", params={"project": project}).raise_for_status().json()["issues"]
                    assert {r["id"] for r in rows} == {tagged[index]["id"], untagged[index]["id"]}
                    rows = (
                        client
                        .get("/api/v1/issues", params={"project": project, "label": LABEL})
                        .raise_for_status()
                        .json()["issues"]
                    )
                    assert [r["id"] for r in rows] == [tagged[index]["id"]]
        finally:
            server.should_exit = True
            thread.join(timeout=10)
            store.db.close()
    reopened = Tianxuan(database)
    persisted = []
    try:
        for original in tagged + untagged:
            detail = reopened.read_issue_detail(reader, original["project"], original["number"])
            changed = original in tagged
            assert detail["type"] == ("bug" if changed else "feature")
            assert detail["labels"] == ([LABEL] if changed else [])
            assert all(detail[k] == v for k, v in original.items() if k not in {"type", "updated_at"})
            persisted.append({k: detail[k] for k in ("project", "number", "id", "title", "type", "labels")})
    finally:
        reopened.db.close()
    assert [w["status"] for w in writes] == [200] * 4 + [403, 404, 409, 200]
    # On Windows the console executable is only a wrapper around this implementation.
    editor = binary.with_name(binary.name.replace(".console.exe", ".exe"))
    with editor.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {
        "state": "passed",
        "editor_sha256": digest,
        "native_sessions": native,
        "classification_puts": writes,
        "reopened_database": persisted,
        "pre_i17_schema_upgrade": "existing issues reopened with empty label sets",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="workbench-i17-") as directory:
        result = exercise(Path(directory), args.godot.resolve(strict=True))
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Passed I17 native issue classification and label lookup")
