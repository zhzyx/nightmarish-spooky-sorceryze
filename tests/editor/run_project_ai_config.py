"""Headless project AI settings/status acceptance with private loopback credentials."""

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from editor_test_isolation import copy_editor
from run_unified_settings_native import sanitized_environment


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    script = Path(__file__).with_name("project_ai_config.gd")
    events = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def respond(self, code, value):
            body = json.dumps(value).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass  # An obsolete probe is deliberately cancelled.

        def do_GET(self):
            self.respond(200, {"data": [{"id": "fixture-model"}]})

        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            events.append({"path": self.path, "model": payload.get("model")})
            if any("project-ai-invalid-response" in str(m.get("content", "")) for m in payload.get("messages", [])):
                self.respond(200, {})
                return
            if self.path.startswith("/slow/"):
                time.sleep(0.8)
            if self.path.startswith("/fail/"):
                self.respond(401, {"error": {"message": "synthetic unavailable"}})
            else:
                self.respond(
                    200, {"choices": [{"message": {"role": "assistant", "content": "OK"}, "finish_reason": "stop"}]}
                )

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    runs = []
    try:
        with tempfile.TemporaryDirectory(prefix="project-ai-config-") as directory:
            base = Path(directory)
            binary = copy_editor(args.godot, base / "editor")
            env = sanitized_environment(base)
            endpoint = f"http://127.0.0.1:{server.server_port}"
            bridge = base / "synthetic_cli.py"
            bridge.write_text("""import json, sys, time
from pathlib import Path
if sys.argv[1] == "models":
    print(json.dumps({"models": [{"id": "cli-model"}]}))
else:
    value = json.loads(Path(sys.argv[3]).read_text())
    assert value["available_tools"] == []
    assert value["tool_context"]["permission_enabled"] is False
    if value["model"] == "cli-failure":
        sys.exit(1)
    if value["model"] == "cli-slow":
        time.sleep(1)
    print(json.dumps({"choices": [{"message": {"content": "OK"}}]}))
""")
            env.update({"PROJECT_AI_PYTHON": sys.executable, "PROJECT_AI_CLI_BRIDGE": str(bridge)})
            settings_file = base / "editor/editor_data/editor_settings-4.8.tres"
            settings_file.write_text(
                '[gd_resource type="EditorSettings" format=3]\n[resource]\nai_chat/backend = 0\nai_chat/model = "fixture-model"\nai_chat/endpoint = '
                + json.dumps(endpoint + "/v1/chat/completions")
                + "\nai_chat/editor_control_bridge_enabled = false\n"
            )
            for name in ["first", "second"]:
                project = base / name
                project.mkdir()
                (project / "project.godot").write_text(
                    '[application]\nconfig/name="Project AI fixture"\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n'
                )
                (project / "accept.gd").write_bytes(script.read_bytes())
            modes = [
                ("full", "first"),
                ("reopen", "first"),
                ("other", "second"),
                ("child", "first"),
                ("scheduled", "first"),
            ]
            for mode, name in modes:
                project = base / name
                if mode in {"child", "scheduled"}:
                    parent = dict(
                        id=0,
                        title="Parent",
                        draft="",
                        model="old-parent-model",
                        cli_model="",
                        codex_model="",
                        backend=0,
                        messages=[],
                        transcript=[],
                        draft_images=[],
                    )
                    child = dict(parent, id=1, title="Execution", model="execution-override")
                    history = dict(version=1, active_agent=1, next_agent=2, agents=[parent, child])
                    if mode == "child":
                        child["sub_agent"] = dict(
                            parent=0, work_order=1, issue_number=0, request_id="", source="manual", state="manual"
                        )
                    else:
                        child["scheduled_run"] = dict(schedule_id=1, state="completed")
                        history["scheduled_tasks"] = [
                            dict(
                                id=1,
                                title="Disabled fixture",
                                prompt="Never execute",
                                frequency=1,
                                unit=0,
                                sequence=0,
                                next_due=int(time.time()) + 3600,
                                backend=0,
                                model="execution-override",
                                cli_model="",
                                enabled=False,
                            )
                        ]
                    (project / ".godot/editor").mkdir(parents=True, exist_ok=True)
                    (project / ".godot/editor/ai_chat_history.json").write_text(json.dumps(history))
                report = base / f"{mode}.json"
                command = [
                    str(binary),
                    "--headless",
                    "--editor",
                    "--path",
                    str(project),
                    "--script",
                    str(project / "accept.gd"),
                ]
                process = subprocess.run(
                    command,
                    cwd=project,
                    env={
                        **env,
                        "PROJECT_AI_MODE": mode,
                        "PROJECT_AI_ENDPOINT": endpoint,
                        "PROJECT_AI_REPORT": str(report),
                    },
                    capture_output=True,
                    text=True,
                    timeout=50,
                )
                log = process.stdout + process.stderr
                receipt = json.loads(report.read_text()) if report.exists() else {}
                passed = process.returncode == 0 and receipt.get("passed") and "SCRIPT ERROR:" not in log
                runs.append({"mode": mode, "passed": bool(passed), "receipt": receipt, "log": log})
                print(mode, "passed" if passed else "failed")
                if not passed:
                    print(log[-12000:])
                    break
            secret_on_disk = any(
                b"project-ai-synthetic-secret" in f.read_bytes()
                for f in (base / "editor/editor_data").rglob("*")
                if f.is_file()
            )
            project_clean = all(
                "project-ai-synthetic-secret" not in (base / name / "project.godot").read_text()
                for name in ["first", "second"]
            )
    finally:
        server.shutdown()
        server.server_close()
    result = {
        "passed": len(runs) == len(modes)
        and all(run["passed"] for run in runs)
        and not secret_on_disk
        and project_clean,
        "runs": runs,
        "events": events,
        "secret_on_disk": secret_on_disk,
        "project_sources_clean": project_clean,
        "binary_sha256": hashlib.sha256(args.godot.read_bytes()).hexdigest(),
        "fixture_sha256": hashlib.sha256(script.read_bytes()).hexdigest(),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
