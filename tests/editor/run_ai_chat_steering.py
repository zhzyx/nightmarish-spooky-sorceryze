"""Headless continuous-conversation acceptance against a loopback mock, without provider calls."""

import argparse
import ctypes
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from editor_test_isolation import copy_editor


class OwnedCliProcesses:
    def __init__(self):
        self.handles = {}
        self.lock = threading.Lock()
        self.kernel = None
        if os.name == "nt":
            self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            self.kernel.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
            self.kernel.OpenProcess.restype = ctypes.c_void_p
            self.kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
            self.kernel.WaitForSingleObject.restype = ctypes.c_uint32
            self.kernel.CloseHandle.argtypes = [ctypes.c_void_p]
            self.kernel.CloseHandle.restype = ctypes.c_int

    def observe(self, pid):
        with self.lock:
            if pid in self.handles:
                return
            if self.kernel is None:
                self.handles[pid] = None
                return
            handle = self.kernel.OpenProcess(0x00100000, False, pid)
            if not handle and ctypes.get_last_error() != 87:
                raise ctypes.WinError(ctypes.get_last_error())
            # An invalid PID means the observed worker already exited. A live
            # handle pins its process identity even if Windows later reuses PID.
            self.handles[pid] = handle

    def wait_for_exit(self, timeout=5.0):
        deadline = time.monotonic() + timeout
        with self.lock:
            handles = list(self.handles.items())
        for pid, handle in handles:
            if self.kernel is not None:
                if not handle:
                    continue
                remaining_ms = max(0, int((deadline - time.monotonic()) * 1000))
                result = self.kernel.WaitForSingleObject(handle, remaining_ms)
                if result == 0:
                    continue
                if result == 0xFFFFFFFF:
                    raise ctypes.WinError(ctypes.get_last_error())
                raise TimeoutError(f"Owned CLI process {pid} is still running before fixture cleanup")
            while True:
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    break
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"Owned CLI process {pid} is still running before fixture cleanup")
                time.sleep(0.05)

    def close(self):
        with self.lock:
            handles = list(self.handles.values())
            self.handles.clear()
        if self.kernel is not None:
            for handle in handles:
                if handle:
                    self.kernel.CloseHandle(handle)


@contextmanager
def temporary_fixture(parent, owned_cli, report_path):
    parent = parent.resolve()
    project = Path(tempfile.mkdtemp(prefix="chat-steering-", dir=parent)).resolve()
    if project.parent != parent:
        raise ValueError("Fixture cleanup target escaped its output directory")
    cleanup = {"passed": False}
    try:
        yield str(project)
    finally:
        try:
            owned_cli.wait_for_exit()
            deadline = time.monotonic() + 10.0
            retries = 0
            while True:
                try:
                    shutil.rmtree(project)
                    cleanup = {"passed": True, "retries": retries}
                    break
                except OSError as error:
                    if os.name != "nt" or error.winerror not in (32, 145) or time.monotonic() >= deadline:
                        raise
                    retries += 1
                    time.sleep(0.2)
        except BaseException as error:
            cleanup["error"] = f"{type(error).__name__}: {error}"
            raise
        finally:
            owned_cli.close()
            if report_path.is_file():
                report = json.loads(report_path.read_text(encoding="utf-8"))
                report["cleanup"] = cleanup
                report["passed"] = report.get("passed", False) and cleanup["passed"]
                report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


