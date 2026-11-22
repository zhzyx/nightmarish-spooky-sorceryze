"""Exercise exact-version task splitting from the compiled workbench against a private Tianxuan database."""

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
from concurrent.futures import ThreadPoolExecutor
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

PROJECT = "d10/bridge"


def run_editor(root, binary, origin, token, items):
    editor = copy_editor(binary, root / "engine")
    project = root / "project"
    project.mkdir()
    (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="D10"\n')
    shutil.copyfile(Path(__file__).with_name("workbench_design_tasks.gd"), project / "probe.gd")
    env = {k: v for k, v in sanitized_environment(root).items() if not k.startswith("TIANXUAN_")}
    env.update(
        TIANXUAN_API=origin, TIANXUAN_TOKEN=token, TIANXUAN_PROJECT=PROJECT, D10_FIXTURE=json.dumps({"items": items})
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
        timeout=90,
    )
    output = (run.stdout + run.stderr).decode("utf-8", errors="replace")
    assert token not in output, "Credential in editor diagnostics"
    lines = [line.removeprefix("D10_NATIVE=") for line in output.splitlines() if line.startswith("D10_NATIVE=")]
    if run.returncode or "SCRIPT ERROR" in output or len(lines) != 1:
        raise RuntimeError(output[-6500:])
    return json.loads(lines[0])


def exercise(root, binary):
    database = root / "business.sqlite"
    store = Tianxuan(str(database))
    user = store.register("Design Studio", "author@example.invalid", secrets.token_urlsafe(24))
    actor = user["user_id"]
    token = store.issue_session(actor)
    reader = store.add_member(actor, "reader@example.invalid", secrets.token_urlsafe(24), role="viewer")
    viewer = {"Authorization": "Bearer " + store.issue_session(reader["user_id"])}
    original = "Program the lever.\r\nHandle repeated pulls.\r\n\r\nAnimate the bridge opening."
    doc = store.create_doc(actor, "Bridge", original)
    doc_id = doc["id"]
    items = []
    for n, (name, title, acceptance) in enumerate(
        [
            ("程序", "操作拉杆", "拉杆触发一次开桥事件"),
            ("动画", "桥面展开", "桥面动画播放至展开状态"),
        ],
        1,
    ):
        module = store.create_business_module(actor, PROJECT, name, call_id=f"module-{n}")
        items.append(dict(paragraph=n, title=title, acceptance=acceptance, module_id=module["id"]))
    route = f"/api/v1/docs/{doc_id}/versions/1"
    task_path = route + "/tasks"
    writes = []
    observe_native = False
    modes = dict(
        TIANXUAN_AUTH_MODE="accounts",
        TIANXUAN_PUBLIC_ORIGIN="https://fixture.invalid",
        TIANXUAN_TENANT_ID=user["tenant_id"],
    )
    with patch.dict(os.environ, modes), socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        origin = "http://127.0.0.1:" + str(sock.getsockname()[1])
        app = create_app(store)

        @app.middleware("http")
        async def observe(request, call_next):
            track = observe_native and request.method == "POST" and request.url.path == task_path
            payload = await request.json() if track else None
            reply = await call_next(request)
            if track:
                assert request.query_params.get("project") == PROJECT
                server = reply.status_code
                if not writes and server == 200:
                    reply = Response(status_code=503)
                writes.append(dict(payload=payload, server=server, client=reply.status_code))
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
            with httpx.Client(
                base_url=origin,
                headers={"Authorization": "Bearer " + token},
                params={"project": PROJECT},
                trust_env=False,
            ) as client:
                request = dict(call_id="preflight", items=items)
                assert client.post(task_path, json=request).status_code == 409
                signoff = client.post(route + "/signoff", json={"acceptance": "拉杆触发开桥，桥面完成展开"}).json()[
                    "signoff"
                ]
                assert signoff["document_id"] == doc_id and signoff["version"] == 1
                assert client.post(task_path, json=request, headers=viewer).status_code == 403
                bad = [items[0], items[1] | {"module_id": "missing"}]
                assert client.post(task_path, json=request | {"items": bad}).status_code == 404
                bad = [items[0], items[1] | {"paragraph": 3}]
                assert client.post(task_path, json=request | {"items": bad}).status_code == 400
                assert not store.list_issues(actor) and client.get(task_path).json()["tasks"] == []
                observe_native = True
                native = run_editor(root, binary, origin, token, items)
                observe_native = False
                assert [(w["server"], w["client"]) for w in writes] == [(200, 503), (200, 200)]
                assert native["items"] == items and native["revision"] == 1
                request = writes[0]["payload"]
                assert request == writes[1]["payload"] and request["items"] == items
                assert client.post(task_path, json=request | {"items": items[:1]}).status_code == 409
                expected = client.post(task_path, json=request).json()["tasks"]
                assert len(expected) == 2
                revised = client.get(f"/api/v1/docs/{doc_id}")
                assert revised.json()["version"] == 2 and revised.json()["body_md"] == "A different design."
                assert len(native["opened"]) == 2
                for item, task, opened in zip(items, expected, native["opened"], strict=True):
                    assert opened == dict(
                        number=task["number"],
                        reference=dict(document_id=doc_id, version=1, paragraph=item["paragraph"]),
                        body=original,
                    )
                assert client.get(route).json()["body_md"] == original
                current = task_path.replace("/versions/1/", "/versions/2/")
                assert client.get(current).json() == {"tasks": []}
                assert client.post(current, json=request).status_code == 409
                assert client.get(task_path, params={"project": "other"}).json()["tasks"] == []
                links = client.get(task_path, headers=viewer).json()["tasks"]
                assert len(links) == 2
                for item, task, link in zip(items, expected, links, strict=True):
                    source = dict(
                        document_id=doc_id,
                        version=1,
                        project=PROJECT,
                        module_id=item["module_id"],
                        paragraph=item["paragraph"],
                        acceptance=item["acceptance"],
                    )
                    assert link == dict(id=task["id"], number=task["number"], title=item["title"]) | source
                    detail_path = f"/api/v1/issues/by-number/{task['number']}/detail"
                    detail = client.get(detail_path, headers=viewer).json()
                    assert detail["design_source"] == task["design_source"] == source
                    assert (detail["id"], detail["title"], detail["acceptance"], detail["module_id"]) == (
                        task["id"],
                        item["title"],
                        item["acceptance"],
                        item["module_id"],
                    )
                    assert f"#{task['number']} {item['title']}" in native["status"]
                    assert client.get(detail_path, params={"project": "other"}).status_code == 404
        finally:
            service.should_exit = True
            thread.join(10)
            store.db.close()

    def reopen_and_replay(_):
        fresh = Tianxuan(str(database))
        try:
            return fresh.split_design(actor, doc_id, 1, PROJECT, items, request["call_id"])
        finally:
            fresh.db.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(reopen_and_replay, range(2))) == [expected, expected]
    fresh = Tianxuan(str(database))
    try:
        counts = {
            table: fresh.db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("issues", "doc_issue_links", "design_task_sources")
        }
        assert set(counts.values()) == {2}
        assert fresh.design_tasks(actor, doc_id, 1, PROJECT) == links
        assert fresh.design_signoff(actor, doc_id, 1) == signoff
    finally:
        fresh.db.close()
    return dict(
        state="passed",
        editor_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
        native=native,
        writes=writes,
        durable_sources=links,
        original_signoff=signoff,
        database_counts=counts,
        unsigned_status=409,
        viewer_write_status=403,
        missing_module_rollback=404,
        bad_paragraph_rollback=400,
        conflicting_replay=409,
        unrelated_project_count=0,
        unsigned_next_revision_count=0,
        concurrent_replays=2,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="d10-tasks-") as temp, patch.dict(os.environ, GONGGONG_WORKSPACE=""):
        report = exercise(Path(temp), args.godot.resolve())
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
