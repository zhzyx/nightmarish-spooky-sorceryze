"""Ordinary main and installed remote worker over actual loopback HTTP."""

import hashlib
import importlib
import json
import os
import shutil
import socket
import sys
import threading
import time
from pathlib import Path

import httpx
import pytest
import uvicorn
from native_node import NativeNode
from native_store import NativeStore
from native_worker import NativeWorker
from test_native_entry_context import policy
from test_native_entry_normal import HERE, PROGRAM
from tianxuan_core import Tianxuan


def test_remote_ordinary_main(tmp_path, monkeypatch):
    root = tmp_path
    node = os.environ.get("NATIVE_TEST_NODE") or shutil.which("node")
    if not node:
        pytest.skip("Installed Node required")
    program = root / "deterministic_installation.py"
    program.write_text(PROGRAM, encoding="utf-8")
    python = str(Path(sys.executable).resolve())
    driver = str(HERE.parent / "sinan-workorders" / "native_entry_driver.mjs")
    environment = {k: v for k, v in os.environ.items() if k.upper() in {"SYSTEMROOT", "WINDIR"}}
    files = {p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in (python, node, str(program), driver)}
    commands = {
        r: dict(argv=[python, "-X", "utf8", str(program), r], env=environment)
        for r in ("planner", "producer", "checker", "reviewer")
    }
    commands["dispatcher"] = dict(argv=[node, driver], env=environment)
    spec = dict(
        version=2,
        mode="deterministic-test",
        identity="deterministic-normal-entry-test",
        files=files,
        commands=commands,
        principals=dict(
            producer="test-producer",
            checker="test-checker",
            reviewer="test-reviewer",
            publisher="test-publisher",
        ),
        scopes={"text": {"outputs": ["text/output"]}},
        complexity={"simple": ["text"]},
        catalog=[dict(id="installed", available=True, targets=["agent"], capabilities=["text"])],
    )
    manifest = root / "installation.json"
    manifest.write_text(json.dumps(spec), encoding="utf-8")
    env = dict(
        TIANXUAN_DB=str(root / "domain.sqlite"),
        TIANXUAN_NATIVE_DB=str(root / "native.sqlite"),
        TIANXUAN_STORAGE_MODE="native",
        TIANXUAN_NATIVE_INSTALLATION=str(manifest),
        TIANXUAN_NATIVE_INSTALLATION_SHA256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
        TIANXUAN_NATIVE_STATE=str(root / "state"),
    )
    domain = Tianxuan(str(root / "domain.sqlite"))
    actor = domain.register("remote", "remote@example.invalid", "password123")["user_id"]
    tenant = domain.actor_context(actor)["tenant"]
    domain.db.close()
    node_worker = NativeWorker(
        NativeStore(root / "node.sqlite"),
        root / "node-work",
        {"installed": {**commands["producer"], "timeout": 600, "log_bytes": 900000}},
        lambda *args: True,
        authorize=lambda *args: True,
    )
    import native_node

    installation = node_worker.installation("installed")
    runtime = policy(
        root,
        env["TIANXUAN_NATIVE_INSTALLATION_SHA256"],
        remote=dict(
            profiles={"installed": dict(timeout=600, installation=installation)},
            nodes={
                "node-a": dict(
                    tenant=tenant,
                    token_sha256=hashlib.sha256(b"local-secret").hexdigest(),
                    profiles={"installed": installation},
                    capacity=1,
                    enabled=True,
                    package=hashlib.sha256(Path(native_node.__file__).read_bytes()).hexdigest(),
                )
            },
        ),
    )
    env.update(TIANXUAN_NATIVE_RUNTIME=str(runtime.path), TIANXUAN_NATIVE_RUNTIME_SHA256=runtime.sha256)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    sys.modules.pop("main", None)
    main = importlib.import_module("main")
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    url = "http://127.0.0.1:" + str(sock.getsockname()[1])
    server = uvicorn.Server(uvicorn.Config(main.app, log_level="error", timeout_graceful_shutdown=3))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    deadline = time.monotonic() + 20
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.01)
    assert server.started
    worker = NativeNode(node_worker, url, "local-secret")
    try:
        with httpx.Client(base_url=url, timeout=35) as client:
            login = client.post(
                "/api/v1/auth/session", json=dict(email="remote@example.invalid", password="password123")
            )
            headers = {"Authorization": "Bearer " + login.json()["token"]}
            requirement = client.post(
                "/api/v1/requirements",
                headers=headers,
                json=dict(
                    request_id="remote",
                    title="Remote entry",
                    outcome="Output",
                    scope="Text",
                    acceptance="output must equal deterministic accepted output",
                ),
            ).json()["id"]
            response = client.post(
                "/api/v1/native/entry/execute",
                headers=headers,
                json=dict(requirement=requirement, call_id="execute", scopes=["text"]),
            )
            assert response.status_code == 200, response.text
            key = response.json()["entry"]
            worker.step()
            worker.pool.shutdown(wait=True)
            for future in worker.futures:
                future.result()
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                status = client.get("/api/v1/native/entry/" + key, headers=headers).json()
                if status["state"] == "delivered" or status["failures"]:
                    break
                time.sleep(0.05)
            assert status["state"] == "delivered", (status, getattr(main._NATIVE_ENTRY, "last_denied", None))
            assert status["progress"]["percent"] == 100
            assert list((root / "node-work").rglob("physical-producer-marker"))
            assert not list((root / "state/workers").rglob("physical-producer-marker"))
    finally:
        worker.pool.shutdown(wait=True)
        server.should_exit = True
        thread.join(15)
        sock.close()
        main._STORE.db.close()
        sys.modules.pop("main", None)
        assert not thread.is_alive()
