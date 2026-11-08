"""Actual isolated headless editor/HTTP/native-confirmation fixtures for #559.

The test driver emits native confirmation signals in its private editor. These
are simulated host confirmations, not evidence of human approval or a provider
business result. No production project, credentials or editor is used.
"""

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import struct
import subprocess
import tempfile
import threading
import time
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from editor_test_isolation import copy_editor

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("editor_client", ROOT / "tools/editor_control_client.py")
if spec is None or spec.loader is None:
    raise RuntimeError("Editor client module loader is unavailable")
client_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client_module)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    records = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            body = json.dumps({"data": [{"id": "fixture-model", "reasoning_efforts": ["high"]}]}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
            body = json.dumps({
                "choices": [
                    {"message": {"role": "assistant", "content": "PRIVATE_FIXTURE_ONLY"}, "finish_reason": "stop"}
                ]
            }).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    os.environ.pop("GONGGONG_WORKSPACE", None)
    with tempfile.TemporaryDirectory(prefix="chat-command-gaps-") as tmp:
        folder = Path(tmp)
        binary = copy_editor(args.godot, folder / "editor")
        artifact_sha256 = hashlib.sha256(binary.read_bytes()).hexdigest()
        project = folder / "project"
        project.mkdir()
        (project / "project.godot").write_text(
            'config_version=5\n[application]\nconfig/name="Private chat command gaps"\n'
        )
        shutil.copyfile(ROOT / "tests/editor/chat_command_gaps.gd", project / "gate.gd")
        (project / "entry.js").write_text("// private fixture path only\n")
        settings = {
            "ai_chat/backend": 0,
            "ai_chat/endpoint": f"http://127.0.0.1:{server.server_port}/v1/chat/completions",
            "ai_chat/model": "fixture-model",
            "ai_chat/editor_control_bridge_enabled": True,
        }
        (binary.parent / "editor_data/editor_settings-4.8.tres").write_text(
            '[gd_resource type="EditorSettings" format=3]\n\n[resource]\n'
            + "\n".join(key + " = " + json.dumps(value) for key, value in settings.items())
            + "\n"
        )
        env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("GONGGONG_") and key not in {"OPENAI_API_KEY", "GODOT_AI_API_KEY"}
        }
        for key in ["APPDATA", "LOCALAPPDATA", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "TEMP", "TMP"]:
            (folder / key).mkdir()
            env[key] = str(folder / key)
        log = folder / "editor.log"
        with log.open("wb") as output:
            process = subprocess.Popen(
                [str(binary), "--headless", "--editor", "--path", str(project), "--script", "res://gate.gd"],
                env=env,
                stdout=output,
                stderr=subprocess.STDOUT,
            )
            serial = 0

            def until(callback, seconds=25):
                deadline = time.monotonic() + seconds
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise AssertionError("Private editor exited: " + log.read_text(errors="replace")[-6000:])
                    value = callback()
                    if value:
                        return value
                    time.sleep(0.03)
                raise AssertionError("Private fixture timed out: " + log.read_text(errors="replace")[-6000:])

            def command(action, **values):
                nonlocal serial
                serial += 1
                pending = project / "command.pending"
                pending.write_text(json.dumps({"serial": serial, "action": action, **values}))
                pending.replace(project / "fixture-command.json")
                target = project / f"ack-{serial}.json"
                until(target.exists)
                return json.loads(target.read_text())

            try:
                until((project / "ready.json").exists, 90)
                client = client_module.EditorClient(project, process.pid)
                request_counter = 0

                def operation(action, **values):
                    nonlocal request_counter
                    if action not in {
                        "chat_state",
                        "chat_stop",
                        "chat_sessions",
                        "chat_schedules",
                        "chat_configuration",
                        "chat_attachments",
                        "chat_history",
                        "chat_host_context",
                    }:
                        until(lambda: not command("state")["send_disabled"])
                    request_counter += 1
                    ident = f"private-chat-{request_counter}"
                    result = client.route({
                        "intent": "engine_operation",
                        "request_id": ident,
                        "source": "private-chat-fixture",
                        "operation": {"action": action, **values},
                    })
                    return ident, result

                def detail(result):
                    for key in ("result", "outcome"):
                        if isinstance(result.get(key), dict):
                            return result[key]
                    return result

                def read(action, **values):
                    _, result = operation(action, **values)
                    result = detail(result)
                    assert result.get("ok") is True, result
                    records.append({"case": action, "state": "passed"})
                    return result

                def mutate(action, **values):
                    ident, result = operation(action, **values)
                    assert result.get("confirmation_required") and result.get("manual_confirmation_required"), result
                    assert command("approve")["visible"], result
                    terminal = until(
                        lambda: (
                            r
                            if (r := client.status(ident, "private-chat-fixture")).get("state")
                            != "awaiting_confirmation"
                            else None
                        )
                    )
                    assert detail(terminal).get("ok") is True, terminal
                    if action in {"chat_set_model_id", "chat_set_cli_path", "chat_set_runtime_field"}:
                        # The normal native model-refresh debounce is 0.5s.
                        time.sleep(0.65)
                        until(lambda: not command("state")["send_disabled"])
                    records.append({"case": action, "state": "passed", "confirmation": "private native signal"})
                    return detail(terminal)

                parent = read("chat_sessions")["rows"][0]["agent_id"]
                ident, result = operation("chat_rename_session", agent_id=parent, value="Renamed parent")
                assert result.get("manual_confirmation_required") and command("state")["title"] != "Renamed parent", (
                    result
                )
                command("approve")
                assert detail(client.status(ident, "private-chat-fixture")).get("ok"), client.status(
                    ident, "private-chat-fixture"
                )
                assert command("state")["title"] == "Renamed parent"
                records.append({"case": "rename waits despite autoexec", "state": "passed"})
                ident, result = operation("chat_rename_session", agent_id=parent, value="Stale forbidden")
                command("draft", value="changed after proposal")
                command("approve")
                terminal = client.status(ident, "private-chat-fixture")
                assert detail(terminal).get("error") == "chat_changed_since_confirmation", terminal
                assert command("state")["title"] == "Renamed parent"
                command("draft", value="")
                records.append({"case": "stale confirmation rejected", "state": "passed"})
                child = mutate("chat_create_child", parent_id=parent)["child_id"]
                rows = read("chat_sessions")["rows"]
                assert next(row for row in rows if row["agent_id"] == child)["parent_id"] == parent
                _, rejection = operation("chat_create_child", parent_id=child)
                assert detail(rejection).get("error") == "invalid_child_parent_or_capacity", rejection
                mutate("chat_close_session", agent_id=child)
                assert len(read("chat_sessions")["rows"]) == 1
                definition = {"title": "Fixture schedule", "prompt": "private fixture only", "frequency": 2, "unit": 1}
                schedule = mutate("chat_schedule_create", value=definition)["schedule_id"]
                assert read("chat_schedules")["rows"][0]["frequency"] == 2
                definition["frequency"] = 3
                mutate("chat_schedule_update", schedule_id=schedule, value=definition)
                mutate("chat_schedule_enable", schedule_id=schedule, value=False)
                assert read("chat_schedules")["rows"][0]["enabled"] is False
                mutate("chat_schedule_select", schedule_id=schedule)
                mutate("chat_schedule_run", schedule_id=schedule)
                run_session = next(row for row in read("chat_sessions")["rows"] if row["kind"] == "scheduled")
                state = read("chat_state")
                _, stopped = operation(
                    "chat_stop", value={"conversation_id": state["conversation_id"], "generation": state["generation"]}
                )
                assert detail(stopped).get("ok") is True, stopped
                mutate("chat_close_session", agent_id=run_session["agent_id"])
                mutate("chat_schedule_delete", schedule_id=schedule)
                assert read("chat_schedules")["total"] == 0
                mutate("chat_set_model_id", value="fixture-model")
                mutate("chat_set_reasoning", value="high")
                assert read("chat_configuration")["configuration"]["reasoning"] == "high"
                _, rejection = operation("chat_set_reasoning", value="unadvertised")
                assert detail(rejection).get("error") == "unsupported_reasoning_effort", rejection
                mutate("chat_set_cli_path", field="codebuddy_bridge", value=str(project / "entry.js"))
                mutate(
                    "chat_set_runtime_field", field="node", value=shutil.which("node") or str(Path(os.sys.executable))
                )
                # Tamper only compressed headers in tiny private fixtures. The
                # native header query must reject before pixel decompression.
                for extension in ["png", "jpg", "webp"]:
                    data = bytearray((project / ("tiny." + extension)).read_bytes())
                    if extension == "png":
                        data[16:24] = struct.pack(">II", 8193, 8193)
                        data[29:33] = struct.pack(">I", zlib.crc32(data[12:29]))
                    elif extension == "jpg":
                        marker = next(
                            i
                            for i in range(len(data) - 9)
                            if data[i] == 255
                            and data[i + 1] in {192, 193, 194, 195, 197, 198, 199, 201, 202, 203, 205, 206, 207}
                        )
                        data[marker + 5 : marker + 9] = struct.pack(">HH", 65535, 65535)
                    else:
                        marker = data.index(b"VP8L") + 8
                        assert data[marker] == 47
                        bits = int.from_bytes(data[marker + 1 : marker + 5], "little")
                        data[marker + 1 : marker + 5] = ((bits & 0xF0000000) | 8192 | (8192 << 14)).to_bytes(
                            4, "little"
                        )
                    hostile = project / ("oversize." + extension)
                    hostile.write_bytes(data)
                    _, rejected = operation("chat_attachment_add", value=str(hostile))
                    assert detail(rejected).get("error") == "attachment_image_header_invalid_or_oversize", rejected
                    assert not rejected.get("confirmation_required"), rejected
                    records.append({"case": extension + " oversized header rejected before decode", "state": "passed"})
                ident, proposal = operation("chat_attachment_add", value=str(project / "tiny.png"))
                assert proposal.get("confirmation_required"), proposal
                command("change_image")
                command("approve")
                stale = client.status(ident, "private-chat-fixture")
                assert detail(stale).get("error") == "chat_changed_since_confirmation", stale
                records.append({"case": "image file replacement rejects stale confirmation", "state": "passed"})
                mutate("chat_attachment_add", value=str(project / "tiny.png"))
                assert read("chat_attachments")["total"] == 1
                mutate("chat_attachment_remove", index=0)
                assert read("chat_attachments")["total"] == 0
                _, unavailable = operation("chat_attachment_paste")
                assert detail(unavailable).get("error") == "clipboard_image_unavailable", unavailable
                records.append({"case": "headless clipboard reports unavailable", "state": "passed"})
                for extension in ["jpg", "webp"]:
                    mutate("chat_attachment_add", value=str(project / ("tiny." + extension)))
                    assert read("chat_attachments")["total"] == 1
                    mutate("chat_attachment_remove", index=0)
                read("chat_history", limit=1)
                assert mutate("chat_show_history")["opened"] is True
                _, rejection = operation("chat_show_changes", value="unrelated-snapshot")
                assert detail(rejection).get("error") == "snapshot_not_in_current_conversation", rejection
                host = read("chat_host_context")
                assert host["mounted"] is False
                _, rejection = operation(
                    "chat_host_send_message", host_instance=host["host_instance"], value="do not send"
                )
                assert detail(rejection).get("error") == "mounted_host_owner_changed_or_unbound", rejection
                command("tools", value=False)
                _, rejection = operation("chat_sessions")
                assert rejection.get("error") == "permission_denied", rejection
                command("tools", value=True)
                mutate("chat_close_session", agent_id=parent)
                assert len(read("chat_sessions")["rows"]) == 1  # native last-parent replacement
                command("exit")
                process.wait(timeout=15)
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=15)
                args.out.parent.mkdir(parents=True, exist_ok=True)
                args.out.with_suffix(".log").write_bytes(log.read_bytes())
    server.shutdown()
    args.out.write_text(
        json.dumps(
            {
                "ok": True,
                "issue_number": 559,
                "request_id": "editor-command-gaps-batch-20261108",
                "editor_sha256": artifact_sha256,
                "cases": records,
                "limitations": [
                    "Private native confirmations simulate the host; no human approval claimed.",
                    "No production LLM/account, mounted-host successful owner flow, scheduler actual business execution, CodeBuddy provider, OS UI or visual rendering acceptance claimed.",
                    "Positive clipboard image input requires a display; headless verifies explicit unavailability only.",
                    "Nonempty historical snapshot diff viewing/restoration were not exercised; empty history view and foreign snapshot refusal were verified.",
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    print(f"CHAT_COMMAND_GAPS_NATIVE_OK {len(records)}")


if __name__ == "__main__":
    main()
