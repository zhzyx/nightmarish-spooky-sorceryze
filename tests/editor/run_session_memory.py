"""Exercise remembered connections across native editor processes with RAM-only secrets."""

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
    secret = "synthetic-" + uuid.uuid4().hex
    store = {}
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_POST(self):
            value = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            if self.path == "/credentials":
                time.sleep(0.15)
                action, account = value["action"], value["account"]
                calls.append(action)
                if action == "save":
                    store[account] = value["secret"]
                    result = {"status": "saved"}
                elif action == "delete":
                    store.pop(account, None)
                    result = {"status": "deleted"}
                else:
                    result = (
                        {"status": "loaded", "secret": store[account]} if account in store else {"status": "missing"}
                    )
                status = 200
            elif self.headers.get("Authorization") == "Bearer " + secret:
                status, result = 200, {"choices": [{"message": {"role": "assistant", "content": "OK"}}]}
            else:
                status, result = 401, {"error": {"message": "fixture rejected"}}
            body = json.dumps(result).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    reports = {}
    errors = []
    try:
        with tempfile.TemporaryDirectory(prefix="session-memory-") as directory:
            base = Path(directory)
            binary = copy_editor(args.godot, base / "engine")
            endpoint = f"http://127.0.0.1:{server.server_port}"
            for name in ["project", "other"]:
                project = base / name
                project.mkdir()
                (project / "project.godot").write_text(
                    'config_version=5\n[application]\nconfig/name="Memory Fixture"\n'
                )
                shutil.copyfile(Path(__file__).with_name("session_memory.gd"), project / "accept.gd")
                (project / "accept.tscn").write_text(
                    '[gd_scene load_steps=2 format=3]\n[ext_resource type="Script" path="res://accept.gd" id="1"]\n'
                    '[node name="MemoryAcceptance" type="Node"]\nscript = ExtResource("1")\n'
                )
                (project / "credential_fixture.py").write_text(
                    "import sys,urllib.request\n"
                    "body=sys.stdin.buffer.readline(16385)\n"
                    f"request=urllib.request.Request({endpoint + '/credentials'!r},data=body,headers={{'Content-Type':'application/json'}})\n"
                    "with urllib.request.urlopen(request, timeout=4) as response: sys.stdout.buffer.write(response.read(16384))\n"
                )
            for stage in ["save", "other-project", "restore", "forgotten"]:
                project = base / ("other" if stage == "other-project" else "project")
                report = base / (stage + ".json")
                env = sanitized_environment(base)
                env.update(
                    MEMORY_SECRET=secret,
                    MEMORY_ENDPOINT=endpoint,
                    MEMORY_STAGE=stage,
                    MEMORY_REPORT=str(report),
                    GONGGONG_PYTHON=sys.executable,
                )
                if stage == "restore":
                    # A mismatched ambient credential must not mask the saved
                    # custom endpoint's private-store credential on restart.
                    env["OPENAI_API_KEY"] = "synthetic-unrelated-" + uuid.uuid4().hex
                try:
                    process = subprocess.run(
                        [str(binary), "--headless", "--editor", "--path", str(project), "res://accept.tscn"],
                        cwd=project,
                        env=env,
                        capture_output=True,
                        text=True,
                        timeout=45,
                    )
                except subprocess.TimeoutExpired as error:
                    print((error.stdout or b"").decode(errors="replace"))
                    print((error.stderr or b"").decode(errors="replace"))
                    raise
                log = process.stdout + process.stderr
                print(log)
                errors.extend(line for line in log.splitlines() if "ERROR:" in line)
                value = json.loads(report.read_text()) if report.is_file() else {"passed": False, "missing": True}
                reports[stage] = {"result": value, "exit": process.returncode}
                if not value.get("passed") or process.returncode:
                    break
            leaked = any(
                secret.encode() in p.read_bytes()
                for p in base.rglob("*")
                if p.is_file() and p.stat().st_size < 5_000_000
            )
            result = {
                "binary_sha256": hashlib.sha256(args.godot.read_bytes()).hexdigest(),
                "stages": reports,
                "strict_errors": errors,
                "secret_on_disk": leaked,
                "store_empty_after_forget": not store,
                "operations": calls,
                "pending_save_observed": calls[:2] == ["save", "save"],
            }
            args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
            return (
                0
                if len(reports) == 4
                and all(v["result"].get("passed") and v["exit"] == 0 for v in reports.values())
                and not errors
                and not leaked
                and not store
                and result["pending_save_observed"]
                else 1
            )
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
