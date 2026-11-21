"""Reopen one isolated editor project and recover real module drafts, references and consultation history."""

import argparse
import hashlib
import json
import os
import secrets
import shutil
import socket
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch

from run_workbench_business_modules import (
    BASE,
    CHATS,
    NativeStore,
    Tianxuan,
    copy_editor,
    create_app,
    httpx,
    sanitized_environment,
    success,
    uvicorn,
)

# The shared fixture adds Tianxuan's installed service modules to sys.path.
# isort: split
from gateway import ModelGateway  # noqa: E402

HERE = Path(__file__).resolve().parent
PROJECT = "d12/studio"


def exercise(root, editor):
    engine = copy_editor(editor, root / "editor")
    project = root / "project"
    project.mkdir()
    (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="D12"\n')
    for src, dest in [("workbench_business_modules.gd", "module_probe.gd"), ("workbench_module_drafts.gd", "probe.gd")]:
        shutil.copyfile(HERE / src, project / dest)
    store = Tianxuan(str(root / "domain.db"))
    password = secrets.token_urlsafe(24)
    user = store.register("Studio", "owner@example.invalid", password)
    actor = user["user_id"]
    other = store.add_member(actor, "peer@example.invalid", password)["user_id"]
    keys = [store.issue_access_key(actor, who, "D12 temporary fixture")["key"] for who in (actor, other)]
    modules = []
    for i in range(2):
        (project / f"module{i}.tres").write_text(
            f'[gd_resource type="Gradient" format=3]\n\n[resource]\noffsets = PackedFloat32Array(0, {0.25 + i * 0.5})\n'
        )
        module = store.create_business_module(actor, PROJECT, "Same module name", call_id=str(i))["id"]
        issue = store.create_issue(actor, "Same issue title", project=PROJECT, module_id=module)["id"]
        for who in (actor, other):
            store.save_module_location(who, PROJECT, module, issue, None, "issue/details")
        modules.append({"module": module, "issue": issue})

    model_calls = []

    def answer(request):
        model_calls.append(json.loads(request.content)["messages"])
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "D12 fixture answer"}}],
                "model": "fixture",
                "usage": {"prompt_tokens": 4, "completion_tokens": 3},
            },
        )

    gateway = ModelGateway(":memory:", transport=httpx.MockTransport(answer))
    env = {
        "TIANXUAN_AUTH_MODE": "accounts",
        "TIANXUAN_PUBLIC_ORIGIN": "https://fixture.invalid",
        "TIANXUAN_TENANT_ID": user["tenant_id"],
        "TIANXUAN_CHAT_MODEL": "fixture",
        "TIANXUAN_CHAT_BASE_URL": "https://fixture.invalid/v1",
        "TIANXUAN_CHAT_MODEL_KEY": secrets.token_urlsafe(24),
    }
    with patch.dict(os.environ, env), socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        api = "http://127.0.0.1:" + str(sock.getsockname()[1])
        native = NativeStore(root / "native.db")
        app = create_app(store, gateway=gateway, native_store=native, native_only=True)
        calls = []

        @app.middleware("http")
        async def observe(request, call_next):
            result = await call_next(request)
            calls.append([request.method, request.url.path, result.status_code])
            return result

        server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        try:
            end = time.monotonic() + 15
            while not server.started:
                assert time.monotonic() < end and thread.is_alive(), "Loopback service did not start"
                time.sleep(0.02)
            model = "draft-assets"
            path = "B-model.glb"
            revision = native.submit(
                user["tenant_id"],
                actor,
                "draft-asset",
                [{"module": model, "base": None, "reads": None, "edits": {path: b"fixture"}}],
            )["revisions"][model]
            with httpx.Client(base_url=api, headers={"Authorization": "Bearer " + keys[0]}, trust_env=False) as client:
                response = client.post(
                    BASE + "/native/business-modules/" + modules[1]["module"] + "/assets",
                    params={"project": PROJECT},
                    json={"source_module": model, "revision": revision, "path": path},
                )
                response.raise_for_status()
                asset = response.json()
            controls = []
            scoped_http = {}
            diagnostics = {}
            for phase in ("write", "reopen", "cleared", "other-account", "other-project"):
                child = {
                    k: v for k, v in sanitized_environment(root).items() if not k.startswith(("TIANXUAN_", "D12_"))
                }
                child.update(
                    TIANXUAN_API=api,
                    TIANXUAN_PROJECT="d12/other" if phase == "other-project" else PROJECT,
                    TIANXUAN_TOKEN=keys[phase == "other-account"],
                    D12_PHASE=phase,
                    D12_MODULES=json.dumps(modules),
                    D12_ASSET=json.dumps(asset),
                )
                start = len(calls)
                run = subprocess.run(
                    [str(engine), "--headless", "--editor", "--path", str(project), "--script", "res://probe.gd"],
                    env=child,
                    cwd=root,
                    capture_output=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=90,
                )
                output = run.stdout + run.stderr
                assert not any(secret in output for secret in [*keys, password]), (
                    "Credential reached runtime diagnostics"
                )
                assert run.returncode == 0 and "SCRIPT ERROR" not in output, output[-6000:]
                marker = next((line for line in run.stdout.splitlines() if line.startswith("D12_OBSERVED=")), "")
                assert marker, output[-6000:]
                controls.append(json.loads(marker.split("=", 1)[1]))
                diagnostics[phase] = [line for line in output.splitlines() if line.startswith(("WARNING:", "ERROR:"))]
                scoped_http[phase] = calls[start:]
                posted = [
                    path for method, path, status in scoped_http[phase] if method == "POST" and path.startswith(CHATS)
                ]
                if phase == "write":
                    assert len(posted) == 2 and posted[0] == CHATS and posted[1].endswith("/turns")
                else:
                    assert posted == []
            assert len(model_calls) == 1
            with httpx.Client(base_url=api, trust_env=False, headers={"Authorization": "Bearer " + keys[0]}) as client:
                first = modules[0]
                location = success(
                    client.get(BASE + "/business-modules/" + first["module"] + "/location", params={"project": PROJECT})
                )["location"]
                assert location["issue_id"] == first["issue"]
                chat = success(client.get(CHATS + "/" + location["conversation_id"]))
                (turn,) = chat["turns"]
                assert turn["state"] == "answered" and turn["answer"] == "D12 fixture answer"
                (ref,) = turn["context_snapshot"]["references"]
                assert ref["object_id"] == "res://module0.tres"
                assert ref["revision"] == hashlib.sha256((project / "module0.tres").read_bytes()).hexdigest()
                assert all(
                    row["conversation"] == chat["id"]
                    for group in controls
                    for row in group.get("controls", [])
                    if row["turns"] == 1
                )
            scanned = 0
            for folder in (project, root / "editor/editor_data", root / "private-home"):
                for path in folder.rglob("*"):
                    if path.is_file():
                        data = path.read_bytes()
                        assert not any(
                            value.encode() in data for value in [*keys, password, env["TIANXUAN_CHAT_MODEL_KEY"]]
                        )
                        scanned += 1
            return {
                "controls": controls,
                "service_calls": scoped_http,
                "editor_diagnostics": diagnostics,
                "stored_turn": turn,
                "model_fixture_calls": len(model_calls),
                "credential_scan_files": scanned,
            }
        finally:
            server.should_exit = True
            thread.join(10)
            store.db.close()
            gateway.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    os.environ.pop("GONGGONG_WORKSPACE", None)
    with tempfile.TemporaryDirectory(prefix="workbench-d12-") as directory:
        report = exercise(Path(directory), args.godot.resolve(strict=True))
    report.update(
        request_id="gonggong-ai-workbench-plan1-d12",
        issue_number=1748,
        editor_sha256=hashlib.sha256(args.godot.read_bytes()).hexdigest(),
        state="passed",
    )
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
