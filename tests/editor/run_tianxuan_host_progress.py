"""Exercise compiled Tianxuan host progress against an isolated delayed HTTP provider."""

import argparse
import hashlib
import json
import os
import secrets
import shutil
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from editor_test_isolation import copy_editor
from run_unified_settings_native import sanitized_environment


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    binary = args.godot.resolve(strict=True)
    report = {"ok": False, "editor_sha256": hashlib.sha256(binary.read_bytes()).hexdigest()}
    with tempfile.TemporaryDirectory(prefix="tianxuan-host-progress-") as temporary:
        private = Path(temporary).resolve()
        project = private / "project"
        project.mkdir()
        markers = private / "markers"
        markers.mkdir()
        with patch.dict(os.environ, {"GONGGONG_WORKSPACE": ""}):
            editor = copy_editor(binary, private / "engine")
        (project / "project.godot").write_text(
            'config_version=5\n[application]\nconfig/name="Tianxuan Host Progress"\n'
        )
        for name in ("tianxuan_host_progress.gd", "tianxuan_local_model_fixture.gd"):
            shutil.copy2(Path(__file__).with_name(name), project / name)
        key = secrets.token_urlsafe(24)
        requests = []
        failures = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def respond(self, status, value):
                payload = json.dumps(value).encode()
                try:
                    self.send_response(status)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                except (BrokenPipeError, ConnectionResetError):
                    pass  # The cancellation test intentionally closes an in-flight HTTP connection.

            def do_GET(self):
                self.respond(200, {"data": [{"id": "native-local-fixture"}]})

            def do_POST(self):
                if self.path != "/v1/chat/completions" or self.headers.get("Authorization") != "Bearer " + key:
                    failures.append("unexpected provider route or fixture credential")
                    self.respond(403, {})
                    return
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                marker = next(item["content"] for item in reversed(body["messages"]) if item["role"] == "user")
                if marker not in ("progress-cancel", "progress-complete", "progress-fail"):
                    failures.append("unexpected provider input")
                    self.respond(400, {})
                    return
                if body.get("tools"):
                    failures.append("consultation unexpectedly exposed tools")
                requests.append(marker)
                (markers / marker).touch()
                time.sleep(1.0 if marker == "progress-complete" else 0.35)
                if marker == "progress-fail":
                    self.respond(503, {"error": {"message": "PRIVATE_PROVIDER_DIAGNOSTIC"}})
                    return
                self.respond(
                    200,
                    {
                        "choices": [
                            {
                                "message": {"role": "assistant", "content": "PRIVATE_PROVIDER_ANSWER"},
                                "finish_reason": "stop",
                            }
                        ]
                    },
                )

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        output = private / "result.json"
        environment = sanitized_environment(private)
        environment.update(
            GONGGONG_WORKSPACE="",
            TIANXUAN_API="http://127.0.0.1:1",
            TX_LOCAL_MODEL_ENDPOINT=f"http://127.0.0.1:{server.server_port}/v1/chat/completions",
            TX_LOCAL_MODEL_KEY=key,
            TX_PROGRESS_MARKERS=str(markers),
            TX_REPORT=str(output),
        )
        try:
            result = subprocess.run(
                [
                    str(editor),
                    "--headless",
                    "--editor",
                    "--path",
                    str(project),
                    "--script",
                    "res://tianxuan_host_progress.gd",
                ],
                cwd=project,
                env=environment,
                capture_output=True,
                timeout=60,
            )
            report["exit_code"] = result.returncode
            report["native"] = json.loads(output.read_text()) if output.is_file() else {}
            report["requests"] = requests
            report["fixture_failures"] = failures
            report["script_error_seen"] = b"SCRIPT ERROR:" in result.stderr
            report["ok"] = (
                result.returncode == 0
                and report["native"].get("ok", False)
                and not failures
                and not report["script_error_seen"]
                and set(requests) == {"progress-cancel", "progress-complete", "progress-fail"}
            )
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.with_suffix(".stdout.log").write_bytes(result.stdout)
            args.out.with_suffix(".stderr.log").write_bytes(result.stderr)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=10)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
