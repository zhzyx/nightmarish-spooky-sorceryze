"""Exercise the native module selector against an authenticated Tianxuan loopback app."""

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
from uuid import uuid4

import httpx
import uvicorn
from editor_test_isolation import copy_editor

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "customizations/components/tianxuan/server"))

# isort: split
from api import create_app  # noqa: E402
from native_store import NativeStore  # noqa: E402
from tianxuan_core import Tianxuan  # noqa: E402

PROJECT = "c06/studio"
BASE = "/api/v1"
CHATS = BASE + "/workspace/conversations"


def success(response):
    response.raise_for_status()
    return response.json()


def seed(client, store, actor):
    fixtures = []
    for label in ("A", "B"):
        module = success(
            client.post(
                BASE + "/business-modules", params={"project": PROJECT}, json={"name": "Lighting", "call_id": label}
            )
        )
        issue = store.create_issue(
            actor, "Review", project=PROJECT, module_id=module["id"], body_md=label + " issue body"
        )
        success(client.post(BASE + "/issues/" + issue["id"] + "/comments", json={"body": label + " comment"}))
        chat = success(client.post(CHATS, json={"id": str(uuid4())}))
        chat_path = CHATS + "/" + chat["id"]
        message = label + " prior turn"
        design = label + " saved design"
        chat = success(
            client.post(
                chat_path + "/turns",
                json={
                    "id": str(uuid4()),
                    "expected_version": 0,
                    "content": message,
                },
            )
        )
        success(
            client.post(
                chat_path + "/design/direction/drafts",
                json={
                    "expected_version": chat["version"],
                    "body": design,
                },
            )
        )
        state = {"issue_id": issue["id"], "conversation_id": chat["id"], "position": "issue/comments#" + label}
        success(
            client.put(
                BASE + "/business-modules/" + module["id"] + "/location", params={"project": PROJECT}, json=state
            )
        )
        fixtures.append(
            dict(
                module_id=module["id"],
                message=message,
                design=design,
                comment=label + " comment",
                issue_body=label + " issue body",
                **state,
            )
        )
    return fixtures


def exercise(editor, root):
    private = copy_editor(editor, root / "editor")
    project = root / "project"
    project.mkdir()
    (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="C06"\n')
    shutil.copyfile(Path(__file__).with_name("workbench_business_modules.gd"), project / "probe.gd")
    store = Tianxuan(str(root / "domain.db"))
    account = store.register("Studio", "maker@example.invalid", "local-test-password")
    password = secrets.token_urlsafe(24)
    second = store.add_member(account["user_id"], "reviewer@example.invalid", password)["user_id"]
    store.save_module_location(second, PROJECT, "default", None, None, "second-account-private-position")
    os.environ.update(
        TIANXUAN_AUTH_MODE="accounts",
        TIANXUAN_PUBLIC_ORIGIN="https://studio.example",
        TIANXUAN_TENANT_ID=account["tenant_id"],
    )
    app = create_app(store, native_store=NativeStore(root / "native.db"), native_only=True)
    calls = []

    @app.middleware("http")
    async def record(request, call_next):
        response = await call_next(request)
        calls.append((request.method, request.url.path, response.status_code))
        return response

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        base = "http://127.0.0.1:" + str(sock.getsockname()[1])
        server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 10
            while not server.started:
                assert thread.is_alive() and time.monotonic() < deadline
                time.sleep(0.02)
            with httpx.Client(base_url=base, trust_env=False) as client:
                token = success(
                    client.post(
                        BASE + "/auth/session",
                        json={
                            "email": "maker@example.invalid",
                            "password": "local-test-password",
                        },
                    )
                )["token"]
                client.headers["Authorization"] = "Bearer " + token
                fixtures = seed(client, store, account["user_id"])
                env = os.environ | dict(
                    TIANXUAN_API=base,
                    TIANXUAN_TOKEN=token,
                    TIANXUAN_PROJECT=PROJECT,
                    C06_FIXTURE=json.dumps(fixtures),
                    C06_SECOND_PASSWORD=password,
                    C06_SECOND_ID=second,
                )
                for k in ("APPDATA", "LOCALAPPDATA", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME"):
                    env[k] = str(root / k)
                calls.clear()
                run = subprocess.run(
                    [str(private), "--headless", "--editor", "--path", str(project), "--script", "res://probe.gd"],
                    cwd=root,
                    env=env,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=90,
                )
                assert run.returncode == 0 and "SCRIPT ERROR" not in run.stderr, run.stdout + run.stderr
                trace = json.loads(
                    next(
                        line.removeprefix("C06_NATIVE=")
                        for line in run.stdout.splitlines()
                        if line.startswith("C06_NATIVE=")
                    )
                )
                native_calls = list(calls)
                assert len(trace) == 4
                posts = [path for method, path, _ in native_calls if method == "POST" and path.startswith(CHATS)]
                assert len(posts) == 2 and posts[0] == CHATS
                fresh = success(client.get(BASE + "/business-modules/default/location", params={"project": PROJECT}))[
                    "location"
                ]
                fresh_chat = success(client.get(CHATS + "/" + fresh["conversation_id"]))
                assert posts[1] == CHATS + "/" + fresh_chat["id"] + "/turns"
                assert len(fresh_chat["turns"]) == 1
                only_turn = fresh_chat["turns"][0]
                assert only_turn["content"] == "Explicit consultation"
                assert only_turn["context_snapshot"] == {
                    "project": PROJECT,
                    "module_id": "default",
                    "issue_id": None,
                    "references": [],
                }
                if "C06_REAL_ACCOUNT_SWITCH=passed" in run.stdout:
                    assert ("POST", BASE + "/auth/session", 200) in native_calls
                for item in fixtures:
                    chat = success(client.get(CHATS + "/" + item["conversation_id"]))
                    assert [t["content"] for t in chat["turns"]] == [item["message"]]
                b = fixtures[1]
                final_position = success(
                    client.get(BASE + "/business-modules/" + b["module_id"] + "/location", params={"project": PROJECT})
                )["location"]
                assert final_position == {
                    "issue_id": None,
                    "conversation_id": b["conversation_id"],
                    "position": "module/overview",
                }
                return {
                    "state": "passed",
                    "native_steps": trace,
                    "native_http": native_calls,
                    "real_account_switch": "C06_REAL_ACCOUNT_SWITCH=passed" in run.stdout,
                    "isolated_identity_race": "C06_ISOLATED_IDENTITY_RACE=passed" in run.stdout,
                    "last_position_saved": final_position,
                    "explicit_send_snapshot": only_turn["context_snapshot"],
                }
        finally:
            server.should_exit = True
            thread.join(10)
            store.db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    # The fixture never uses a configured external model.
    for key in ("TIANXUAN_CHAT_BASE_URL", "TIANXUAN_CHAT_MODEL_KEY", "TIANXUAN_CHAT_MODEL"):
        os.environ.pop(key, None)
    with tempfile.TemporaryDirectory(prefix="c06-native-", ignore_cleanup_errors=os.name == "nt") as directory:
        result = exercise(args.godot.resolve(), Path(directory))
    result["editor_sha256"] = hashlib.sha256(args.godot.read_bytes()).hexdigest()
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
