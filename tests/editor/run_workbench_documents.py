"""Open duplicate design documents and pinned paragraphs through the compiled native sidebar."""

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

# isort: split
from api import create_app  # noqa: E402
from tianxuan_core import Tianxuan  # noqa: E402


def exercise(root, binary):
    with patch.dict(os.environ, {"GONGGONG_WORKSPACE": ""}):
        editor = copy_editor(binary, root / "engine")
    project = root / "project"
    project.mkdir()
    (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="D02"\n')
    shutil.copyfile(Path(__file__).with_name("workbench_documents.gd"), project / "probe.gd")
    store = Tianxuan(str(root / "business.sqlite"))
    user = store.register("studio", "reader@example.invalid", secrets.token_urlsafe(24))
    actor = user["user_id"]
    first = store.create_doc(actor, "同名设计", "# 标题\n\n第一个目标\n延续一行\n\n结尾")
    second = store.create_doc(actor, "同名设计", "# 标题\n\n原始段落\n\n结束")
    revised = store.update_doc(actor, second["id"], second["body_md"].replace("原始段落", "第二个目标"), 1)
    fixtures = [
        {"id": first["id"], "version": 1, "text": "第一个目标\n延续一行"},
        {"id": second["id"], "version": revised["version"], "text": "第二个目标"},
    ]
    token = store.issue_session(actor)
    modes = {
        "TIANXUAN_AUTH_MODE": "accounts",
        "TIANXUAN_PUBLIC_ORIGIN": "https://fixture.invalid",
        "TIANXUAN_TENANT_ID": user["tenant_id"],
    }
    reads = []
    with patch.dict(os.environ, modes), socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        api = create_app(store)

        @api.middleware("http")
        async def observe(request, call_next):
            response = await call_next(request)
            reads.append((request.url.path, response.status_code))
            return response

        service = uvicorn.Server(uvicorn.Config(api, log_level="error", access_log=False))
        thread = threading.Thread(target=service.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 15
            while not service.started:
                if time.monotonic() > deadline or not thread.is_alive():
                    raise RuntimeError("Fixture did not start")
                time.sleep(0.05)
            env = {k: v for k, v in sanitized_environment(root).items() if not k.startswith("TIANXUAN_")}
            env.update(
                TIANXUAN_API="http://127.0.0.1:" + str(sock.getsockname()[1]),
                TIANXUAN_TOKEN=token,
                TIANXUAN_PROJECT="studio/game",
                D02_EXPECT=json.dumps(fixtures),
            )
            result = subprocess.run(
                [str(editor), "--headless", "--editor", "--path", str(project), "--script", "res://probe.gd"],
                env=env,
                cwd=root,
                capture_output=True,
                timeout=75,
            )
            output = (result.stdout + result.stderr).decode("utf-8", errors="replace")
            if token in output:
                raise AssertionError("Fixture token appeared in diagnostics")
            checks = [
                line.removeprefix("D02_CHECKS=") for line in output.splitlines() if line.startswith("D02_CHECKS=")
            ]
            if result.returncode or "SCRIPT ERROR" in output or len(checks) != 1:
                raise RuntimeError(output[-5500:])
            trace = json.loads(checks[0])
            assert [(x["document_id"], x["version"], x["paragraph"]) for x in trace] == [
                (first["id"], 1, 2),
                (second["id"], 2, 2),
                (second["id"], 1, 2),
            ]
            for id_, version, code in (
                (first["id"], 1, 200),
                (second["id"], 2, 200),
                (second["id"], 1, 200),
                (second["id"], 99, 404),
            ):
                assert (f"/api/v1/docs/{id_}/versions/{version}", code) in reads
        finally:
            service.should_exit = True
            thread.join(timeout=10)
            store.db.close()
    return {
        "editor_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "state": "passed",
        "native_selections": trace,
        "service_reads": reads,
        "same_title": True,
        "readonly_body": True,
        "invalid_targets_cleared": True,
        "signout_cleared": True,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="workbench-documents-") as directory:
        result = exercise(Path(directory), args.godot.resolve())
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Passed native document and paragraph readback")
