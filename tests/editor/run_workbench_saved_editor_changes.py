"""Inspect actual next-turn requests after native saves and an external script edit."""

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

import httpx
import uvicorn
from run_workbench_document_reference import (
    ModelGateway,
    NativeStore,
    Tianxuan,
    copy_editor,
    create_app,
    sanitized_environment,
)


def exercise(root, binary):
    editor = copy_editor(binary, root / "engine")
    project = root / "project"
    project.mkdir()
    (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="Saved editor changes"\n')
    (project / "actor.gd").write_text("extends Node\nfunc score():\n\treturn 11\n")
    outside = root / "outside.png"
    outside.write_bytes(b"outside the selected project")
    (project / "redirect.png").symlink_to(outside)
    (project / "broken.tres").write_text(
        '[gd_resource type="StandardMaterial3D" load_steps=3 format=3]\n'
        '[ext_resource type="Texture2D" path="res://absent.png" id="1"]\n'
        '[ext_resource type="Texture2D" path="res://redirect.png" id="2"]\n'
        '[resource]\nalbedo_texture = ExtResource("1")\nemission_texture = ExtResource("2")\n'
    )
    material = project / "paint.tres"
    material.write_text('[gd_resource type="CanvasItemMaterial" format=3]\n[resource]\nblend_mode = 1\n')
    (project / "level.tscn").write_text(
        '[gd_scene load_steps=2 format=3]\n[ext_resource type="Material" path="res://paint.tres" id="1"]\n'
        '[node name="Level" type="Node2D"]\n[node name="Actor" type="Sprite2D" parent="."]\nmaterial = ExtResource("1")\n'
    )
    for src, dst in [("workbench_document_reference.gd", "base.gd"), ("workbench_saved_editor_changes.gd", "probe.gd")]:
        shutil.copyfile(Path(__file__).with_name(src), project / dst)
    material_hash = hashlib.sha256(material.read_bytes()).hexdigest()
    store = Tianxuan(str(root / "store.db"))
    user = store.register("studio", "editor@example.invalid", secrets.token_urlsafe(24))
    actor = user["user_id"]
    inputs = []

    def receive(request):
        inputs.append(json.loads(json.loads(request.content)["messages"][-1]["content"]))
        return httpx.Response(
            200,
            json={
                "model": "fixture",
                "usage": {"prompt_tokens": 10, "completion_tokens": 1},
                "choices": [{"message": {"content": "received"}}],
            },
        )

    gateway = ModelGateway(":memory:", transport=httpx.MockTransport(receive))
    modes = dict(
        TIANXUAN_AUTH_MODE="accounts",
        TIANXUAN_PUBLIC_ORIGIN="https://fixture.invalid",
        TIANXUAN_TENANT_ID=user["tenant_id"],
        TIANXUAN_CHAT_MODEL="fixture",
        TIANXUAN_CHAT_BASE_URL="https://fixture.invalid/v1",
        TIANXUAN_CHAT_MODEL_KEY="local",
    )
    with patch.dict(os.environ, modes), socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        app = create_app(store, gateway=gateway, native_store=NativeStore(root / "native.db"), native_only=True)
        service = uvicorn.Server(uvicorn.Config(app, log_level="error", access_log=False))
        worker = threading.Thread(target=service.run, kwargs={"sockets": [sock]}, daemon=True)
        worker.start()
        try:
            deadline = time.monotonic() + 15
            while not service.started:
                if not worker.is_alive() or time.monotonic() > deadline:
                    raise RuntimeError("Loopback service unavailable")
                time.sleep(0.05)
            env = {k: v for k, v in sanitized_environment(root).items() if not k.startswith("TIANXUAN_")}
            env.update(
                TIANXUAN_API=f"http://127.0.0.1:{sock.getsockname()[1]}",
                TIANXUAN_TOKEN=store.issue_session(actor),
                TIANXUAN_PROJECT="studio/game",
            )
            for phase in ["save", "reopen"]:
                result = subprocess.run(
                    [str(editor), "--headless", "--editor", "--path", str(project), "--script", "res://probe.gd"],
                    cwd=root,
                    env={**env, "SAVE_PHASE": phase},
                    capture_output=True,
                    timeout=100,
                )
                output = (
                    (result.stdout + result.stderr)
                    .decode(errors="replace")
                    .replace(env["TIANXUAN_TOKEN"], "[redacted]")
                )
                if result.returncode or "SCRIPT ERROR" in output or f"SAVE_RESULT={phase}" not in output:
                    raise AssertionError(f"{phase}: received {[v['content'][:80] for v in inputs]}\n{output[-5500:]}")
        finally:
            service.should_exit = True
            worker.join(timeout=10)
            gateway.close()
            store.db.close()
    assert len(inputs) == 6
    assert inputs[1]["context_snapshot"]["references"] == []

    def change(index):
        records = json.loads(inputs[index]["content"].split("[已引用对象的保存修订]\n", 1)[1])
        assert len(records) == 1
        item = records[0]
        assert inputs[index]["context_snapshot"]["references"] == [
            {"kind": "editor", "object_id": item["object_id"], "revision": item["revision"]}
        ]
        return item

    native, external, scene = change(2), change(3), change(5)
    assert native["text"] == "\treturn 29" and native["first_line"] == native["last_line"] == 3
    assert native["actor"] == actor and native["source"] == "editor_save", (native, actor, scene)
    assert external["text"] == "\treturn 53" and external["previous_revision"] == native["revision"]
    assert external["source"] == "disk_readback" and external["actor"] is None
    assert scene["previous_revision"] == inputs[4]["context_snapshot"]["references"][0]["revision"]
    assert scene["revision"] == hashlib.sha256((project / "level.tscn").read_bytes()).hexdigest()
    assert scene["actor"] == actor and scene["dependencies"] == {"res://paint.tres": material_hash}, scene
    return {
        "state": "passed",
        "editor_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "received": inputs,
        "reopened_node_x": 37.5,
        "original_dependency_sha256": material_hash,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="workbench-saved-editor-") as directory:
        report = exercise(Path(directory), args.godot.resolve())
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print("Passed native saved editor changes and reopened task input")