MOCK_CODEX = r"""
// Offline Codex JSONL fixture. Uses only the test loopback server.
const http = require('node:http');
if (process.argv.slice(2).join(' ') === 'login status') process.exit(0);
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
    if (process.env.STEERING_CASE === 'issues' && input.messages.some(m => m.role === 'user' && m.content === 'ISSUE_B')) {
        // Godot can only query child handles on Windows. B independently observes
        // A's OS process exiting while B's own response remains blocked.
        const fs = require('node:fs');
        const path = require('node:path');
        const folder = process.env.STEERING_FIXTURE_ROOT;
        const pid = Number(fs.readFileSync(path.join(folder, 'ISSUE_A'), 'utf8'));
        if (!Number.isSafeInteger(pid) || pid <= 0 || pid === process.pid) process.exit(8);
        fs.writeFileSync(path.join(folder, 'cli-b-probing'), String(pid));
        const timer = setInterval(() => {
            try { process.kill(pid, 0); }
            catch (error) {
                if (error.code !== 'ESRCH') process.exit(9);
                clearInterval(timer);
                fs.writeFileSync(path.join(folder, 'cli-a-exited'), String(process.pid));
            }
        }, 40);
        timer.unref();
    }
    const request = http.request(process.env.STEERING_ENDPOINT, {method: 'POST', headers: {
        'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body),
        Authorization: 'Bearer isolated-fixture-key', 'X-Fixture-CLI-Pid': String(process.pid)
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
    parser.add_argument(
        "--responses", action="store_true", help="Exercise the Responses wire format for concurrent Issues"
    )
    args = parser.parse_args()
    if args.responses and (args.case != "issues" or args.codex):
        parser.error("--responses requires the HTTP issues case")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    errors, requests, model_requests = [], [], []
    cli_pids = set()
    owned_cli = OwnedCliProcesses()
    with temporary_fixture(args.out.parent, owned_cli, args.out) as folder:
        project = Path(folder).resolve()
        (project / "project.godot").write_text(
            'config_version=5\n[application]\nconfig/name="Steering Fixture"\n'
            '[rendering]\nrenderer/rendering_method="gl_compatibility"\n',
            encoding="utf-8",
        )
        # Per-process self-contained settings also isolate macOS, which ignores XDG.
        isolated_editor = copy_editor(args.godot, project / "isolated-editor")
        if args.codex:
            installation = isolated_editor.parent
            (installation / "SConstruct").touch()
            tools = Path(__file__).resolve().parents[2] / "tools"
            for provider in ("codex_cli", "codebuddy_cli"):
                target = installation / "tools" / provider
                target.mkdir(parents=True)
                for source in (tools / provider).glob("*.js"):
                    shutil.copyfile(source, target / source.name)
            shutil.copyfile(tools / "codex_cli/attach_job.ps1", installation / "tools/codex_cli/attach_job.ps1")
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
                    if args.responses:
                        assert self.path == "/v1/responses" and body["stream"] is False and body["store"] is False
                    messages = body["input" if args.responses else "messages"]
                    users = [m["content"] for m in messages if m["role"] == "user"]
                    requests.append({"users": users})
                    if args.codex:
                        pid = int(self.headers.get("X-Fixture-CLI-Pid", 0))
                        assert pid > 0, "Missing CLI worker PID"
                        owned_cli.observe(pid)
                        cli_pids.add(pid)
                    assert self.headers.get("Authorization") == "Bearer isolated-fixture-key"
                    assert body["model"] == "fixture"
                    if args.case != "tools":
                        assert body.get("tools", []) == [], "Read-only fixture acquired tools"
                    if args.case == "issues":
                        (issue,) = users
                        assert issue in {"ISSUE_A", "ISSUE_B"}, users
                        (project / issue).write_text(str(pid) if args.codex else "", encoding="ascii")
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
                    response = {"choices": [{"message": message, "finish_reason": finish}]}
                    if args.responses:
                        response = {
                            "status": "completed",
                            "output": [{"type": "message", "content": [{"type": "output_text", "text": text}]}],
                        }
                    payload = json.dumps(response).encode()
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
        # Join the bounded handlers before checking their observed CLI handles.
        server.daemon_threads = False
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        env = {key: value for key, value in os.environ.items() if not key.startswith("GONGGONG_")}
        for key in ["OPENAI_API_KEY", "GODOT_AI_API_KEY", "GONGGONG_WORKSPACE", "GONGGONG_TEST_WORKSPACE"]:
            env.pop(key, None)
        for key in ["APPDATA", "LOCALAPPDATA", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "TEMP", "TMP"]:
            env[key] = str(project / key)
            (project / key).mkdir()
        env.update(
            STEERING_ENDPOINT=f"http://127.0.0.1:{server.server_port}/v1/chat/completions",
            STEERING_CASE=args.case,
            STEERING_FIXTURE_ROOT=str(project),
            STEERING_RESPONSES="1" if args.responses else "",
            STEERING_CODEX="1" if args.codex else "",
            STEERING_CODEX_ENTRY=str(entry),
            STEERING_NODE=str(args.node.resolve()) if args.node else shutil.which("node") or "",
            STEERING_BRIDGE=str(Path(__file__).resolve().parents[2] / "tools/codebuddy_cli/godot_bridge.js"),
        )
        if args.codex and not env["STEERING_NODE"]:
            parser.error("--codex requires Node on PATH or --node")
        settings = isolated_editor.parent / "editor_data/editor_settings-4.8.tres"
        settings.write_text(
            '[gd_resource type="EditorSettings" format=3]\n\n[resource]\nai_chat/backend = 0\n'
            + "ai_chat/endpoint = "
            + json.dumps(env["STEERING_ENDPOINT"])
            + "\n",
            encoding="utf-8",
        )
        if args.codex:
            entry.chmod(0o755)
            private_config = isolated_editor.parent / "editor_data/gonggong/config.json"
            private_config.parent.mkdir(parents=True, exist_ok=True)
            private_config.write_text(
                json.dumps({"schema_version": 1, "runtimes": {"codex": str(entry), "node": env["STEERING_NODE"]}}),
                encoding="utf-8",
            )
        restored = None
        try:
            try:
                run = subprocess.run(
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
                    timeout=65,
                )
            except subprocess.TimeoutExpired as error:
                args.out.with_suffix(".stdout.log").write_bytes(error.stdout or b"")
                args.out.with_suffix(".stderr.log").write_bytes(error.stderr or b"")
                raise
            if args.case in {"stop", "cancel", "issues"} and run.returncode == 0:
                seeded = json.loads((project / "steering-report.json").read_bytes())
                env["STEERING_CASE"] = "restore"
                try:
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
                except subprocess.TimeoutExpired as error:
                    args.out.with_suffix(".restart.stdout.log").write_bytes(error.stdout or b"")
                    args.out.with_suffix(".restart.stderr.log").write_bytes(error.stderr or b"")
                    args.out.with_suffix(".stdout.log").write_bytes(run.stdout)
                    args.out.with_suffix(".stderr.log").write_bytes(run.stderr)
                    raise
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
            responses=args.responses,
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
            cli_pids=sorted(cli_pids),
            model_transport="Codex bridge + offline JSONL CLI + loopback mock"
            if args.codex
            else "isolated loopback mock",
        )
        report["passed"] = (
            report.get("passed", False)
            and (restored is None or restored.get("passed", False))
            and run.returncode == 0
            and (not args.codex or args.case != "issues" or len(cli_pids) == 2)
            and not errors
            and len(requests) == (2 if args.case in {"steering", "tools", "issues"} else 1)
        )
        args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report))
        return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
