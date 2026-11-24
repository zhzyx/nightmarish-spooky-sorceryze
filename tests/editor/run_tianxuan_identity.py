"""Run separate private editor processes against loopback and a throwaway OS credential service."""

import argparse
import hashlib
import importlib.util
import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from unittest.mock import patch

from editor_test_isolation import copy_editor
from run_tianxuan_connect import digest, fixture
from run_unified_settings_native import sanitized_environment

ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "customizations/components/godot-host/session_credentials.py"


def exercise(base, binary, source_loaded):
    with patch.dict(os.environ, {"GONGGONG_WORKSPACE": ""}):
        editor = copy_editor(binary, base / "engine")
    project = base / "project"
    project.mkdir()
    (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="Identity fixture"\n')
    shutil.copyfile(Path(__file__).with_name("tianxuan_identity.gd"), project / "probe.gd")
    if source_loaded:
        for path in (
            ROOT / "editor/docks/tianxuan/session_controller.gd",
            ROOT / "editor/docks/daqian/session_memory.gd",
            HELPER,
        ):
            shutil.copyfile(path, project / path.name)
    service_name = "Godot.Verification." + secrets.token_hex(16)
    spec = importlib.util.spec_from_file_location("private_store", HELPER)
    vault = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vault)
    vault.TIANXUAN_SERVICE = service_name
    password, device, personal, legacy = (secrets.token_urlsafe(27) for _ in range(4))
    launcher = secrets.token_urlsafe(27)
    actors = {device: "alice", personal: "bob", legacy: "alice", launcher: "alice"}
    observed = []
    cross_origin = []
    state = base / "mode"

    class Service(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            path = self.path.partition("?")[0]
            actor = actors.get(self.headers.get("Authorization", "").removeprefix("Bearer "))
            status, payload = 404, {}
            if path == "/api/v1/auth/config":
                status, payload = 200, {"mode": "accounts"}
            elif path == "/api/v1/auth/me":
                mode = state.read_text()
                status = 503 if mode == "offline" else (403 if mode == "revoked" else (200 if actor else 401))
                payload = {"id": actor, "role": "viewer", "name": actor} if status == 200 else {}
            elif path == "/api/v1/issues/slow":
                time.sleep(2)
                status = 401
            self.reply(status, payload)

        def do_POST(self):
            path = self.path.partition("?")[0]
            request = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))) or "{}")
            actor = actors.get(self.headers.get("Authorization", "").removeprefix("Bearer "))
            status, payload = 404, {}
            if path == "/api/v1/auth/editor-session" and state.read_text() != "legacy":
                if request == {"email": "user@example.test", "password": password}:
                    status, payload = 200, {"token": device}
                    observed.append("issued")
            elif path == "/api/v1/auth/session" and state.read_text() == "legacy":
                if request == {"email": "user@example.test", "password": password}:
                    status, payload = 200, {"token": legacy}
                    observed.append("legacy-issued")
            elif path == "/api/v1/auth/logout":
                observed.append("logout-" + str(actor))
                if actor == "alice":
                    actors.pop(self.headers["Authorization"].removeprefix("Bearer "), None)
                status, payload = 200, {"revoked": True}
            elif path == "/api/v1/issues/measure" and actor:
                observed.append("audit-" + actor)
                status, payload = 200, {"actor": actor}
            elif path == "/api/v1/issues/denied":
                status = 403
            self.reply(status, payload)

        def reply(self, status, data):
            body = json.dumps(data).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    class OtherService(Service):
        def do_GET(self):
            if self.headers.get("Authorization"):
                cross_origin.append("credential")
            self.reply(404, {})

        do_POST = do_GET

    phases = {}
    with fixture(Service) as port, fixture(OtherService) as other:
        api = f"http://127.0.0.1:{port}"
        secondary = f"http://127.0.0.1:{other}"

        def stored(action, origin=api):
            return vault.dispatch({
                "action": action,
                "service": "tianxuan-editor",
                "account": hashlib.sha256(origin.encode()).hexdigest(),
            })

        env = {
            key: value for key, value in sanitized_environment(base).items() if not key.startswith(("TX_", "TIANXUAN_"))
        }
        env.update(
            TIANXUAN_API=api,
            TX_OTHER_ORIGIN=secondary,
            TX_TEST_SERVICE=service_name,
            TX_STATE=str(state),
            TX_PYTHON=sys.executable,
            GONGGONG_PYTHON=sys.executable,
            TX_FIXTURE_PASSWORD=password,
            TX_FIXTURE_KEY=personal,
            TX_SOURCE_LOADED=str(int(source_loaded)),
        )
        try:
            for phase in ("login", "restart", "precedence", "offline", "logout", "legacy", "early_logout"):
                state.write_text(phase if phase in ("legacy", "offline") else "online")
                launch_env = {"TIANXUAN_TOKEN": launcher} if phase == "precedence" else {}
                result = subprocess.run(
                    [str(editor), "--headless", "--editor", "--path", str(project), "--script", "res://probe.gd"],
                    cwd=base,
                    env={**env, **launch_env, "TX_PHASE": phase},
                    capture_output=True,
                    timeout=90,
                )
                output = result.stdout + result.stderr
                assert not any(value.encode() in output for value in (device, personal, password, legacy, launcher)), (
                    "secret in editor diagnostics"
                )
                reports = [json.loads(line) for line in result.stdout.splitlines() if line.startswith(b"{")]
                if result.returncode or b"SCRIPT ERROR" in output or not reports or not reports[-1].get("passed"):
                    raise AssertionError(f"{phase}: {output[-5000:].decode('utf-8', 'replace')}")
                phases[phase] = reports[-1]["checks"]
                stored_record = stored("load")
                if phase in ("login", "restart", "precedence", "legacy"):
                    assert stored_record["status"] == "loaded", "credential not persisted to native store"
                    record = json.loads(stored_record["secret"])
                    assert record["origin"] == api and record["token"] == {"login": device, "legacy": legacy}.get(
                        phase, personal
                    )
                    assert record["user_id"] == ("bob" if phase in ("precedence", "restart") else "alice")
                    assert password not in stored_record["secret"]
                else:
                    assert stored_record == {"status": "missing"}, "local grant survived logout/revocation"
            assert observed.count("issued") == observed.count("legacy-issued") == 1
            assert observed.count("logout-alice") == 2 and "logout-bob" not in observed
            assert "audit-bob" in observed and not cross_origin
            for directory in (base / "engine/editor_data", project):
                for path in directory.rglob("*"):
                    if path.is_file():
                        contents = path.read_bytes()
                        assert not any(
                            value.encode() in contents for value in (device, personal, password, legacy, launcher)
                        ), "plaintext in project or editor settings"
        finally:
            for origin in (api, secondary):
                assert stored("delete", origin)["status"] == "deleted"
    return {
        "passed": True,
        "mode": "source_loaded" if source_loaded else "compiled_native",
        "platform": sys.platform,
        "binary_sha256": digest(editor),
        "phases": phases,
        "service_observations": observed,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--source-loaded", action="store_true")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="tianxuan-identity-") as temp:
        report = exercise(Path(temp), args.godot.resolve(strict=True), args.source_loaded)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": True, "mode": report["mode"], "phases": list(report["phases"])}))
