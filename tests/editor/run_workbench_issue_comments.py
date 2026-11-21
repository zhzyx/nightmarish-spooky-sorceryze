"""Exercise I05 using two accounts and four launches of an isolated native editor."""

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
from fastapi.responses import Response
from run_unified_settings_native import sanitized_environment

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "customizations/components/tianxuan/server"))
from api import create_app  # noqa: E402
from native_store import NativeStore  # noqa: E402
from tianxuan_core import Tianxuan  # noqa: E402


def launch(engine, project, environment):
    result = subprocess.run(
        [str(engine), "--headless", "--editor", "--path", str(project), "--script", "res://probe.gd"],
        env=environment,
        cwd=project.parent,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=90,
    )
    output = result.stdout + result.stderr
    if environment["TIANXUAN_TOKEN"] in output:
        raise AssertionError("Credentials appeared in editor output")
    reports = [line.removeprefix("I05_REPORT=") for line in output.splitlines() if line.startswith("I05_REPORT=")]
    if result.returncode or len(reports) != 1 or "SCRIPT ERROR" in output:
        raise AssertionError(output[-6000:])
    return json.loads(reports[0])


def exercise(base, binary):
    with patch.dict(os.environ, {"GONGGONG_WORKSPACE": ""}):
        engine = copy_editor(binary, base / "engine")
    project = base / "project"
    project.mkdir()
    (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="I05"\n', encoding="utf-8")
    shutil.copyfile(Path(__file__).with_name("workbench_issue_comments.gd"), project / "probe.gd")
    database = str(base / "domain.db")
    store = Tianxuan(database)
    native = NativeStore(base / "native.db")
    account = store.register("I05", "a@example.invalid", secrets.token_urlsafe(30), name="林川")
    first = account["user_id"]
    second = store.add_member(first, "b@example.invalid", secrets.token_urlsafe(30), name="唐敏")["user_id"]
    tokens = [store.issue_session(actor) for actor in (first, second)]
    scope = "studio/game"
    issue = store.create_issue(first, "审阅入口", project=scope)
    modes = {
        "TIANXUAN_AUTH_MODE": "accounts",
        "TIANXUAN_TENANT_ID": account["tenant_id"],
        "TIANXUAN_PUBLIC_ORIGIN": "https://fixture.invalid",
    }
    phases = []
    requests = []
    comment_responses = []
    try:
        with patch.dict(os.environ, modes), socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            api = create_app(store, native_store=native, native_only=True)

            @api.middleware("http")
            async def lose_first_receipt(request, call_next):
                response = await call_next(request)
                requests.append([request.method, request.url.path, response.status_code])
                if request.method == "POST" and request.url.path.endswith("/comments"):
                    if not comment_responses and response.status_code == 200:
                        comment_responses.append(503)
                        return Response(status_code=503)
                    comment_responses.append(response.status_code)
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
                environment = {k: v for k, v in sanitized_environment(base).items() if not k.startswith("TIANXUAN_")}
                environment.update(
                    TIANXUAN_API=f"http://127.0.0.1:{sock.getsockname()[1]}",
                    TIANXUAN_PROJECT=scope,
                    I05_NUMBER=str(issue["number"]),
                )
                for phase, token in enumerate([tokens[0], tokens[1], tokens[0], tokens[0]]):
                    try:
                        phases.append(
                            launch(engine, project, environment | {"TIANXUAN_TOKEN": token, "I05_PHASE": str(phase)})
                        )
                    except AssertionError as error:
                        raise AssertionError(f"Editor phase {phase}, observed responses {requests}: {error}") from None
            finally:
                server.should_exit = True
                thread.join(timeout=10)
    finally:
        store.db.close()

    fresh = Tianxuan(database)
    try:
        rows = fresh.list_issue_comments(first, issue["id"])
    finally:
        fresh.db.close()
    assert comment_responses == [503, 200, 200, 200]
    assert len(rows) == 3
    assert [row["author"] for row in rows] == [first, second, first]
    assert [row["author_name"] for row in rows] == ["林川", "唐敏", "林川"]
    assert [row["body"] for row in rows] == [
        "入口截图已更新",
        "请补上验收步骤" + "\n复核入口和返回路径" * 9,
        "已补充第二步",
    ]
    assert [row["parent_id"] for row in rows] == [None, rows[0]["id"], rows[1]["id"]]
    for index, record in enumerate(phases):
        visible = rows[: min(index + 1, 3)]
        assert [r["data"] for r in record["rows"]] == visible
        assert [r["display"] for r in record["rows"]] == [
            f"{r['author_name']}　{r['body'].splitlines()[0]}" for r in visible
        ]
    with binary.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {
        "engine_sha256": digest,
        "comment_post_status": comment_responses,
        "verified_thread": rows,
        "editor_launches": [{k: v for k, v in phase.items() if k != "rows"} for phase in phases],
        "pass": True,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="workbench-i05-") as directory:
        report = exercise(Path(directory), args.godot.resolve(strict=True))
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Passed I05 two-account native comment thread and restart checks")
