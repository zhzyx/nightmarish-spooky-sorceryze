"""Run native Mac editor acceptance for animation comparisons and script continuation."""

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


def run_probe(editor, project, env, marker):
    result = subprocess.run(
        [editor, "--editor", "--audio-driver", "Dummy", "--path", project, "--script", "res://probe.gd"],
        env=env,
        cwd=project,
        capture_output=True,
        timeout=60,
    )
    log = (result.stdout + result.stderr).decode(errors="replace")
    if os.getenv("WORKBENCH_PROBE_LOG"):
        with open(os.environ["WORKBENCH_PROBE_LOG"], "a") as record:
            record.write(log.replace(env.get("TIANXUAN_TOKEN", "no-candidate-token"), "[redacted]"))
    if env.get("TIANXUAN_TOKEN") and env["TIANXUAN_TOKEN"] in log:
        raise RuntimeError("Token appeared in diagnostics")
    for line in log.splitlines():
        if line.startswith(marker + "=") and result.returncode == 0 and "SCRIPT ERROR" not in log:
            return line.partition("=")[2]
    raise RuntimeError(log[:5000])


def exercise_script(root, editor, project, *, same_line_conflict=False):
    actor_file = project / "actor.gd"
    actor_file.write_text(
        "extends RefCounted\n\nstatic func score(points: int) -> int:\n\treturn points\nstatic func play() -> int:\n\treturn score(2)\n"
    )
    original = hashlib.sha256(actor_file.read_bytes()).hexdigest()
    proposed = {}
    for name, target in [
        ("workbench_document_reference.gd", "base.gd"),
        ("workbench_saved_editor_changes.gd", "changes.gd"),
        ("workbench_script_candidate.gd", "probe.gd"),
    ]:
        shutil.copyfile(Path(__file__).with_name(name), project / target)
    store = Tianxuan(str(root / "store.sqlite"))
    user = store.register("studio", "review@example.invalid", secrets.token_urlsafe(24))
    inputs = []

    def receive(request):
        turn = json.loads(json.loads(request.content)["messages"][-1]["content"])
        inputs.append(turn)
        answer = "已记录"
        if len(inputs) == 2:
            (ref,) = turn["context_snapshot"]["references"]
            saved = actor_file.read_bytes()
            before, after = b"return score(2)", b"return score(2, 7)"
            assert saved.count(before) == 1 and hashlib.sha256(saved).hexdigest() == ref["revision"]
            proposed.update(revision=hashlib.sha256(saved.replace(before, after)).hexdigest(), reference=ref)
            answer = json.dumps({
                "object_id": ref["object_id"],
                "revision": ref["revision"],
                "original": before.decode(),
                "replacement": after.decode(),
            })
        return httpx.Response(
            200,
            json={
                "model": "fixture",
                "usage": {"prompt_tokens": 10, "completion_tokens": 10},
                "choices": [{"message": {"content": answer}}],
            },
        )

    gateway = ModelGateway(":memory:", transport=httpx.MockTransport(receive))
    modes = dict(
        TIANXUAN_AUTH_MODE="accounts",
        TIANXUAN_PUBLIC_ORIGIN="https://fixture.invalid",
        TIANXUAN_TENANT_ID=user["tenant_id"],
        TIANXUAN_CHAT_MODEL="fixture",
        TIANXUAN_CHAT_BASE_URL="https://fixture.invalid/v1",
        TIANXUAN_CHAT_MODEL_KEY="fixture",
    )
    with patch.dict(os.environ, modes), socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        server = uvicorn.Server(
            uvicorn.Config(
                create_app(store, gateway=gateway, native_store=NativeStore(root / "native.db"), native_only=True),
                log_level="error",
                access_log=False,
            )
        )
        worker = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        worker.start()
        try:
            deadline = time.monotonic() + 15
            while not server.started:
                if not worker.is_alive() or time.monotonic() > deadline:
                    raise RuntimeError("Test service did not start")
                time.sleep(0.05)
            env = {k: v for k, v in sanitized_environment(root).items() if not k.startswith("TIANXUAN_")}
            env.update(
                TIANXUAN_API=f"http://127.0.0.1:{sock.getsockname()[1]}",
                WORKBENCH_SCRIPT_CASE="same_line" if same_line_conflict else "disjoint",
                TIANXUAN_PROJECT="studio/game",
                TIANXUAN_TOKEN=store.issue_session(user["user_id"]),
            )
            evidence = json.loads(run_probe(editor, project, env, "SCRIPT_CANDIDATE"))
            assert (
                len(inputs) == 2 and inputs[-1]["context_snapshot"]["references"][0]["revision"] == evidence["manual"]
            )
            selected = hashlib.sha256(actor_file.read_bytes()).hexdigest()
            assert evidence["candidate"] == selected
            assert (selected == proposed["revision"]) == (not same_line_conflict)
            env["WORKBENCH_SCRIPT_REOPEN"] = selected
            reopened = json.loads(run_probe(editor, project, env, "SCRIPT_REOPEN"))
            assert reopened["saved"] == selected and reopened["play"] == (99 if same_line_conflict else 2)
            evidence.update(original=original, proposed=proposed, reopened=reopened)
            check = subprocess.run(
                [editor, "--headless", "--path", project, "--check-only", "--script", "res://actor.gd"],
                capture_output=True,
                env=env,
                cwd=project,
                timeout=20,
            )
            assert check.returncode == 0 and b"SCRIPT ERROR" not in check.stderr, check.stderr
            evidence["gdscript_check_only"] = check.returncode
            return evidence
        finally:
            server.should_exit = True
            worker.join(10)
            gateway.close()
            store.db.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("feature", choices=["animation", "script", "script-conflict"])
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="workbench-candidate-") as tmp:
        root = Path(tmp).resolve()
        editor = copy_editor(args.godot, root / "engine")
        project = root / "project"
        project.mkdir()
        (project / "project.godot").write_text(
            'config_version=5\n[application]\nconfig/name="Workbench Candidate"\n[internationalization]\nlocale/test="en"\n'
        )
        if args.feature != "animation":
            evidence = exercise_script(root, editor, project, same_line_conflict=args.feature == "script-conflict")
        else:
            shutil.copyfile(Path(__file__).with_name("workbench_approach_replay.gd"), project / "probe.gd")
            env = sanitized_environment(root)
            saved = run_probe(editor, project, env, "APPROACH_SAVE")
            evidence = json.loads(run_probe(editor, project, env, "APPROACH_REOPEN"))
            assert saved == evidence["saved"]
        print(json.dumps(evidence, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
