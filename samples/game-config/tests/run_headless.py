#!/usr/bin/env python3
"""Real HTTP/WebSocket/Godot acceptance against a disposable local Tianxuan.

Run with the repository's server dependencies installed. No production accounts,
services or Godot settings are used. Tokens exist only in process memory/env.
"""

from __future__ import annotations

import argparse
import copy
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
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

SAMPLE = Path(__file__).resolve().parents[1]
ROOT = SAMPLE.parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", required=True, type=Path)
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT / "customizations/components/tianxuan/server"))
    # The fixture must never inherit production authentication/deployment settings.
    for key in tuple(os.environ):
        if key.startswith("TIANXUAN_"):
            os.environ.pop(key)
    import uvicorn
    from api import create_app
    from tianxuan_core import Tianxuan

    with tempfile.TemporaryDirectory(prefix=".acceptance-", dir=SAMPLE) as directory:
        temp = Path(directory)
        project_dir = temp / "project"
        shutil.copytree(
            SAMPLE, project_dir, ignore=shutil.ignore_patterns(".acceptance-*", ".godot", "__pycache__", "*.uid")
        )
        env = {
            **os.environ,
            "XDG_CONFIG_HOME": str(temp / "config"),
            "XDG_DATA_HOME": str(temp / "data"),
            "XDG_CACHE_HOME": str(temp / "cache"),
        }
        unit = subprocess.run(
            [str(args.godot.resolve()), "--headless", "--path", str(project_dir), "--script", "res://tests/unit.gd"],
            env=env,
            capture_output=True,
            text=True,
            timeout=20,
        )
        assert unit.returncode == 0 and '"passed":true' in unit.stdout, (
            "Godot unit validation failed: " + unit.stdout + unit.stderr
        )
        print("PASS: candidate isolation, explicit ack, rejected/stale values, defensive copies", flush=True)
        smoke = subprocess.run(
            [str(args.godot.resolve()), "--headless", "--path", str(project_dir), "--quit-after", "3"],
            env=env,
            capture_output=True,
            text=True,
            timeout=20,
        )
        assert smoke.returncode == 0 and "SCRIPT ERROR" not in smoke.stdout + smoke.stderr, (
            "Example scene startup failed: " + smoke.stdout + smoke.stderr
        )
        print("PASS: runnable example scene starts without credentials", flush=True)

        store = Tianxuan(str(temp / "server.sqlite"))
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(128)
        base = f"http://127.0.0.1:{listener.getsockname()[1]}"
        server = uvicorn.Server(uvicorn.Config(create_app(store), log_level="error", access_log=False))
        thread = threading.Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
        thread.start()
        process = None
        token = ""

        def request(method: str, path: str, body=None, expected=200, bearer=None):
            headers = {"Content-Type": "application/json"}
            credential = token if bearer is None else bearer
            if credential:
                headers["Authorization"] = "Bearer " + credential
            req = urllib.request.Request(
                base + path, data=None if body is None else json.dumps(body).encode(), headers=headers, method=method
            )
            try:
                with urllib.request.urlopen(req, timeout=5) as response:
                    status, raw = response.status, response.read()
            except urllib.error.HTTPError as error:
                status, raw = error.code, error.read()
            assert status in (expected if isinstance(expected, tuple) else (expected,)), (
                f"{method} {path}: expected {expected}, got {status}"
            )
            return json.loads(raw)

        events: list[dict[str, Any]] = []
        event_lock = threading.Lock()

        def wait_for(predicate, description, timeout=12):
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if predicate():
                    return
                if process is not None and process.poll() is not None:
                    raise AssertionError(f"Godot stopped ({process.returncode}) while waiting for {description}")
                time.sleep(0.025)
            raise AssertionError("Timed out waiting for " + description)

        def has_event(expected, count=1):
            with event_lock:
                return sum(all(event.get(k) == v for k, v in expected.items()) for event in events) >= count

        def read_output():
            for line in process.stdout:
                if line.startswith("GAME_CONFIG_EVENT "):
                    with event_lock:
                        events.append(json.loads(line.removeprefix("GAME_CONFIG_EVENT ")))

        try:
            wait_for(lambda: server.started, "local server startup")
            password = secrets.token_urlsafe(24)
            request(
                "POST",
                "/api/v1/auth/register",
                {"tenant_name": "Godot acceptance", "email": "godot@example.test", "password": password},
            )
            token = request("POST", "/api/v1/auth/session", {"email": "godot@example.test", "password": password})[
                "token"
            ]
            features: list[dict[str, Any]] = [
                {
                    "id": "combat",
                    "name": "Combat",
                    "description": "Demo",
                    "entries": [
                        {
                            "id": "damage",
                            "name": "Damage",
                            "kind": "parameter",
                            "type": "number",
                            "value": 10,
                            "default": 10,
                            "description": "Damage per hit",
                            "min": 0,
                            "max": 1000,
                        },
                        {
                            "id": "large_content",
                            "name": "Large content",
                            "kind": "content",
                            "type": "string",
                            "value": "配置" * 150000,
                            "default": "",
                        },
                    ],
                }
            ]
            project = request(
                "POST",
                "/api/v1/game-config/projects",
                {"title": "Disposable Godot acceptance", "features": features},
                201,
            )
            endpoint = "/api/v1/game-config/projects/" + project["id"]
            assert request("GET", endpoint + "/clients")["clients"] == []
            env.update(TIANXUAN_TOKEN=token, GAME_CONFIG_URL=base, GAME_CONFIG_PROJECT_ID=project["id"])
            process = subprocess.Popen(
                [
                    str(args.godot.resolve()),
                    "--headless",
                    "--path",
                    str(project_dir),
                    "--script",
                    "res://tests/live.gd",
                ],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            output_thread = threading.Thread(target=read_output, daemon=True)
            output_thread.start()

            def clients_match(status, version):
                clients = request("GET", endpoint + "/clients")["clients"]
                return len(clients) == 1 and clients[0]["status"] == status and clients[0]["version"] == version

            wait_for(lambda: clients_match("pending", 0), "pending before game application")
            wait_for(lambda: has_event({"applied": 1, "damage": 10}), "initial game application")
            wait_for(lambda: clients_match("applied", 1), "initial server receipt")
            print("PASS: authenticated 900 KiB snapshot and pending → applied receipt", flush=True)

            def update(value, version):
                changed = copy.deepcopy(features)
                changed[0]["entries"][0]["value"] = value
                return request(
                    "PUT",
                    endpoint,
                    {"title": "Disposable Godot acceptance", "features": changed, "expected_version": version},
                )

            project = update(20, 1)
            wait_for(
                lambda: has_event({"applied": 2, "damage": 20}, 2),
                "automatic reconnect and second authoritative receipt",
            )
            wait_for(lambda: clients_match("applied", 2), "reconnected server receipt")
            assert has_event({"state": "reconnecting"})
            print(
                "PASS: hot update, actual socket disconnect, automatic reconnect and authoritative reapply", flush=True
            )

            project = update(900, 2)
            wait_for(
                lambda: has_event({"rejected": 3, "damage": 20, "applied": 2}),
                "game constraint rejection with last value intact",
            )
            wait_for(lambda: clients_match("failed", 2), "failed status preserving actual applied version")
            print("PASS: game rejects valid service configuration and retains version 2 / damage 20", flush=True)

            invalid = copy.deepcopy(features)
            invalid[0]["entries"][0]["value"] = "wrong type"
            request("PUT", endpoint, {"title": "Invalid", "features": invalid, "expected_version": 3}, (400, 422))
            request("PUT", endpoint, {"title": "Conflict", "features": features, "expected_version": 1}, 409)
            assert request("GET", endpoint)["version"] == 3
            project = update(30, 3)
            wait_for(lambda: has_event({"applied": 4, "damage": 30}), "recovery after rejection")
            wait_for(lambda: clients_match("applied", 4), "recovered receipt")
            request("POST", f"/api/v1/docs/{project['id']}/versions/1/restore", {"expected_version": 4})
            wait_for(lambda: has_event({"applied": 5, "damage": 10}), "restored history delivered as new version")
            wait_for(lambda: clients_match("applied", 5), "restored receipt")
            print(
                "PASS: invalid/conflicting writes rejected; subsequent update and historical restore apply live",
                flush=True,
            )

            request(
                "POST",
                "/api/v1/auth/register",
                {"tenant_name": "Other tenant", "email": "other@example.test", "password": password},
                bearer="",
            )
            other = request(
                "POST", "/api/v1/auth/session", {"email": "other@example.test", "password": password}, bearer=""
            )["token"]
            request("GET", endpoint, expected=(403, 404), bearer=other)
            request("GET", endpoint, expected=(400, 401), bearer="")
            process.terminate()
            process.wait(timeout=5)
            process = None
            wait_for(lambda: request("GET", endpoint + "/clients")["clients"] == [], "disconnected runtime removed")
            print("PASS: tenant/authentication isolation and disconnected runtime removal", flush=True)
            print("GAME_CONFIG_ACCEPTANCE passed", flush=True)
        finally:
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            server.should_exit = True
            thread.join(timeout=10)
            listener.close()
            store.db.close()


if __name__ == "__main__":
    main()
