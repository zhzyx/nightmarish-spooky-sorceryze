"""Verify a sent paragraph reference against a real later document revision."""

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
from gateway import ModelGateway  # noqa: E402
from native_store import NativeStore  # noqa: E402
from tianxuan_core import Tianxuan  # noqa: E402


def exercise(root, binary, saved_edit=False):
    with patch.dict(os.environ, {"GONGGONG_WORKSPACE": ""}):
        editor = copy_editor(binary, root / "engine")
    project = root / "project"
    project.mkdir()
    (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="U10"\n')
    shutil.copyfile(Path(__file__).with_name("workbench_document_reference.gd"), project / "probe.gd")
    store = Tianxuan(str(root / "business.sqlite"))
    user = store.register("studio", "reader@example.invalid", secrets.token_urlsafe(24))
    actor = user["user_id"]
    old = "# 设计\n\n原始目标段落\n\n另一段"
    moved = "# 设计\n\n另一段\n\n原始目标段落"
    doc = store.create_doc(actor, "段落引用", old)
    token = store.issue_session(actor)
    modes = {
        "TIANXUAN_AUTH_MODE": "accounts",
        "TIANXUAN_PUBLIC_ORIGIN": "https://fixture.invalid",
        "TIANXUAN_TENANT_ID": user["tenant_id"],
    }
    model_inputs = []

    def receive(request):
        model_inputs.append(json.loads(request.content)["messages"][-1]["content"])
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "received"}}],
                "model": "fixture",
                "usage": {"prompt_tokens": 10, "completion_tokens": 1},
            },
        )

    gateway = None
    if saved_edit:
        modes.update(
            TIANXUAN_CHAT_MODEL="fixture",
            TIANXUAN_CHAT_BASE_URL="https://fixture.invalid/v1",
            TIANXUAN_CHAT_MODEL_KEY="local-only",
        )
        gateway = ModelGateway(":memory:", transport=httpx.MockTransport(receive))
    reads = []
    with patch.dict(os.environ, modes), socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        api = create_app(store, gateway=gateway, native_store=NativeStore(root / "native.db"), native_only=True)

        @api.middleware("http")
        async def observe(request, call_next):
            response = await call_next(request)
            reads.append((request.url.path, response.status_code))
            if (
                not saved_edit
                and request.method == "POST"
                and request.url.path.endswith("/turns")
                and response.status_code == 200
            ):
                store.update_doc(actor, doc["id"], moved, 1)
            return response

        service = uvicorn.Server(uvicorn.Config(api, log_level="error", access_log=False))
        thread = threading.Thread(target=service.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 15
            while not service.started:
                if time.monotonic() > deadline or not thread.is_alive():
                    raise RuntimeError("Fixture did not start")
                time.sleep(0.05)
            env = {k: v for k, v in sanitized_environment(root).items() if not k.startswith("TIANXUAN_")}
            env.update(
                TIANXUAN_API="http://127.0.0.1:" + str(sock.getsockname()[1]),
                TIANXUAN_TOKEN=token,
                TIANXUAN_PROJECT="studio/game",
                U10_DOC=doc["id"],
            )
            env.pop("E02_EDIT", None)
            if saved_edit:
                env["E02_EDIT"] = "1"
            result = subprocess.run(
                [str(editor), "--headless", "--editor", "--path", str(project), "--script", "res://probe.gd"],
                env=env,
                cwd=root,
                capture_output=True,
                timeout=75,
            )
            output = (result.stdout + result.stderr).decode("utf-8", errors="replace")
            if token in output:
                raise AssertionError("Fixture token appeared in diagnostics")
            if saved_edit:
                checks = [
                    json.loads(line.removeprefix("E02_RESULT="))
                    for line in output.splitlines()
                    if line.startswith("E02_RESULT=")
                ]
                if result.returncode or "SCRIPT ERROR" in output or len(checks) != 1:
                    raise RuntimeError(f"Observed HTTP {reads!r}\n" + output[-5500:])
                turn = checks[0]["turn"]
                expected_edits = [
                    {
                        "kind": "document_edit",
                        "object_id": doc["id"],
                        "revision": 3,
                        "author": actor,
                        "changes": [
                            {
                                "before": [{"paragraph": 2, "text": "临时交付条件"}],
                                "after": [{"paragraph": 2, "text": "人改后的交付条件"}],
                            }
                        ],
                    }
                ]
                assert store.version(doc["id"], 3)["body_md"] == old.replace("原始目标段落", "人改后的交付条件")
                assert turn["document_edits"] == expected_edits and turn["state"] == "answered"
                assert len(model_inputs) == 1 and json.loads(model_inputs[0])["document_edits"] == expected_edits
                return {
                    "state": "passed",
                    "editor_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
                    "turn": turn["id"],
                    "received": json.loads(model_inputs[0]),
                    "http": reads,
                }
            checks = [
                line.removeprefix("U10_RESULT=") for line in output.splitlines() if line.startswith("U10_RESULT=")
            ]
            if result.returncode or "SCRIPT ERROR" in output or len(checks) != 1:
                raise RuntimeError(f"Observed HTTP {reads!r}\n" + output[-5500:])
            trace = json.loads(checks[0])
            expected = {"kind": "document", "object_id": doc["id"], "revision": 1, "paragraph": 2}
            assert trace["sent"] == expected and trace["current_version"] == 2
            assert trace["opened"] == {"document_id": doc["id"], "version": 1, "paragraph": 2}
            with httpx.Client(
                base_url=env["TIANXUAN_API"], headers={"Authorization": "Bearer " + token}, trust_env=False
            ) as client:
                read = client.get("/api/v1/workspace/conversations/" + trace["conversation"])
                read.raise_for_status()
                conversation = read.json()
                saved = conversation["turns"][0]["context_snapshot"]
                assert saved["references"] == [expected]
                invalid = {**saved, "references": [{**expected, "paragraph": 4}]}
                denied = client.post(
                    "/api/v1/workspace/conversations/" + trace["conversation"] + "/turns",
                    json={
                        "id": str(uuid4()),
                        "content": "验证历史段落边界",
                        "expected_version": conversation["version"],
                        "context_snapshot": invalid,
                    },
                )
                assert denied.status_code == 409, denied.text
                reopened = client.get("/api/v1/workspace/conversations/" + trace["conversation"])
                reopened.raise_for_status()
                assert reopened.json()["turns"] == conversation["turns"]
            assert reads.count(("/api/v1/docs/" + doc["id"] + "/versions/1", 200)) >= 2
        finally:
            service.should_exit = True
            thread.join(timeout=10)
            if gateway:
                gateway.close()
            store.db.close()
    return {
        "state": "passed",
        "editor_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "turn": trace,
        "real_service_reads": reads,
        "persisted_reference": expected,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--saved-edit", action="store_true")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="workbench-doc-reference-") as directory:
        result = exercise(Path(directory), args.godot.resolve(), args.saved_edit)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Passed saved document change" if args.saved_edit else "Passed sent reference after paragraph moved")
