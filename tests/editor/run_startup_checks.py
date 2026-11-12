"""Validate native startup orchestration using a private project and loopback API."""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from editor_test_isolation import copy_editor
from run_unified_settings_native import sanitized_environment


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    events = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def respond(self, status, value):
            body = json.dumps(value).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

        def do_GET(self):
            self.respond(200, {"data": [{"id": "startup-model"}]})

        def do_POST(self):
            self.rfile.read(int(self.headers["Content-Length"]))
            events.append(self.path)
            if self.path.startswith("/slow/"):
                time.sleep(0.8)
            if self.path.startswith("/fail/"):
                self.respond(401, {"error": {"message": "synthetic unavailable"}})
            else:
                self.respond(200, {"choices": [{"message": {"role": "assistant", "content": "OK"}}]})

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with tempfile.TemporaryDirectory(prefix="startup-checks-") as directory:
            base = Path(directory)
            binary = copy_editor(args.godot, base / "engine")
            project = base / "project"
            project.mkdir()
            (project / "project.godot").write_text(
                'config_version=5\n[application]\nconfig/name="Startup Check Fixture"\n'
            )
            shutil.copyfile(Path(__file__).with_name("startup_checks.gd"), project / "accept.gd")
            (project / "accept.tscn").write_text(
                '[gd_scene load_steps=2 format=3]\n[ext_resource type="Script" path="res://accept.gd" id="1"]\n'
                '[node name="StartupAcceptance" type="Node"]\nscript = ExtResource("1")\n'
            )
            workspace = base / "model-workspace"
            workspace.mkdir()
            (binary.parent / "SConstruct").touch()
            helper = binary.parent / "customizations/components/godot-host/daqian/models_cli.py"
            helper.parent.mkdir(parents=True)
            helper.write_text("""import json, sys, time, subprocess
from pathlib import Path
value=json.loads(sys.stdin.readline())
root=Path(sys.argv[2])
(root/'model-helper-target').write_text(str(root))
if (root/'cancel-mode').exists():
    code="import time;from pathlib import Path;time.sleep(.8);Path("+repr(str(root/'descendant-ran'))+").write_text('ran')"
    subprocess.Popen([sys.executable,'-c',code])
    time.sleep(2)
else:
    time.sleep(0.25)
print(json.dumps({'result':[]}))
""")
            env = sanitized_environment(base)
            receipt = base / "receipt.json"
            secret = "synthetic-" + uuid.uuid4().hex
            env.update(
                STARTUP_SECRET=secret,
                STARTUP_MODEL_WORKSPACE=str(workspace),
                STARTUP_ENDPOINT=f"http://127.0.0.1:{server.server_port}",
                STARTUP_REPORT=str(receipt),
                GONGGONG_PYTHON=sys.executable,
            )
            try:
                process = subprocess.run(
                    [str(binary), "--headless", "--editor", "--path", str(project), "res://accept.tscn"],
                    cwd=project,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
            except subprocess.TimeoutExpired as error:
                print(
                    (error.stdout or b"").decode(errors="replace")
                    if isinstance(error.stdout, bytes)
                    else error.stdout or ""
                )
                print(
                    (error.stderr or b"").decode(errors="replace")
                    if isinstance(error.stderr, bytes)
                    else error.stderr or ""
                )
                raise
            log = process.stdout + process.stderr
            value = json.loads(receipt.read_text()) if receipt.is_file() else {}
            errors = [line for line in log.splitlines() if "ERROR:" in line]
            secret_on_disk = any(
                secret.encode() in p.read_bytes()
                for folder in (project, base / "engine/editor_data")
                for p in folder.rglob("*")
                if p.is_file()
            )
            result = {
                "passed": process.returncode == 0 and value.get("passed", False) and not errors and not secret_on_disk,
                "binary_sha256": hashlib.sha256(args.godot.read_bytes()).hexdigest(),
                "receipt": value,
                "errors": errors,
                "secret_on_disk": secret_on_disk,
                "returncode": process.returncode,
                "requests": events,
            }
            if not result["passed"]:
                result["log_tail"] = log[-15000:]
            args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2))
            print(log)
            print(json.dumps({"passed": result["passed"], "checks": len(value.get("checks", []))}))
            return 0 if result["passed"] else 1
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
