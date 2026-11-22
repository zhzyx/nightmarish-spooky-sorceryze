"""Exercise the native document editor across a real Tianxuan stop/restart on the same port."""

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
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import uvicorn
from run_workbench_documents import Tianxuan, copy_editor, create_app, sanitized_environment


@contextmanager
def serve(app, port, *, websocket=True):
    with socket.socket() as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", port))
        server = uvicorn.Server(
            uvicorn.Config(app, log_level="error", access_log=False, ws="auto" if websocket else "none")
        )
        thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 15
            while not server.started:
                if not thread.is_alive() or time.monotonic() >= deadline:
                    raise RuntimeError("Fixture server did not start")
                time.sleep(0.05)
            yield sock.getsockname()[1]
        finally:
            server.should_exit = True
            thread.join(timeout=15)
            if thread.is_alive():
                raise RuntimeError("Fixture server did not stop")


def wait_for_marker(path, window):
    deadline = time.monotonic() + 50
    while not path.exists():
        if window.done():
            raise AssertionError(f"Missing {path.name} after editor finished: {window.result()}")
        if time.monotonic() >= deadline:
            raise TimeoutError(path.name)
        time.sleep(0.05)


def exercise(root, editor, scenario):
    root.mkdir()
    project = root / "project"
    project.mkdir()
    (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="D08"\n')
    shutil.copyfile(Path(__file__).with_name("workbench_offline_document.gd"), project / "probe.gd")
    store = Tianxuan(str(root / "documents.sqlite"))
    owner = store.register("D08", "owner@example.invalid", secrets.token_urlsafe(24))
    actor = owner["user_id"]
    peer = store.add_member(actor, "peer@example.invalid", secrets.token_urlsafe(24))["user_id"]
    tokens = {user: store.issue_session(user) for user in (actor, peer)}
    doc = store.create_doc(actor, "同名设计", "第一段\n\n设计原文")["id"]
    other = store.create_doc(actor, "同名设计", "独立正文")["id"]
    modes = {
        "TIANXUAN_AUTH_MODE": "accounts",
        "TIANXUAN_TENANT_ID": owner["tenant_id"],
        "TIANXUAN_PUBLIC_ORIGIN": "https://fixture.invalid",
    }
    writes = []
    results = {}

    def window(stage):
        env = {k: v for k, v in sanitized_environment(root).items() if not k.startswith(("D08_", "TIANXUAN_"))}
        env.update(
            TIANXUAN_API=f"http://127.0.0.1:{port}",
            TIANXUAN_TOKEN=tokens[actor],
            TIANXUAN_PROJECT="studio/game",
            D08_STAGE=stage,
            D08_SCENARIO=scenario,
            D08_DOC=doc,
            D08_OTHER=other,
            D08_PEER=tokens[peer],
            D08_SYNC=str(root),
        )
        proc = subprocess.run(
            [str(editor), "--headless", "--editor", "--path", str(project), "--script", "res://probe.gd"],
            env=env,
            cwd=root,
            capture_output=True,
            timeout=105,
        )
        output = (proc.stdout + proc.stderr).decode("utf-8", errors="replace")
        if any(token in output for token in tokens.values()):
            raise AssertionError("Session credential appeared in diagnostics")
        records = [
            line.removeprefix("D08_OBSERVED=") for line in output.splitlines() if line.startswith("D08_OBSERVED=")
        ]
        if proc.returncode or "SCRIPT ERROR" in output or len(records) != 1:
            raise AssertionError(f"{stage} editor: {output[-6000:]}")
        return json.loads(records[0])

    with patch.dict(os.environ, modes), ThreadPoolExecutor(max_workers=1) as pool:
        app = create_app(store)

        @app.middleware("http")
        async def observe(request, next_handler):
            payload = await request.json() if request.method == "PATCH" else None
            reply = await next_handler(request)
            if payload is not None:
                writes.append({
                    "path": request.url.path,
                    "project": request.query_params.get("project"),
                    "expected_version": payload["expected_version"],
                    "body_md": payload["body_md"],
                    "status": reply.status_code,
                })
            return reply

        try:
            with serve(app, 0) as port:
                offline = pool.submit(window, "disconnect")
                wait_for_marker(root / "connected", offline)
            wait_for_marker(root / "typed", offline)
            if scenario == "advanced":
                store.update_doc(peer, doc, "在线协作者的修订\n\n设计原文", 1)
            with serve(app, port, websocket=scenario != "http_only"):
                results["disconnect"] = offline.result()
                if scenario == "advanced":
                    assert not writes and store.get_doc(doc)["version"] == 2
                    scopes = results["disconnect"]
                    assert scopes["other_account"]["account"] == peer and scopes["other_account"]["document"] == doc
                    assert (
                        scopes["other_project"]["account"] == actor
                        and scopes["other_project"]["project"] == "studio/other"
                    )
                    assert scopes["other_document"]["document"] == other
                    results["resume"] = window("resume")
                head = store.get_doc(doc)
                saved = results.get("resume", results["disconnect"])["saved"]
                assert head["version"] == saved["version"] and head["body_md"] == saved["body_md"]
                assert len(writes) == 1 and writes[0]["status"] == 200 and writes[0]["path"] == f"/api/v1/docs/{doc}"
                assert writes[0]["expected_version"] == head["version"] - 1 and writes[0]["body_md"] == head["body_md"]
                assert store.get_doc(other)["version"] == 1
        finally:
            store.db.close()
    return {"windows": results, "service_patches": writes}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    binary = args.godot.resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix="workbench-d08-") as directory:
        base = Path(directory)
        with patch.dict(os.environ, {"GONGGONG_WORKSPACE": ""}):
            editor = copy_editor(binary, base / "engine")
        observations = {case: exercise(base / case, editor, case) for case in ("unchanged", "advanced", "http_only")}
        digest = hashlib.sha256()
        with editor.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    result = {"state": "passed", "editor_sha256": digest.hexdigest(), "scenarios": observations}
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Passed native offline edits, reconnect comparison, restart recovery and scope isolation")
