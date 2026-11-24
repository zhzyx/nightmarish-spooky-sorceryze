"""Verify missing-device-endpoint compatibility without production credentials or providers."""

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
    sources = [
        ROOT / "editor/docks/tianxuan/session_controller.gd",
        ROOT / "editor/docks/daqian/session_memory.gd",
        HELPER,
        Path(__file__),
        Path(__file__).with_name("tianxuan_legacy_key_identity.gd"),
    ]
    fingerprints = {str(path.relative_to(ROOT)): digest(path) for path in sources}
    original_binary = digest(binary)
    with patch.dict(os.environ, {"GONGGONG_WORKSPACE": ""}):
        editor = copy_editor(binary, base / "engine")
    project = base / "project"
    project.mkdir()
    (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="Private legacy identity"\n')
    shutil.copy2(Path(__file__).with_name("tianxuan_legacy_key_identity.gd"), project / "probe.gd")
    if source_loaded:
        for path in sources[:3]:
            shutil.copy2(path, project / path.name)
    service_name = "Godot.Verification." + secrets.token_hex(16)
    spec = importlib.util.spec_from_file_location("private_legacy_key_store", HELPER)
    vault = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vault)
    vault.TIANXUAN_SERVICE = service_name
    personal, device, replacement = (secrets.token_urlsafe(27) for _ in range(3))
    actors = {personal: "bob", device: "alice", replacement: "charlie"}
    private_values = (personal, device, replacement)
    state = base / "mode"
    state.write_text("online")
    entered = base / "entered"
    observed = []
    failures = []
    cross_origin = []

    class Service(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def reply(self, status, payload):
            data = json.dumps(payload).encode()
            try:
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def do_GET(self):
            route = self.path.partition("?")[0]
            bearer = self.headers.get("Authorization", "").removeprefix("Bearer ").strip()
            actor = actors.get(bearer)
            mode = state.read_text()
            if route == "/api/v1/auth/config":
                self.reply(200, {"mode": "keys"})
                return
            if route == "/api/v1/slow":
                entered.touch()
                time.sleep(0.5)
                self.reply(401, {})
                return
            if route != "/api/v1/auth/me":
                self.reply(404, {})
                return
            observed.append("me-" + str(actor) + "-" + mode)
            status = 200 if actor else 401
            payload = {"id": actor, "role": "viewer", "name": actor, "tenant_id": "private-fixture"}
            if bearer == personal:
                if mode.startswith("me_") and mode.removeprefix("me_").isdigit():
                    status = int(mode.removeprefix("me_"))
                elif mode == "me_disconnect":
                    self.close_connection = True
                    return
                elif mode == "me_missing_id":
                    payload.pop("id")
                elif mode == "me_null_id":
                    payload["id"] = None
                elif mode == "me_missing_role":
                    payload.pop("role")
                elif mode == "me_unknown_role":
                    payload["role"] = "unrecognized-permission"
                elif mode == "delay_me":
                    entered.touch()
                    time.sleep(0.5)
                elif mode == "replace_persisted":
                    previous = stored("load")
                    if previous.get("status") != "loaded" or previous.get("secret") != original_record:
                        failures.append("original persistent login changed before independent replacement")
                    updated = stored("save", concurrent_record, digest_text(original_record))
                    if updated.get("status") != "saved":
                        failures.append("private concurrent vault update failed")
            self.reply(status, payload)

        def do_POST(self):
            route = self.path.partition("?")[0]
            self.rfile.read(int(self.headers.get("Content-Length", "0")))
            bearer = self.headers.get("Authorization", "").removeprefix("Bearer ").strip()
            mode = state.read_text()
            if route == "/api/v1/auth/logout":
                failures.append("temporary compatibility attempted credential revocation")
                self.reply(200, {})
                return
            if route != "/api/v1/auth/device-session":
                self.reply(404, {})
                return
            observed.append("enrollment-" + mode)
            if bearer != personal:
                failures.append("unexpected enrollment credential")
                self.reply(401, {})
                return
            status, payload = 404, {"error": "PRIVATE_SERVER_BODY_" + personal}
            if mode.startswith("enrollment_") and mode.removeprefix("enrollment_").isdigit():
                status = int(mode.removeprefix("enrollment_"))
            elif mode == "enrollment_disconnect":
                self.close_connection = True
                return
            elif mode == "enrollment_empty":
                status, payload = 200, {}
            elif mode in ("enrollment_echo", "enrollment_echo_spaced"):
                status, payload = 200, {"token": personal}
            elif mode == "delay_enrollment":
                entered.touch()
                time.sleep(0.5)
            self.reply(status, payload)

    class OtherService(Service):
        def do_GET(self):
            if self.headers.get("Authorization"):
                cross_origin.append("credential")
            self.reply(404, {})

        do_POST = do_GET

    def digest_text(value):
        return hashlib.sha256(value.encode()).hexdigest()

    with fixture(Service) as port, fixture(OtherService) as other:
        api = f"http://127.0.0.1:{port}"

        def stored(action, secret=None, expected=None):
            request = {"action": action, "service": "tianxuan-editor", "account": digest_text(api)}
            if secret is not None:
                request["secret"] = secret
            if expected is not None:
                request["expected"] = expected
            return vault.dispatch(request)

        original_record = json.dumps({
            "version": 1,
            "origin": api,
            "project": "saved-project",
            "user_id": "alice",
            "owned": True,
            "token": device,
            "binding_id": "private-original",
        })
        concurrent_record = json.dumps({
            **json.loads(original_record),
            "user_id": "charlie",
            "token": replacement,
            "binding_id": "private-concurrent",
        })
        assert stored("save", original_record)["status"] == "saved"
        env = {
            key: value for key, value in sanitized_environment(base).items() if not key.startswith(("TX_", "TIANXUAN_"))
        }
        output = base / "result.json"
        env.update(
            TIANXUAN_API=api,
            TX_OTHER_ORIGIN=f"http://127.0.0.1:{other}",
            TX_STATE=str(state),
            TX_ENTERED=str(entered),
            TX_TEST_SERVICE=service_name,
            TX_PYTHON=sys.executable,
            TX_PERSONAL_KEY=personal,
            TX_SOURCE_LOADED=str(int(source_loaded)),
            TX_REPORT=str(output),
        )
        if sys.platform == "darwin":
            env["TX_VAULT_HOME"] = str(Path.home())
        try:
            try:
                result = subprocess.run(
                    [str(editor), "--headless", "--editor", "--path", str(project), "--script", "res://probe.gd"],
                    cwd=base,
                    env=env,
                    capture_output=True,
                    timeout=90,
                )
            except subprocess.TimeoutExpired as error:
                diagnostics = (error.stdout or b"") + (error.stderr or b"")
                assert not any(value.encode() in diagnostics for value in private_values), (
                    "private credential leaked into diagnostics"
                )
                raise AssertionError(
                    "private legacy identity probe timed out: " + diagnostics[-7000:].decode("utf-8", "replace")
                ) from None
            diagnostics = result.stdout + result.stderr
            assert not any(value.encode() in diagnostics for value in private_values), (
                "private credential leaked into diagnostics"
            )
            assert b"PRIVATE_SERVER_BODY_" not in diagnostics, "raw service body leaked into diagnostics"
            native = json.loads(output.read_text()) if output.is_file() else {}
            assert result.returncode == 0 and b"SCRIPT ERROR" not in diagnostics and native.get("passed"), diagnostics[
                -5000:
            ].decode("utf-8", "replace")
            assert not failures and not cross_origin, failures + cross_origin
            assert stored("load") == {"status": "loaded", "secret": concurrent_record}, (
                "temporary session changed another process's persisted login"
            )
            for mode in (
                "enrollment_401",
                "enrollment_403",
                "enrollment_500",
                "enrollment_503",
                "enrollment_disconnect",
                "enrollment_empty",
                "enrollment_echo",
                "enrollment_echo_spaced",
            ):
                assert "me-bob-" + mode not in observed, "forbidden fallback attempted after " + mode
            for directory in (base / "engine/editor_data", project):
                for path in directory.rglob("*"):
                    if path.is_file():
                        assert not any(value.encode() in path.read_bytes() for value in private_values), (
                            "plaintext credential in project/editor data"
                        )
        finally:
            assert stored("delete")["status"] == "deleted"
    stale = [name for name, sha in fingerprints.items() if digest(ROOT / name) != sha]
    assert not stale and digest(binary) == original_binary, "candidate changed during legacy identity validation"
    return {
        "passed": True,
        "mode": "source_loaded" if source_loaded else "compiled_native",
        "binary_sha256": original_binary,
        "source_sha256": fingerprints,
        "checks": native["checks"],
        "service_observations": observed,
        "stale_sources": stale,
        "private_vault_preserved": True,
        "credential_privacy_passed": True,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--source-loaded", action="store_true")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="tianxuan-legacy-key-") as temporary:
        report = exercise(Path(temporary), args.godot.resolve(strict=True), args.source_loaded)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"passed": True, "mode": report["mode"], "checks": len(report["checks"])}))
