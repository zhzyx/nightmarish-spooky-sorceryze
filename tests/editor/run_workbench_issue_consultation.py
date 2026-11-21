"""Open A/B from native issue details and inspect their persisted, read-revision-bound consultations."""

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
from api import create_app  # noqa: E402
from gateway import ModelGateway  # noqa: E402
from native_store import NativeStore  # noqa: E402
from tianxuan_core import Tianxuan  # noqa: E402
from workspace_conversations import Conversations, Turn  # noqa: E402

CHATS = "/api/v1/workspace/conversations"
PROJECT = "studio/u11"


def exercise(binary, root, separate_modules=False):
    with patch.dict(os.environ, {"GONGGONG_WORKSPACE": ""}):
        engine = copy_editor(binary, root / "engine")
    project = root / "project"
    project.mkdir()
    (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="U11"\n')
    shutil.copyfile(Path(__file__).with_name("workbench_issue_consultation.gd"), project / "probe.gd")
    database = str(root / "domain.db")
    store = Tianxuan(database)
    account = store.register("U11", "owner@example.invalid", secrets.token_urlsafe(32))
    owner = account["user_id"]
    token = store.issue_session(owner)
    module = store.create_business_module(owner, PROJECT, "共享模块", call_id="module-A")
    second = (
        store.create_business_module(owner, PROJECT, "共享模块", call_id="module-B") if separate_modules else module
    )
    issues = [store.create_issue(owner, "同名工单", project=PROJECT, module_id=m["id"]) for m in (module, second)]
    a, b = issues
    revisions = [store.issue_snapshot(owner, issue["id"])["revision"] for issue in issues]
    chats = Conversations(store)
    old = chats.create(owner, str(uuid4()))["id"]
    chats.turn(owner, old, Turn(id=uuid4(), expected_version=0, content="B previous"), None)
    store.save_module_location(owner, PROJECT, b["module_id"], b["id"], old, "issue/details")
    model_messages = []
    calls = []

    def model_reply(request):
        model_messages.append(json.loads(request.content)["messages"])
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "fixture reply"}}],
                "model": "u11",
                "usage": {"prompt_tokens": 4, "completion_tokens": 1},
            },
        )

    gateway = ModelGateway(":memory:", transport=httpx.MockTransport(model_reply))
    settings = {
        "TIANXUAN_AUTH_MODE": "accounts",
        "TIANXUAN_PUBLIC_ORIGIN": "https://fixture.invalid",
        "TIANXUAN_TENANT_ID": account["tenant_id"],
        "TIANXUAN_CHAT_MODEL": "u11",
        "TIANXUAN_CHAT_MODEL_KEY": "isolated-fixture",
        "TIANXUAN_CHAT_BASE_URL": "https://fixture.invalid/v1",
    }
    with patch.dict(os.environ, settings), socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        app = create_app(store, gateway=gateway, native_store=NativeStore(root / "native.db"), native_only=True)

        @app.middleware("http")
        async def observe(request, call_next):
            response = await call_next(request)
            path = request.url.path
            calls.append([request.method, path, response.status_code])
            if path == CHATS + "/for-issue/" + a["id"] and len(revisions) == 2 and response.status_code == 200:
                # The issue changes after the editor's detail read and before its first message.
                store.set_issue_parent(owner, a["id"], PROJECT, b["number"], None)
                revisions.append(store.issue_snapshot(owner, a["id"])["revision"])
            return response

        server = uvicorn.Server(uvicorn.Config(app, log_level="error", access_log=False))
        worker = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        worker.start()
        try:
            deadline = time.monotonic() + 15
            while not server.started:
                assert worker.is_alive() and time.monotonic() < deadline, "loopback service unavailable"
                time.sleep(0.05)
            env = {k: v for k, v in sanitized_environment(root).items() if not k.startswith("TIANXUAN_")}
            env.update(
                TIANXUAN_API=f"http://127.0.0.1:{sock.getsockname()[1]}",
                TIANXUAN_TOKEN=token,
                TIANXUAN_PROJECT=PROJECT,
                U11_FIXTURES=json.dumps({
                    "numbers": [i["number"] for i in issues],
                    "module_id": b["module_id"],
                    "prior_chat": old,
                }),
            )
            child = subprocess.run(
                [str(engine), "--headless", "--editor", "--path", str(project), "--script", "res://probe.gd"],
                cwd=root,
                env=env,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=110,
            )
        finally:
            server.should_exit = True
            worker.join(15)
            gateway.close()
            store.db.close()
    output = child.stdout + child.stderr
    assert token not in output, "credential in editor output"
    assert child.returncode == 0 and "SCRIPT ERROR" not in output, output[-6000:]
    markers = [s[len("U11_REPORT=") :] for s in child.stdout.splitlines() if s.startswith("U11_REPORT=")]
    assert len(markers) == 1, output[-3000:]
    trace = json.loads(markers[0])
    assert [p["issue"] for p in trace] == [a["id"], b["id"]] * 2
    assert [p["revision"] for p in trace] == [*revisions, revisions[1]]
    assert revisions[2] != revisions[0]
    assert [p["draft"] for p in trace] == ["", "B unsent", "A unsent", "B next"]
    assert trace[0]["chat"] == trace[2]["chat"] != old == trace[1]["chat"] == trace[3]["chat"]
    assert not any("/execution" in path for _, path, _ in calls)
    mutations = [path for method, path, _ in calls if method != "GET"]
    assert all(path.startswith(CHATS + "/for-issue/") or path.endswith(("/turns", "/location")) for path in mutations)
    stored = []
    reopened = Tianxuan(database)
    try:
        independent = Conversations(reopened)
        for issue, sample, expected in [(a, trace[0], ["A first", "A next"]), (b, trace[1], ["B first"])]:
            with independent.transaction(write=False) as db:
                chat = independent.get(db, independent.owner(owner), sample["chat"])
            assert (
                chat["consultation_issue_id"] == issue["id"]
                and chat["id"] == sample["chat"]
                and chat["execution"] is None
                and chat["past_executions"] == []
            )
            turns = chat["turns"] if issue is a else chat["turns"][1:]
            assert [t["content"].splitlines()[0] for t in turns] == expected
            assert all(t["state"] == "answered" for t in turns)
            stored.append({
                "issue": issue["id"],
                "chat": chat["id"],
                "execution": chat["execution"],
                "past_executions": chat["past_executions"],
                "turns": [t["context_snapshot"] for t in turns],
            })
    finally:
        reopened.db.close()
    received = [
        json.loads(next(m["content"] for m in reversed(history) if m["role"] == "user")) for history in model_messages
    ]
    assert len(received) == 3
    for index, issue in enumerate([a, b, a]):
        expected = {
            "project": PROJECT,
            "module_id": issue["module_id"],
            "issue_id": issue["id"],
            "references": [{"kind": "issue", "object_id": issue["id"], "revision": revisions[index]}],
        }
        assert received[index]["context_snapshot"] == expected and issue["title"] in received[index]["content"]
        assert stored[index % 2]["turns"][index // 2] == expected
    with binary.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    return {
        "engine_sha256": digest,
        "headless_exit": child.returncode,
        "native_previews": trace,
        "stored_rooms": stored,
        "model_fixture_received": received,
        "editor_writes": mutations,
        "execution_requests": 0,
        "different_revision_before_first_send": True,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    report = {}
    for scenario in ["same_module", "separate_modules"]:
        with tempfile.TemporaryDirectory(prefix="workbench-u11-") as temporary:
            report[scenario] = exercise(
                args.godot.resolve(strict=True), Path(temporary), scenario == "separate_modules"
            )
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Passed U11 native detail-to-consultation checks")
