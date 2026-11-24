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
from run_unified_settings_native import sanitized_environment

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


def exercise(editor, root, references=False):
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
                if references:
                    shutil.copyfile(
                        Path(__file__).with_name("workbench_business_references.gd"), project / "reference_probe.gd"
                    )
                    (project / "retained.tscn").write_text(
                        '[gd_scene format=3]\n[node name="RetainedManualNode" type="Node3D"]\n', encoding="utf-8"
                    )
                    for folder in ("alpha", "beta"):
                        (project / folder).mkdir()
                        (project / folder / "same.gd").write_text(
                            f'extends Node\nconst MARKER = "{folder} u15-business-fixture {token}"\n',
                            encoding="utf-8",
                            newline="\n",
                        )
                env = sanitized_environment(root) | dict(
                    TIANXUAN_API=base,
                    TIANXUAN_TOKEN=token,
                    TIANXUAN_PROJECT=PROJECT,
                    C06_FIXTURE=json.dumps(fixtures),
                    U15_BUSINESS_REFERENCES="1" if references else "0",
                    C06_SECOND_PASSWORD=password,
                    C06_SECOND_ID=second,
                )
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
                if references:
                    evidence = json.loads(
                        next(
                            line.removeprefix("U15_BUSINESS=")
                            for line in run.stdout.splitlines()
                            if line.startswith("U15_BUSINESS=")
                        )
                    )
                    turns = []
                    native_calls = list(calls)
                    assert [
                        path for method, path, _ in native_calls if method == "POST" and path.startswith(CHATS)
                    ] == [CHATS + "/" + f["conversation_id"] + "/turns" for f in fixtures]
                    for fixture in fixtures:
                        chat = success(client.get(CHATS + "/" + fixture["conversation_id"]))
                        assert len(chat["turns"]) == 2
                        turn = chat["turns"][-1]
                        turns.append({"content": turn["content"], "context_snapshot": turn["context_snapshot"]})
                    alpha, beta = evidence["selected"]
                    assert evidence["automatic_latest_only"] and evidence["manual_preserved_until_explicit_removal"]
                    for i, turn in enumerate(turns):
                        selected = beta if i == 0 else alpha
                        assert turn["context_snapshot"] == {
                            "project": PROJECT,
                            "module_id": fixtures[i]["module_id"],
                            "issue_id": fixtures[i]["issue_id"],
                            "references": [selected],
                        }
                        assert "当前编辑现场：本轮主要处理对象" in turn["content"]
                        assert selected["object_id"] in turn["content"]
                        assert selected["revision"] in turn["content"]
                        marker = "beta" if i == 0 else "alpha"
                        assert f'const MARKER = "{marker} [REDACTED] [REDACTED]"' in turn["content"]
                        assert all(
                            value not in turn["content"] for value in (token, "u15-business-fixture", "retained.tscn")
                        )
                    assert turns[0]["content"].startswith("keep beta\n") and "alpha" not in turns[0]["content"]
                    assert turns[1]["content"].startswith("module B uses current alpha\n")
                    return {
                        "state": "passed",
                        "editor_exit": run.returncode,
                        "controls": evidence,
                        "stored_turns": turns,
                        "native_http": native_calls,
                    }
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
                    assert ("POST", BASE + "/auth/editor-session", 200) in native_calls
                for item in fixtures:
                    chat = success(client.get(CHATS + "/" + item["conversation_id"]))
                    assert [t["content"] for t in chat["turns"]] == [item["message"]]
                b = fixtures[1]
                final_position = success(
                    client.get(BASE + "/business-modules/" + b["module_id"] + "/location", params={"project": PROJECT})
                )["location"]
                assert final_position == {
                    "issue_id": None,
                    "conversation_id": None,
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
    parser.add_argument("--references", action="store_true", help="Exercise U15 on two authenticated module issues")
    args = parser.parse_args()
    # The fixture never uses a configured external model.
    for key in ("GONGGONG_WORKSPACE", "TIANXUAN_CHAT_BASE_URL", "TIANXUAN_CHAT_MODEL_KEY", "TIANXUAN_CHAT_MODEL"):
        os.environ.pop(key, None)
    with tempfile.TemporaryDirectory(prefix="c06-native-", ignore_cleanup_errors=os.name == "nt") as directory:
        result = exercise(args.godot.resolve(), Path(directory), args.references)
    result["editor_sha256"] = hashlib.sha256(args.godot.read_bytes()).hexdigest()
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
