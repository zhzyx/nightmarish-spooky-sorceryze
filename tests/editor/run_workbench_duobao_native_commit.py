"""Run a real materialized project through the native dialog before and after a service restart."""

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
import time
import urllib.request
from pathlib import Path
from unittest.mock import patch

import uvicorn
from editor_test_isolation import copy_editor
from fastapi.responses import JSONResponse
from run_unified_settings_native import sanitized_environment
from run_workbench_duobao_branches import ROOT, SERVER, Tianxuan, create_app
from run_workbench_duobao_commit import run_controls

sys.path.insert(0, str(ROOT / SERVER.parent / "duobao"))
from native_store import NativeStore  # noqa: E402
from native_workspace import NativeWorkspace  # noqa: E402


def serve(base, phase, port):
    accounts = Tianxuan(str(base / "accounts.sqlite"))
    native = NativeStore(base / "modules.sqlite")
    tenant, actor = json.loads((base / "fixture.json").read_bytes())
    app = create_app(accounts, native_store=native, native_only=True)

    @app.middleware("http")
    async def record_receipts(request, call_next):
        body = None
        if request.url.path == "/api/v1/native/batches" and request.method == "POST":
            body = await request.json()
        response = await call_next(request)
        row = None
        if response.status_code == 200:
            if body:
                row = {
                    "method": "POST",
                    "key": body["request_key"],
                    "edits": list(body["changes"][0]["edits"]),
                    "revision": native.head(tenant, "game"),
                }
                if phase == "first":
                    response = JSONResponse({"detail": "lost successful response"}, status_code=503)
            elif request.url.path.startswith("/api/v1/native/batches/"):
                key = request.url.path.rsplit("/", 1)[1]
                row = {"method": "GET", "key": key, "received": native.batch_receipt(tenant, actor, key) is not None}
        if row:
            with (base / "audit.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(row) + "\n")
        return response

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="error", access_log=False)


