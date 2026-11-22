"""Run the K01 editor-to-module round trip with the B05 shared model and a local Tianxuan."""

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

from run_workbench_business_modules import (
    BASE,
    CHATS,
    ROOT,
    copy_editor,
    create_app,
    httpx,
    sanitized_environment,
    uvicorn,
)

B05 = ROOT / "samples/gonggong-workbench/fixtures/b05"
sys.path.insert(0, str(B05))

# isort: split
from gateway import ModelGateway  # noqa: E402
from sample import sample  # noqa: E402

PROJECT = "k01/character"
ANSWER = "K01 movement consultation received"


def exercise(root, binary, entry):
    with patch.dict(os.environ, {"GONGGONG_WORKSPACE": ""}):
        engine = copy_editor(binary, root / "editor")
    spec = json.loads((B05 / "sample.json").read_text("utf-8"))
    model = spec["asset"]
    project = root / "project"
    project.mkdir()
    (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="K01"\n', encoding="utf-8")
    model_file = project / model["path"]
    model_file.parent.mkdir(parents=True)
    shutil.copyfile(ROOT / model["repo_source"], model_file)
    (project / "character.gd").write_text(
        f'extends Node3D\n## {model["path"]}\nconst MODEL = "res://{model["path"]}"\n', encoding="utf-8"
    )
    for origin, target in [("ai_chat_tab_order.gd", "editor_probe.gd"), ("workbench_context_milestone.gd", "probe.gd")]:
        shutil.copyfile(Path(__file__).with_name(origin), project / target)
    model_messages = []

    def answer(request):
        model_messages.append(json.loads(request.content)["messages"])
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": ANSWER}}],
                "model": "fixture",
                "usage": {"prompt_tokens": 4, "completion_tokens": 3},
            },
        )

    model_gateway = ModelGateway(":memory:", transport=httpx.MockTransport(answer))
    with sample() as (domain, native, state), socket.socket() as sock:
        owner = state["users"]["movement"]
        asset = dict(source_module=model["module"], revision=state["asset_revision"], path=model["path"])
        token = domain.issue_session(owner)
        config = dict(
            TIANXUAN_AUTH_MODE="accounts",
            TIANXUAN_PUBLIC_ORIGIN="https://fixture.invalid",
            TIANXUAN_TENANT_ID=state["tenant"],
            TIANXUAN_CHAT_BASE_URL="https://fixture.invalid/v1",
            TIANXUAN_CHAT_MODEL="fixture",
            TIANXUAN_CHAT_MODEL_KEY=secrets.token_urlsafe(),
        )
        with patch.dict(os.environ, config):
            app = create_app(domain, native_store=native, gateway=model_gateway, native_only=True)
            writes = []

            @app.middleware("http")
            async def observe(request, call_next):
                response = await call_next(request)
                if request.method == "POST" and request.url.path.startswith(CHATS):
                    writes.append([request.url.path, response.status_code])
                return response

            sock.bind(("127.0.0.1", 0))
            base = f"http://127.0.0.1:{sock.getsockname()[1]}"
            server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
            thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
            thread.start()
            try:
                deadline = time.monotonic() + 15
                while not server.started:
                    assert thread.is_alive() and time.monotonic() < deadline, "Tianxuan loopback startup failed"
                    time.sleep(0.02)
                with httpx.Client(base_url=base, headers={"Authorization": "Bearer " + token}, trust_env=False) as api:
                    modules = []
                    for item in spec["modules"]:
                        module = domain.create_business_module(owner, PROJECT, item["title"], call_id=item["id"])
                        modules.append(module["id"])
                        api.post(
                            f"{BASE}/native/business-modules/{module['id']}/assets",
                            params={"project": PROJECT},
                            json=asset,
                        ).raise_for_status()
                    context = (
                        api
                        .get(
                            f"{BASE}/native/asset-context/{asset['source_module']}/{asset['revision']}/{asset['path']}",
                            params={"project": PROJECT},
                        )
                        .raise_for_status()
                        .json()
                    )
                    assert {item["id"] for item in context["modules"]} == set(modules)
                    assert context["sha256"] == hashlib.sha256(model_file.read_bytes()).hexdigest() == model["sha256"]
                    fixture = {"modules": modules, "asset": asset, "entry": entry, "answer": ANSWER}
                    env = {k: v for k, v in sanitized_environment(root).items() if not k.startswith("TIANXUAN_")}
                    env.update(
                        TIANXUAN_API=base,
                        TIANXUAN_PROJECT=PROJECT,
                        TIANXUAN_TOKEN=token,
                        K01_FIXTURE=json.dumps(fixture),
                    )
                    run = subprocess.run(
                        [str(engine), "--headless", "--editor", "--path", str(project), "--script", "res://probe.gd"],
                        cwd=root,
                        env=env,
                        capture_output=True,
                        encoding="utf-8",
                        errors="replace",
                        timeout=120,
                    )
                    output = run.stdout + run.stderr
                    assert token not in output and config["TIANXUAN_CHAT_MODEL_KEY"] not in output, (
                        "Credential in output"
                    )
                    assert run.returncode == 0 and "SCRIPT ERROR" not in output, output[-6000:]
                    (result,) = [
                        json.loads(s.removeprefix("K01_RESULT="))
                        for s in run.stdout.splitlines()
                        if s.startswith("K01_RESULT=")
                    ]
                    route = f"{CHATS}/{result['conversation']}"
                    chat = api.get(route).raise_for_status().json()
                    (turn,) = chat["turns"]
                    assert turn["context_snapshot"] == {
                        "project": PROJECT,
                        "module_id": modules[0],
                        "issue_id": None,
                        "references": [
                            {
                                "kind": "editor",
                                "object_id": "duobao:" + context["asset_id"],
                                "revision": asset["revision"],
                            }
                        ],
                    }
                    assert (
                        turn["content"] == result["sent"] and turn["answer"] == ANSWER and turn["state"] == "answered"
                    )
                    assert len(model_messages) == 1
                    model_request = json.loads(model_messages[0][-1]["content"])
                    assert model_request == {"content": result["sent"], "context_snapshot": turn["context_snapshot"]}
                    assert [path for path, _ in writes] == [CHATS, route + "/turns"] and all(
                        200 <= status < 300 for _, status in writes
                    )
                    editor_path = (
                        engine.with_name(engine.name.removesuffix(".console.exe") + ".exe")
                        if engine.name.endswith(".console.exe")
                        else engine
                    )
                    with editor_path.open("rb") as stream:
                        digest = hashlib.file_digest(stream, "sha256").hexdigest()
                    return {
                        "state": "passed",
                        "request_id": "gonggong-ai-workbench-plan1-k01",
                        "issue_number": 1717,
                        "editor_sha256": digest,
                        "sample": {"model_sha256": model["sha256"], **fixture},
                        "editor": result,
                        "received_turn": turn,
                        "conversation_writes": writes,
                        "model_call_count": len(model_messages),
                        "received_by_model": model_request,
                    }
            finally:
                server.should_exit = True
                thread.join(10)
                model_gateway.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--entry", choices=("shortcut", "palette"), default="shortcut")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="workbench-k01-") as directory:
        report = exercise(Path(directory), args.godot.resolve(strict=True), args.entry)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
