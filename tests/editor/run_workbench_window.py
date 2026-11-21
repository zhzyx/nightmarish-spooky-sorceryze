"""Exercise modal and auxiliary window AI requests in an isolated headless editor."""

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from editor_test_isolation import copy_editor
from run_unified_settings_native import sanitized_environment


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    engine = args.godot.resolve()
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def respond(self, result):
            encoded = json.dumps(result).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self):
            self.respond({"data": [{"id": "fixture"}]})

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            users = [message["content"] for message in body["messages"] if message["role"] == "user"]
            capability = next(
                message["content"]
                for message in body["messages"]
                if message.get("role") == "system"
                and "Godot tool state (authoritative host metadata): " in message["content"]
            )
            state = json.loads(
                capability.partition("Godot tool state (authoritative host metadata): ")[2].splitlines()[0]
            )
            requests.append({
                "last_user": users[-1],
                "consultation": state["consultation_only"],
                "writes": state["writes_allowed"],
                "execution": state["execution_allowed"],
            })
            self.respond({
                "choices": [{"message": {"role": "assistant", "content": "WINDOW_REPLY_OK"}, "finish_reason": "stop"}]
            })

    fixture = Path(__file__).with_name("workbench_window.gd")
    with (
        tempfile.TemporaryDirectory(prefix="u06-window-") as directory,
        ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server,
    ):
        base = Path(directory)
        binary = copy_editor(engine, base / "engine")
        project = base / "project"
        project.mkdir()
        (project / "project.godot").write_text(
            'config_version=5\n[application]\nconfig/name="Window Route"\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n',
            encoding="utf-8",
        )
        shutil.copyfile(fixture, project / "fixture.gd")
        env = sanitized_environment(base)
        env["WINDOW_ENDPOINT"] = f"http://127.0.0.1:{server.server_port}/v1/chat/completions"
        settings = binary.parent / "editor_data/editor_settings-4.8.tres"
        settings.write_text(
            '[gd_resource type="EditorSettings" format=3]\n\n[resource]\ninterface/editor/editor_language = "en"\nai_chat/backend = 0\nai_chat/endpoint = '
            + json.dumps(env["WINDOW_ENDPOINT"])
            + "\n",
            encoding="utf-8",
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            run = subprocess.run(
                [str(binary), "--headless", "--editor", "--path", str(project), "--script", "res://fixture.gd"],
                cwd=project,
                env=env,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=70,
            )
        finally:
            server.shutdown()
            thread.join()
        result = next(
            (
                json.loads(line.partition("=")[2])
                for line in run.stdout.splitlines()
                if line.startswith("WINDOW_ROUTE_RESULT=")
            ),
            {},
        )
        expected = (
            bool(requests)
            and len(requests) == 1
            and requests[0]["last_user"].endswith("saved-s")
            and requests[0]["consultation"]
            and not requests[0]["writes"]
            and not requests[0]["execution"]
        )
        output = run.stdout + run.stderr
        passed = run.returncode == 0 and bool(result) and expected and "SCRIPT ERROR" not in output
        with engine.open("rb") as executable:
            engine_sha = hashlib.file_digest(executable, "sha256").hexdigest()
        diagnostics = [line for line in output.splitlines() if line.startswith(("WARNING:", "ERROR:", "SCRIPT ERROR"))]
        report = {
            "passed": passed,
            "native_exit": run.returncode,
            "engine_sha256": engine_sha,
            "controls": result,
            "loopback": requests,
            "diagnostics": diagnostics,
        }
        args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        if not passed:
            raise SystemExit(run.stdout + run.stderr + json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
