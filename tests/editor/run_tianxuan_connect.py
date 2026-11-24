"""Exercise the ordinary native Connect button with private settings and loopback fixtures."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from editor_test_isolation import copy_editor
from run_unified_settings_native import sanitized_environment

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ORIGIN = "https://167-172-70-41.sslip.io"


@contextmanager
def fixture(handler):
    with ThreadingHTTPServer(("127.0.0.1", 0), handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield server.server_port
        finally:
            server.shutdown()
            thread.join()


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def exercise(base, binary, source_loaded):
    with patch.dict(os.environ, {"GONGGONG_WORKSPACE": ""}):
        editor = copy_editor(binary, base / "engine")
    project = base / "project"
    project.mkdir()
    (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="Connect test"\n')
    shutil.copyfile(Path(__file__).with_name("tianxuan_connect.gd"), project / "probe.gd")
    script_hashes = {}
    if source_loaded:
        for name in ("session_controller.gd", "workspace_controller.gd", "workspace_view.gd"):
            shutil.copyfile(ROOT / "editor/docks/tianxuan" / name, project / name)
            script_hashes[name] = digest(project / name)
    mode = base / "response-mode"
    mode.write_text("keys")
    proxy_targets = []
    origin_responses = []
    device_tokens = set()

    class QuietHandler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

    class RejectProxy(QuietHandler):
        def do_CONNECT(self):
            proxy_targets.append(self.path)
            self.send_error(502)

    class Service(QuietHandler):
        def do_POST(self):
            bearer = self.headers.get("Authorization", "").removeprefix("Bearer ")
            if self.path == "/api/v1/auth/device-session" and bearer == "fixture-viewer-key":
                token = f"fixture-device-{len(device_tokens) + 1}"
                device_tokens.add(token)
                payload = {"token": token}
            elif self.path == "/api/v1/auth/logout" and bearer in device_tokens:
                device_tokens.remove(bearer)
                payload = {"ok": True}
            else:
                self.send_error(401)
                return
            body = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/api/v1/auth/config":
                state = mode.read_text()
                origin_responses.append(state)
                if state == "unavailable":
                    self.send_error(503)
                    return
                payload = {"mode": state}
            elif (
                self.path == "/api/v1/auth/me"
                and self.headers.get("Authorization", "").removeprefix("Bearer ") in device_tokens
            ):
                payload = {"id": "test-viewer", "role": "viewer", "name": "Fixture"}
            else:
                self.send_error(404)
                return
            body = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    results = {}
    with fixture(RejectProxy) as proxy_port, fixture(Service) as service_port:
        api = f"http://127.0.0.1:{service_port}"
        saved = f"http://localhost:{service_port}"
        scenarios = [("source_button" if source_loaded else "environment_over_saved", saved, api, api)]
        if not source_loaded:
            scenarios += [("saved_address", saved, "", saved), ("default_address", "", "", DEFAULT_ORIGIN)]
        for scenario, saved_url, override, expected in scenarios:
            settings = {
                "network/http_proxy/host": "127.0.0.1",
                "network/http_proxy/port": proxy_port,
                "interface/tianxuan/language": "zh",
                "ai_chat/endpoint": api + "/v1/chat/completions",
                "ai_chat/editor_control_bridge_enabled": False,
            }
            if saved_url:
                settings["network/web_platform/url"] = saved_url
            (editor.parent / "editor_data/editor_settings-4.8.tres").write_text(
                '[gd_resource type="EditorSettings" format=3]\n\n[resource]\n'
                + "".join(f"{key} = {json.dumps(value)}\n" for key, value in settings.items()),
                encoding="utf-8",
            )
            environment = {
                key: value
                for key, value in sanitized_environment(base).items()
                if not key.upper().startswith(("TIANXUAN_", "TX_"))
            }
            if override:
                environment["TIANXUAN_API"] = override
            environment.update(
                TX_SOURCE_LOADED="1" if source_loaded else "0",
                TX_TEST_BUTTON="1" if override else "0",
                TX_EXPECT_ORIGIN=expected,
                TX_DEFAULT_ORIGIN=DEFAULT_ORIGIN,
                TX_RESPONSE_MODE=str(mode),
            )
            result = subprocess.run(
                [str(editor), "--headless", "--editor", "--path", str(project), "--script", "res://probe.gd"],
                env=environment,
                cwd=base,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=90,
            )
            reports = [json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")]
            passed = next((report for report in reports if report.get("passed")), None)
            if result.returncode or "SCRIPT ERROR" in result.stdout + result.stderr or passed is None:
                raise AssertionError(f"{scenario}: {(result.stdout + result.stderr)[-8000:]}")
            results[scenario] = passed["checks"]
    assert "connect-probe.invalid:443" in proxy_targets, proxy_targets
    assert not any("127.0.0.1" in target or "localhost" in target for target in proxy_targets), proxy_targets
    assert {"keys", "accounts", "legacy", "unknown", "unavailable"} <= set(origin_responses), origin_responses
    return dict(
        passed=True,
        mode="source_loaded" if source_loaded else "compiled_native",
        binary_sha256=digest(editor),
        input_script_sha256=script_hashes,
        scenarios=results,
        proxy_connect_targets=proxy_targets,
        loopback_read_modes=origin_responses,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--source-loaded", action="store_true", help="Exercise source scripts on an existing editor.")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="tianxuan-connect-") as temp:
        report = exercise(Path(temp), args.godot.resolve(strict=True), args.source_loaded)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"passed": True, "mode": report["mode"], "scenarios": list(report["scenarios"])}))
