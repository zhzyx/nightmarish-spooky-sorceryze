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
from run_tianxuan_legacy_key_identity import exercise as exercise_legacy_key
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
    launcher, other_device, same_user = (secrets.token_urlsafe(27) for _ in range(3))
    actors = {device: "alice", personal: "bob", legacy: "alice", launcher: "alice", same_user: "alice"}
    private_values = (device, personal, password, legacy, launcher, other_device, same_user)
    derived = {}
    observed = []
    cross_origin = []
    state = base / "mode"
    enrolled = base / "enrolled"
    saved_marker = base / "saved"

    class Service(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            path = self.path.partition("?")[0]
            bearer = self.headers.get("Authorization", "").removeprefix("Bearer ").strip()
            actor = actors.get(bearer)
            status, payload = 404, {}
            if path == "/api/v1/auth/config":
                status, payload = 200, {"mode": "accounts"}
            elif path == "/api/v1/auth/me":
                mode = state.read_text()
                status = 503 if mode == "offline" else (403 if mode == "revoked" else (200 if actor else 401))
                if bearer in derived and derived[bearer]["mode"] == "invalid_me":
                    status = 403
                if mode == "saved_offline" and bearer == device:
                    status = 503
                if mode == "prior_revoked" and derived.get(bearer, {}).get("parent") == same_user:
                    status = 401
                if mode == "replace_during_check" and derived.get(bearer, {}).get("parent") == launcher:
                    concurrent = json.loads(stored("load")["secret"])
                    concurrent.update(user_id="bob", token=personal, owned=False, project="external")
                    replace_record(concurrent)
                    observed.append("concurrent-switch")
                if status == 200:
                    payload = {"id": actor, "role": "viewer", "tenant_id": "local-fixture", "name": actor}
            elif path == "/api/v1/issues/slow":
                time.sleep(2)
                status = 401
            self.reply(status, payload)

        def do_POST(self):
            path = self.path.partition("?")[0]
            request = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))) or "{}")
            bearer = self.headers.get("Authorization", "").removeprefix("Bearer ").strip()
            actor = actors.get(bearer)
            status, payload = 404, {}
            if path == "/api/v1/auth/editor-session" and state.read_text() != "legacy":
                if request == {"email": "user@example.test", "password": password}:
                    grant = other_device if "issued" in observed else device
                    actors[grant] = "alice"
                    status, payload = 200, {"token": grant}
                    observed.append("issued")
            elif path == "/api/v1/auth/session" and state.read_text() == "legacy":
                if request == {"email": "user@example.test", "password": password}:
                    status, payload = 200, {"token": legacy}
                    observed.append("legacy-issued")
            elif path == "/api/v1/auth/device-session":
                status = 401
                if actor and state.read_text() == "deny_enrollment":
                    status = 403
                    observed.append("enrollment-denied")
                elif actor and state.read_text() in ("echo_enrollment", "echo_cancel_enrollment"):
                    observed.append("enrollment-echo")
                    if state.read_text() == "echo_cancel_enrollment":
                        enrolled.touch()
                        time.sleep(0.5)
                    status, payload = 200, {"token": bearer}
                elif actor:
                    mode = state.read_text()
                    token = secrets.token_urlsafe(27)
                    actors[token] = actor
                    derived[token] = {"actor": actor, "mode": mode, "parent": bearer}
                    observed.append("enrolled-" + actor + "-" + mode)
                    if mode == "cancel_enrollment":
                        enrolled.touch()
                        time.sleep(0.5)
                    elif mode == "cas_competition":
                        assert stored("save", secret=competing_record)["status"] == "saved"
                    status, payload = (503 if mode == "failed_enrollment" else 200), {"token": token}
            elif path == "/api/v1/auth/logout":
                observed.append("logout-" + str(actor))
                if bearer in (personal, launcher):
                    observed.append("shared-key-revoked")
                actors.pop(bearer, None)
                status, payload = 200, {"revoked": True}
            elif path == "/api/v1/issues/measure" and actor:
                observed.append("audit-" + actor)
                if self.headers.get("Authorization") == "Bearer " + device:
                    observed.append("original-device-used")
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

        def stored(action, origin=api, secret=None):
            request = {
                "action": action,
                "service": "tianxuan-editor",
                "account": hashlib.sha256(origin.encode()).hexdigest(),
            }
            if secret is not None:
                request["secret"] = secret
            return vault.dispatch(request)

        old_record = json.dumps({
            "version": 1,
            "origin": api,
            "project": "legacy-project",
            "user_id": "bob",
            "owned": False,
            "token": personal,
            "binding_id": "pre-upgrade",
        })
        competing_record = json.dumps({**json.loads(old_record), "binding_id": "other-process-login"})
        spaced_record = json.dumps({**json.loads(old_record), "token": "  " + personal + "  "})
        migration_modes = {
            "migrate_failure": "invalid_me",
            "migrate_cancel": "cancel_enrollment",
            "migrate_cas": "cas_competition",
            "migrate_denied": "deny_enrollment",
            "migrate_echo": "echo_enrollment",
            "migrate_echo_cancel": "echo_cancel_enrollment",
            "migrate_logout_during_save": "online",
            "migrate": "online",
        }

        def replace_record(record):
            original = stored("load")["secret"]
            updated = vault.dispatch({
                "action": "save",
                "service": "tianxuan-editor",
                "account": hashlib.sha256(api.encode()).hexdigest(),
                "secret": json.dumps(record),
                "expected": hashlib.sha256(original.encode()).hexdigest(),
            })
            assert updated["status"] == "saved"

        env = {
            key: value for key, value in sanitized_environment(base).items() if not key.startswith(("TX_", "TIANXUAN_"))
        }
        env.update(
            TIANXUAN_API=api,
            TX_OTHER_ORIGIN=secondary,
            TX_TEST_SERVICE=service_name,
            TX_STATE=str(state),
            TX_ENROLLED=str(enrolled),
            TX_SAVED=str(saved_marker),
            TX_PYTHON=sys.executable,
            GONGGONG_PYTHON=sys.executable,
            TX_FIXTURE_PASSWORD=password,
            TX_FIXTURE_KEY=personal,
            TX_SAME_ACCOUNT_KEY=same_user,
            TX_SECOND_KEY=launcher,
            TX_SOURCE_LOADED=str(int(source_loaded)),
        )
        if sys.platform == "darwin":
            env["TX_VAULT_HOME"] = str(Path.home())
        try:
            for phase in (
                "login",
                "same_account",
                "restart",
                "precedence",
                "offline",
                "logout",
                "legacy",
                "early_logout",
                "rebind",
                "concurrent",
                "logout_during_update",
                "authenticate_migrate",
                *migration_modes,
                "migration_restart",
                "migration_logout",
            ):
                if phase == "same_account":
                    original = json.loads(stored("load")["secret"])
                    original.pop("binding_id")
                    replace_record(original)
                state.write_text(migration_modes.get(phase, phase if phase in ("legacy", "offline") else "online"))
                if phase in migration_modes or phase == "authenticate_migrate":
                    assert (
                        stored("save", secret=spaced_record if phase == "migrate_echo" else old_record)["status"]
                        == "saved"
                    )
                    enrolled.unlink(missing_ok=True)
                    saved_marker.unlink(missing_ok=True)
                enrollments_before = len(derived)
                launch_env = {"TIANXUAN_TOKEN": launcher} if phase == "precedence" else {}
                result = subprocess.run(
                    [str(editor), "--headless", "--editor", "--path", str(project), "--script", "res://probe.gd"],
                    cwd=base,
                    env={**env, **launch_env, "TX_PHASE": phase},
                    capture_output=True,
                    timeout=90,
                )
                output = result.stdout + result.stderr
                assert not any(value.encode() in output for value in (*private_values, *derived)), (
                    "secret in editor diagnostics"
                )
                reports = [json.loads(line) for line in result.stdout.splitlines() if line.startswith(b"{")]
                if result.returncode or b"SCRIPT ERROR" in output or not reports or not reports[-1].get("passed"):
                    raise AssertionError(f"{phase}: {output[-5000:].decode('utf-8', 'replace')}")
                phases[phase] = reports[-1]["checks"]
                stored_record = stored("load")
                selected_token = (
                    json.loads(stored_record["secret"])["token"] if stored_record["status"] == "loaded" else None
                )
                for grant in list(derived)[enrollments_before:]:
                    # The automated launcher owns its process-only login; it never uses the desktop vault.
                    launched = phase == "precedence" and derived[grant]["parent"] == launcher
                    assert grant == selected_token or launched or grant not in actors, (
                        f"{phase}: newly created but unselected device authorization survived"
                    )
                if phase in (
                    "migrate_failure",
                    "migrate_cancel",
                    "migrate_cas",
                    "migrate_denied",
                    "migrate_echo",
                    "migrate_echo_cancel",
                ):
                    expected = (
                        competing_record
                        if phase == "migrate_cas"
                        else spaced_record
                        if phase == "migrate_echo"
                        else old_record
                    )
                    assert stored_record == {"status": "loaded", "secret": expected}, phase
                elif phase in (
                    "login",
                    "same_account",
                    "restart",
                    "precedence",
                    "legacy",
                    "rebind",
                    "concurrent",
                    "migrate",
                    "migration_restart",
                ):
                    assert stored_record["status"] == "loaded", "credential not persisted to native store"
                    record = json.loads(stored_record["secret"])
                    assert record["origin"] == api
                    if phase == "concurrent":
                        assert record["token"] == personal and record["owned"] is False
                        assert record["project"] == "external"
                    else:
                        assert record["owned"] is True
                        if phase in ("login", "same_account", "legacy"):
                            assert record["token"] == (legacy if phase == "legacy" else device)
                        else:
                            parent = launcher if phase == "rebind" else personal
                            assert record["token"] in derived and derived[record["token"]]["parent"] == parent
                            assert record["token"] != parent
                    assert record["user_id"] == (
                        "alice" if phase in ("login", "same_account", "legacy", "rebind") else "bob"
                    )
                    if phase == "same_account":
                        assert record == {**original, "project": "project-b"}
                        assert other_device not in actors and device in actors
                        assert all(token not in actors for token in derived), "unused confirmation grants survived"
                    if phase == "migration_restart":
                        assert len(derived) == enrollments_before, "owned device was enrolled twice"
                    assert password not in stored_record["secret"]
                else:
                    assert stored_record == {"status": "missing"}, "local grant survived logout/revocation"
            assert observed.count("issued") == 2 and observed.count("legacy-issued") == 1
            assert device not in actors and legacy not in actors and other_device not in actors, observed
            assert (
                "shared-key-revoked" not in observed
                and personal in actors
                and launcher in actors
                and same_user in actors
            )
            assert all(token not in actors for token, info in derived.items() if info["actor"] == "bob")
            assert observed.count("enrolled-bob-online") == 7
            assert observed.count("enrolled-bob-invalid_me") == 2
            assert observed.count("enrolled-bob-cancel_enrollment") == 2
            assert observed.count("enrolled-bob-failed_enrollment") == 1
            assert observed.count("enrolled-bob-cas_competition") == 1
            assert observed.count("enrollment-denied") == 1
            assert observed.count("enrollment-echo") == 2
            assert {"original-device-used", "concurrent-switch", "audit-bob"} <= set(observed) and not cross_origin
            for directory in (base / "engine/editor_data", project):
                for path in directory.rglob("*"):
                    if path.is_file():
                        contents = path.read_bytes()
                        assert not any(value.encode() in contents for value in (*private_values, *derived)), (
                            "plaintext in project or editor settings"
                        )
        finally:
            for origin in (api, secondary):
                assert stored("delete", origin)["status"] == "deleted"
    return {
        "passed": True,
        "mode": "source_loaded" if source_loaded else "compiled_native",
        "platform": sys.platform,
        "binary_sha256": digest(editor),
        "source_sha256": {
            str(path.relative_to(ROOT)).replace("\\", "/"): digest(path)
            for path in (
                ROOT / "editor/docks/tianxuan/session_controller.gd",
                ROOT / "editor/docks/daqian/session_memory.gd",
                HELPER,
                Path(__file__),
                Path(__file__).with_name("tianxuan_identity.gd"),
            )
        },
        "phases": phases,
        "service_observations": observed,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--source-loaded", action="store_true")
    args = parser.parse_args()
    candidate = args.godot.resolve(strict=True)
    candidate_sha = digest(candidate)
    inputs = (
        ROOT / "editor/docks/tianxuan/session_controller.gd",
        ROOT / "editor/docks/daqian/session_memory.gd",
        HELPER,
        Path(__file__),
        Path(__file__).with_name("tianxuan_identity.gd"),
        Path(__file__).with_name("run_tianxuan_legacy_key_identity.py"),
        Path(__file__).with_name("tianxuan_legacy_key_identity.gd"),
    )
    fingerprints = {str(path.relative_to(ROOT)): digest(path) for path in inputs}
    with tempfile.TemporaryDirectory(prefix="tianxuan-identity-") as temp:
        report = exercise(Path(temp), candidate, args.source_loaded)
    with tempfile.TemporaryDirectory(prefix="tianxuan-legacy-key-") as temp:
        report["legacy_key_compatibility"] = exercise_legacy_key(Path(temp), candidate, args.source_loaded)
    assert report["binary_sha256"] == report["legacy_key_compatibility"]["binary_sha256"] == candidate_sha
    assert digest(candidate) == candidate_sha and all(
        digest(ROOT / name) == sha for name, sha in fingerprints.items()
    ), "candidate changed during identity validation"
    report["source_sha256"] = fingerprints
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": True, "mode": report["mode"], "phases": list(report["phases"])}))
