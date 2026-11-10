"""Headless continuous-conversation acceptance against a loopback mock, without provider calls."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from editor_test_isolation import copy_editor

MOCK_CODEX = r"""
// Offline Codex JSONL fixture. Uses only the test loopback server.
const http = require('node:http');
let wire = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', data => wire += data);
process.stdin.on('end', () => {
    const args = process.argv;
    if (args[args.indexOf('--sandbox') + 1] !== 'read-only'
        || !args.includes('approval_policy="never"')
        || !args.includes('features.shell_tool=false')
        || !args.includes('features.apply_patch_freeform=false')) process.exit(4);
    const input = JSON.parse(wire.slice(wire.indexOf('\n') + 1));
    if (input.tool_context.consultation_only !== true
        || input.tool_context.writes_allowed !== false
        || input.tool_context.execution_allowed !== false) process.exit(5);
    const body = JSON.stringify({model: input.model, messages: input.messages, tools: input.available_tools});
    const request = http.request(process.env.STEERING_ENDPOINT, {method: 'POST', headers: {
        'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body),
        Authorization: 'Bearer isolated-fixture-key'
    }}, response => {
        let text = '';
        response.setEncoding('utf8');
        response.on('data', chunk => text += chunk);
        response.on('end', () => {
            if (response.statusCode !== 200) process.exit(6);
            const message = JSON.parse(text).choices[0].message;
            const answer = {content: message.content, actions: (message.tool_calls || []).map(call => ({
                name: call.function.name, arguments: JSON.parse(call.function.arguments)
            }))};
            console.log(JSON.stringify({type: 'item.completed', item: {type: 'agent_message', text: JSON.stringify(answer)}}));
            console.log(JSON.stringify({type: 'turn.completed'}));
        });
    });
    request.on('error', () => process.exit(7));
    request.end(body);
});
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--codex", action="store_true", help="Use the real Codex bridge with an offline CLI fixture")
    parser.add_argument("--node", type=Path, help="Node executable for --codex; defaults to PATH")
    parser.add_argument("--case", choices=["steering", "tools", "stop", "cancel", "mode", "issues"], default="steering")
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    errors, requests, model_requests = [], [], []
    with tempfile.TemporaryDirectory(prefix="chat-steering-", dir=args.out.parent) as folder:
        project = Path(folder).resolve()
        (project / "project.godot").write_text(
            'config_version=5\n[application]\nconfig/name="Steering Fixture"\n'
            '[rendering]\nrenderer/rendering_method="gl_compatibility"\n',
            encoding="utf-8",
        )
        # Per-process self-contained settings also isolate macOS, which ignores XDG.
        isolated_editor = copy_editor(args.godot, project / "isolated-editor")
        fixture = Path(__file__).with_name("ai_chat_issues.gd" if args.case == "issues" else "ai_chat_steering.gd")
        shutil.copyfile(fixture, project / "gate.gd")
        entry = project / "offline-codex.js"
        entry.write_text(MOCK_CODEX, encoding="utf-8")
        (project / "stale-tool.txt").write_text("STALE_TOOL_FILE_CONTENT_MUST_NOT_BE_READ", encoding="utf-8")

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                model_requests.append(self.path)
                payload = json.dumps({"data": [{"id": "fixture"}]}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def do_POST(self):
                try:
                    body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                    messages = body["messages"]
                    users = [m["content"] for m in messages if m["role"] == "user"]
                    requests.append({"users": users})
                    assert self.headers.get("Authorization") == "Bearer isolated-fixture-key"
                    assert body["model"] == "fixture"
                    if args.case != "tools":
                        assert body.get("tools", []) == [], "Read-only fixture acquired tools"
                    if args.case == "issues":
                        (issue,) = users
                        assert issue in {"ISSUE_A", "ISSUE_B"}, users
                        (project / issue).touch()
                        deadline = time.monotonic() + 25
                        while not (project / "release-response").exists() and time.monotonic() < deadline:
                            time.sleep(0.02)
                        assert all((project / name).exists() for name in ("ISSUE_A", "ISSUE_B", "release-response"))
                        text = json.dumps({"result": issue + "_REPLY"})
                    elif len(requests) == 1:
                        assert users == ["STEERING_ORIGINAL"], users
                        (project / "server-waiting").touch()
                        deadline = time.monotonic() + 25
                        while not (project / "release-response").exists() and time.monotonic() < deadline:
                            time.sleep(0.02)
                        assert (project / "release-response").exists(), "Fixture did not release delayed request"
                        text = "STALE_ORIGINAL_REPLY"
                    else:
                        assert args.case in {"steering", "tools"}, (
                            "Stopped or different-mode input was automatically submitted"
                        )
                        assert len(requests) == 2, "Each supplement started another model request"
                        assert users == ["STEERING_ORIGINAL", "STEERING_ADDITION_ONE", "STEERING_ADDITION_TWO"], users
                        assert all(m.get("content") != "STALE_ORIGINAL_REPLY" for m in messages), (
                            "Stale response polluted model context"
                        )
                        if args.case == "tools":
                            calls = [call for m in messages for call in m.get("tool_calls", [])]
                            results = [m for m in messages if m["role"] == "tool"]
                            assert len(calls) == len(results) == 2, "Skipped batch lost tool-result pairing"
                            assert {m["tool_call_id"] for m in results} == {c["id"] for c in calls}
                            assert all("Skipped unexecuted proposal" in m["content"] for m in results), results
                            assert all(
                                "STALE_TOOL_FILE_CONTENT_MUST_NOT_BE_READ" not in m["content"] for m in results
                            ), "Stale tools executed"
                        text = "STEERING_APPLIED_OK"
                    message = {"role": "assistant", "content": text}
                    finish = "stop"
                    if len(requests) == 1 and args.case == "tools":
                        message = {
                            "role": "assistant",
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": f"stale_read_{i}",
                                    "type": "function",
                                    "function": {
                                        "name": "read_file",
                                        "arguments": json.dumps({"path": "res://stale-tool.txt"}),
                                    },
                                }
                                for i in range(2)
                            ],
                        }
                        finish = "tool_calls"
                    payload = json.dumps({"choices": [{"message": message, "finish_reason": finish}]}).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    pass
                except Exception as exc:
                    errors.append(str(exc))
                    self.send_error(500)

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
            STEERING_ENDPOINT=f"http://127.0.0.1:{server.server_port}/v1/chat/completions",
            STEERING_CASE=args.case,
            STEERING_CODEX="1" if args.codex else "",
            STEERING_CODEX_ENTRY=str(entry),
            STEERING_NODE=str(args.node.resolve()) if args.node else shutil.which("node") or "",
            STEERING_BRIDGE=str(Path(__file__).resolve().parents[2] / "tools/codebuddy_cli/godot_bridge.js"),
        )
        if args.codex and not env["STEERING_NODE"]:
            parser.error("--codex requires Node on PATH or --node")
        restored = None
        try:
            run = subprocess.run(
                [str(isolated_editor), "--headless", "--editor", "--path", str(project), "--script", "res://gate.gd"],
                env=env,
                cwd=project,
                capture_output=True,
                timeout=65,
            )
            if args.case in {"stop", "cancel", "issues"} and run.returncode == 0:
                seeded = json.loads((project / "steering-report.json").read_bytes())
                env["STEERING_CASE"] = "restore"
                restart = subprocess.run(
                    [
                        str(isolated_editor),
                        "--headless",
                        "--editor",
                        "--path",
                        str(project),
                        "--script",
                        "res://gate.gd",
                    ],
                    env=env,
                    cwd=project,
                    capture_output=True,
                    timeout=30,
                )
                args.out.with_suffix(".restart.stdout.log").write_bytes(restart.stdout)
                args.out.with_suffix(".restart.stderr.log").write_bytes(restart.stderr)
                restored = json.loads((project / "steering-report.json").read_bytes())
                restored["passed"] = (
                    restored.get("passed", False)
                    and restart.returncode == 0
                    and restored.get("snapshot") == seeded.get("final_snapshot")
                )
                (project / "steering-report.json").write_text(json.dumps(seeded), encoding="utf-8")
        finally:
            server.shutdown()
            server.server_close()
            worker.join()
        args.out.with_suffix(".stdout.log").write_bytes(run.stdout)
        args.out.with_suffix(".stderr.log").write_bytes(run.stderr)
        report_file = project / "steering-report.json"
        report = json.loads(report_file.read_bytes()) if report_file.exists() else {}
        report.update(
            case=args.case,
            restart=restored,
            requests=requests,
            model_requests=model_requests,
            errors=errors,
            native_exit_code=run.returncode,
            editor_sha256=hashlib.sha256(
                args.godot.with_name(args.godot.name.replace(".console.exe", ".exe")).read_bytes()
            ).hexdigest(),
            fixture_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__), fixture]},
            real_provider=False,
            model_transport="Codex bridge + offline JSONL CLI + loopback mock"
            if args.codex
            else "isolated loopback mock",
        )
        report["passed"] = (
            report.get("passed", False)
            and (restored is None or restored.get("passed", False))
            and run.returncode == 0
            and not errors
            and len(requests) == (2 if args.case in {"steering", "tools", "issues"} else 1)
        )
        args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report))
        return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
