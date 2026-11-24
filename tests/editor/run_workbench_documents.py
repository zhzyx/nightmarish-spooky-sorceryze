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
from starlette.responses import Response

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "customizations/components/tianxuan/server"))

# isort: split
from api import create_app  # noqa: E402
from tianxuan_core import Tianxuan  # noqa: E402


def verify_history(output, store, actor, edits, stale_id, scopes, restores, reads):
    events = [line.removeprefix("D06_CHECKS=") for line in output.splitlines() if line.startswith("D06_CHECKS=")]
    assert len(events) == 1
    revisions = json.loads(events[0])
    key = revisions["document_id"]
    assert key == edits["document_id"] and set(scopes) == {"studio/game"}
    path = f"/api/v1/docs/{key}"
    route = path + "/versions/1/restore"
    stale = f"/api/v1/docs/{stale_id}/versions/1/restore"
    assert [(r, server, client) for r, _, server, client in restores] == [
        (route, 200, 503),
        (route, 200, 200),
        (stale, 409, 409),
    ]
    assert restores[0][1] == restores[1][1] and restores[0][1]["call_id"]
    assert all(payload["expected_version"] == 2 for _, payload, _, _ in restores)
    assert [v["version"] for v in store.versions(key)] == [1, 2, 3]
    assert [v["version"] for v in revisions["revisions"]] == [1, 2, 3]
    a, b = [v["body"] for v in edits["reopened"]]
    assert a != b and [v["body"] for v in revisions["revisions"]] == [a, b, a]
    for version, expected in enumerate([a, b, a], start=1):
        observed = store.version(key, version)
        assert observed["body_md"] == expected and observed["author"] == actor
        assert (path + f"/versions/{version}", 200) in reads
    assert store.get_doc(stale_id)["body_md"] == "Concurrent revision"
    revisions.update(project=scopes[0], restores=restores, concurrent_head_preserved=True)
    return revisions


def exercise(root, binary, manual=False, history=False):
    manual = manual or history
    with patch.dict(os.environ, {"GONGGONG_WORKSPACE": ""}):
        editor = copy_editor(binary, root / "engine")
    project = root / "project"
    project.mkdir()
    (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="D02"\n')
    shutil.copyfile(Path(__file__).with_name("workbench_documents.gd"), project / "probe.gd")
    if manual:
        shutil.copyfile(Path(__file__).with_name("workbench_document_edits.gd"), project / "edits.gd")
    if history:
        shutil.copyfile(Path(__file__).with_name("workbench_document_history.gd"), project / "history.gd")
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
    writes = []
    restores = []
    scopes = []
    with patch.dict(os.environ, modes), socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        api = create_app(store)

        @api.middleware("http")
        async def observe(request, call_next):
            is_restore = history and request.method == "POST" and request.url.path.endswith("/restore")
            if history and request.url.path.startswith("/api/v1/docs"):
                scopes.append(request.query_params.get("project"))
            if is_restore:
                payload = await request.json()
                if request.url.path == f"/api/v1/docs/{second['id']}/versions/1/restore":
                    # Another writer advances the head after the reviewer saw its diff.
                    store.update_doc(actor, second["id"], "Concurrent revision", 2)
            response = await call_next(request)
            if is_restore:
                server_status = response.status_code
                if not restores and server_status == 200:
                    response = Response(status_code=503)
                restores.append((request.url.path, payload, server_status, response.status_code))
            elif manual and request.method in {"POST", "PATCH"}:
                server_status = response.status_code
                if len(writes) == 1 and request.method == "PATCH" and server_status == 200:
                    response = Response(status_code=503)  # Committed write with a lost success response.
                writes.append((request.method, request.url.path, server_status, response.status_code))
            if request.method == "GET":
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
            env.pop("D06_HISTORY", None)
            if history:
                env["D06_HISTORY"] = "1"
            env.pop("D04_AUTHOR", None)
            if manual:
                env["D04_AUTHOR"] = actor
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
            if manual:
                observations = [
                    line.removeprefix("D04_CHECKS=") for line in output.splitlines() if line.startswith("D04_CHECKS=")
                ]
                assert len(observations) == 1
                edits = json.loads(observations[0])
                created = store.get_doc(edits["document_id"])
                assert created["created_by"] == actor and created["title"] == "手工设计"
                assert created["version"] == (3 if history else 2)
                assert len(store.list_docs(actor)) == 3
                for observed in edits["reopened"]:
                    revision = store.version(created["id"], observed["version"])
                    assert revision["body_md"] == observed["body"] and revision["author"] == observed["author"] == actor
                path = "/api/v1/docs/" + created["id"]
                assert writes == [
                    ("POST", "/api/v1/docs", 200, 200),
                    ("PATCH", path, 200, 503),
                    ("PATCH", path, 200, 200),
                    ("PATCH", path, 409, 409),
                ]
                edits["write_receipts"] = [
                    {"method": method, "path": route, "service_status": server, "client_status": client}
                    for method, route, server, client in writes
                ]
                edits["retry_after_lost_success"] = "one committed revision"
            if history:
                revisions = verify_history(output, store, actor, edits, second["id"], scopes, restores, reads)
        finally:
            service.should_exit = True
            thread.join(timeout=10)
            store.db.close()
    return {
        "editor_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "state": "passed",
        **({"manual_design": edits} if manual else {}),
        **({"history": revisions} if history else {}),
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
    parser.add_argument("--manual", action="store_true", help="Also exercise manual creation, save, retry and reopen")
    parser.add_argument("--history", action="store_true", help="Exercise manual saves, comparison and restore")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="workbench-documents-") as directory:
        result = exercise(Path(directory), args.godot.resolve(), manual=args.manual, history=args.history)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Passed native document and paragraph readback")
