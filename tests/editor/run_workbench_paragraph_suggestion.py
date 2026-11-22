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


def exercise(root, binary, source_controls, windowed, images, resolution=None, race=False):
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
    peer = store.add_member(actor, "reviewer@example.invalid", secrets.token_urlsafe(22), role="editor")["user_id"]
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
    if resolution is not None:
        fixture["resolution"] = resolution
        fixture["race"] = race
    contested = candidate.replace(replacement, "另一位作者改为持续十秒")
    merged_doc = candidate.replace("# 虹桥", "# 人工定稿的虹桥")
    merged_doc = merged_doc.replace("照亮桥面", "再次确认的桥面", 1)
    fixture["merged"] = merged_doc
    prompts, writes, previews, other_writes = [], [], [], []
    identity_preview_started = root / "identity-preview-started"

    def model(request):
        content = json.loads(json.loads(request.content)["messages"][-1]["content"])
        prompts.append(content)
        if content["instruction"] == "切换身份":
            identity_preview_started.touch()
        if content["instruction"].startswith("切换"):
            time.sleep(0.25)
        return httpx.Response(
            200,
            json={
                "model": "native-fixture",
                "choices": [
                    {
                        "message": {
                            "content": "桥灯保持蓝色"
                            if content["instruction"] == "并发修订"
                            else replacement.replace("\r\n", "\n")
                        }
                    }
                ],
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
                if payload.get("call_id") in {"fixture-peer-first", "fixture-peer-second"}:
                    return await call_next(request)
                if request.url.path.endswith("/" + other["id"]):
                    if payload["expected_version"] == 2 and len(other_writes) == 1:
                        latest = store.get_doc(other["id"])["body_md"]
                        async with httpx.AsyncClient(base_url=str(request.base_url)) as participant:
                            raced = await participant.patch(
                                request.url.path,
                                headers={"Authorization": "Bearer " + store.issue_session(peer)},
                                json={
                                    "expected_version": 2,
                                    "body_md": latest.replace("照亮桥面", "再次确认的桥面", 1),
                                    "call_id": "fixture-peer-second",
                                },
                            )
                            raced.raise_for_status()
                    response = await call_next(request)
                    # Lose the acknowledgement after the rebased submission was committed.
                    client = 503 if response.status_code == 200 and len(other_writes) == 3 else response.status_code
                    other_writes.append((payload, response.status_code, client))
                    return Response(status_code=503) if client != response.status_code else response
                if payload["expected_version"] == 2:
                    store.update_doc(actor, doc["id"], contested, 2)
                if race and len(writes) == 3:
                    store.update_doc(peer, doc["id"], candidate, 3)
                response = await call_next(request)
                lose_ack = not writes or (resolution is not None and len(writes) == (4 if race else 3))
                client = 503 if lose_ack and response.status_code == 200 else response.status_code
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
                    if prompts[-1]["instruction"] == "独立修改":
                        # Publish a real version notification while the suggestion is being reviewed.
                        token_peer = store.issue_session(peer)
                        async with httpx.AsyncClient(base_url=str(request.base_url)) as participant:
                            changed = await participant.patch(
                                "/api/v1/docs/" + other["id"],
                                headers={"Authorization": "Bearer " + token_peer},
                                json={
                                    "expected_version": 1,
                                    "body_md": body.replace("# 虹桥", "# 人工定稿的虹桥"),
                                    "call_id": "fixture-peer-first",
                                },
                            )
                            changed.raise_for_status()
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
                D05_IDENTITY_PREVIEW_STARTED=str(identity_preview_started),
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
            if resolution is not None:
                expected = prefix + ["另一位作者改为持续十秒", "桥灯保持蓝色", "人工折中为五秒"][resolution] + suffix
                final_version = 5 if race else 4
                if race:
                    assert writes[3][1:] == (409, 409)
                    assert store.version(doc["id"], 4)["body_md"] == candidate
                    if resolution == 0:
                        expected = candidate
                assert store.get_doc(doc["id"])["version"] == final_version
                assert store.version(doc["id"], 3)["body_md"] == contested
                assert store.version(doc["id"], final_version)["body_md"] == expected
                assert trace[-1] == {"choice": resolution, "version": final_version, "resolved": expected}
                assert writes[-2][0] == writes[-1][0] and writes[-2][1:] == (200, 503) and writes[-1][1:] == (200, 200)
                return dict(
                    choice=resolution,
                    trace=trace,
                    writes=writes,
                    editor_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                )
            assert [item["instruction"] for item in prompts] == [
                "取消",
                "越界回执",
                "更明确",
                "并发修订",
                "独立修改",
                "切换段落",
                "切换文档",
                "切换身份",
            ], [item["instruction"] for item in prompts]
            assert all(p["paragraph"] == original for p in prompts[:3])
            assert [p["writes_seen"] for p in previews[:3]] == [0, 0, 0]
            assert [p["paragraph"] for p in previews[:3]] == [3, 3, 3]
            assert [p["revision_seen"] for p in previews[:3]] == [1, 1, 1]
            assert [(service, client) for _, service, client in writes] == [(200, 503), (200, 200), (409, 409)]
            assert writes[0][0] == writes[1][0] and writes[0][0]["body_md"] == candidate and writes[0][0]["call_id"]
            assert store.version(doc["id"], 1)["body_md"] == body
            assert store.version(doc["id"], 2)["body_md"] == candidate
            assert store.get_doc(doc["id"])["body_md"] == contested
            assert store.get_doc(other["id"])["version"] == 4
            assert store.get_doc(other["id"])["body_md"] == merged_doc
            assert [(status, client) for _, status, client in other_writes] == [
                (409, 409),
                (409, 409),
                (409, 409),
                (200, 503),
                (200, 200),
            ]
            assert other_writes[3][0] == other_writes[4][0]
            assert other_writes[3][0]["call_id"] != other_writes[0][0]["call_id"]
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
                "merged_version": 4,
                "merged_markdown": merged_doc,
                "rebased_write_statuses": [write[1:] for write in other_writes],
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
    parser.add_argument("--resolution", type=int, choices=range(3))
    parser.add_argument("--race", action="store_true")
    args = parser.parse_args()
    if args.images and not args.windowed:
        parser.error("--images needs --windowed")
    with tempfile.TemporaryDirectory(prefix="mac-1786-native-probe-") as tmp:
        report = exercise(
            Path(tmp), args.godot.resolve(), args.source_controls, args.windowed, args.images, args.resolution
        )
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Passed native paragraph suggestion, explicit acceptance, retry and conflict")
