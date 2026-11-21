"""Exercise the compiled D03 controls against Tianxuan with a deterministic model transport."""

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
from starlette.responses import Response

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "customizations/components/tianxuan/server"))

# isort: split
from api import create_app  # noqa: E402
from gateway import ModelGateway  # noqa: E402
from native_store import NativeStore  # noqa: E402
from tianxuan_core import Tianxuan  # noqa: E402

CHATS = "/api/v1/workspace/conversations"
PROJECT = "d03/studio"


def exercise(root, binary, windowed):
    editor = copy_editor(binary, root / "engine")
    project = root / "project"
    project.mkdir()
    (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="D03"\n')
    shutil.copyfile(Path(__file__).with_name("workbench_consultation_design.gd"), project / "probe.gd")
    store = Tianxuan(str(root / "domain.sqlite"))
    user = store.register("Studio", "author@example.invalid", secrets.token_urlsafe(24))
    actor = user["user_id"]
    auth = {"Authorization": "Bearer " + store.issue_session(actor)}
    key = str(uuid4())
    route = CHATS + "/" + key
    direction = route + "/design/direction"
    fixture = {
        "id": key,
        "question": "How should the bridge open?",
        "answer": "Use one lever. Decide on the lever color later. Check that one pull opens the bridge.",
        "saved": "Original design paragraph.",
        "handwritten": "Handwritten note: the lever can be reached from the path.",
        "edited": "User edit: show the open bridge from the path.",
        "concurrent": "A different editor saved this direction.",
    }
    proposal = (
        "Goal: open the bridge.\n\nPlan: one lever.\n\nDecision: lever color.\n\nAcceptance: one pull opens the bridge."
    )
    entered = fixture["saved"] + "\n\n" + fixture["handwritten"]
    fixture["generated"] = entered + "\n\n" + proposal
    prompts = []

    def model(request):
        messages = json.loads(request.content)["messages"]
        prompts.append(messages)
        answer = fixture["answer"] if len(prompts) == 1 else fixture["handwritten"] + "\n\n" + proposal
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": answer}}],
                "model": "d03-test",
                "usage": {"prompt_tokens": 4, "completion_tokens": 2},
            },
        )

    gateway = ModelGateway(":memory:", transport=httpx.MockTransport(model))
    modes = dict(
        TIANXUAN_AUTH_MODE="accounts",
        TIANXUAN_PUBLIC_ORIGIN="https://fixture.invalid",
        TIANXUAN_TENANT_ID=user["tenant_id"],
        TIANXUAN_CHAT_BASE_URL="https://d03-model.invalid/v1",
        TIANXUAN_CHAT_MODEL="d03-test",
        TIANXUAN_CHAT_MODEL_KEY="fixture",
    )
    calls, controls, diagnostics = [], [], []
    with patch.dict(os.environ, modes), socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        origin = "http://127.0.0.1:" + str(sock.getsockname()[1])
        app = create_app(store, native_store=NativeStore(root / "native.sqlite"), native_only=True, gateway=gateway)
        faults = {"native": False, "lose_readback": False}

        @app.middleware("http")
        async def observe(request, call_next):
            path = request.url.path
            if faults["lose_readback"] and request.method == "GET" and path == route:
                faults["lose_readback"] = False
                calls.append(["GET", path, None, 503])
                return Response(status_code=503)
            response = await call_next(request)
            status = response.status_code
            if faults["native"] and path == direction + "/suggest" and status == 200:
                async with httpx.AsyncClient(base_url=origin, trust_env=False, headers=auth) as writer:
                    first = (await writer.get(route)).json()
                    assert len(first["revisions"]) == 1
                    write = await writer.post(
                        direction + "/drafts",
                        json={
                            "expected_version": first["version"],
                            "body": fixture["concurrent"],
                        },
                        headers={"X-Test-Writer": "concurrent"},
                    )
                    write.raise_for_status()
            if (
                faults["native"]
                and path == direction + "/drafts"
                and status == 200
                and not request.headers.get("X-Test-Writer")
            ):
                faults["lose_readback"] = True
                response = Response(status_code=503)
            calls.append([request.method, path, status, response.status_code])
            return response

        service = uvicorn.Server(uvicorn.Config(app, log_level="error", access_log=False))
        worker = threading.Thread(target=service.run, kwargs={"sockets": [sock]}, daemon=True)
        worker.start()
        try:
            deadline = time.monotonic() + 15
            while not service.started:
                assert worker.is_alive() and time.monotonic() < deadline
                time.sleep(0.02)
            with httpx.Client(base_url=origin, headers=auth, trust_env=False) as client:

                def post(path, **payload):
                    response = client.post(path, json=payload)
                    response.raise_for_status()
                    return response.json()

                def native():
                    env = sanitized_environment(root) | {
                        "TIANXUAN_API": origin,
                        "TIANXUAN_TOKEN": auth["Authorization"].removeprefix("Bearer "),
                        "TIANXUAN_PROJECT": PROJECT,
                        "D03_FIXTURE": json.dumps(fixture),
                    }
                    display = (
                        ["--single-window", "--resolution", "1366x900", "--rendering-method", "gl_compatibility"]
                        if windowed
                        else ["--headless", "--single-window", "--resolution", "1366x900"]
                    )
                    run = subprocess.run(
                        [str(editor), *display, "--editor", "--path", str(project), "--script", "res://probe.gd"],
                        cwd=root,
                        env=env,
                        capture_output=True,
                        text=True,
                        timeout=90,
                    )
                    assert run.returncode == 0 and "SCRIPT ERROR" not in run.stderr, run.stdout + run.stderr
                    controls.append(
                        json.loads(
                            next(line[11:] for line in run.stdout.splitlines() if line.startswith("D03_NATIVE="))
                        )
                    )
                    diagnostics.append(run.stderr)

                chat = post(CHATS, id=key)
                chat = post(
                    route + "/turns", id=str(uuid4()), expected_version=chat["version"], content=fixture["question"]
                )
                assert chat["turns"][0]["answer"] == fixture["answer"]
                post(direction + "/drafts", expected_version=chat["version"], body=fixture["saved"])
                store.save_module_location(actor, PROJECT, "default", None, key, "module/overview")
                faults["native"] = True
                native()
                faults["native"] = False
                chat = client.get(route).json()
                saved = fixture["generated"] + "\n\n" + fixture["edited"]
                assert [rev["body"] for rev in chat["revisions"]] == [fixture["saved"], fixture["concurrent"], saved]
                assert saved.count(fixture["handwritten"]) == 1
                source = json.loads(prompts[1][-1]["content"])
                assert source["existing_draft"] == entered and source["conversation"] == [
                    {"user": fixture["question"], "reply": fixture["answer"]},
                ]
                assert len(prompts) == 2
                chat = post(
                    direction + "/confirm", expected_version=chat["version"], revision=chat["current"]["direction"]
                )
                for stage in ("plan", "design"):
                    prefix = route + "/design/" + stage
                    chat = post(
                        prefix + "/drafts",
                        expected_version=chat["version"],
                        body="Operate the lever.",
                        title="Bridge lever",
                        acceptance="One pull opens the bridge.",
                    )
                    chat = post(prefix + "/confirm", expected_version=chat["version"], revision=chat["current"][stage])
                chat = post(route + "/requirement", expected_version=chat["version"], lang="en")
                fixture.update(document=chat["requirement_id"], version=chat["requirement_version"])
                native()
                return {
                    "state": "passed",
                    "display": "windowed" if windowed else "headless",
                    "editor_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
                    "editor_version": subprocess.check_output([str(editor), "--version"], text=True).strip(),
                    "selector_sha256": hashlib.sha256(
                        (ROOT / "editor/docks/workbench/module_selector.gd").read_bytes()
                    ).hexdigest(),
                    "controls": controls,
                    "model_source": source,
                    "http": calls,
                    "editor_stderr": diagnostics,
                }
        finally:
            service.should_exit = True
            worker.join(10)
            gateway.close()
            store.db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--windowed", action="store_true", help="Exercise the native desktop window")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="d03-native-") as temporary, patch.dict(os.environ, GONGGONG_WORKSPACE=""):
        result = exercise(Path(temporary), args.godot.resolve(), args.windowed)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
