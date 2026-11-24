"""Exercise the embedded I11 controls against an isolated authenticated Tianxuan service."""

import argparse
import asyncio
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
from fastapi.responses import JSONResponse
from run_unified_settings_native import sanitized_environment

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "customizations/components/tianxuan/server"))
from api import create_app  # noqa: E402
from native_store import NativeStore  # noqa: E402
from tianxuan_core import Tianxuan  # noqa: E402


def seed(store, scope):
    password = secrets.token_urlsafe(32)
    tenant = store.register("I11", "admin@example.invalid", password)
    admin = tenant["user_id"]
    owner = store.add_member(admin, "artist@example.invalid", password, name="顾青", role="viewer")["user_id"]
    title = "检查场景"
    keyword = "Alpha & 复核"
    left, right = (store.create_business_module(admin, scope, name, call_id=name)["id"] for name in ["场景", "关卡"])
    fixture = dict(owner_name="顾青", owner_id=owner, title=title, keyword=keyword, left=left, right=right, visible=[])

    def issue(module, body, assignee, status, project=scope, requirement=None):
        row = store.create_issue(
            admin, title, body_md=body, project=project, module_id=module, requirement_id=requirement
        )
        with store.db:
            store.db.execute("INSERT INTO issue_assignees VALUES (?,?)", (row["id"], assignee))
        if status != "backlog":
            store.transition_issue(admin, row["id"], status)
        if project == scope and not requirement:
            fixture["visible"].append(row["number"])
        return row

    for name, module in [("left", left), ("right", right)]:
        record = issue(module, keyword.lower(), owner, "planned")
        fixture.update({f"{name}_number": record["number"], f"{name}_id": record["id"]})
    issue(left, keyword, admin, "planned")
    issue(left, keyword, owner, "backlog")
    issue(left, "另一正文", owner, "planned")
    issue("default", keyword, owner, "planned", project="studio/elsewhere")
    private = store.create_requirement(admin, "private", "Private", "why", "scope", "done")
    store.set_visibility(admin, private["id"], "private")
    issue(left, keyword, owner, "planned", requirement=private["id"])
    return fixture, tenant["tenant_id"], store.issue_session(owner)


def exercise(base, binary):
    with patch.dict(os.environ, {"GONGGONG_WORKSPACE": ""}):
        engine = copy_editor(binary, base / "engine")
    project = base / "project"
    project.mkdir()
    (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="I11"\n', encoding="utf-8")
    shutil.copyfile(Path(__file__).with_name("workbench_issue_search.gd"), project / "probe.gd")
    scope = "studio/game"
    store = Tianxuan(str(base / "domain.db"))
    fixture, tenant, token = seed(store, scope)
    modes = {
        "TIANXUAN_AUTH_MODE": "accounts",
        "TIANXUAN_TENANT_ID": tenant,
        "TIANXUAN_PUBLIC_ORIGIN": "https://fixture.invalid",
    }
    reads = []
    with patch.dict(os.environ, modes), socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        api = create_app(store, native_store=NativeStore(base / "native.db"), native_only=True)

        @api.middleware("http")
        async def observe(request, call_next):
            response = await call_next(request)
            if request.query_params.get("q") == "legacy-filter":
                # Earlier servers successfully returned the whole project list for unknown filters.
                response = JSONResponse({"issues": store.list_issues(fixture["owner_id"], project=scope)})
            if request.url.path == "/api/v1/issues" or request.url.path.endswith("/detail"):
                reads.append([request.url.path, dict(request.query_params), response.status_code])
            if request.query_params.get("q") == "slow-request":
                (project / "slow-started").touch()
                await asyncio.sleep(0.6)
            return response

        service = uvicorn.Server(uvicorn.Config(api, log_level="error", access_log=False))
        thread = threading.Thread(target=service.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 20
            while not service.started:
                if not thread.is_alive() or time.monotonic() > deadline:
                    raise RuntimeError("Fixture failed to start")
                time.sleep(0.05)
            env = {k: v for k, v in sanitized_environment(base).items() if not k.startswith("TIANXUAN_")}
            env.update(
                TIANXUAN_API=f"http://127.0.0.1:{sock.getsockname()[1]}",
                TIANXUAN_PROJECT=scope,
                TIANXUAN_TOKEN=token,
                I11_FIXTURE=json.dumps(fixture),
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
        finally:
            service.should_exit = True
            thread.join(timeout=10)
            store.db.close()
    output = result.stdout + result.stderr
    if token in output:
        raise AssertionError("Credential in fixture diagnostics")
    markers = [
        line.removeprefix("I11_REPORT=") for line in result.stdout.splitlines() if line.startswith("I11_REPORT=")
    ]
    if result.returncode or len(markers) != 1 or "SCRIPT ERROR" in output:
        raise AssertionError(output[-6000:])
    for module in ("left", "right"):
        params = dict(
            project=scope,
            module_id=fixture[module],
            assignee=fixture["owner_name"],
            status="planned",
            q=fixture["keyword"],
        )
        assert ["/api/v1/issues", params, 200] in reads
        assert [f"/api/v1/issues/by-number/{fixture[module + '_number']}/detail", {"project": scope}, 200] in reads
    with binary.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"editor_sha256": digest, "fixture": fixture, "observed": json.loads(markers[0]), "http_reads": reads}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="workbench-i11-") as directory:
        report = exercise(Path(directory), args.godot.resolve(strict=True))
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Passed I11 native issue search checks")
