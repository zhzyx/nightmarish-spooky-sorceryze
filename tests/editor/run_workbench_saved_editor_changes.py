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


def exercise(root, binary, continuation=False):
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
    if continuation:
        shutil.copyfile(project / "probe.gd", project / "changes.gd")
        shutil.copyfile(Path(__file__).with_name("workbench_saved_continuation.gd"), project / "probe.gd")
    material_hash = hashlib.sha256(material.read_bytes()).hexdigest()
    store = Tianxuan(str(root / "store.db"))
    user = store.register("studio", "editor@example.invalid", secrets.token_urlsafe(24))
    actor = user["user_id"]
    unchanged = "需要保留的背景。" * 5000
    doc = store.create_doc(actor, "接续文档", unchanged + "\n\n原来第 2 段") if continuation else {}
    second_actor = (
        store.add_member(actor, "reviewer@example.invalid", secrets.token_urlsafe(24))["user_id"]
        if continuation
        else ""
    )
    inputs = []
    track_revisions = {}

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
            if continuation:
                env["EDIT_DOCUMENT"] = doc["id"]
            for phase in ["save", "reopen"]:
                if continuation and phase == "reopen":
                    # Another editor commits after the first user's draft already cites v2.
                    with httpx.Client(
                        base_url=env["TIANXUAN_API"],
                        trust_env=False,
                        headers={"Authorization": "Bearer " + store.issue_session(second_actor)},
                    ) as client:
                        update = client.patch(
                            "/api/v1/docs/" + doc["id"],
                            params={"project": "studio/game"},
                            json={
                                "expected_version": 2,
                                "body_md": unchanged + "\n\n协作者保存的第 2 段",
                                "call_id": "later-human-edit",
                            },
                        )
                        update.raise_for_status()
                        assert update.json()["version"] == 3
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
                for line in output.splitlines():
                    if line.startswith("TRACK_REVISIONS="):
                        track_revisions = json.loads(line.partition("=")[2])
                if result.returncode or "SCRIPT ERROR" in output or f"SAVE_RESULT={phase}" not in output:
                    raise AssertionError(f"{phase}: received {[v['content'][:80] for v in inputs]}\n{output[-5500:]}")
        finally:
            service.should_exit = True
            worker.join(timeout=10)
            gateway.close()
            store.db.close()
    if continuation:
        assert len(inputs) == 3
        final = inputs[-1]
        changes = json.loads(final["content"].split("[已引用对象的保存修订]\n", 1)[1])
        by_id = {obj["object_id"]: obj for obj in changes}
        script, node, animation = [
            by_id[k] for k in ["res://actor.gd#L3:1-L3:11", "res://motion.tscn#Actor", "res://motion.tscn#Player"]
        ]
        assert script["starting_state"]["text"] == "\treturn 11" and script["latest_state"]["text"] == "\treturn 29"
        assert (
            node["starting_state"]["position"] == "(5.0, 0.0)" and node["latest_state"]["position"] == "(37.5, 0.0)"
        ), node
        assert all(item["actor"] == actor and item["start_revision"] != item["revision"] for item in changes)
        assert final["context_snapshot"]["continuation"]["preserve"] == "保留三个现场的人工修改"
        document = final["document_edits"][0]
        assert (document["start_revision"], document["revision"], document["author"]) == (1, 3, second_actor)
        assert document["changes"] == [
            {
                "before": [{"paragraph": 2, "text": "原来第 2 段"}],
                "after": [{"paragraph": 2, "text": "协作者保存的第 2 段"}],
            }
        ]
        assert len(json.dumps(document, ensure_ascii=False)) < 1000
        assert any(
            ref["kind"] == "document_edit" and ref["revision"] == 2 for ref in final["context_snapshot"]["references"]
        )
        assert any(
            ref["kind"] == "document" and ref["revision"] == 1 for ref in inputs[0]["context_snapshot"]["references"]
        )
        (delta,) = animation["animation_changes"]
        (key,) = delta["keys"]
        assert delta["animation"] == "Walk" and delta["path"] == "Actor:position:x" and key["time"] == 0.5
        assert key["before"]["value"] == 12 and key["after"]["value"] == 18
        y = next(k for k, track in track_revisions["before"].items() if track["path"] == "Actor:position:y")
        assert track_revisions["before"][y] == track_revisions["after"][y]
        return {
            "state": "passed",
            "editor_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
            "received": final,
            "track_revisions": track_revisions,
        }
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
    parser.add_argument("--continuation", action="store_true")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="workbench-saved-editor-") as directory:
        report = exercise(Path(directory), args.godot.resolve(), args.continuation)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print("Passed native saved editor changes and reopened task input")
