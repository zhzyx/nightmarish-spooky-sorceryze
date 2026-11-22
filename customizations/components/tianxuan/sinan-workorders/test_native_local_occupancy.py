"""Crash an actual coordinator and race two reopen requests while its producer lives."""

import asyncio
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
import test_native_workflow as native_fixture
from api import create_app
from fastapi.responses import Response
from fastapi.testclient import TestClient
from native_store import NativeStore
from native_worker import NativeWorker
from native_workflow import NativeWorkflow
from test_native_workflow import reserve, task
from tianxuan_core import Tianxuan

fixture = native_fixture.fixture

EDITOR_TESTS = Path(__file__).resolve().parents[4] / "tests/editor"


def launch_owner():
    data = json.load(sys.stdin)
    root = Path(data["root"])
    domain = Tianxuan(str(root / "domain.sqlite"))
    worker = NativeWorker(
        NativeStore(root / "native.sqlite"),
        root / "workers",
        data["profiles"],
        lambda *a: True,
        authorize=lambda *a: True,
    )
    workflow = NativeWorkflow(domain, worker, None, None, lambda *a: True, catalog=data["catalog"])
    for key in data["keys"]:
        reserve((workflow, data["actor"]), key)
    workflow.execute(data["actor"], data["keys"][1])


def wait_until(check, timeout=30):
    end = time.monotonic() + timeout
    while not check():
        if time.monotonic() > end:
            raise TimeoutError("Expected process or editor event was not observed")
        time.sleep(0.025)


def editor_requests(app, binary, root, tokens, project):
    sys.path.insert(0, str(EDITOR_TESTS))
    from editor_test_isolation import copy_editor
    from run_unified_settings_native import sanitized_environment
    from run_workbench_offline_document import serve

    arrived = []
    all_open = asyncio.Event()
    responses = []

    @app.middleware("http")
    async def open_together(request, call_next):
        if request.url.path.endswith("/recover-occupancy"):
            arrived.append(True)
            if len(arrived) == 2:
                all_open.set()
            await asyncio.wait_for(all_open.wait(), 15)
            response = await call_next(request)
            body = b"".join([chunk async for chunk in response.body_iterator])
            assert response.status_code == 200
            index = tokens.index(request.headers["Authorization"].removeprefix("Bearer "))
            responses.append({"instance": index, "items": json.loads(body)["items"]})
            if len(responses) == 2:
                (root / "responses").touch()
            return Response(content=body, status_code=response.status_code, headers=dict(response.headers))
        return await call_next(request)

    def run(index, port):
        private = root / f"editor-{index}"
        private.mkdir()
        editor = copy_editor(binary, private / "engine")
        game = private / "project"
        game.mkdir()
        (game / "project.godot").write_text('[application]\nconfig/name="R09"\n')
        for script in ("workbench_issue_detail.gd", "workbench_reclaim.gd"):
            (game / script).write_bytes((EDITOR_TESTS / script).read_bytes())
        env = sanitized_environment(private) | {
            "TIANXUAN_TOKEN": tokens[index],
            "TIANXUAN_API": f"http://127.0.0.1:{port}",
            "TIANXUAN_PROJECT": project,
            "R09_DONE": str(root / "responses"),
        }
        editor = subprocess.run(
            [editor, "--headless", "--editor", "--path", game, "--script", "res://workbench_reclaim.gd"],
            capture_output=True,
            text=True,
            env=env,
            timeout=90,
        )
        assert editor.returncode == 0 and "SCRIPT ERROR" not in editor.stderr, (arrived, responses, editor.stderr)
        return int(next(line.split()[-1] for line in editor.stdout.splitlines() if line.startswith("R09_EDITOR ")))

    with serve(app, 0) as port, ThreadPoolExecutor(2) as pool:
        pids = list(pool.map(lambda i: run(i, port), range(2)))
    assert len(set(pids)) == len(arrived) == 2
    return [{"pid": pids[row["instance"]], "items": row["items"]} for row in responses]


