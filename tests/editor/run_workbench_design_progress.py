"""Read, return and confirm exact Yanshi revisions from a compiled headless editor."""

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
from uuid import uuid4

import httpx
import uvicorn
from editor_test_isolation import copy_editor
from run_unified_settings_native import sanitized_environment

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "customizations/components/tianxuan/server"))

# isort: split
from api import create_app  # noqa: E402
from native_store import NativeStore  # noqa: E402
from tianxuan_core import Tianxuan  # noqa: E402

CHATS = "/api/v1/workspace/conversations"
PROJECT = "d13/studio"


def exercise(root, binary):
    editor = copy_editor(binary, root / "engine")
    project = root / "project"
    project.mkdir()
    (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="D13"\n')
    shutil.copyfile(Path(__file__).with_name("workbench_design_progress.gd"), project / "probe.gd")
    store = Tianxuan(str(root / "domain.sqlite"))
    user = store.register("Studio", "author@example.invalid", secrets.token_urlsafe(24))
    actor = user["user_id"]
    token = store.issue_session(actor)
    auth = {"Authorization": "Bearer " + token}
    other = store.add_member(actor, "other@example.invalid", secrets.token_urlsafe(24), role="viewer")
    viewer = {"Authorization": "Bearer " + store.issue_session(other["user_id"])}
    key = str(uuid4())
    route = CHATS + "/" + key
    controls, decisions = {}, []
    modes = dict(
        TIANXUAN_AUTH_MODE="accounts",
        TIANXUAN_PUBLIC_ORIGIN="https://fixture.invalid",
        TIANXUAN_TENANT_ID=user["tenant_id"],
    )
    with patch.dict(os.environ, modes), socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        origin = "http://127.0.0.1:" + str(sock.getsockname()[1])
        app = create_app(store, native_store=NativeStore(root / "native.sqlite"), native_only=True)

        @app.middleware("http")
        async def concurrent_writer(request, call_next):
            native = (
                request.method == "POST"
                and "/design/" in request.url.path
                and request.query_params.get("project") == PROJECT
            )
            body = await request.json() if native else None
            if native and not decisions:
                async with httpx.AsyncClient(base_url=origin, headers=auth, trust_env=False) as writer:
                    changed = await writer.post(
                        route + "/design/direction/drafts",
                        json={"expected_version": body["expected_version"], "body": "Replacement direction"},
                    )
                    changed.raise_for_status()
            response = await call_next(request)
            if native:
                decisions.append({"path": request.url.path, "payload": body, "status": response.status_code})
            return response

        server = uvicorn.Server(uvicorn.Config(app, log_level="error", access_log=False))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 15
            while not server.started:
                assert thread.is_alive() and time.monotonic() < deadline
                time.sleep(0.03)
            with httpx.Client(base_url=origin, headers=auth, trust_env=False) as client:

                def post(path, **payload):
                    result = client.post(path, json=payload)
                    result.raise_for_status()
                    return result.json()

                def native(mode, **fixture):
                    env = {k: v for k, v in sanitized_environment(root).items() if not k.startswith("TIANXUAN_")}
                    env.update(
                        TIANXUAN_API=origin,
                        TIANXUAN_TOKEN=token,
                        TIANXUAN_PROJECT=PROJECT,
                        D13_FIXTURE=json.dumps(dict(fixture, mode=mode, id=key, actor=actor)),
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
                        line.removeprefix("D13_NATIVE=")
                        for line in output.splitlines()
                        if line.startswith("D13_NATIVE=")
                    ]
                    if run.returncode or "SCRIPT ERROR" in output or len(lines) != 1:
                        raise RuntimeError(output[-8000:])
                    controls[mode] = json.loads(lines[0])
                    return client.get(route).json()

                chat = post(CHATS, id=key)
                chat = post(route + "/turns", expected_version=chat["version"], id=str(uuid4()), content="Open bridge")
                chat = post(
                    route + "/design/direction/drafts", expected_version=chat["version"], body="Original direction"
                )
                store.save_module_location(actor, PROJECT, "default", None, key, "module/overview")
                assert (
                    client.post(
                        route + "/design/plan/drafts", json={"expected_version": chat["version"], "body": "Too early"}
                    ).status_code
                    == 409
                )
                chat = native("stale", body="Original direction")
                assert chat["revisions"][1]["return_reason"] == "Include the lever location."
                assert all(r["confirmed_at"] is None for r in chat["revisions"])
                assert (
                    client.post(
                        route + "/design/direction/confirm", json={"expected_version": chat["version"], "revision": 2}
                    ).status_code
                    == 409
                )
                chat = post(route + "/design/direction/drafts", expected_version=chat["version"], body="Lever on path")
                chat = native("direction", body="Lever on path", pending="策划")
                assert chat["current"] == {"direction": 3} and chat["revisions"][2]["confirmed_by"] == actor
                chat = post(route + "/design/plan/drafts", expected_version=chat["version"], body="Pull the lever")
                assert chat["revisions"][3]["confirmed_at"] is None
                chat = native("plan", body="Pull the lever", pending="详设")
                assert chat["current"] == {"direction": 3, "plan": 4} and chat["revisions"][3]["confirmed_by"] == actor
                chat = post(
                    route + "/design/design/drafts",
                    expected_version=chat["version"],
                    title="Bridge",
                    body="Open within a second",
                    acceptance="One pull.",
                )
                assert chat["revisions"][4]["confirmed_at"] is None
                chat = post(route + "/design/design/confirm", expected_version=chat["version"], revision=5)
                chat = post(route + "/requirement", expected_version=chat["version"], lang="en")
                doc = chat["requirement_id"]
                docs = "/api/v1/docs/" + doc
                signoff = post(docs + "/versions/1/signoff", acceptance="One pull.")["signoff"]
                client.patch(docs, json={"expected_version": 1, "body_md": "A newer document."}).raise_for_status()
                lookup = f"{CHATS}/for-document/{doc}/versions/"
                other_projection = client.get(lookup + "1", headers=viewer)
                other_projection.raise_for_status()
                assert other_projection.json() == {"document_id": doc, "version": 1, "conversation": None}
                assert client.get(lookup + "99").status_code == 404
                assert client.get(route, headers=viewer).status_code == 404
                native("document", bodies=["Lever on path", "Pull the lever", "Open within a second"])
                assert [(d["path"].removeprefix(route), d["payload"]["revision"], d["status"]) for d in decisions] == [
                    ("/design/direction/confirm", 1, 409),
                    ("/design/direction/return", 2, 200),
                    ("/design/direction/confirm", 3, 200),
                    ("/design/plan/confirm", 4, 200),
                ]
                assert client.get(lookup + "1").json()["current"] == chat["current"]
                assert client.get(lookup + "2").json()["conversation"] is None
                assert client.get(docs + "/versions/2/signoff").json()["signoff"] is None
                assert not store.list_issues(actor)
        finally:
            server.should_exit = True
            thread.join(10)
            store.db.close()
    return dict(
        state="passed",
        editor_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
        native=controls,
        native_decisions=decisions,
        signed_document=signoff,
        stage_revisions=chat["revisions"],
        separate_approvals=chat["current"],
        created_issues=0,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="d13-stages-") as directory, patch.dict(os.environ, GONGGONG_WORKSPACE=""):
        result = exercise(Path(directory), args.godot.resolve())
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
