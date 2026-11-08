"""Private macOS native socket acceptance; offline model/Issue fixtures only.

Run directly using /usr/bin/python3 from Codex desktop. No production bridge,
application, history or global settings are opened. Model replies are fixtures.
"""

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from editor_test_isolation import copy_editor
from external_chat_consultation import consultation_reply, run_consultation
from run_design_batch import BRIDGE, git, tool_call

ROOT = Path(__file__).resolve().parents[2]


def load_client(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


instruction_client = load_client("editor_instruction_client")
EditorInstructionClient = instruction_client.EditorInstructionClient
InstructionClientError = instruction_client.InstructionClientError
EditorClient = load_client("editor_control_client").EditorClient


def await_json(path, process, timeout=60):
    deadline = time.monotonic() + timeout
    while not path.exists():
        if process.poll() is not None or time.monotonic() > deadline:
            raise AssertionError("Private fixture exited or timed out: " + path.name)
        time.sleep(0.03)
    return json.loads(path.read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--node", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--untrusted-python", type=Path)
    parser.add_argument("--scenario", choices=("production", "consultation"), default="production")
    args = parser.parse_args()
    if sys.platform != "darwin":
        parser.error("This native OS peer acceptance is macOS only")
    os.environ.pop("GONGGONG_WORKSPACE", None)
    report = {"ok": False, "model": "offline typed-loop fixture, not production LLM", "checks": [], "errors": []}
    report["source_sha256"] = {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in (
            "editor/docks/ai_chat_dock.cpp",
            "editor/docks/ai_chat_dock.h",
            "editor/docks/ai_chat_external_chat.cpp",
            "tools/editor_instruction_client.py",
            "tests/editor/run_external_chat_submit.py",
            "tests/editor/external_chat_consultation.py",
            "tests/editor/external_chat_submit.gd",
        )
    }
    process = None
    calls = []
    release_hold = threading.Event()
    hold_started = threading.Event()
    with tempfile.TemporaryDirectory(prefix="external-chat-private-") as temporary:
        folder = Path(temporary).resolve()
        original = folder / "original"
        original.mkdir()
        remote = folder / "remote.git"
        git(folder, "init", "--bare", str(remote))
        git(original, "init", "-b", "main")
        git(original, "config", "user.name", "Offline Fixture")
        git(original, "config", "user.email", "fixture@example.invalid")
        git(original, "remote", "add", "origin", "https://github.com/example/design-batch.git")
        git(original, "config", "url." + str(remote) + ".insteadOf", "https://github.com/example/design-batch.git")
        files = {
            "work-items.json": json.dumps({
                "repository": "example/design-batch",
                "tenant_id": "fixture",
                "category_labels": ".github/labels.json",
            }),
            ".github/labels.json": '[{"name":"type:bug"}]',
            "SConstruct": "# private fixture\n",
            "tools/gonggong_bridge.py": BRIDGE,
            "tools/editor_self_build.py": "# private fixture build entry\n",
            "editor/source.cpp": "OFFLINE_SOURCE\n",
            "gonggong-diting-data/dataset.json": json.dumps({
                "schema_version": 1,
                "dataset_id": "00000000-0000-4000-8000-000000000441",
                "name": "gonggong-diting-data",
                "origin_framework": "gonggong",
            }),
            "gonggong-diting-data/.gitattributes": "* text eol=lf\n",
        }
        for name, content in files.items():
            path = original / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        git(original, "add", ".")
        git(original, "commit", "-m", "offline external chat fixture")
        git(original, "push", "origin", "main")
        git(original, "checkout", "-b", "existing-owner")
        project = original / "samples/project"
        project.mkdir(parents=True)
        (project / "project.godot").write_text(
            'config_version=5\n[application]\nconfig/name="External Chat Fixture"\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n'
        )
        shutil.copyfile(Path(__file__).with_name("external_chat_submit.gd"), project / "gate.gd")
        issue = {
            "number": 441,
            "html_url": "https://github.com/example/design-batch/issues/441",
            "state": "open",
            "updated_at": "2026-11-08T00:00:00Z",
            "body": "<!-- gonggong-request:design-batch-fixture -->",
            "labels": [{"name": name} for name in ("type:bug", "status:in-progress", "workspace:gonggong")],
        }
        gh = folder / "fake-gh"
        gh.write_text(
            "#!"
            + sys.executable
            + "\nimport json,sys\nassert sys.argv[-1].endswith('/441')\nprint(json.dumps("
            + repr(issue)
            + "))\n"
        )
        gh.chmod(0o700)
        git_wrapper = folder / "git"
        git_wrapper.write_text(
            "#!"
            + sys.executable
            + '\nimport os,sys\na=sys.argv[1:]\nif a[-3:]==["remote","get-url","origin"]: print("https://github.com/example/design-batch.git")\nelse: os.execv("/usr/bin/git",["git",*a])\n'
        )
        git_wrapper.chmod(0o700)
        binary = copy_editor(args.godot, folder / "private-editor")
        (folder / "SConstruct").touch()
        (folder / "tools").symlink_to(ROOT / "tools", target_is_directory=True)
        report["artifact_sha256"] = hashlib.sha256(binary.read_bytes()).hexdigest()
        peer_probe = folder / "peer_probe.py"
        peer_probe.write_text(
            "import sys,json\nfrom pathlib import Path\nsys.path.insert(0,"
            + repr(str(ROOT / "tools"))
            + ")\nfrom editor_instruction_client import EditorInstructionClient,InstructionClientError\ntry: result=EditorInstructionClient(sys.argv[1],int(sys.argv[2])).context()\nexcept InstructionClientError as e: result={'ok':False,'error':str(e)}\nPath(sys.argv[3]).write_text(json.dumps(result))\n"
        )
        consultation_target = project / "consultation-sentinel.txt"
        consultation_target.write_text("CONSULTATION_READ_SENTINEL")
        gh_calls = folder / "gh-calls.jsonl"
        gh.write_text(
            gh.read_text().replace(
                "import json,sys\n",
                "import json,sys\nfrom pathlib import Path\nPath("
                + repr(str(gh_calls))
                + ").open('a').write(json.dumps(sys.argv[1:])+'\\n')\n",
            )
        )

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                data = json.dumps({"data": [{"id": "external-chat-fixture"}]}).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_POST(self):
                try:
                    body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                    prompt = next(x["content"] for x in reversed(body["messages"]) if x["role"] == "user")
                    calls.append(prompt)
                    if args.scenario == "consultation":
                        message = consultation_reply(body, consultation_target, hold_started, release_hold)
                    elif prompt == "DESIGN_BATCH_WARMUP":
                        message = {"role": "assistant", "content": "EXTERNAL_WARMUP_OK"}
                    elif prompt == "EXTERNAL_CHAT_SUBMITTED":
                        results = [
                            x
                            for x in body["messages"]
                            if x["role"] == "tool" and x.get("tool_call_id") == "internal-submit"
                        ]
                        if not results:
                            message = tool_call(
                                "internal-submit",
                                "route_engine_message",
                                {
                                    "intent": "engine_operation",
                                    "request_id": "forbidden-internal",
                                    "source": "desktop.codex",
                                    "operation": {
                                        "action": "chat_submit_instruction",
                                        "value": {"text": "NEVER_SEND", "expected": {}},
                                    },
                                },
                            )
                            message["tool_calls"].extend(
                                tool_call(
                                    "internal-cached-submit",
                                    "route_engine_message",
                                    {
                                        "intent": "engine_operation",
                                        "request_id": "submit-once",
                                        "source": "desktop.codex",
                                        "operation": {
                                            "action": "chat_submit_instruction",
                                            "value": {"text": "EXTERNAL_CHAT_SUBMITTED", "expected": expected},
                                        },
                                    },
                                )["tool_calls"]
                            )
                        else:
                            assert "trusted_desktop_peer_required" in results[-1]["content"]
                            cached = next(
                                x["content"]
                                for x in body["messages"]
                                if x.get("tool_call_id") == "internal-cached-submit"
                            )
                            assert "trusted_desktop_peer_required" in cached
                            message = {"role": "assistant", "content": "EXTERNAL_CHAT_ACCEPTED"}
                    elif prompt == "EXTERNAL_CHAT_HOLD":
                        hold_started.set()
                        assert release_hold.wait(30)
                        message = {"role": "assistant", "content": "EXTERNAL_HOLD_FINISHED"}
                    elif prompt == "FIXTURE_QUEUED_MESSAGE":
                        message = {"role": "assistant", "content": "EXTERNAL_STEER_OK"}
                    else:
                        raise AssertionError("Unexpected model request: " + prompt[:100])
                    data = json.dumps({"choices": [{"message": message, "finish_reason": "stop"}]}).encode()
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                except Exception as error:
                    if args.scenario == "consultation" and isinstance(error, (BrokenPipeError, ConnectionResetError)):
                        return
                    report["errors"].append(type(error).__name__ + ": " + str(error))
                    self.send_error(500)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        endpoint = f"http://127.0.0.1:{server.server_port}/v1/chat/completions"
        settings = binary.parent / "editor_data/editor_settings-4.8.tres"
        settings.write_text(
            '[gd_resource type="EditorSettings" format=3]\n\n[resource]\n'
            + "\n".join(
                k + " = " + json.dumps(v)
                for k, v in {
                    "ai_chat/backend": 0,
                    "ai_chat/endpoint": endpoint,
                    "ai_chat/model": "external-chat-fixture",
                    "ai_chat/editor_control_bridge_enabled": True,
                }.items()
            )
            + "\n"
        )
        env = {
            k: v
            for k, v in os.environ.items()
            if not k.startswith("GONGGONG_") and k not in ("OPENAI_API_KEY", "GODOT_AI_API_KEY")
        }
        for key in ("APPDATA", "LOCALAPPDATA", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "TEMP", "TMP"):
            (folder / key).mkdir()
            env[key] = str(folder / key)
        env.update(
            DESIGN_BATCH_ROOT=str(original),
            DESIGN_BATCH_PYTHON=sys.executable,
            DESIGN_BATCH_SOURCE=str(ROOT),
            DESIGN_BATCH_NODE=str(args.node.resolve()),
            DESIGN_BATCH_ENDPOINT=endpoint,
            DESIGN_BATCH_FINALIZED="# Private fixture\n",
            EXTERNAL_CHAT_PEER_PROBE=str(peer_probe),
            EXTERNAL_CHAT_SCENARIO=args.scenario,
            GONGGONG_GH=str(gh),
            GONGGONG_GIT=str(git_wrapper),
            PATH=str(folder) + os.pathsep + env.get("PATH", ""),
        )
        command = [str(binary), "--headless", "--editor", "--path", str(project), "--script", "res://gate.gd"]
        output = []
        command_number = 0

        def start(restore=False):
            nonlocal process
            (project / "external-ready.json").unlink(missing_ok=True)
            (project / "external-command.json").unlink(missing_ok=True)
            run_env = dict(env, EXTERNAL_CHAT_PHASE="restore" if restore else "initial")
            process = subprocess.Popen(
                command, env=run_env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            ready = await_json(project / "external-ready.json", process)
            return EditorInstructionClient(project, ready["pid"])

        def fixture(name, value=None):
            nonlocal command_number
            command_number += 1
            content = {"id": command_number, "name": name, "value": value}
            pending = project / "external-command.json.pending"
            pending.write_text(json.dumps(content))
            pending.replace(project / "external-command.json")
            return await_json(project / f"external-ack-{command_number}.json", process)

        def check(label, value):
            assert value, label
            report["checks"].append(label)

        def rejected(client, label, text, expected, error):
            result = client.submit(text, expected, label)
            check(label, not result["ok"] and result.get("error") == error)
            return result

        def wait_text(marker):
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                state = fixture("read")
                if marker in state["text"] and not state["busy"]:
                    return state
                time.sleep(0.05)
            raise AssertionError("Missing native marker " + marker)

        try:
            client = start()
            if args.scenario == "consultation":
                run_consultation(
                    client,
                    fixture,
                    check,
                    rejected,
                    wait_text,
                    calls,
                    report,
                    hold_started,
                    release_hold,
                    EditorClient(project, process.pid),
                )
                check("no_issue_intake_or_write", not gh_calls.exists())
                check("no_production_candidate_created", not (original / ".git/gonggong-engine-candidates").exists())
                check("no_model_file_write", consultation_target.read_text() == "CONSULTATION_READ_SENTINEL")
                check("no_model_command_execution", not (project / "forbidden-command").exists())
                report["ok"] = not report["errors"]
                return 0 if report["ok"] else 1
            initial = client.context()
            report["initial_peer_reply"] = initial
            expected = initial["context"]
            report["actual_peer_allow"] = {
                k: initial[k] for k in ("authenticated_desktop_peer", "peer_pid", "trusted_desktop_pid", "engine_pid")
            }
            check("kernel_verified_desktop_peer", initial["ok"] and initial["authenticated_desktop_peer"])
            check(
                "known_parent_candidate_owner",
                expected["owner"] == expected["conversation_id"] and expected["issue_number"] == 441,
            )
            first = client.submit("EXTERNAL_CHAT_SUBMITTED", expected, "submit-once")
            check(
                "atomic_submit_requested",
                first["ok"] and first["instruction_submitted"] and first["business_completed"] is False,
            )
            wait_text("EXTERNAL_CHAT_ACCEPTED")
            count = len(calls)
            duplicate = client.submit("EXTERNAL_CHAT_SUBMITTED", expected, "submit-once")
            check("same_id_does_not_resend", duplicate["ok"] and duplicate["idempotent"] and len(calls) == count)
            rejected(client, "changed-id-payload", "OTHER", expected, "chat_instruction_state_changed")
            conflict = client.submit("OTHER", expected, "submit-once")
            check("same_id_changed_payload_refused", not conflict["ok"] and conflict["error"] == "request_id_conflict")
            check(
                "internal_model_tool_refused", calls.count("EXTERNAL_CHAT_SUBMITTED") == 2 and "NEVER_SEND" not in calls
            )
            fixture("close_prompt")
            rejected(client, "pending-parent-close", "NEVER_SEND", client.context()["context"], "parent_close_pending")
            fixture("close_cancel")
            check(
                "close_cancel_restores_availability",
                client.context()["context"]["instruction_available"] and len(calls) == count,
            )
            tcp = EditorClient(project, process.pid)
            denied = tcp.route({
                "intent": "engine_operation",
                "source": "fixture",
                "request_id": "tcp-forbidden",
                "operation": {
                    "action": "chat_submit_instruction",
                    "value": {"text": "NEVER_SEND", "expected": client.context()["context"]},
                },
            })
            check("ordinary_tcp_cannot_submit", denied.get("error") == "trusted_desktop_peer_required")
            cached_tcp = tcp.route({
                "intent": "engine_operation",
                "source": "desktop.codex",
                "request_id": "submit-once",
                "operation": {
                    "action": "chat_submit_instruction",
                    "value": {"text": "EXTERNAL_CHAT_SUBMITTED", "expected": expected},
                },
            })
            check(
                "tcp_cannot_recover_as_trusted_peer",
                cached_tcp.get("error") == "trusted_desktop_peer_required" and len(calls) == count,
            )
            numeric_context = client.context()["context"]
            for label, field, value in [
                ("boolean", "generation", True),
                ("fraction", "generation", 1.5),
                ("unsafe", "generation", 9007199254740992),
                ("extra", "unexpected", "field"),
            ]:
                changed_context = dict(numeric_context)
                changed_context[field] = value
                rejected(client, "context-" + label, "NEVER_SEND", changed_context, "chat_instruction_state_changed")
            missing_context = dict(numeric_context)
            missing_context.pop("snapshot_id")
            rejected(client, "context-missing", "NEVER_SEND", missing_context, "chat_instruction_state_changed")
            stale = client.context()["context"]
            fixture("draft", "unsent human draft")
            rejected(client, "draft-race", "NEVER_SEND", stale, "chat_instruction_state_changed")
            rejected(client, "nonempty-draft", "NEVER_SEND", client.context()["context"], "draft_not_empty")
            check("human_draft_preserved", fixture("read")["draft"] == "unsent human draft")
            fixture("draft", "")
            for name in ("tools", "automatic"):
                fixture(name, False)
                rejected(client, "disabled-" + name, "NEVER_SEND", client.context()["context"], "permission_denied")
                fixture(name, True)
            fixture("child")
            rejected(client, "child-parent-only", "NEVER_SEND", client.context()["context"], "parent_session_required")
            fixture("parent")
            fixture("new_parent")
            rejected(
                client, "unknown-owner", "NEVER_SEND", client.context()["context"], "known_work_order_owner_required"
            )
            fixture("first_parent")
            for unused in range(300):
                ready = fixture("read")
                if ready["send_enabled"] and not ready["busy"]:
                    break
                time.sleep(0.03)
            check("original_parent_restored", client.context()["context"]["owner"] == expected["owner"])
            fixture("peer_child")
            child = await_json(project / "peer-child.json", process)
            report["actual_engine_child_deny"] = child
            check("apple_python_from_engine_refused", not child["ok"] and child["error"] == "godot_ancestor")
            if args.untrusted_python:
                negative = subprocess.run(
                    [
                        str(args.untrusted_python),
                        str(peer_probe),
                        str(project),
                        str(process.pid),
                        str(project / "peer-unknown.json"),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                unknown = await_json(project / "peer-unknown.json", process)
                report["actual_unknown_client_deny"] = unknown
                check("unknown_intermediate_code_refused", negative.returncode == 0 and not unknown["ok"])
            descriptor = project / ".godot/editor/ai_control" / (str(process.pid) + ".json")
            original_discovery = descriptor.read_bytes()
            with tempfile.TemporaryDirectory(prefix="fake-instruction-") as fake_temp:
                fake_path = Path(fake_temp).resolve() / "fake.sock"
                fake = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                fake.bind(str(fake_path))
                fake_path.chmod(0o600)
                fake.listen(1)
                fake_bytes = []

                def accept_fake():
                    with fake.accept()[0] as connection:
                        fake_bytes.append(connection.recv(32768))

                thread = threading.Thread(target=accept_fake)
                thread.start()
                altered = json.loads(original_discovery)
                altered["instruction_socket"] = str(fake_path)
                descriptor.write_text(json.dumps(altered))
                try:
                    EditorInstructionClient(project, process.pid).context()
                    raise AssertionError("Replaced socket was accepted")
                except InstructionClientError as error:
                    check("client_kernel_engine_pid_check", str(error) == "instruction_server_identity_mismatch")
                finally:
                    descriptor.write_bytes(original_discovery)
                    thread.join(5)
                    fake.close()
                check("fake_server_received_no_instruction", fake_bytes == [b""])
            report["before_hold_context"] = client.context()["context"]
            hold = client.submit("EXTERNAL_CHAT_HOLD", report["before_hold_context"], "hold-once")
            report["hold_reply"] = hold
            check("ordinary_workflow_busy_submit", hold["ok"] and hold_started.wait(20))
            queue_context = client.context()["context"]
            fixture("queue")
            rejected(client, "queue-race", "NEVER_SEND", queue_context, "chat_instruction_state_changed")
            release_hold.set()
            wait_text("EXTERNAL_STEER_OK")
            before_restart = len(calls)
            fixture("exit")
            output.append(process.communicate(timeout=30)[0])
            client = start(True)
            restored = client.status("submit-once")
            check(
                "durable_receipt_restored",
                restored["ok"]
                and restored["receipt_restored"]
                and restored["instruction_submitted"]
                and restored["business_completed"] is False,
            )
            repeated = client.submit("EXTERNAL_CHAT_SUBMITTED", expected, "submit-once")
            check("restart_does_not_replay", repeated["ok"] and repeated["idempotent"] and len(calls) == before_restart)
            pending = project / ".godot/editor/ai_control_receipts.json.pending"
            pending.mkdir()
            rejected(
                client, "durable-save-failure", "NEVER_SEND", client.context()["context"], "receipt_store_unavailable"
            )
            check("journal_failure_has_no_send", len(calls) == before_restart and fixture("read")["draft"] == "")
            check(
                "one_original_candidate", len(list((original / ".git/gonggong-engine-candidates").glob("*.json"))) == 1
            )
            fixture("exit")
            output.append(process.communicate(timeout=30)[0])
            pending.rmdir()
            # Only this exited private fixture is altered. Matching expected
            # state cannot legitimize another conversation's candidate owner.
            history = json.loads((project / ".godot/editor/ai_chat_history.json").read_text())
            parent = next(agent for agent in history["agents"] if agent["id"] == 0)
            snapshot_path = project / ".godot/editor/ai_chat_snapshots" / (parent["snapshot_id"] + ".json")
            snapshot_envelope = json.loads(snapshot_path.read_text())
            snapshot = json.loads(snapshot_envelope["payload"])
            binding_path = Path(snapshot["engine_candidate"]["binding_path"])
            assert folder in binding_path.parents
            binding = json.loads(binding_path.read_text())
            foreign_owner = "c" * 32
            snapshot["engine_candidate"]["owner"] = foreign_owner
            binding["owner"] = foreign_owner
            snapshot_payload = json.dumps(snapshot, ensure_ascii=False, separators=(",", ":"))
            snapshot_path.write_text(
                json.dumps({
                    "payload": snapshot_payload,
                    "sha256": hashlib.sha256(snapshot_payload.encode()).hexdigest(),
                })
            )
            binding_path.write_text(json.dumps(binding))
            client = start(True)
            foreign_context = client.context()["context"]
            check(
                "foreign_owner_fixture_loaded",
                foreign_context["owner"] == foreign_owner and foreign_owner != foreign_context["conversation_id"],
            )
            rejected(
                client,
                "foreign-owner-with-matching-context",
                "NEVER_SEND",
                foreign_context,
                "known_work_order_owner_required",
            )
            check("foreign_owner_has_no_model_call", len(calls) == before_restart)
            report["ok"] = not report["errors"]
        except Exception as error:
            report["errors"].append(type(error).__name__ + ": " + str(error))
        finally:
            release_hold.set()
            if process and process.poll() is None:
                try:
                    fixture("exit")
                    output.append(process.communicate(timeout=15)[0])
                except Exception:
                    process.terminate()
                    output.append(process.communicate(timeout=10)[0])
            elif process and process.stdout and not process.stdout.closed:
                output.append(process.communicate(timeout=5)[0])
            server.shutdown()
            report["model_requests"] = calls
            report["stdout"] = "\n".join(output)
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(json.dumps(report, indent=2) + "\n")
            print(json.dumps({k: v for k, v in report.items() if k not in ("stdout", "model_requests")}, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
