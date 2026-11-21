"""Exercise a version-bound paragraph suggestion through native Godot controls and the Tianxuan API."""

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

import httpx
import uvicorn
from editor_test_isolation import copy_editor
from run_unified_settings_native import sanitized_environment
from starlette.responses import JSONResponse, Response

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "customizations/components/tianxuan/server"))

from api import create_app  # noqa: E402
from gateway import ModelGateway  # noqa: E402
from tianxuan_core import Tianxuan  # noqa: E402


def exercise(root, binary, source_controls, windowed, images):
    with patch.dict(os.environ, {"GONGGONG_WORKSPACE": ""}):
        editor = copy_editor(binary, root / "engine")
    project = root / "project"
    project.mkdir()
    (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="D05"\n')
    shutil.copyfile(Path(__file__).with_name("workbench_paragraph_suggestion.gd"), project / "probe.gd")
    if source_controls:
        for name in ("business_session.gd", "paragraph_suggestion.gd"):
            shutil.copyfile(ROOT / "editor/docks/workbench" / name, project / name)

    store = Tianxuan(str(root / "domain.sqlite"))
    user = store.register("Studio", "writer@example.invalid", secrets.token_urlsafe(24))
    actor = user["user_id"]
    token = store.issue_session(actor)
    original = "照亮桥面\r\n持续两秒"
    replacement = "点亮整座桥\r\n持续三秒"
    prefix = "# 虹桥  \r\n \t\r\n" + original + "\n\n"
    suffix = "\r\n\t\r\n收尾  \n"
    body = prefix + original + suffix
    doc = store.create_doc(actor, "虹桥", body)
    other = store.create_doc(actor, "副本", body)
    candidate = prefix + replacement + suffix
    fixture = dict(
        id=doc["id"], other=other["id"], body=body, original=original, replacement=replacement, candidate=candidate
    )
    prompts, writes, previews = [], [], []

    def model(request):
        content = json.loads(json.loads(request.content)["messages"][-1]["content"])
        prompts.append(content)
        if content["instruction"].startswith("切换"):
            time.sleep(0.25)
        return httpx.Response(
            200,
            json={
                "model": "native-fixture",
                "choices": [{"message": {"content": replacement.replace("\r\n", "\n")}}],
                "usage": {"prompt_tokens": 4, "completion_tokens": 2},
            },
        )

    gateway = ModelGateway(":memory:", transport=httpx.MockTransport(model))
    modes = dict(
        TIANXUAN_AUTH_MODE="accounts",
        TIANXUAN_PUBLIC_ORIGIN="https://fixture.invalid",
        TIANXUAN_TENANT_ID=user["tenant_id"],
        TIANXUAN_CHAT_BASE_URL="https://model.invalid/v1",
        TIANXUAN_CHAT_MODEL="native-fixture",
        TIANXUAN_CHAT_MODEL_KEY="fixture",
    )
    with patch.dict(os.environ, modes), socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        app = create_app(store, gateway=gateway)

        @app.middleware("http")
        async def observe(request, call_next):
            if request.method == "PATCH":
                payload = await request.json()
                if payload["expected_version"] == 2:
                    store.update_doc(actor, doc["id"], candidate + "其他作者", 2)
                response = await call_next(request)
                client = 503 if not writes and response.status_code == 200 else response.status_code
                writes.append((payload, response.status_code, client))
                return Response(status_code=503) if client != response.status_code else response
            response = await call_next(request)
            if request.url.path.endswith("/paragraph-suggestion"):
                response_bytes = b"".join([chunk async for chunk in response.body_iterator])
                data = json.loads(response_bytes)
                if response.status_code == 200:
                    previews.append({
                        "paragraph": data["paragraph"],
                        "revision_seen": store.get_doc(data["document_id"])["version"],
                        "writes_seen": len(writes),
                    })
                    if prompts[-1]["instruction"] == "越界回执":
                        data["candidate_body"] += "不应发生的尾部改动"
                return JSONResponse(data, status_code=response.status_code)
            return response

        service = uvicorn.Server(uvicorn.Config(app, log_level="error", access_log=False))
        thread = threading.Thread(target=service.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 12
            while not service.started:
                if time.monotonic() > deadline or not thread.is_alive():
                    raise RuntimeError("Loopback service did not start")
                time.sleep(0.05)
            env = {k: v for k, v in sanitized_environment(root).items() if not k.startswith(("TIANXUAN_", "D05_"))}
            env.update(
                TIANXUAN_API="http://127.0.0.1:" + str(sock.getsockname()[1]),
                TIANXUAN_TOKEN=token,
                TIANXUAN_PROJECT="studio/game",
                D05_FIXTURE=json.dumps(fixture),
            )
            if source_controls:
                env["D05_SOURCE_CONTROLS"] = "1"
            if images:
                env["D05_IMAGES"] = str(images.resolve(strict=True))
            args = [
                str(editor),
                *([] if windowed else ["--headless"]),
                "--editor",
                "--path",
                str(project),
                "--script",
                "res://probe.gd",
            ]
            result = subprocess.run(args, cwd=root, env=env, capture_output=True, timeout=55)
            output = (result.stdout + result.stderr).decode("utf-8", errors="replace").replace(token, "[redacted]")
            lines = [s.removeprefix("D05_CHECKS=") for s in output.splitlines() if s.startswith("D05_CHECKS=")]
            if result.returncode or "SCRIPT ERROR" in output or len(lines) != 1:
                raise RuntimeError(f"{output[-6500:]}\nFixture prompts={prompts} previews={previews} writes={writes}")
            trace = json.loads(lines[0])
            assert [item["instruction"] for item in prompts] == [
                "取消",
                "越界回执",
                "更明确",
                "并发修订",
                "切换段落",
                "切换文档",
                "切换身份",
            ]
            assert all(p["paragraph"] == original for p in prompts[:3])
            assert [p["writes_seen"] for p in previews[:3]] == [0, 0, 0]
            assert [p["paragraph"] for p in previews[:3]] == [3, 3, 3]
            assert [p["revision_seen"] for p in previews[:3]] == [1, 1, 1]
            assert [(service, client) for _, service, client in writes] == [(200, 503), (200, 200), (409, 409)]
            assert writes[0][0] == writes[1][0] and writes[0][0]["body_md"] == candidate and writes[0][0]["call_id"]
            assert store.version(doc["id"], 1)["body_md"] == body
            assert store.version(doc["id"], 2)["body_md"] == candidate
            assert store.get_doc(doc["id"])["body_md"] == candidate + "其他作者"
            assert store.get_doc(other["id"])["version"] == 1
            return {
                "state": "passed",
                "host": "source controls" if source_controls else "compiled native sidebar",
                "display": "windowed" if windowed else "headless",
                "model_transport": "fixture",
                "trace": trace,
                "editor_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
                "previews": previews,
                "saved_v2": candidate,
                "patch_statuses": [w[1:] for w in writes],
                "same_call_id_on_retry": True,
                "conflict_preserved_external_write": True,
                "stale_selection_document_identity_cleared": True,
            }
        finally:
            service.should_exit = True
            thread.join(timeout=10)
            gateway.close()
            store.db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument(
        "--source-controls", action="store_true", help="Diagnostic only: mount the two candidate scripts directly"
    )
    parser.add_argument("--windowed", action="store_true")
    parser.add_argument("--images", type=Path, help="Write two windowed screenshots in this directory")
    args = parser.parse_args()
    if args.images and not args.windowed:
        parser.error("--images needs --windowed")
    with tempfile.TemporaryDirectory(prefix="mac-1786-native-probe-") as tmp:
        report = exercise(Path(tmp), args.godot.resolve(), args.source_controls, args.windowed, args.images)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Passed native paragraph suggestion, explicit acceptance, retry and conflict")
