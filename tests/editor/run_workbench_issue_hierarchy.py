"""Exercise parent links through native controls and compare with independent stored issues."""

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


def exercise(base, binary):
    with patch.dict(os.environ, {"GONGGONG_WORKSPACE": ""}):
        engine = copy_editor(binary, base / "engine")
    project = base / "project"
    project.mkdir()
    (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="I03"\n', encoding="utf-8")
    shutil.copyfile(Path(__file__).with_name("workbench_issue_hierarchy.gd"), project / "probe.gd")
    database = str(base / "domain.db")
    store = Tianxuan(database)
    scope = "studio/game"
    password = secrets.token_urlsafe(32)
    account = store.register("I03", "owner@example.invalid", password)
    owner = account["user_id"]
    reader = store.add_member(owner, "reader@example.invalid", password, role="viewer")["user_id"]
    ancestor = store.create_issue(owner, "设计集合", project=scope, body_md="保留父项")
    child = store.create_issue(owner, "待归类的设计", project=scope, body_md="保留正文", acceptance="原验收")
    numbers = [ancestor["number"], child["number"]]
    token = store.issue_session(owner)
    modes = {
        "TIANXUAN_AUTH_MODE": "accounts",
        "TIANXUAN_TENANT_ID": account["tenant_id"],
        "TIANXUAN_PUBLIC_ORIGIN": "https://fixture.invalid",
    }
    reads = []
    stored_after_write = []
    with patch.dict(os.environ, modes), socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        api = create_app(store, native_store=NativeStore(base / "native.db"), native_only=True)

        @api.middleware("http")
        async def observe(request, call_next):
            response = await call_next(request)
            if request.url.path.endswith("/hierarchy"):
                reads.append([request.method, request.url.path, response.status_code])
                if request.method == "PUT":
                    independent = Tianxuan(database)
                    try:
                        for original in (ancestor, child):
                            saved = independent.read_issue(reader, original["id"])
                            for field in original.keys() - {"parent_id", "updated_at"}:
                                assert saved[field] == original[field]
                        children = independent.issue_hierarchy(reader, ancestor["id"], scope)["children"]
                        stored_after_write.append({
                            "http": response.status_code,
                            "parent": independent.read_issue(reader, child["id"])["parent_id"],
                            "children": [row["id"] for row in children],
                        })
                    finally:
                        independent.db.close()
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
                I03_NUMBERS=json.dumps(numbers),
            )
            result = subprocess.run(
                [str(engine), "--headless", "--editor", "--path", str(project), "--script", "res://probe.gd"],
                env=env,
                cwd=base,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=90,
            )
        finally:
            service.should_exit = True
            thread.join(timeout=10)
            store.db.close()
    output = result.stdout + result.stderr
    if token in output or password in output:
        raise AssertionError("Credential in fixture diagnostics")
    markers = [line.removeprefix("I03_REPORT=") for line in output.splitlines() if line.startswith("I03_REPORT=")]
    if result.returncode or "SCRIPT ERROR" in output or len(markers) != 1:
        raise RuntimeError(output[-5000:])
    trace = json.loads(markers[0])
    assert trace["attached"] == ancestor["id"] and trace["cycle_parent"] is None and trace["detached"] is None
    assert [code for method, _, code in reads if method == "PUT"] == [200, 409, 200]
    expected_link = {"parent": ancestor["id"], "children": [child["id"]]}
    assert stored_after_write == [
        {"http": 200, **expected_link},
        {"http": 409, **expected_link},
        {"http": 200, "parent": None, "children": []},
    ]
    reopened = Tianxuan(database)
    original_content = []
    try:
        for initial in [ancestor, child]:
            saved = reopened.read_issue(owner, initial["id"])
            assert saved["parent_id"] is None
            assert {k: v for k, v in saved.items() if k != "updated_at"} == {
                k: v for k, v in initial.items() if k != "updated_at"
            }
            original_content.append({k: saved[k] for k in ("number", "title", "body_md", "acceptance", "parent_id")})
        assert reopened.issue_hierarchy(owner, ancestor["id"], scope)["children"] == []
    finally:
        reopened.db.close()
    with binary.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {
        "state": "passed",
        "editor_sha256": digest,
        "native": trace,
        "authenticated_requests": reads,
        "viewer_after_each_write": stored_after_write,
        "reopened_issues": original_content,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="workbench-i03-") as directory:
        report = exercise(Path(directory), args.godot.resolve(strict=True))
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Passed I03 native issue detail checks")
