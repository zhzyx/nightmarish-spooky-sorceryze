"""Open two I02 detail cards in the native editor, then audit their C05 turns by actor and revision."""

import argparse
import hashlib
import json
import os
import secrets
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import closing
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
from gateway import ModelGateway  # noqa: E402
from native_store import NativeStore  # noqa: E402
from tianxuan_core import Tianxuan  # noqa: E402

CHATS = "/api/v1/workspace/conversations"

PROJECT = "u11/studio"


def exercise(root, binary, verify_routes=None, *, prepare_issues=None, http_trace=None):
    engine = copy_editor(binary, root / "editor")
    project = root / "project"
    project.mkdir()
    (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="U11"\n')
    shutil.copyfile(Path(__file__).with_name("workbench_issue_consultation.gd"), project / "probe.gd")
    database = root / "domain.db"
    store = Tianxuan(str(database))
    password = secrets.token_urlsafe()
    owner = store.register("Studio", "owner@example.invalid", password)
    actor = owner["user_id"]
    other = store.add_member(actor, "peer@example.invalid", password)["user_id"]
    issues = (
        prepare_issues(store, actor, PROJECT)
        if prepare_issues
        else [
            store.create_issue(actor, "核对入口", body_md=body, project=PROJECT)
            for body in ("桥梁方案 <tianxuan-doc://example/1/1>", "隧道方案")
        ]
    )
    token = store.issue_session(actor)
    other_token = store.issue_session(other)
    model_inputs = []

    def model(request):
        messages = json.loads(request.content)["messages"]
        model_inputs.append(messages)
        return httpx.Response(
            200,
            json={
                "model": "fixture",
                "usage": {"prompt_tokens": 3, "completion_tokens": 2},
                "choices": [{"message": {"content": f"建议复核第 {len(model_inputs)} 项的验收记录。"}}],
            },
        )

    gateway = ModelGateway(":memory:", transport=httpx.MockTransport(model))
    modes = {
        "TIANXUAN_AUTH_MODE": "accounts",
        "TIANXUAN_PUBLIC_ORIGIN": "https://studio.invalid",
        "TIANXUAN_TENANT_ID": owner["tenant_id"],
        "TIANXUAN_CHAT_BASE_URL": "https://model.invalid/v1",
        "TIANXUAN_CHAT_MODEL": "fixture",
        "TIANXUAN_CHAT_MODEL_KEY": "fixture",
    }
    calls = [] if http_trace is None else http_trace
    with patch.dict(os.environ, modes), socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        origin = f"http://127.0.0.1:{sock.getsockname()[1]}"
        app = create_app(store, gateway=gateway, native_store=NativeStore(root / "native.db"), native_only=True)

        @app.middleware("http")
        async def observe(request, call_next):
            reply = await call_next(request)
            calls.append((request.method, request.url.path, reply.status_code))
            return reply

        service = uvicorn.Server(uvicorn.Config(app, log_level="error", access_log=False))
        thread = threading.Thread(target=service.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 15
            while not service.started:
                if not thread.is_alive() or time.monotonic() > deadline:
                    raise RuntimeError("Tianxuan startup failed")
                time.sleep(0.05)
            env = sanitized_environment(root) | dict(
                TIANXUAN_API=origin,
                TIANXUAN_TOKEN=token,
                TIANXUAN_PROJECT=PROJECT,
                U11_NUMBERS=json.dumps([i["number"] for i in issues]),
            )
            run = subprocess.run(
                [str(engine), "--headless", "--editor", "--path", str(project), "--script", "res://probe.gd"],
                env=env,
                cwd=root,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=90,
            )
            output = run.stdout + run.stderr
            if any(secret in output for secret in (token, password, other_token)):
                raise AssertionError("Credential appeared in diagnostics")
            markers = [
                line.removeprefix("U11_NATIVE=") for line in run.stdout.splitlines() if line.startswith("U11_NATIVE=")
            ]
            assert not run.returncode and len(markers) == 1 and "SCRIPT ERROR" not in output, output[-4500:]
            native = json.loads(markers[0])
            assert native["identity"]["id"] == actor and native["identity"]["project"] == PROJECT
            native_calls = calls.copy()
            assert len(model_inputs) == 2
            assert not any(method != "GET" and not path.startswith(CHATS + "/") for method, path, _ in native_calls)
            assert not any("/execution" in path for _, path, _ in native_calls)
            route_results = None
            if verify_routes:
                try:
                    route_results = verify_routes(engine, project, env, store, actor, issues, native)
                except AssertionError as exc:
                    raise AssertionError(f"{exc}\nHTTP route diagnostics: {calls[len(native_calls) :]}") from exc
                route_results["http"] = sorted(set(calls[len(native_calls) :]))
            records = []
            with httpx.Client(base_url=origin, headers={"Authorization": "Bearer " + token}, trust_env=False) as client:
                for issue, record, prompt in zip(issues, native["records"], model_inputs, strict=True):
                    path = CHATS + "/" + record["chat"]
                    conversation = client.get(path).raise_for_status().json()
                    (turn,) = conversation["turns"]
                    expected = {
                        "project": PROJECT,
                        "module_id": issue["module_id"],
                        "issue_id": issue["id"],
                        "references": [{"kind": "issue", "object_id": issue["id"], "revision": record["revision"]}],
                    }
                    assert turn["id"] == record["turn"] and turn["context_snapshot"] == expected
                    assert turn["state"] == "answered" and issue["body_md"] in turn["content"]
                    assert record["revision"] == store.issue_snapshot(actor, issue["id"])["revision"]
                    assert [json.loads(m["content"]) for m in prompt if m["role"] == "user"] == [
                        {"content": turn["content"], "context_snapshot": expected}
                    ]
                    assert conversation["execution"] is None and conversation["past_executions"] == []
                    assert client.get(path, headers={"Authorization": "Bearer " + other_token}).status_code == 404
                    records.append({"conversation": conversation["id"], "turn": turn})
                first = records[0]
                store.set_issue_parent(actor, issues[0]["id"], PROJECT, issues[1]["number"], None)
                changed = store.issue_snapshot(actor, issues[0]["id"])["revision"]
                snapshot = first["turn"]["context_snapshot"]
                assert changed != snapshot["references"][0]["revision"]
                path = CHATS + "/" + first["conversation"]
                reread = client.get(path).raise_for_status().json()
                assert reread["turns"] == [first["turn"]]
                stale = client.post(
                    path + "/turns",
                    json={
                        "id": str(uuid4()),
                        "content": "过期引用",
                        "expected_version": reread["version"],
                        "context_snapshot": snapshot,
                    },
                )
                assert stale.status_code == 409 and client.get(path).json()["turns"] == reread["turns"]
        finally:
            service.should_exit = True
            thread.join(10)
            store.db.close()
    with closing(sqlite3.connect(database)) as audit:
        rows = audit.execute("SELECT tenant, actor, state FROM workspace_conversations").fetchall()
        assert len(rows) == 2
        assert all(tenant == owner["tenant_id"] and user == actor for tenant, user, _ in rows)
        assert all(
            json.loads(state)["execution"] is None and not json.loads(state)["past_executions"] for _, _, state in rows
        )
    return {
        "editor_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        **({"routes": route_results} if verify_routes else {}),
        "native": native,
        "http": native_calls,
        "turns": records,
        "changed_revision": changed,
        "stale_status": stale.status_code,
        "stored_executions": 0,
        "other_account_chat_read": 404,
        "model_transport": "isolated fixture",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    with patch.dict(os.environ, {"GONGGONG_WORKSPACE": ""}), tempfile.TemporaryDirectory(prefix="u11-") as directory:
        result = exercise(Path(directory), args.godot.resolve(strict=True))
    args.report.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("Passed U11 native issue consultation checks")
