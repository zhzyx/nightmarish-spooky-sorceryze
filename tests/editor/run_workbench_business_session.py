"""Drive the native account controls against an isolated, real Tianxuan accounts service."""

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
import threading
import time
from pathlib import Path
from unittest.mock import patch

import uvicorn
from editor_test_isolation import copy_editor
from run_unified_settings_native import sanitized_environment

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "customizations/components/tianxuan/server"))
from api import create_app  # noqa: E402
from tianxuan_core import Tianxuan  # noqa: E402

PROBE = Path(__file__).with_name("workbench_business_session.gd")
SCRIPT = ROOT / "editor/docks/workbench/business_session.gd"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def exercise(base, binary):
    project = base / "project"
    project.mkdir()
    (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="D14"\n', encoding="utf-8")
    shutil.copyfile(PROBE, project / "test.gd")
    before = {p.name: digest(p) for p in project.iterdir()}

    with patch.dict(os.environ, {"GONGGONG_WORKSPACE": ""}):
        engine = copy_editor(binary, base / "engine")
    store = Tianxuan(str(base / "domain.db"))
    password = secrets.token_urlsafe(32)
    first = store.register("Test studio", "first@example.invalid", password)
    owner = first["user_id"]
    viewer = store.add_member(owner, "second@example.invalid", password)["user_id"]
    for actor, position in [(owner, "first-private-position"), (viewer, "second-private-position")]:
        store.save_module_location(actor, "studio/game", "default", None, None, position)
    store.set_role(owner, viewer, "viewer")
    key = store.issue_access_key(owner, viewer, "Temporary integration fixture")

    # Retain emitted credentials only in RAM to scan every project and editor settings file after exit.
    credentials = [password, key["key"]]
    issue_session = store.issue_session

    def remember(*args, **kwargs):
        token = issue_session(*args, **kwargs)
        credentials.append(token)
        return token

    store.issue_session = remember
    control = base / "revoke"
    revoked = base / "revoked"
    modes = {
        "TIANXUAN_AUTH_MODE": "accounts",
        "TIANXUAN_REQUIRE_KEYS": "0",
        "TIANXUAN_TENANT_ID": first["tenant_id"],
        "TIANXUAN_PUBLIC_ORIGIN": "https://fixture.invalid",
    }
    with patch.dict(os.environ, modes), socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        api = "http://127.0.0.1:" + str(sock.getsockname()[1])
        service = uvicorn.Server(uvicorn.Config(create_app(store), log_level="error", access_log=False))
        thread = threading.Thread(target=service.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 20
            while not service.started:
                if not thread.is_alive() or time.monotonic() > deadline:
                    raise RuntimeError("Fixture service failed to start")
                time.sleep(0.05)
            env = {k: v for k, v in sanitized_environment(base).items() if not k.startswith(("TIANXUAN_", "D14_"))}
            env.update(
                TIANXUAN_API=api,
                D14_USER_A=owner,
                D14_USER_B=viewer,
                D14_PASSWORD=password,
                D14_PERSONAL_KEY=key["key"],
                D14_REVOKE=str(control),
                D14_REVOKED=str(revoked),
            )
            cmd = [str(engine), "--headless", "--editor", "--path", str(project), "--script", "res://test.gd"]
            # Redirect output to temporary files to avoid pipe backpressure. No credentials are command arguments.
            with (base / "stdout").open("wb") as stdout, (base / "stderr").open("wb") as stderr:
                proc = subprocess.Popen(cmd, env=env, cwd=base, stdout=stdout, stderr=stderr)
                try:
                    deadline = time.monotonic() + 90
                    while proc.poll() is None and time.monotonic() < deadline:
                        if control.exists() and not revoked.exists():
                            assert store.revoke_access_key(owner, key["id"])
                            revoked.touch()
                        time.sleep(0.03)
                    proc.wait(timeout=1)
                finally:
                    if proc.poll() is None:
                        proc.kill()
                        proc.wait()
        finally:
            service.should_exit = True
            thread.join(timeout=10)
            store.db.close()
    output = (base / "stdout").read_text(encoding="utf-8", errors="replace")
    errors = (base / "stderr").read_text(encoding="utf-8", errors="replace")
    for secret in credentials:
        if secret in output or secret in errors:
            raise AssertionError("Credential found in runtime diagnostics")
    markers = [line for line in output.splitlines() if line.startswith("D14_CHECKS=")]
    if proc.returncode or not markers or "SCRIPT ERROR" in errors:
        raise AssertionError(output[-1500:] + errors[-2500:])
    assert {name: digest(project / name) for name in before} == before, "Project source changed"
    secret_bytes = [value.encode() for value in credentials]
    files = 0
    for folder in [project, engine.parent / "editor_data", base / "private-home"]:
        for path in folder.rglob("*"):
            if path.is_file():
                files += 1
                data = path.read_bytes()
                assert not any(value in data for value in secret_bytes), "Credential persisted in fixture"
    return {
        "target": "compiled editor sidebar",
        "project_files_created_by_editor": sorted(p.name for p in project.iterdir() if p.name not in before),
        "exit_diagnostics": [
            line for line in (output + errors).splitlines() if line.startswith(("ERROR:", "WARNING:"))
        ],
        "engine_sha256": digest(binary),
        "script_sha256": digest(SCRIPT),
        "checks": json.loads(markers[-1].split("=", 1)[1]),
        "credentials_checked": len(credentials),
        "files_scanned": files,
        "project_source_sha256_unchanged": before,
        "fixture": "loopback FastAPI accounts service, disposable tenant, admin and viewer, isolated editor copy",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="workbench-d14-") as directory:
        report = exercise(Path(directory), args.godot.resolve(strict=True))
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Passed", report["target"], len(report["checks"]), "checks")


if __name__ == "__main__":
    main()
