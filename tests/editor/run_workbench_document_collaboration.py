"""Drive two isolated D04 editor windows against one accounts-mode Tianxuan document."""

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
from pathlib import Path
from unittest.mock import patch

import uvicorn
from run_workbench_documents import Tianxuan, copy_editor, create_app, sanitized_environment
from starlette.responses import Response


def exercise(root, binary):
    store = Tianxuan(str(root / "documents.sqlite"))
    owner = store.register("D07", "writer-a@example.invalid", secrets.token_urlsafe(24))
    invite = store.create_invite(owner["user_id"], "writer-b@example.invalid")
    writer = store.accept_invite(invite["code"], secrets.token_urlsafe(24))
    actors = {"A": owner["user_id"], "B": writer["user_id"]}
    tokens = {role: store.issue_session(actor) for role, actor in actors.items()}
    document = store.create_doc(actors["A"], "共同设计", "设计目标\n约束条件\n\n交付清单")
    modes = {
        "TIANXUAN_AUTH_MODE": "accounts",
        "TIANXUAN_TENANT_ID": owner["tenant_id"],
        "TIANXUAN_PUBLIC_ORIGIN": "https://fixture.invalid",
    }
    writes = []

    def run_window(role, port):
        directory = root / role
        directory.mkdir()
        editor = copy_editor(binary, directory / "engine")
        project = directory / "project"
        project.mkdir()
        (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="D07"\n')
        shutil.copyfile(Path(__file__).with_name("workbench_document_collaboration.gd"), project / "probe.gd")
        env = {key: value for key, value in sanitized_environment(directory).items() if not key.startswith("TIANXUAN_")}
        env.update(
            TIANXUAN_API=f"http://127.0.0.1:{port}",
            TIANXUAN_TOKEN=tokens[role],
            TIANXUAN_PROJECT="studio/game",
            D07_ROLE=role,
            D07_SYNC=str(root),
            D07_DOC=document["id"],
        )
        result = subprocess.run(
            [str(editor), "--headless", "--editor", "--path", str(project), "--script", "res://probe.gd"],
            env=env,
            cwd=directory,
            capture_output=True,
            timeout=110,
        )
        output = (result.stdout + result.stderr).decode("utf-8", errors="replace")
        if any(token in output for token in tokens.values()):
            raise AssertionError("Session credential appeared in diagnostics")
        records = [line.partition("=")[2] for line in output.splitlines() if line.startswith("D07_OBSERVED=")]
        if result.returncode or "SCRIPT ERROR" in output or len(records) != 1:
            raise RuntimeError(f"Window {role}: {output[-8000:]}")
        return json.loads(records[0])

    with patch.dict(os.environ, modes | {"GONGGONG_WORKSPACE": ""}), socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        api = create_app(store)

        @api.middleware("http")
        async def observe(request, call_next):
            response = await call_next(request)
            if request.method in {"PATCH", "POST"}:
                status = response.status_code
                committed = store.get_doc(document["id"])["version"]
                if (
                    request.method == "PATCH"
                    and status == 200
                    and committed == 3
                    and not any(row["client_status"] == 503 for row in writes)
                ):
                    response = Response(status_code=503)
                writes.append({
                    "method": request.method,
                    "path": request.url.path,
                    "status": status,
                    "client_status": response.status_code,
                    "current_version": committed,
                })
            return response

        service = uvicorn.Server(uvicorn.Config(api, log_level="error", access_log=False))
        thread = threading.Thread(target=service.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 15
            while not service.started:
                if time.monotonic() > deadline or not thread.is_alive():
                    raise RuntimeError("Fixture service did not start")
                time.sleep(0.05)
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = {role: pool.submit(run_window, role, sock.getsockname()[1]) for role in actors}
            errors = [str(f.exception()) for f in futures.values() if f.exception()]
            if errors:
                raise RuntimeError("\n".join(errors))
            windows = {role: f.result() for role, f in futures.items()}
            history = [store.version(document["id"], version) for version in range(1, 6)]
            assert store.get_doc(document["id"])["version"] == 5
            assert [row["author"] for row in history] == [actors[role] for role in ("A", "A", "B", "A", "B")]
            assert all(windows[role]["account"] == actor for role, actor in actors.items())
            for trace in windows.values():
                assert trace["different_paragraphs"]["body_md"] == history[2]["body_md"]
                assert trace["resolved"]["body_md"] == history[4]["body_md"]
            assert windows["B"]["conflict"]["remote"] == history[3]["body_md"]
            assert [row["status"] for row in writes if row["path"].endswith("/preview")] == [200, 409]
            assert len([row for row in writes if row["client_status"] == 503]) == 1
        finally:
            service.should_exit = True
            thread.join(timeout=10)
            store.db.close()
    with binary.open("rb") as executable:
        digest = hashlib.file_digest(executable, "sha256").hexdigest()
    return {"state": "passed", "editor_sha256": digest, "windows": windows, "history": history, "requests": writes}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="workbench-d07-") as directory:
        result = exercise(Path(directory), args.godot.resolve())
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Passed two-account native document collaboration")
