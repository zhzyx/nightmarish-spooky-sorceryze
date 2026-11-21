"""Run the native C07 picker against fresh Tianxuan and Duobao databases."""

import argparse
import asyncio
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import httpx
import uvicorn
from editor_test_isolation import copy_editor

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "customizations/components/tianxuan/server"))

PROJECT = "studio/assets"
BASE = "/api/v1"


def exercise(editor, root):
    from api import create_app
    from native_store import NativeStore
    from tianxuan_core import Tianxuan

    binary = copy_editor(editor, root / "editor")
    project = root / "project"
    project.mkdir()
    (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="C07"\n')
    shutil.copyfile(Path(__file__).with_name("workbench_asset_ownership.gd"), project / "probe.gd")
    domain = Tianxuan(str(root / "domain.db"))
    native = NativeStore(root / "native.db")
    account = domain.register("Studio", "maker@example.invalid", "test-pass-local")
    actor = account["user_id"]
    os.environ.update(
        TIANXUAN_AUTH_MODE="accounts",
        TIANXUAN_PUBLIC_ORIGIN="https://studio.example",
        TIANXUAN_TENANT_ID=account["tenant_id"],
    )
    app = create_app(domain, native_store=native, native_only=True)
    calls = []

    @app.middleware("http")
    async def observe(request, call_next):
        response = await call_next(request)
        if request.url.path.endswith("/delayed.glb"):
            (root / "read-started").touch()
            deadline = time.monotonic() + 12
            while not (root / "release-read").exists() and time.monotonic() < deadline:
                await asyncio.sleep(0.02)
            (root / "read-released").touch()
        calls.append((request.method, request.url.path, response.status_code))
        return response

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        base = "http://127.0.0.1:" + str(sock.getsockname()[1])
        server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 10
            while not server.started:
                assert thread.is_alive() and time.monotonic() < deadline
                time.sleep(0.02)
            token = domain.issue_session(actor)
            with httpx.Client(base_url=base, headers={"Authorization": "Bearer " + token}, trust_env=False) as client:
                spec = json.loads((ROOT / "samples/gonggong-workbench/fixtures/b05/sample.json").read_text("utf8"))
                model = spec["asset"]
                content = (ROOT / model["repo_source"]).read_bytes()
                assert hashlib.sha256(content).hexdigest() == model["sha256"]
                free = "unused/独立 模型.glb"
                revision = native.submit(
                    account["tenant_id"],
                    actor,
                    "seed",
                    [
                        {
                            "module": model["module"],
                            "base": None,
                            "reads": None,
                            "edits": {model["path"]: content, free: content, "delayed.glb": content},
                        }
                    ],
                )["revisions"][model["module"]]
                reference = {"source_module": model["module"], "revision": revision, "path": model["path"]}
                modules = []
                for call_id in ("a", "b"):
                    info = domain.create_business_module(actor, PROJECT, "角色", call_id=call_id)
                    modules.append(info["id"])
                    linked = (
                        client
                        .post(
                            BASE + "/native/business-modules/" + info["id"] + "/assets",
                            params={"project": PROJECT},
                            json=reference,
                        )
                        .raise_for_status()
                        .json()
                    )
                issue = domain.create_issue(actor, "验证模型", project=PROJECT, module_id=modules[1])
                before = [item["id"] for item in domain.list_issues(actor)]
                fixture = dict(**reference, free=free, modules=modules, issue=issue["id"])
                env = os.environ | dict(
                    TIANXUAN_API=base,
                    TIANXUAN_TOKEN=token,
                    TIANXUAN_PROJECT=PROJECT,
                    C07_FIXTURE=json.dumps(fixture),
                    C07_SYNC=str(root),
                )
                for key in ("APPDATA", "LOCALAPPDATA", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME"):
                    env[key] = str(root / key)
                calls.clear()
                run = subprocess.run(
                    [str(binary), "--headless", "--editor", "--path", str(project), "--script", "res://probe.gd"],
                    cwd=root,
                    env=env,
                    capture_output=True,
                    text=True,
                    encoding="utf8",
                    errors="replace",
                    timeout=150,
                )
                assert run.returncode == 0 and "SCRIPT ERROR" not in run.stderr, run.stdout + run.stderr
                trace = json.loads(
                    next(s[len("C07_NATIVE=") :] for s in run.stdout.splitlines() if s.startswith("C07_NATIVE="))
                )
                observed = list(calls)
                assert all(200 <= code < 300 for _, _, code in observed), observed
                writes = [(method, path) for method, path, _ in observed if method != "GET"]
                assert writes[0] == ("POST", BASE + "/workspace/conversations")
                assert all(
                    not (method != "GET" and ("/issues" in path or "/native/" in path)) for method, path, _ in observed
                )
                after = [item["id"] for item in domain.list_issues(actor)]
                assert before == after == [issue["id"]]
                chat = client.get(BASE + "/workspace/conversations/" + trace["conversation"]).raise_for_status().json()
                turns = chat["turns"]
                assert len(turns) == 2
                for turn, origin in zip(turns, (None, issue["id"]), strict=True):
                    assert turn["context_snapshot"] == {
                        "project": PROJECT,
                        "module_id": modules[1],
                        "issue_id": origin,
                        "references": [
                            {"kind": "editor", "object_id": "duobao:" + linked["asset_id"], "revision": revision}
                        ],
                    }
                return {
                    "state": "passed",
                    "ui": trace,
                    "issue_ids_before": before,
                    "issue_ids_after": after,
                    "sent_snapshots": [t["context_snapshot"] for t in turns],
                    "native_http": observed,
                    "model_sha256": model["sha256"],
                }
        finally:
            server.should_exit = True
            thread.join(10)
            domain.db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    for key in ("TIANXUAN_CHAT_BASE_URL", "TIANXUAN_CHAT_MODEL_KEY", "TIANXUAN_CHAT_MODEL"):
        os.environ.pop(key, None)
    with tempfile.TemporaryDirectory(prefix="c07-native-") as tmp:
        report = exercise(args.godot.resolve(), Path(tmp))
    digest = hashlib.sha256()
    with args.godot.open("rb") as binary:
        for block in iter(lambda: binary.read(1024 * 1024), b""):
            digest.update(block)
    report["editor_sha256"] = digest.hexdigest()
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
