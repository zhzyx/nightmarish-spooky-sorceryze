"""Exercise native API credential audiences using synthetic loopback traffic only."""

import argparse
import hashlib
import json
import shutil
import subprocess
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
    calls, runs = [], {}
    current = ""

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def respond(self, method):
            payload = {}
            if method == "POST":
                payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            authorized = self.headers.get("Authorization") == "Bearer " + secret
            calls.append({
                "case": current,
                "method": method,
                "path": self.path,
                "authorized": authorized,
                "chat": "SYNTHETIC_CREDENTIAL_REQUEST" in json.dumps(payload),
                "child": "SYNTHETIC_CHILD_CREDENTIAL_REQUEST" in json.dumps(payload),
                "continuation": "SYNTHETIC_CONTINUATION_REQUEST" in json.dumps(payload),
            })
            response = (
                {"data": [{"id": "synthetic-model"}]}
                if method == "GET"
                else {"choices": [{"message": {"role": "assistant", "content": "OK"}}]}
            )
            if "SYNTHETIC_CONTINUATION_REQUEST" in json.dumps(payload) and not any(
                message.get("role") == "tool" for message in payload.get("messages", [])
            ):
                time.sleep(0.5)
                response = {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": None,
                                "tool_calls": [
                                    {
                                        "id": "fixture-read",
                                        "type": "function",
                                        "function": {"name": "list_directory", "arguments": '{"path":"res://"}'},
                                    }
                                ],
                            }
                        }
                    ]
                }
            body = json.dumps(response).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            self.respond("GET")

        def do_POST(self):
            self.respond("POST")

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with tempfile.TemporaryDirectory(prefix="credential-binding-") as temporary:
            base = Path(temporary)
            binary = copy_editor(args.godot, base / "engine")
            endpoint = f"http://127.0.0.1:{server.server_port}"
            for current in ("openai", "godot-unbound", "godot-other", "godot-bound", "openai-official"):
                project = base / current
                metadata = project / ".godot/editor"
                metadata.mkdir(parents=True)
                (project / "project.godot").write_text(
                    'config_version=5\n[application]\nconfig/name="Credential Fixture"\n'
                )
                initial_endpoint = (
                    "https://api.openai.com/v1/chat/completions"
                    if current == "openai-official"
                    else endpoint + "/v1/chat/completions"
                )
                initial_backend = 2 if current == "openai-official" else 0
                (metadata / "project_metadata.cfg").write_text(
                    "[ai_chat]\nproject_configuration_initialized=true\nbackend="
                    + str(initial_backend)
                    + "\nendpoint="
                    + json.dumps(initial_endpoint)
                    + '\nmodel="synthetic-model"\n[ai_connection_memory]\nenabled=false\n'
                )
                shutil.copyfile(Path(__file__).with_name("credential_binding.gd"), project / "accept.gd")
                (project / "accept.tscn").write_text(
                    '[gd_scene load_steps=2 format=3]\n[ext_resource type="Script" path="res://accept.gd" id="1"]\n'
                    '[node name="CredentialAcceptance" type="Node"]\nscript = ExtResource("1")\n'
                )
                report = base / (current + ".json")
                env = sanitized_environment(base)
                # No provider credential is copied from the host environment.
                env.update(
                    BINDING_SECRET=secret, BINDING_ENDPOINT=endpoint, BINDING_CASE=current, BINDING_REPORT=str(report)
                )
                if current in ("openai", "openai-official"):
                    env.update(OPENAI_API_KEY=secret, OPENAI_BASE_URL=endpoint + "/v1")
                else:
                    env["GODOT_AI_API_KEY"] = secret
                    if current != "godot-unbound":
                        env["GODOT_AI_API_ENDPOINT"] = endpoint + (
                            "/v1/responses" if current == "godot-bound" else "/other/responses"
                        )
                run = subprocess.run(
                    [str(binary), "--headless", "--editor", "--path", str(project), "res://accept.tscn"],
                    cwd=project,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=90,
                )
                log = run.stdout + run.stderr
                value = json.loads(report.read_text()) if report.exists() else {"passed": False, "missing_report": True}
                rows = [row for row in calls if row["case"] == current]
                first_post = next((row for row in rows if row["method"] == "POST"), {})
                assertions = {
                    "initial_probe_audience": first_post.get("authorized") == (current == "godot-bound"),
                    "manual_chat_authorized": any(row["chat"] and row["authorized"] for row in rows),
                    "silent_mutation_unauthorized": any(
                        row["path"].startswith("/silent/") and not row["authorized"] for row in rows
                    ),
                    "model_list_observed": any(row["method"] == "GET" for row in rows),
                    "child_request_drops_stale_key": any(
                        row["child"] and not row["authorized"] and row["path"].startswith("/parent-other/")
                        for row in rows
                    ),
                    "continuation_cannot_retarget_key": any(row["continuation"] and row["authorized"] for row in rows)
                    and not any(row["path"].startswith("/continuation-other/") and row["authorized"] for row in rows),
                    "initial_model_list_audience": next(
                        (row["authorized"] for row in rows if row["method"] == "GET"), None
                    )
                    == (current == "godot-bound"),
                }
                runs[current] = {
                    "exit": run.returncode,
                    "result": value,
                    "assertions": assertions,
                    "strict_errors": [
                        line.replace(secret, "[REDACTED]") for line in log.splitlines() if "ERROR:" in line
                    ],
                }
                print(current, "passed" if value.get("passed") and all(assertions.values()) else "failed")
            result = {
                "binary_sha256": hashlib.sha256(args.godot.read_bytes()).hexdigest(),
                "runs": runs,
                "requests": calls,
            }
            args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
            return (
                0
                if all(
                    run["exit"] == 0
                    and run["result"].get("passed")
                    and all(run["assertions"].values())
                    and not run["strict_errors"]
                    for run in runs.values()
                )
                else 1
            )
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
