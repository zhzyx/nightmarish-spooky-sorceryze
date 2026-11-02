"""Real native editor + real framework, isolated evidence; no model traffic allowed."""

import argparse
import http.server
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from olympus_test_source import active_source

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--receipt-delay", type=float, default=0)
    parser.add_argument("--max-frame-gap", type=float)
    parser.add_argument(
        "--mode",
        choices=[
            "recovery_receipt_failure",
            "receipt_retry",
            "receipt_cancel",
            "receipt_failure",
            "rejected",
            "accepted",
            "admitted",
            "cancel",
            "tool",
            "recovery",
            "recovery_rejected",
            "recovery_cancel",
        ],
        default="rejected",
    )
    args = parser.parse_args()
    requests = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append(body)
            message = {"role": "assistant", "content": "OLYMPUS_FIXTURE_REPLY"}
            if args.mode == "tool" and len(requests) == 1:
                message = {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "fixture-tool",
                            "type": "function",
                            "function": {"name": "list_scripts", "arguments": "{}"},
                        }
                    ],
                }
            response = json.dumps({
                "choices": [{"message": message, "finish_reason": "tool_calls" if "tool_calls" in message else "stop"}]
            }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with tempfile.TemporaryDirectory(prefix="olympus-gate-") as temporary:
            root = Path(temporary)
            shutil.copytree(ROOT / "Olympus", root / "Olympus", ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copytree(
                ROOT / "customizations/components/godot-host",
                root / "customizations/components/godot-host",
                ignore=shutil.ignore_patterns("__pycache__"),
            )
            (root / "tools").mkdir()
            shutil.copyfile(ROOT / "tools/olympus_bridge.py", root / "tools/olympus_bridge.py")
            if args.receipt_delay or args.mode in ("receipt_failure", "receipt_retry", "recovery_receipt_failure"):
                shutil.copyfile(root / "tools/olympus_bridge.py", root / "tools/bridge_impl.py")
                failure = (
                    'import json\nif len(sys.argv)>1 and sys.argv[1]=="flush":\n    from pathlib import Path\n    Path(sys.argv[sys.argv.index("--out")+1]).write_text(json.dumps({"ok":False}))\n    raise SystemExit(1)\n'
                    if args.mode in ("receipt_failure", "receipt_retry", "recovery_receipt_failure")
                    else ""
                )
                if args.mode in ("receipt_retry", "recovery_receipt_failure"):
                    failure = (
                        failure
                        .replace("import json", "import json\nfrom pathlib import Path")
                        .replace(
                            'sys.argv[1]=="flush":', 'sys.argv[1]=="flush" and not Path(__file__+".failed").exists():'
                        )
                        .replace(
                            "    from pathlib import Path", '    Path(__file__+".failed").write_text("failed once")'
                        )
                    )
                (root / "tools/olympus_bridge.py").write_text(
                    'import sys,time,runpy\nif len(sys.argv)>1 and sys.argv[1]=="flush": time.sleep('
                    + repr(args.receipt_delay)
                    + ")\n"
                    + failure
                    + 'runpy.run_path(__file__.replace("olympus_bridge.py","bridge_impl.py"),run_name="__main__")\n',
                    encoding="utf-8",
                )
            if args.mode in (
                "recovery_receipt_failure",
                "receipt_retry",
                "receipt_cancel",
                "receipt_failure",
                "accepted",
                "cancel",
                "tool",
                "recovery",
                "recovery_cancel",
            ):
                # Transport fixture only, never an Olympus admission or production framework.
                delay = 2000 if args.mode in ("cancel", "recovery_cancel") else 0
                (root / "Olympus/tools/agent-context.mjs").write_text(
                    f'setTimeout(()=>process.stdout.write("ISOLATED_FRAMEWORK_CONTEXT_FIXTURE"),{delay});',
                    encoding="utf-8",
                )
            # A deliberately absent upstream, never a production approval fixture.
            (root / ".olympus-local.json").write_text(
                json.dumps({"GONGGONG_FRAMEWORK_SOURCE": str(root / "missing-source")}), encoding="utf-8"
            )
            if args.mode == "admitted":
                # Real approved definitions and real source verification, isolated model transport/data.
                source = active_source(ROOT, ROOT / "Olympus")
                (root / ".olympus-local.json").write_text(
                    json.dumps({"GONGGONG_FRAMEWORK_SOURCE": str(source)}), encoding="utf-8"
                )
            subprocess.run(["git", "init", "--quiet", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "add", "Olympus"], check=True, capture_output=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(root),
                    "-c",
                    "user.name=Isolated Test",
                    "-c",
                    "user.email=test@example.invalid",
                    "-c",
                    "commit.gpgsign=false",
                    "commit",
                    "--quiet",
                    "-m",
                    "Isolated framework fixture",
                ],
                check=True,
            )
            subprocess.run(
                [
                    sys.executable,
                    str(root / "Olympus/extensions/hermes-files/hermes_files.py"),
                    "init",
                    "--repo",
                    str(root),
                ],
                check=True,
            )
            project = root / "project"
            project.mkdir()
            (project / "project.godot").write_text(
                '[application]\nconfig/name="Isolated Olympus validation"\n', encoding="utf-8"
            )
            shutil.copyfile(ROOT / "tests/editor/olympus_chat_gate.gd", project / "gate.gd")
            if args.mode.startswith("recovery"):
                journal_dir = project / ".godot/editor"
                journal_dir.mkdir(parents=True)
                call = {
                    "id": "pending-build",
                    "type": "function",
                    "function": {"name": "build_engine", "arguments": "{}"},
                }
                journal = {
                    "version": 1,
                    "agent": 0,
                    "tool_rounds": 1,
                    "tool_index": 0,
                    "model": "fixture",
                    "cli_model": "fixture",
                    "backend": 0,
                    "snapshot_id": "fixture-recovery",
                    "messages": [
                        {"role": "user", "content": "Isolated Olympus gate validation"},
                        {"role": "assistant", "content": "", "tool_calls": [call]},
                    ],
                    "tool_calls": [call],
                    "restart": {
                        "from_executable": str(root / "old.exe"),
                        "to_executable": str(args.godot.resolve()),
                        "token": "abc12345",
                        "attempt": 1,
                        "tool_call_id": "pending-build",
                        "tool_name": "build_engine",
                    },
                }
                (journal_dir / "ai_chat_resume.json").write_text(json.dumps(journal), encoding="utf-8")
            env = dict(
                os.environ,
                OLYMPUS_TEST_WORKSPACE=str(root),
                OLYMPUS_PYTHON=sys.executable,
                OLYMPUS_WORKSPACE=str(root),
                OLYMPUS_TEST_MODE="accepted" if args.mode == "admitted" else args.mode,
                OLYMPUS_TEST_ENDPOINT=f"http://127.0.0.1:{server.server_port}/v1/chat/completions",
            )
            # Isolate user settings, so tests cannot change real accounts or projects.
            for name in ("APPDATA", "LOCALAPPDATA", "XDG_CONFIG_HOME", "XDG_DATA_HOME"):
                env[name] = str(root / name)
                (root / name).mkdir()
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
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                timeout=75,
            )
            gaps = [
                float(line.split("=", 1)[1])
                for line in result.stdout.splitlines()
                if line.startswith("OLYMPUS_FRAME_GAP=")
            ]
            gaps = [gap for gap in gaps if gap >= 0]
            if gaps:
                print(
                    json.dumps({"max_frame_gap_seconds": max(gaps), "injected_flush_delay_seconds": args.receipt_delay})
                )
            if args.max_frame_gap is not None and args.mode not in ("rejected", "recovery_rejected"):
                assert gaps and max(gaps) < args.max_frame_gap, "UI stalled during receipt wait"
            marker = {
                "recovery_receipt_failure": "OLYMPUS_CHAT_RECOVERY_RECEIPT_FAILURE_OK",
                "receipt_retry": "OLYMPUS_CHAT_FIXTURE_ACCEPTED_OK",
                "receipt_cancel": "OLYMPUS_CHAT_RECEIPT_CANCEL_OK",
                "receipt_failure": "OLYMPUS_CHAT_RECEIPT_FAILURE_OK",
                "rejected": "OLYMPUS_CHAT_FAIL_CLOSED_OK",
                "recovery_rejected": "OLYMPUS_CHAT_FAIL_CLOSED_OK",
                "recovery": "OLYMPUS_CHAT_RECOVERY_OK",
                "recovery_cancel": "OLYMPUS_CHAT_FIXTURE_ACCEPTED_OK",
                "admitted": "OLYMPUS_CHAT_FIXTURE_ACCEPTED_OK",
                "accepted": "OLYMPUS_CHAT_FIXTURE_ACCEPTED_OK",
                "tool": "OLYMPUS_CHAT_FIXTURE_ACCEPTED_OK",
                "cancel": "OLYMPUS_CHAT_CANCEL_OK",
            }[args.mode]
            if result.returncode or marker not in result.stdout:
                print(result.stdout[-5000:])
                print(result.stderr[-5000:])
                return 1
            if args.mode in ("accepted", "admitted", "tool", "recovery_cancel", "receipt_retry"):
                assert len(requests) == (2 if args.mode == "tool" else 1)
                if args.mode == "admitted":
                    assert "ISOLATED_FRAMEWORK_CONTEXT_FIXTURE" not in requests[0]["messages"][0]["content"]
                    assert "athena" in requests[0]["messages"][0]["content"].lower()
                    assert "zeus" in requests[0]["messages"][0]["content"].lower()
                else:
                    assert "ISOLATED_FRAMEWORK_CONTEXT_FIXTURE" in requests[0]["messages"][0]["content"]
            else:
                assert not requests, "Rejected/cancelled chat reached the model endpoint"
            if args.mode == "receipt_failure":
                assert not requests
                assert list((root / ".olympus-outbox/chat").glob("*.json")), "Failed flush lost envelopes"
                print(
                    json.dumps({
                        "mode": args.mode,
                        "model_requests": 0,
                        "pending_preserved": True,
                        "production_data_written": False,
                    })
                )
                return 0
            events = [
                json.loads(p.read_text(encoding="utf-8")) for p in (root / "olympus-hermes-data/events").rglob("*.json")
            ]
            if args.mode == "recovery_receipt_failure":
                assert not any(
                    e["payload"].get("phase") == "restart_result_recovery"
                    and e["payload"].get("status") == "result_restored"
                    for e in events
                )
            event = next(e for e in events if e["source_ref"] == "godot-editor:chat-context-loader")
            assert event["payload"]["context_accepted"] is (args.mode not in ("rejected", "recovery_rejected"))
            assert "Isolated Olympus gate validation" not in json.dumps(events)
            if args.mode in ("recovery_rejected", "recovery_receipt_failure"):
                assert (project / ".godot/editor/ai_chat_resume.json").is_file(), (
                    "Rejected recovery lost its durable journal"
                )
            if args.mode not in ("rejected", "recovery_rejected"):
                if args.mode == "recovery_cancel":
                    assert {e["payload"]["status"] for e in events if e["kind"] == "request_end"} == {
                        "cancelled",
                        "completed",
                    }
                ending = next(
                    e
                    for e in events
                    if e["kind"] == "request_end"
                    and (args.mode not in ("recovery_cancel", "receipt_retry") or e["payload"]["status"] == "completed")
                )
                assert ending["payload"]["status"] == (
                    "cancelled"
                    if args.mode in ("cancel", "receipt_cancel")
                    else "paused"
                    if args.mode == "recovery"
                    else "failed"
                    if args.mode == "recovery_receipt_failure"
                    else "completed"
                )
                assert ending["agent"]["id"] == "athena"
                assert any(e["kind"] == "request" for e in events)
                if args.mode in ("accepted", "admitted", "tool"):
                    assert any(e.get("supersedes") for e in events)
                if args.mode == "tool":
                    assert len([e for e in events if e["payload"].get("context_accepted")]) == 2
                    assert any(e["payload"].get("phase") == "tool-1-0" and e.get("supersedes") for e in events)
            assert not list((root / ".olympus-outbox/chat").glob("*.json"))
            print(
                json.dumps({
                    "native_page": True,
                    "mode": args.mode,
                    "real_framework_called": args.mode in ("admitted", "rejected", "recovery_rejected"),
                    "model_transport_fixture": True,
                    "receipt_verified": True,
                    "model_requests": len(requests),
                    "production_data_written": False,
                })
            )
            return 0
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    sys.exit(main())
