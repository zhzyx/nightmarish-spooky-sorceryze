"""Native read-only permission regression against an isolated loopback model."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    failures, observed = [], []
    with tempfile.TemporaryDirectory(prefix="consultation-native-") as temporary:
        root = Path(temporary)
        project = root / "project"
        project.mkdir()
        (project / "project.godot").write_text('[application]\nconfig/name="Consultation fixture"\n')
        shutil.copyfile(ROOT / "tests/editor/consultation_only.gd", project / "gate.gd")
        target = root / "sentinel.txt"
        target.write_text("CONSULTATION_SENTINEL", encoding="utf-8")

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_POST(self):
                try:
                    request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                    names = {x["function"]["name"] for x in request["tools"]}
                    assert names == {"read_file", "read_script", "read_logs", "list_scripts", "list_directory"}, names
                    messages = request["messages"]
                    assert all("consultation_only" not in m for m in messages)
                    latest = max(i for i, m in enumerate(messages) if m["role"] == "user")
                    prompt = messages[latest]["content"]
                    assert prompt != "DEVELOPMENT_MUST_GATE", "Development escaped its gate"
                    results = [m for m in messages[latest:] if m["role"] == "tool"]
                    observed.append({"prompt": prompt, "tool_results": len(results)})
                    calls = []
                    content = ""
                    if prompt == "CLI_MUST_NOT_START":
                        content = "CONSULTATION_QUEUE_OK"
                    elif not results:
                        attacks = [
                            "write_file",
                            "write_script",
                            "run_command",
                            "build_engine",
                            "restart_engine",
                            "rollback_engine",
                            "run_test",
                            "check_script",
                        ]
                        for i, name in enumerate(attacks):
                            calls.append({
                                "id": str(i),
                                "type": "function",
                                "function": {
                                    "name": name,
                                    "arguments": json.dumps({
                                        "path": str(target),
                                        "content": "MUTATED",
                                        "command": "exit 99",
                                    }),
                                },
                            })
                    elif len(results) == 8:
                        assert all("Consultation only permits read tools" in m["content"] for m in results)
                        calls = [
                            {
                                "id": "read",
                                "type": "function",
                                "function": {"name": "read_file", "arguments": json.dumps({"path": str(target)})},
                            }
                        ]
                    else:
                        assert len(results) == 9 and "CONSULTATION_SENTINEL" in results[-1]["content"]
                        content = "CONSULTATION_READ_OK"
                    message = {"role": "assistant", "content": content}
                    if calls:
                        message["tool_calls"] = calls
                    response = {"choices": [{"message": message, "finish_reason": "tool_calls" if calls else "stop"}]}
                except Exception as error:
                    failures.append(repr(error))
                    response = {"error": str(error)}
                body = json.dumps(response).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        env = dict(
            os.environ,
            OLYMPUS_TEST_WORKSPACE=str(root / "absent-workspace"),
            OLYMPUS_TEST_ENDPOINT=f"http://127.0.0.1:{server.server_port}/v1/chat/completions",
        )
        for key in ["OPENAI_API_KEY", "GODOT_AI_API_KEY"]:
            env.pop(key, None)
        for key in ["APPDATA", "LOCALAPPDATA", "XDG_CONFIG_HOME", "XDG_DATA_HOME"]:
            env[key] = str(root / key)
            (root / key).mkdir()
        try:
            result = subprocess.run(
                [
                    str(args.godot.resolve()),
                    "--headless",
                    "--editor",
                    "--path",
                    str(project),
                    "--script",
                    "res://gate.gd",
                ],
                cwd=root,
                env=env,
                capture_output=True,
                timeout=180,
            )
        finally:
            server.shutdown()
            server.server_close()
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.with_suffix(".stdout.log").write_bytes(result.stdout)
        args.out.with_suffix(".stderr.log").write_bytes(result.stderr)
        assert result.returncode == 0 and b"CONSULTATION_NATIVE_OK" in result.stdout, result.stdout[-4000:]
        assert not failures, failures
        assert len(observed) == 4, observed
        assert target.read_text() == "CONSULTATION_SENTINEL"
        assert not list(root.rglob("ai_chat_resume.json")), (
            "Consultation must not create a replayable development journal"
        )
        assert not (root / "absent-workspace").exists()
        args.out.write_text(
            json.dumps(
                {
                    "ok": True,
                    "editor_sha256": hashlib.sha256(args.godot.read_bytes()).hexdigest(),
                    "requests": observed,
                    "denied_tools": 8,
                    "read_result": "verified",
                    "issue_monitoring": "No configured workspace/host; no workspace created; code path reviewed. Not a global API spy.",
                    "fixture_events_imported": False,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