@pytest.mark.skipif(os.name != "posix", reason="POSIX process-group witness")
def test_crashed_owner_and_live_group(fixture, record_property, monkeypatch):
    workflow, actor, tenant, _, _, root = fixture
    monkeypatch.setenv("TIANXUAN_AUTH_MODE", "accounts")
    monkeypatch.setenv("TIANXUAN_TENANT_ID", tenant)
    monkeypatch.setenv("TIANXUAN_PUBLIC_ORIGIN", "https://fixture.invalid")
    started, release = root / "process", root / "release"
    worker_code = (
        "import os,pathlib,sys,time; p,r=map(pathlib.Path,sys.argv[1:]); "
        "p.write_text(str(os.getpid()));\nwhile not r.exists(): time.sleep(.02)"
    )
    workflow.worker.profiles["local"]["argv"] = [
        str(Path(sys.executable).resolve()),
        "-c",
        worker_code,
        str(started),
        str(release),
    ]
    original, issue = task(fixture, "a")
    live, _ = task(fixture, "b")
    token = workflow.domain.issue_session(actor)
    app = create_app(workflow.domain, native_workflow=workflow)
    owner = subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), "owner"],
        stdin=subprocess.PIPE,
        env={**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)},
        text=True,
    )
    owner.stdin.write(
        json.dumps({
            "actor": actor,
            "root": str(root),
            "profiles": workflow.worker.profiles,
            "catalog": workflow.catalog,
            "keys": [original, live],
        })
    )
    owner.stdin.close()
    project = issue["project"]
    headers = {"Authorization": "Bearer " + token}
    path = "/api/v1/native/workflow/recover-occupancy"
    try:
        wait_until(lambda: started.exists() and started.stat().st_size)
        child = int(started.read_text())
        with TestClient(app) as client:

            def reopen():
                return client.post(path, headers=headers, json={"project": project}).raise_for_status().json()["items"]

            def counts():
                with workflow._transaction(write=False) as db:
                    return [
                        event[0]
                        for event in db.execute("SELECT type FROM events WHERE type='native.local-occupancy-recovered'")
                    ]

            assert not any(item["reclaimed"] for item in reopen())
            assert client.post(path, json={"project": project}).status_code == 401
            assert client.post(path, headers=headers, json={"project": "unrelated"}).raise_for_status().json() == {
                "items": []
            }
            peer = workflow.domain.add_member(actor, "peer@example.invalid", "test-password", role="editor")
            peer_headers = {"Authorization": "Bearer " + workflow.domain.issue_session(peer["user_id"])}
            assert client.post(path, headers=peer_headers, json={"project": project}).raise_for_status().json() == {
                "items": []
            }
            owner.kill()
            owner.wait(10)
            binary = os.environ.get("R09_GODOT")
            if binary:
                editors = editor_requests(
                    create_app(workflow.domain, native_workflow=workflow),
                    Path(binary).resolve(strict=True),
                    root,
                    [token, workflow.domain.issue_session(actor)],
                    project,
                )
            else:
                editors = []
                with ThreadPoolExecutor(2) as pool:
                    attempts = list(pool.map(lambda _: reopen(), range(2)))
                assert sum(item["reclaimed"] for items in attempts for item in items) == 1
            if editors:
                assert sum(item["reclaimed"] for ed in editors for item in ed["items"]) == 1
            assert len(counts()) == 1
            assert {r["task"]: r["state"] for r in reopen()} == {original: "reserved", live: "running"}
            os.kill(child, 0)
            release.touch()

            def group_gone():
                try:
                    os.killpg(child, 0)
                except ProcessLookupError:
                    return True
                return False

            wait_until(group_gone)
            orphan = [i for i in reopen() if i["reclaimed"]]
            assert orphan == [
                {"task": live, "worker_ref": "native-worker:" + live, "state": "closed-unresolved", "reclaimed": True}
            ]
            assert not any(i["reclaimed"] for i in reopen())
            assert len(counts()) == 2
            assert workflow.status(actor, live)["terminal"] is None
            record_property(
                "recovery",
                json.dumps({
                    "supervisor": owner.pid,
                    "worker": child,
                    "editors": editors,
                    "original_reserved": original,
                    "original_active": live,
                    "claims_while_worker_alive": 1,
                    "claimed_after_physical_exit": orphan,
                    "terminal": None,
                }),
            )
    finally:
        release.touch()
        if owner.poll() is None:
            owner.kill()
        owner.wait(10)


if __name__ == "__main__" and sys.argv[1:] == ["owner"]:
    launch_owner()
