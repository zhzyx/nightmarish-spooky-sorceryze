"""Measure native Stop and frame latency against an isolated delayed HTTP server."""

import argparse
import gzip
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from editor_test_isolation import macos_editor

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--case", choices=["headers", "body", "models"], default="headers")
    parser.add_argument("--delay", type=float, default=3)
    parser.add_argument("--max-stop", type=float, default=0.25)
    parser.add_argument("--max-frame-gap", type=float, default=0.25)
    parser.add_argument("--visible", action="store_true")
    parser.add_argument(
        "--manual-stop", action="store_true", help="Wait for a real click on Stop in the isolated visible window"
    )
    parser.add_argument(
        "--gzip-recovery", action="store_true", help="Exercise a compressed 1 MiB JSON response after cancellation"
    )
    args = parser.parse_args()
    if args.manual_stop and not args.visible:
        parser.error("--manual-stop requires --visible")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="http-cancel-", dir=args.out.parent) as folder:
        project = Path(folder)
        isolated_editor = macos_editor(args.godot, project / "isolated-editor")
        (project / "project.godot").write_text(
            '[application]\nconfig/name="Issue51 HTTP Cancel Fixture"\n'
            '[rendering]\nrenderer/rendering_method="gl_compatibility"\n',
            encoding="utf-8",
        )
        shutil.copyfile(Path(__file__).with_name("ai_chat_http_cancel.gd"), project / "gate.gd")
        errors = []
        requests = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def respond(self, models=False):
                body = {} if models else json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                recovering = (models and any(x["models"] for x in requests)) or any(
                    m.get("content") == "RECOVERY_REQUEST" for m in body.get("messages", [])
                )
                requests.append({"models": models, "recovery": recovering})
                value = (
                    {"data": [{"id": "recovered-model" if recovering else "stale-model"}]}
                    if models
                    else {
                        "choices": [
                            {
                                "message": {
                                    "role": "assistant",
                                    "content": "RECOVERY_OK" if recovering else "STALE_CANCELLED_REPLY",
                                },
                                "finish_reason": "stop",
                            }
                        ]
                    }
                )
                compressed = args.gzip_recovery and recovering and not models
                if compressed:
                    value["fixture_padding"] = "x" * (1024 * 1024)
                payload = json.dumps(value).encode()
                if compressed:
                    payload = gzip.compress(payload)
                try:
                    partial = args.case == "body" and not recovering
                    if partial or recovering:
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.send_header("Content-Length", str(len(payload)))
                        if compressed:
                            self.send_header("Content-Encoding", "gzip")
                        self.end_headers()
                        if partial:
                            self.wfile.write(payload[:1])
                            self.wfile.flush()
                    if not recovering:
                        (project / "server-waiting").write_text("waiting", encoding="utf-8")
                        time.sleep(args.delay)
                        (project / "server-released").write_text("released", encoding="utf-8")
                    if not partial and not recovering:
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.send_header("Content-Length", str(len(payload)))
                        self.end_headers()
                    self.wfile.write(payload[1:] if partial else payload)
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    pass  # Expected when Stop closes a pending request.
                except Exception as exc:
                    errors.append(type(exc).__name__ + ": " + str(exc))

            def do_POST(self):
                self.respond()

            def do_GET(self):
                self.respond(models=True)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        env = dict(os.environ)
        for key in ["OPENAI_API_KEY", "GODOT_AI_API_KEY", "GONGGONG_WORKSPACE", "GONGGONG_TEST_WORKSPACE"]:
            env.pop(key, None)
        for key in ["APPDATA", "LOCALAPPDATA", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "TEMP", "TMP"]:
            env[key] = str(project / key)
            (project / key).mkdir()
        env.update(
            CANCEL_ENDPOINT=f"http://127.0.0.1:{server.server_port}/v1/chat/completions",
            CANCEL_CASE=args.case,
            CANCEL_DELAY=str(args.delay),
            CANCEL_MANUAL="1" if args.manual_stop else "",
        )
        command = [str(isolated_editor)]
        if not args.visible:
            command.append("--headless")
        command += ["--editor", "--path", str(project), "--script", "res://gate.gd"]
        try:
            run = subprocess.run(command, cwd=project, env=env, capture_output=True, timeout=args.delay + 60)
        finally:
            server.shutdown()
            server.server_close()
            worker.join()
        args.out.with_suffix(".stdout.log").write_bytes(run.stdout)
        args.out.with_suffix(".stderr.log").write_bytes(run.stderr)
        report_file = project / "cancel-report.json"
        report = json.loads(report_file.read_bytes()) if report_file.exists() else {}
        editor = args.godot.resolve()
        if editor.name.endswith(".console.exe"):
            editor = editor.with_name(editor.name.replace(".console.exe", ".exe"))
        report.update(
            editor_sha256=hashlib.sha256(editor.read_bytes()).hexdigest(),
            case=args.case,
            server_delay_seconds=args.delay,
            native_exit_code=run.returncode,
            model_transport="isolated loopback mock",
            real_provider=False,
            requests=requests,
            errors=errors,
            visible=args.visible,
            gzip_recovery=args.gzip_recovery,
            fixture_sha256={
                p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in [Path(__file__), Path(__file__).with_name("ai_chat_http_cancel.gd")]
            },
            max_stop_seconds=args.max_stop,
            max_allowed_frame_gap_seconds=args.max_frame_gap,
        )
        report["passed"] = (
            run.returncode == 0
            and not errors
            and report.get("stop_was_enabled")
            and report.get("stop_disabled_after")
            and report.get("recovery_received")
            and report.get("stale_response_absent")
            and report.get("models_recovered", args.case != "models")
            and report.get("late_models_rejected", args.case != "models")
            and report.get("observed_server_release")
            and not report.get("server_released_at_recovery", True)
            and not report.get("server_released_at_stop_return", True)
            and report.get("stop_call_seconds", float("inf")) < args.max_stop
            and report.get("max_frame_gap_seconds", float("inf")) < args.max_frame_gap
        )
        report["passed"] = (
            report["passed"] and report.get("recovery_max_frame_gap_seconds", float("inf")) < args.max_frame_gap
        )
        args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report))
        return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