def exercise(base, binary):
    store = Tianxuan(str(base / "accounts.sqlite"))
    owner = store.register("物化工程", "g11@example.invalid", secrets.token_urlsafe(24))
    tenant, actor = owner["tenant_id"], owner["user_id"]
    token = store.issue_session(actor)
    store.db.close()
    database = base / "modules.sqlite"
    native = NativeStore(database)
    seed = native.submit(
        tenant,
        actor,
        "seed",
        [
            {
                "module": "game",
                "base": None,
                "reads": None,
                "edits": {
                    "project.godot": b'config_version=5\n[application]\nconfig/name="G11"\n',
                    "A.txt": b"original A\n",
                    "B.txt": b"original B\n",
                },
            }
        ],
    )["revisions"]["game"]
    checkout = base / "materialized"
    manifest = NativeWorkspace(native).materialize(tenant, {"game": seed}, checkout)
    project = checkout / "game"
    assert not any((p / ".git").exists() for p in (project, *project.parents))
    (project / "A.txt").write_bytes(b"chosen\n")
    (project / "B.txt").write_bytes(b"working B\n")
    (base / "SConstruct").touch()
    host = base / SERVER
    host.mkdir(parents=True)
    for name in ("tianshu_bridge.py", "selected_commit.py", "native_workcopy_commit.py"):
        shutil.copyfile(ROOT / SERVER / name, host / name)
    (host.parent / "duobao").mkdir()
    for name in ("native_store.py", "native_workspace.py"):
        shutil.copyfile(ROOT / SERVER.parent / "duobao" / name, host.parent / "duobao" / name)
    with patch.dict(os.environ, {"GONGGONG_WORKSPACE": ""}):
        editor = copy_editor(binary, base / "engine")

    phases = {}
    pids = []
    modes = {
        "TIANXUAN_AUTH_MODE": "accounts",
        "TIANXUAN_PUBLIC_ORIGIN": "https://fixture.invalid",
        "TIANXUAN_TENANT_ID": tenant,
    }
    (base / "fixture.json").write_text(json.dumps([tenant, actor]), encoding="utf-8")
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    api = "http://127.0.0.1:" + str(port)
    for phase in ("first", "restart"):
        with (base / "service.log").open("ab") as log:
            proc = subprocess.Popen(
                [sys.executable, "-X", "utf8", str(Path(__file__).resolve()), "--serve", str(base), phase, str(port)],
                env={**os.environ, **modes},
                stdout=log,
                stderr=log,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            pids.append(proc.pid)
            try:
                deadline = time.monotonic() + 30
                while True:
                    if time.monotonic() > deadline or proc.poll() is not None:
                        raise RuntimeError(
                            "Native service startup failed: "
                            + (base / "service.log").read_text(errors="replace")[-1200:]
                        )
                    try:
                        with urllib.request.urlopen(api + "/api/v1/health", timeout=1) as response:
                            assert response.status == 200
                        break
                    except OSError:
                        time.sleep(0.08)
                env = {k: v for k, v in sanitized_environment(base).items() if not k.startswith("TIANXUAN_")}
                env.update(
                    TIANXUAN_API=api,
                    TIANXUAN_ACTOR=actor,
                    TIANXUAN_TOKEN=token,
                    G11_PYTHON=sys.executable,
                    G11_NATIVE_PHASE=phase,
                )
                phases[phase] = run_controls(editor, project, base, env, token)
                if phase == "restart":
                    revision = native.head(tenant, "game")
                    prefix = api + "/api/v1/native/modules/game/revisions/" + revision + "/objects/"
                    for name, expected in (("A.txt", b"chosen\n"), ("B.txt", b"original B\n")):
                        req = urllib.request.Request(prefix + name, headers={"Authorization": "Bearer " + token})
                        with urllib.request.urlopen(req, timeout=10) as response:
                            assert response.read() == expected
            finally:
                proc.terminate()
                proc.wait(timeout=15)
    audit = [json.loads(line) for line in (base / "audit.jsonl").read_text(encoding="utf-8").splitlines()]
    posts = [row for row in audit if row["method"] == "POST"]
    lookups = [row for row in audit if row["method"] == "GET"]
    assert len(posts) == 1 and posts[0]["edits"] == ["A.txt"]
    key = posts[0]["key"]
    assert lookups == [
        {"method": "GET", "key": key, "received": False},
        {"method": "GET", "key": key, "received": True},
    ]
    assert (project / "A.txt").read_bytes() == b"chosen\n" and (project / "B.txt").read_bytes() == b"working B\n"
    assert json.loads((checkout / ".duobao-source.json").read_bytes()) == manifest
    with native._connection() as db:
        assert (
            db.execute("SELECT count(*) FROM native_revisions WHERE tenant=? AND module='game'", (tenant,)).fetchone()[
                0
            ]
            == 2
        )
        assert (
            db.execute(
                "SELECT count(*) FROM native_receipts WHERE request_key=? AND actor=? AND tenant=?",
                (key, actor, tenant),
            ).fetchone()[0]
            == 1
        )
    return {
        "editor_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "source_revision": seed,
        "received_revision": posts[0]["revision"],
        "request_key": key,
        "posted_edits": posts[0]["edits"],
        "receipt_lookups": [entry["received"] for entry in lookups],
        "post_count": len(posts),
        "total_revisions_including_seed": 2,
        "matching_receipts": 1,
        "native_only": True,
        "git_checkout": False,
        "service_and_editor_restarted": True,
        "service_pids": pids,
        "checks": phases,
        "B": {"exact_remote_revision": "original B", "materialized_file": "working B"},
    }


if __name__ == "__main__":
    if sys.argv[1:2] == ["--serve"]:
        serve(Path(sys.argv[2]), sys.argv[3], int(sys.argv[4]))
        sys.exit(0)
    parser = argparse.ArgumentParser()
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="gonggong-g11-native-") as folder:
        result = exercise(Path(folder).resolve(), args.godot.resolve(strict=True))
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Passed materialized native selection, server restart and exact revision readback")
