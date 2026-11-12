import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from editor_test_isolation import copy_editor, macos_editor
from run_daqian_node_approval import prepare_candidate_fixture

ROOT = Path(__file__).resolve().parents[2]
BEFORE = "extends SceneTree\n\nfunc _initialize():\n\tquit(0)\n"
AFTER = (
    'extends SceneTree\n\nfunc _initialize():\n\tprint("AI_CHAT_RUN_OK")\n\tprinterr("AI_CHAT_STDERR_OK")\n\tquit(0)\n'
)
ERRORS: list[str] = []
SEEN: set[str] = set()
EXTERNAL = None
TRANSPORTS: dict[str, list[dict[str, object]]] = {}


def tool(name, arguments, identifier):
    return {
        "id": identifier,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments)},
    }


def completion(content="", calls=None):
    message = {"role": "assistant", "content": content}
    if calls:
        message["tool_calls"] = calls
    return {"choices": [{"message": message, "finish_reason": "tool_calls" if calls else "stop"}]}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_GET(self):
        if self.path == "/v1/no-list/models":
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'{"error":"private-model-error"}')
            return
        assert self.path in {"/v1/models", "/v1/slow-models/models"}
        assert self.headers.get("Authorization") == "Bearer test-secret"
        models = [
            {"id": "mock-model", "name": "Mock Model", "description": "Friendly description"},
            {"id": "mock-alternative", "name": "Alternative"},
        ]
        if self.path == "/v1/slow-models/models":
            time.sleep(1.5)
            models = [{"id": "stale-model", "name": "Old connection"}]
        payload = json.dumps({"data": models}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        try:
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_POST(self):
        try:
            body = self.rfile.read(int(self.headers["Content-Length"]))
            request = json.loads(body)
            assert self.headers.get("Authorization") == "Bearer test-secret"
            assert b"test-secret" not in body, "API key appeared in request content"
            assert request["model"] == "mock-model"
            messages = request["messages"]
            for message in messages:
                if isinstance(message.get("content"), list):
                    parts = message["content"]
                    message["content"] = "\n".join(part["text"] for part in parts if part["type"] == "text")
                    message["images"] = []
                    for part in parts:
                        if part["type"] == "image_url":
                            prefix, data = part["image_url"]["url"].split(";base64,", 1)
                            message["images"].append({"mime_type": prefix.removeprefix("data:"), "data": data})
            start = max(i for i, message in enumerate(messages) if message["role"] == "user")
            case = (
                messages[start]["content"].split("case:", 1)[1].strip().split("\n", 1)[0]
                if messages[start]["content"]
                else "image_only"
            )
            assert len(json.dumps(request, ensure_ascii=False).encode("utf-8")) <= 1024 * 1024, (
                "Full request exceeded the unchanged bridge budget"
            )
            active_calls = set()
            for message in messages:
                if message["role"] == "assistant":
                    active_calls = {call["id"] for call in message.get("tool_calls", [])}
                elif message["role"] == "tool":
                    assert message["tool_call_id"] in active_calls, "Compaction orphaned a tool result"
                    active_calls.remove(message["tool_call_id"])
            transport = request.get("cli_transport")
            if transport:
                TRANSPORTS.setdefault(case, []).append(transport)
                if (case == "workflow" or case.startswith("native_")) and len(TRANSPORTS[case]) > 1:
                    assert transport["pid"] == TRANSPORTS[case][0]["pid"], "Tool continuation restarted the CLI"
                    assert transport["new_users"] == 0, "Tool continuation resubmitted the original user task"
                    assert transport["new_messages"] <= 5, "Tool continuation resubmitted old context"
            SEEN.add(case)
            results = [message["content"] for message in messages[start + 1 :] if message["role"] == "tool"]
            assert messages[-1]["role"] == "system" and messages[-1]["content"].startswith(
                "Godot tool state (authoritative host metadata): "
            )
            state = json.loads(messages[-1]["content"].split("\n", 1)[0].split(": ", 1)[1])
            assert state["max_tool_rounds"] is None
            assert state["remaining_tool_rounds"] is None
            assert state["attach_editor_logs"] is False
            assert all(
                "AI_CHAT_LOG_SENTINEL" not in message["content"]
                and "AI_CHAT_ON_DEMAND_LOG_SENTINEL" not in message["content"]
                for message in messages
                if message["role"] == "user"
            ), "Editor Output was attached to an ordinary user message"
            assert state["unavailable_reason"] == ("none" if state["permission_enabled"] else "permission_disabled")
            assert bool(request.get("tools")) == (state["unavailable_reason"] == "none")
            if case.startswith("image_"):
                import base64
                import struct

                images = messages[start].get("images", [])
                all_images = [image for message in messages for image in message.get("images", [])]
                for image in all_images:
                    raw = base64.b64decode(image["data"], validate=True)
                    assert image["mime_type"] == "image/png" and raw.startswith(b"\x89PNG\r\n\x1a\n")
                    assert struct.unpack(">II", raw[16:24]) == (1600, 800), "Image scaling changed aspect ratio"
                if case == "image_send":
                    assert len(images) == 2 and images[0]["data"] != images[1]["data"], (
                        "Images missing, duplicated or reordered"
                    )
                    if transport:
                        assert transport["image_blocks"] == (2 if not results else 0), (
                            "Tool continuation retransmitted images"
                        )
                    if not results:
                        response = completion(calls=[tool("read_file", {"path": "res://fixture.gd"}, "image_read")])
                    else:
                        assert results == [BEFORE]
                        response = completion("IMAGE_SEND_OK")
                elif case == "image_only":
                    assert len(images) == 1 and not state["permission_enabled"] and not results
                    response = completion("IMAGE_ONLY_OK")
                elif case in {"image_follow", "image_recovery", "image_agent_a"}:
                    assert not images and len(all_images) == 3, (case, len(images), len(all_images), transport)
                    assert any(message.get("content") == "IMAGE_SEND_OK" for message in messages)
                    if case == "image_recovery":
                        assert transport and transport["image_blocks"] == 3, (
                            "Recovery did not supply actual historical image blocks"
                        )
                    elif transport:
                        assert transport["image_blocks"] == 0, "Incremental chat resent old images"
                    response = completion(case.upper() + "_OK")
                elif case in {"image_agent_b", "image_agent_b_resume"}:
                    assert not all_images and not any(message.get("content") == "IMAGE_SEND_OK" for message in messages)
                    if case == "image_agent_b_resume":
                        assert any(message.get("content") == "IMAGE_AGENT_B_OK" for message in messages)
                    response = completion(case.upper() + "_OK")
                else:
                    raise AssertionError("Unknown image case: " + case)
            elif case == "snapshot_earlier":
                if not results:
                    response = completion(
                        calls=[
                            tool(
                                "write_file",
                                {"path": "res://history_fixture.txt", "content": "earlier turn\n"},
                                "snapshot_earlier",
                            )
                        ]
                    )
                else:
                    assert results[-1].startswith("Applied approved script change"), results[-1]
                    response = completion("SNAPSHOT_EARLIER_OK")
            elif case == "snapshot_multi":
                writes = [
                    ("res://fixture.gd", BEFORE + "# intermediate\n"),
                    ("res://eol_fixture.txt", "\ufeffheader\r\n\tvalue = 2\r\nfooter\r\n"),
                    ("res://snapshot_created.txt", "created in one turn\n"),
                    ("res://fixture.gd", AFTER),
                    ("res://history_fixture.txt", "later turn\n"),
                ]
                if len(results) < len(writes):
                    if results:
                        assert results[-1].startswith("Applied approved script change"), results[-1]
                    target, content = writes[len(results)]
                    response = completion(
                        calls=[
                            tool("write_file", {"path": target, "content": content}, "snapshot_" + str(len(results)))
                        ]
                    )
                else:
                    assert (
                        Path(request.get("cli_workspace", {}).get("project_root", EXTERNAL.parent / "project"))
                        / "fixture.gd"
                    ).read_text(encoding="utf-8") == AFTER
                    response = completion("SNAPSHOT_MULTI_OK")
            elif case == "snapshot_seed":
                response = completion("SNAPSHOT_SEED_OK")
            elif case in {"snapshot_follow", "snapshot_verify"}:
                assert any(message.get("content") == "case:snapshot_multi" for message in messages), (
                    "Version restore erased historical dialog instead of recording a new turn"
                )
                notices = [
                    message
                    for message in messages
                    if "Host version restore committed as a new file-change turn" in message.get("content", "")
                ]
                assert len(notices) == 3, "Each version restore must synchronize its context exactly once"
                assert all(
                    "END of the selected version" in message["content"] and "history_fixture.txt" in message["content"]
                    for message in notices
                )
                assert (
                    sum(
                        message.get("role") == "user" and message.get("content", "").startswith("还原到此版本：")
                        for message in messages
                    )
                    == 3
                )
                if case == "snapshot_verify":
                    response = completion("SNAPSHOT_VERIFY_OK")
                elif not results:
                    response = completion(
                        calls=[tool("read_file", {"path": "res://history_fixture.txt"}, "version_read")]
                    )
                elif len(results) == 1:
                    assert "earlier turn" in results[0], results[0]
                    response = completion(
                        calls=[
                            tool(
                                "write_file",
                                {"path": "res://history_fixture.txt", "content": "continued after restore\n"},
                                "version_follow_write",
                            )
                        ]
                    )
                else:
                    assert results[-1].startswith("Applied approved script change"), results[-1]
                    response = completion("SNAPSHOT_FOLLOW_OK")
            elif case in {"auto_write", "auto_create", "auto_eol_edit"}:
                assert state["file_changes_require_approval"] is False
                if not results:
                    if case == "auto_eol_edit" and transport:
                        call = tool(
                            "edit_native",
                            {
                                "path": "res://eol_fixture.txt",
                                "old_string": "header\n\tvalue = 1",
                                "new_string": "header\n\tvalue = 2",
                            },
                            case,
                        )
                    else:
                        target, content = {
                            "auto_write": ("fixture.gd", AFTER),
                            "auto_create": ("auto_created.txt", "Automatically applied\n"),
                            "auto_eol_edit": ("eol_fixture.txt", "\ufeffheader\r\n\tvalue = 2\r\nfooter\r\n"),
                        }[case]
                        call = tool("write_file", {"path": "res://" + target, "content": content}, case)
                    response = completion(calls=[call])
                else:
                    assert results[-1].startswith("Applied approved script change"), results[-1]
                    response = completion(case.upper() + "_OK")
            elif case == "auto_execution":
                assert state["execution_requires_approval"] is False and state["file_changes_require_approval"] is True
                if not results:
                    command = (
                        "Write-Output 'AUTO_COMMAND_OK'; exit 7"
                        if os.name == "nt"
                        else "printf 'AUTO_COMMAND_OK\\n'; exit 7"
                    )
                    response = completion(
                        calls=[
                            tool("check_script", {"path": "res://fixture.gd"}, "auto_check"),
                            tool("run_test", {"path": "res://fixture.gd"}, "auto_test"),
                            tool("run_command", {"command": command}, "auto_command"),
                        ]
                    )
                else:
                    assert len(results) == 3
                    for index, value in enumerate(results):
                        result = json.loads(value)
                        assert result["exit_code"] == (7 if index == 2 else 0) and not result["timed_out"], result
                    assert "AUTO_COMMAND_OK" in json.loads(results[2])["stdout"]
                    response = completion("AUTO_EXECUTION_OK")
            elif case.startswith("native_"):
                assert transport and request.get("tools", []) == (
                    []
                    if state["unavailable_reason"] != "none"
                    else [
                        {"type": "function", "function": {"name": "read_file"}},
                        {"type": "function", "function": {"name": "write_file"}},
                    ]
                )
                if case in {"native_progress", "native_progress_error"}:
                    assert not results and len(TRANSPORTS[case]) == 1
                    response = completion("NATIVE_STREAM_VISIBLE_OK")
                elif case == "native_stream_next":
                    assert not results and len(TRANSPORTS[case]) == 1
                    assert messages[start - 1]["content"] == "NATIVE_STREAM_VISIBLE_OK"
                    assert TRANSPORTS["native_progress"][0]["session_id"] == transport["session_id"]
                    response = completion("NATIVE_STREAM_NEXT_OK")
                elif case in {"native_eol_edit", "native_eol_reject"}:
                    if not results:
                        response = completion(
                            calls=[
                                tool(
                                    "edit_native",
                                    {
                                        "path": "res://eol_fixture.txt",
                                        "old_string": "header\n\tvalue = 1",
                                        "new_string": "header\n\tvalue = 2",
                                    },
                                    "eol_edit",
                                )
                            ]
                        )
                    else:
                        assert state["tool_rounds"] == 2
                        assert results[-1] == (
                            "User rejected tool" if case == "native_eol_reject" else "Applied approved script change"
                        )
                        response = completion(case.upper() + "_OK")
                elif case == "native_search_edit":
                    workspace = request["cli_workspace"]
                    assert (
                        state["max_tool_rounds"] is None
                        and state["remaining_tool_rounds"] is None
                        and state["unavailable_reason"] == "none"
                    )
                    count = len(results)
                    if count == 0:
                        response = completion(
                            calls=[
                                tool(
                                    "Glob",
                                    {"path": workspace["engine_root"], "pattern": "**/ai_chat_dock.h"},
                                    "locate_engine",
                                )
                            ]
                        )
                    elif count == 1:
                        assert results[0].strip().replace("\\", "/").endswith("/editor/docks/ai_chat_dock.h")
                        response = completion(
                            calls=[
                                tool(
                                    "Grep",
                                    {"path": workspace["project_root"], "pattern": "value = 1", "glob": "*.txt"},
                                    "locate_project",
                                )
                            ]
                        )
                    elif count < 9:
                        assert "eol_fixture.txt:2:" in results[1].replace("\\", "/")
                        found = results[1].split(":2:", 1)[0]
                        response = completion(calls=[tool("read_file", {"path": found}, "search_read_" + str(count))])
                    elif count == 9:
                        assert state["tool_rounds"] == 7
                        found = results[1].split(":2:", 1)[0]
                        response = completion(
                            calls=[
                                tool(
                                    "edit_native",
                                    {
                                        "path": found,
                                        "old_string": "header\n\tvalue = 1",
                                        "new_string": "header\n\tvalue = 3",
                                    },
                                    "search_edit",
                                )
                            ]
                        )
                    else:
                        assert results[-1] == "Applied approved script change" and state["tool_rounds"] == 9
                        assert transport["new_users"] == 0
                        response = completion("NATIVE_SEARCH_EDIT_OK")
                elif case == "native_permission_off":
                    assert not state["permission_enabled"] and not results
                    response = completion("NATIVE_PERMISSION_OFF_OK")
                elif case in {"native_read", "native_range", "native_large"}:
                    if not results:
                        args = {"path": "res://large.txt"} if case == "native_large" else {"path": "res://fixture.gd"}
                        if case == "native_range":
                            args.update({"offset": 2, "limit": 1})
                        response = completion(calls=[tool("read_file", args, case)])
                    else:
                        expected = (
                            (EXTERNAL.parent / "project" / "large.txt").read_text(encoding="utf-8")
                            if case == "native_large"
                            else BEFORE.split("\n")[1]
                            if case == "native_range"
                            else BEFORE
                        )
                        assert results[-1] == expected, "Native ACP received a truncated or fabricated file body"
                        response = completion(case.upper() + "_OK")
                elif case == "native_baseline":
                    if not results:
                        response = completion(
                            calls=[
                                tool("write_file", {"path": "res://fixture.gd", "content": BEFORE}, "native_baseline")
                            ]
                        )
                    else:
                        assert results[-1].startswith("Applied approved script change"), results[-1]
                        response = completion("NATIVE_BASELINE_OK")
                elif case in {"native_write", "native_reject"}:
                    if not results:
                        response = completion(calls=[tool("read_file", {"path": "res://fixture.gd"}, "native_before")])
                    elif len(results) == 1:
                        assert results[0] == BEFORE
                        response = completion(
                            calls=[tool("write_file", {"path": "res://fixture.gd", "content": AFTER}, "native_edit")]
                        )
                    else:
                        assert len(results) == 2
                        assert results[-1] == (
                            "User rejected tool" if case == "native_reject" else "Applied approved script change"
                        ), repr(results[-1])
                        response = completion(case.upper() + "_OK")
                elif case == "native_create":
                    if not results:
                        response = completion(
                            calls=[
                                tool(
                                    "write_file",
                                    {"path": "res://native_created.txt", "content": "Created through Godot approval\n"},
                                    "native_new",
                                )
                            ]
                        )
                    else:
                        assert results[-1] == "Applied approved script change"
                        response = completion("NATIVE_CREATE_OK")
                else:
                    raise AssertionError("Unknown native case: " + case)
            elif case == "permission_off":
                assert (
                    not state["permission_enabled"]
                    and state["unavailable_reason"] == "permission_disabled"
                    and not results
                )
                response = completion("PERMISSION_OFF_OK")
            elif case in {"budget", "budget_violation", "budget_resume"}:
                count = len(results)
                assert state["permission_enabled"] and state["tool_rounds"] == count
                if count:
                    expected = "Error: File does not exist." if case != "budget_resume" and count == 2 else BEFORE
                    assert results[-1] == expected, results[-1]
                if case == "budget_resume" and count == 1:
                    response = completion("BUDGET_RESUME_OK")
                elif count < 8:
                    assert state["unavailable_reason"] == "none" and request.get("tools")
                    path = "res://missing-read.gd" if case != "budget_resume" and count == 1 else "res://fixture.gd"
                    response = completion(calls=[tool("read_file", {"path": path}, "unlimited_" + str(count))])
                else:
                    assert count == 8 and state["unavailable_reason"] == "none" and request.get("tools")
                    response = completion(
                        "UNLIMITED_VIOLATION_OK"
                        if case == "budget_violation"
                        else "BUDGET_OK：本条消息八轮工具调用已完成，无轮数上限。"
                    )
            elif case in {"scheduler_run", "scheduler_manual", "scheduler_fail"}:
                if case == "scheduler_fail":
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"error":"Synthetic scheduler failure"}')
                    return
                if case == "scheduler_run":
                    assert not any(message.get("role") == "user" for message in messages[:start]), (
                        "Scheduled Agent reused an earlier conversation"
                    )
                    assert not any("MANUAL_UNSENT_DRAFT" in message.get("content", "") for message in messages), (
                        "Scheduler consumed a manual draft"
                    )
                time.sleep(0.5 if case == "scheduler_run" else 1.5)
                response = completion(case.upper() + "_OK")
            elif case == "cleanup_round":
                if not results:
                    response = completion(
                        "TEMPORARY_ANALYSIS", [tool("read_file", {"path": "res://fixture.gd"}, "cleanup_read")]
                    )
                else:
                    assert results == [BEFORE]
                    time.sleep(0.5)  # Inspect working UI before the final result.
                    response = completion("CLEANUP_FINAL")
            elif case == "cleanup_follow":
                assert any(message.get("content") == "CLEANUP_FINAL" for message in messages[:start])
                if not transport:
                    assert not any(
                        message.get("role") == "tool" or message.get("tool_calls") for message in messages[:start]
                    )
                else:
                    assert transport["new_users"] == 1 and transport["new_messages"] <= 2
                response = completion("CLEANUP_FOLLOW_OK")
            elif case == "workflow":
                count = len(results)
                if count == 0:
                    response = completion(
                        calls=[
                            tool("read_logs", {}, "logs"),
                            tool("list_scripts", {}, "list"),
                            tool("read_script", {"path": "res://fixture.gd"}, "read"),
                        ]
                    )
                elif count == 3:
                    log_result = json.loads(results[0])
                    assert log_result["ok"] and log_result["untrusted"] and log_result["source"] == "editor_output"
                    assert "AI_CHAT_LOG_SENTINEL" in log_result["logs"], "On-demand editor log was not captured"
                    assert len(log_result["logs"]) <= 32000
                    assert "res://fixture.gd" in json.loads(results[1])["paths"]
                    assert results[2] == BEFORE
                    response = completion(
                        calls=[tool("write_script", {"path": "res://fixture.gd", "content": AFTER}, "write")]
                    )
                elif count == 4:
                    assert results[-1].startswith("Applied approved script change")
                    response = completion(calls=[tool("check_script", {"path": "res://fixture.gd"}, "check")])
                elif count == 5:
                    checked = json.loads(results[-1])
                    assert checked["exit_code"] == 0 and not checked["timed_out"], checked
                    response = completion(calls=[tool("run_test", {"path": "res://fixture.gd"}, "test")])
                elif count == 6:
                    tested = json.loads(results[-1])
                    assert tested["exit_code"] == 0 and not tested["timed_out"], tested
                    assert "AI_CHAT_RUN_OK" in tested["stdout"], tested
                    assert "AI_CHAT_STDERR_OK" in tested["stderr"], tested
                    response = completion("WORKFLOW_OK")
                else:
                    raise AssertionError(f"Unexpected workflow result count: {count}")
            elif case == "large_context":
                count = len(results)
                if not count:
                    response = completion(
                        calls=[
                            tool("read_file", {"path": path}, "large_" + str(i))
                            for i, path in enumerate(["res://large.txt", "res://large.txt", "res://large_other.txt"])
                        ]
                    )
                else:
                    assert count == 3
                    assert "duplicate tool snapshot" in results[0]
                    assert "Context compacted:" in results[1] and "Context compacted:" in results[2]
                    assert "incomplete excerpt" in results[1]
                    assert "LARGE_BEGIN" in results[1] and "LARGE_END" in results[1]
                    response = completion("LARGE_CONTEXT_OK")
            elif case == "range_context":
                if not results:
                    response = completion(
                        calls=[tool("read_file", {"path": "res://large.txt", "offset": 1500, "limit": 2}, "ranged")]
                    )
                else:
                    excerpt = json.loads(results[-1])
                    lines = (EXTERNAL.parent / "project" / "large.txt").read_text(encoding="utf-8").split("\n")
                    assert excerpt["offset"] == 1500 and excerpt["returned_lines"] == 2 and excerpt["truncated"]
                    assert excerpt["content"] == "\n".join(lines[1499:1501])
                    response = completion("RANGE_CONTEXT_OK")
            elif case == "long_structured_context":
                if not results:
                    response = completion(
                        calls=[
                            tool("read_file", {"path": "res://long_range.txt", "offset": 2, "limit": 90}, "long_range"),
                            tool("read_file", {"path": "res://large_command.json"}, "command_json"),
                            tool("read_file", {"path": "res://large_array.json"}, "array_json"),
                        ]
                    )
                else:
                    assert len(results) == 3
                    ranged, command, array = [json.loads(result) for result in results]
                    assert (
                        ranged["offset"] == 2
                        and ranged["returned_lines"] == 90
                        and ranged["total_lines"] == 101
                        and ranged["truncated"]
                    )
                    assert ranged["context_excerpted"] and "not the shortened text" in ranged["context_note"]
                    assert ranged["content"].startswith("ROW_001 ") and "ROW_090 " in ranged["content"]
                    assert "Context compacted:" in ranged["content"] and '"\\\t数据' in ranged["content"]
                    assert command["exit_code"] == 7 and command["timed_out"] is True and command["truncated"] is False
                    assert (
                        command["context_excerpted"]
                        and "Context compacted:" in command["stdout"]
                        and "Context compacted:" in command["stderr"]
                    )
                    assert array["context_excerpted"] and "not a complete JSON document" in array["context_note"]
                    assert "entry_0" in array["excerpt"] and "entry_7999" in array["excerpt"]
                    response = completion("LONG_STRUCTURED_CONTEXT_OK")
            elif case == "range_invalid":
                if not results:
                    response = completion(
                        calls=[tool("read_file", {"path": "res://large.txt", "offset": 1.5, "limit": 2}, "bad_range")]
                    )
                else:
                    assert results[-1].startswith("Error: Read offset")
                    response = completion("RANGE_INVALID_OK")
            elif case == "large_next":
                assert any(message.get("content") == "LARGE_CONTEXT_OK" for message in messages[:start])
                assert any(message.get("content") == "RANGE_CONTEXT_OK" for message in messages[:start])
                response = completion("LARGE_NEXT_OK")
            elif case.startswith("history_a_"):
                assert not any(message.get("content") == "HISTORY_B_SEED_OK" for message in messages), (
                    "Agent A inherited Agent B"
                )
                if case == "history_a_seed":
                    assert "[REDACTED]" in messages[start]["content"] and len(messages[start].get("images", [])) == 1
                    if not results:
                        response = completion(calls=[tool("read_file", {"path": "res://fixture.gd"}, "history_read")])
                    else:
                        assert results == [BEFORE]
                        response = completion("HISTORY_A_SEED_OK")
                else:
                    assert case == "history_a_resume"
                    assert any(message.get("content") == "HISTORY_A_SEED_OK" for message in messages[:start]), (
                        "Restart lost Agent A context"
                    )
                    assert not any(
                        call["id"] == "interrupted_history_tool"
                        for message in messages
                        for call in message.get("tool_calls", [])
                    ), "Interrupted tools were restored for execution"
                    assert any(message.get("images") for message in messages[:start]), (
                        "Restart lost historical image input"
                    )
                    response = completion("HISTORY_A_RESUME_OK")
            elif case.startswith("history_b_"):
                assert not any(message.get("content") == "HISTORY_A_SEED_OK" for message in messages), (
                    "Agent B inherited Agent A"
                )
                assert not any(message.get("images") for message in messages), "Agent B inherited Agent A images"
                if case == "history_b_resume":
                    assert any(message.get("content") == "HISTORY_B_SEED_OK" for message in messages[:start]), (
                        "Restart lost Agent B context"
                    )
                response = completion("HISTORY_B_SEED_OK" if case == "history_b_seed" else "HISTORY_B_RESUME_OK")
            elif case == "history_fill":
                response = completion("HISTORY_FILL_OK")
            elif case == "agent_a_seed":
                response = completion("AGENT_A_SECRET")
            elif case == "agent_b_seed":
                assert all("AGENT_A_SECRET" not in message.get("content", "") for message in messages), (
                    "Agent B received agent A context"
                )
                assert not any("case:workflow" in message.get("content", "") for message in messages), (
                    "New agent inherited the previous agent history"
                )
                response = completion("AGENT_B_SECRET")
            elif case == "agent_a_resume":
                assert any(message.get("content") == "AGENT_A_SECRET" for message in messages), (
                    "Switching back lost agent A memory"
                )
                assert all("AGENT_B_SECRET" not in message.get("content", "") for message in messages), (
                    "Agent A received agent B context"
                )
                if transport:
                    assert transport["session_id"] == TRANSPORTS["agent_a_seed"][0]["session_id"], (
                        "Agent A session changed after switching agents"
                    )
                response = completion("AGENT_A_RESUME_OK")
            elif case == "agent_b_resume":
                assert any(message.get("content") == "AGENT_B_SECRET" for message in messages), (
                    "Switching back lost agent B memory"
                )
                assert all("AGENT_A_SECRET" not in message.get("content", "") for message in messages), (
                    "Agent B received agent A context"
                )
                if transport:
                    assert transport["session_id"] == TRANSPORTS["agent_b_seed"][0]["session_id"], (
                        "Agent B session changed after switching agents"
                    )
                response = completion("AGENT_B_RESUME_OK")
            elif case == "incremental_next":
                assert any(message.get("content") == "WORKFLOW_OK" for message in messages[:start])
                if transport:
                    assert transport["pid"] == TRANSPORTS["workflow"][-1]["pid"], "Next user message restarted the CLI"
                    assert transport["new_users"] == 1 and transport["new_messages"] <= 3, (
                        "Next message retransmitted the conversation"
                    )
                response = completion("INCREMENTAL_NEXT_OK")
            elif case in {"model_switch", "model_restore"}:
                assert transport and transport["pid"] == TRANSPORTS["workflow"][0]["pid"], (
                    "Model change restarted the native session"
                )
                assert transport["session_id"] == TRANSPORTS["workflow"][0]["session_id"], (
                    "Model change replaced the native session ID"
                )
                assert any(message.get("content") == "WORKFLOW_OK" for message in messages[:start]), (
                    "Model switch lost retained conversation context"
                )
                response = completion(case.upper() + "_OK")
            elif case == "context_kept":
                assert any(
                    message["role"] == "user" and "case:workflow" in message["content"] for message in messages[:start]
                ), "Model refresh cancellation removed the previous user context"
                assert any(
                    message["role"] == "assistant" and message.get("content") == "WORKFLOW_OK"
                    for message in messages[:start]
                ), "Model refresh cancellation removed the previous AI context"
                response = completion("CONTEXT_KEPT_OK")
            elif case == "after_refresh":
                assert any(message.get("content") == "AFTER_CANCEL_OK" for message in messages[:start]), (
                    "Model refresh cancellation lost conversation context"
                )
                response = completion("AFTER_REFRESH_OK")
            elif case == "scroll":
                time.sleep(1)
                response = completion("SCROLL_OK\n" + "Additional response content\n" * 100)
            elif case in {"unsaved", "reject", "traversal"}:
                if not results:
                    path = "res://fixture.gd:stream" if case == "traversal" else "res://fixture.gd"
                    response = completion(calls=[tool("write_script", {"path": path, "content": AFTER}, case)])
                else:
                    expected = {"unsaved": "unsaved", "reject": "rejected", "traversal": "Invalid local file path"}[
                        case
                    ]
                    assert expected in results[-1], results[-1]
                    response = completion(case.upper() + "_OK")
            elif case.startswith("win_command_"):
                kind = case.removeprefix("win_command_")
                assert EXTERNAL is not None
                # An apostrophe and Unicode exercise literal cwd and exact source transport.
                cwd = EXTERNAL / "工作 ' quoted"
                cwd.mkdir(exist_ok=True)

                def owned():
                    return list((EXTERNAL.parent / "project/temp").glob("godot-command-*.ps1"))

                if not results:
                    assert not owned(), "Previous owned command file leaked"
                    body = {
                        "short": "Write-Output 'short-ok'",
                        "long": "[Console]::Out.WriteLine('中文 😀 ''single'' ` double \"'); [Console]::Error.WriteLine('错误 stderr'); Write-Output (Get-Location).ProviderPath; Write-Output ([Environment]::CurrentDirectory); cmd.exe /d /c exit 7",
                        "near": "Write-Output 'near-ok'",
                        "source": "Remove-Item -LiteralPath 'design-docs/windows-command-fixture.md'",
                        "failstart": "Write-Output 'must-not-start'",
                        "throw": "throw 'long-throw'",
                        "timeout": "Start-Sleep -Seconds 30",
                        "cancel": "[IO.File]::WriteAllText('"
                        + str(cwd / "started").replace("'", "''")
                        + "', [string]$PID); Start-Sleep -Seconds 30; [IO.File]::WriteAllText('"
                        + str(cwd / "unexpected").replace("'", "''")
                        + "', 'bad')",
                        "limit": "Write-Output 'must-not-run'",
                    }[kind]
                    body = "if ($null -ne $f -or $null -ne $r -or $null -ne $s) { throw 'loader-scope-leak' }; " + body
                    if kind == "long":
                        body = (
                            "$owned = @(Get-ChildItem -LiteralPath $env:TEMP -Filter 'godot-command-*.ps1'); if ($owned.Count -ne 1) { throw 'missing-owned-file' }; $blocked = 0; try { [IO.File]::WriteAllText($owned[0].FullName, 'tampered') } catch { $blocked++ }; try { [IO.File]::Delete($owned[0].FullName) } catch { $blocked++ }; if ($blocked -ne 2) { throw 'owner-lock-failed' }; "
                            + body
                        )
                    if kind == "near":
                        body += "\n#" + "a" * 3300
                    elif kind != "short":
                        body += "\n#" + "界😀'\"" * 2700
                    if kind == "limit":
                        body += "x" * 3000
                    arguments = {"command": body, "timeout_seconds": 1 if kind == "timeout" else 30}
                    if kind != "source":
                        arguments["cwd"] = str(cwd)
                    response = completion(
                        calls=[
                            tool(
                                "run_command",
                                arguments,
                                kind,
                            )
                        ]
                    )
                else:
                    assert not owned(), "Owned command file leaked after completion"
                    if kind == "failstart":
                        if results[-1].startswith("Error:"):
                            assert "start" in results[-1], results[-1]
                        else:
                            failed = json.loads(results[-1])
                            assert failed["exit_code"] != 0 and "must-not-start" not in failed["stdout"], failed
                            assert failed["provenance_guard"]["command_exit_code"] == 127, failed
                            assert not failed["provenance_guard"]["commands_replayed"], failed
                    elif kind == "limit":
                        assert "12,000" in results[-1] and "separately approved" in results[-1], results[-1]
                    else:
                        result_value = json.loads(results[-1])
                        if kind == "short":
                            assert result_value["exit_code"] == 0 and "short-ok" in result_value["stdout"], result_value
                        elif kind == "near":
                            assert result_value["exit_code"] == 0 and "near-ok" in result_value["stdout"], result_value
                        elif kind == "source":
                            assert result_value["exit_code"] != 0, result_value
                            assert result_value["provenance_guard"]["restored_count"] == 1, result_value
                            assert result_value["provenance_guard"]["error"] == "provenance_violation", result_value
                        elif kind == "long":
                            assert result_value["exit_code"] == 7, result_value
                            assert "中文 😀 'single' ` double \"" in result_value["stdout"], result_value
                            assert result_value["stdout"].lower().count(str(cwd).lower()) == 2, result_value
                            assert "错误 stderr" in result_value["stderr"], result_value
                        elif kind == "throw":
                            assert result_value["exit_code"] == 1 and "long-throw" in result_value["stderr"], (
                                result_value
                            )
                        elif kind == "timeout":
                            assert result_value["timed_out"] and result_value["exit_code"] != 0, result_value
                        else:
                            raise AssertionError("Cancelled command must not continue the model loop")
                    print("WINDOWS_COMMAND_RESULT", kind, results[-1], flush=True)
                    response = completion(kind.upper() + "_COMMAND_OK")
            elif case == "expanded":
                original = "int sample() { return 0; }\n"
                changed = "int sample() { return 1; }\n"
                count = len(results)
                if count == 0:
                    response = completion(
                        calls=[
                            tool("list_directory", {"path": str(EXTERNAL)}, "directory"),
                            tool("read_file", {"path": str(EXTERNAL / "sample.cpp")}, "source"),
                        ]
                    )
                elif count == 2:
                    assert any(item["path"].endswith("sample.cpp") for item in json.loads(results[0])["entries"])
                    assert results[1] == original
                    response = completion(
                        calls=[
                            tool(
                                "write_file", {"path": str(EXTERNAL / "sample.cpp"), "content": changed}, "source_write"
                            )
                        ]
                    )
                elif count == 3:
                    assert results[-1].startswith("Applied approved script change")
                    assert (EXTERNAL / "sample.cpp").read_text(encoding="utf-8") == changed
                    response = completion(
                        calls=[
                            tool(
                                "run_command",
                                {
                                    "command": 'Write-Output "AI_COMMAND_OK"; Write-Output (Get-Location).ProviderPath',
                                    "cwd": str(EXTERNAL),
                                    "timeout_seconds": 30,
                                },
                                "command",
                            )
                        ]
                    )
                elif count == 4:
                    executed = json.loads(results[-1])
                    assert executed["exit_code"] == 0 and not executed["timed_out"], executed
                    assert "AI_COMMAND_OK" in executed["stdout"], executed
                    assert str(EXTERNAL).lower() in executed["stdout"].lower(), executed
                    response = completion(
                        calls=[
                            tool(
                                "run_command",
                                {"command": "cmd.exe /d /c exit 7", "cwd": str(EXTERNAL), "timeout_seconds": 30},
                                "nonzero",
                            )
                        ]
                    )
                elif count == 5:
                    assert json.loads(results[-1])["exit_code"] == 7, results[-1]
                    response = completion("EXPANDED_OK")
                else:
                    raise AssertionError(f"Unexpected expanded result count: {count}")
            elif case.startswith("queue_"):
                if case == "queue_first":
                    assert not any(
                        message["content"].startswith((
                            "case:queue_second",
                            "case:queue_third",
                            "case:queue_deleted",
                            "UNSENT_",
                        ))
                        for message in messages
                    ), "Queued turns leaked into the running request"
                    time.sleep(0.25)
                    response = (
                        completion("QUEUE_FIRST_OK")
                        if results
                        else completion(calls=[tool("read_file", {"path": "res://fixture.gd"}, "queue_read")])
                    )
                    if results:
                        assert results == [BEFORE]
                elif case in {"queue_second", "queue_third"}:
                    assert any(message["content"] == "QUEUE_FIRST_OK" for message in messages), (
                        "Next turn started without previous final answer"
                    )
                    if case == "queue_second":
                        assert len(messages[start].get("images", [])) == 1
                        time.sleep(0.25)
                    else:
                        assert any(message["content"] == "QUEUE_SECOND_OK" for message in messages)
                        assert not messages[start].get("images"), "Unsent draft image leaked into queued turn"
                    if transport:
                        assert transport["pid"] == TRANSPORTS["queue_first"][0]["pid"], (
                            "Queue restarted the CLI conversation"
                        )
                        assert transport["new_users"] == 1
                    response = completion(case.upper() + "_OK")
                elif case == "queue_fail":
                    time.sleep(0.25)
                    self.send_response(503)
                    self.end_headers()
                    self.wfile.write(b'{"error":"Synthetic queue failure"}')
                    return
                elif case == "queue_slow":
                    time.sleep(1.5)
                    response = completion("QUEUE_STALE_RESPONSE")
                elif case in {"queue_after_failure", "queue_restart_a", "queue_restart_b"}:
                    if case == "queue_restart_a":
                        assert len(messages[start].get("images", [])) == 1
                        assert not any(message["content"] == "case:queue_restart_b" for message in messages), (
                            "Agent queues mixed"
                        )
                    if case == "queue_restart_b":
                        assert not any(
                            message["content"] in {"case:queue_restart_a", "QUEUE_FIRST_OK"} for message in messages
                        ), "Agent queues mixed"
                    response = completion(case.upper() + "_OK")
                else:
                    raise AssertionError("Deleted/unknown queued message was executed: " + case)
            elif case == "slow":
                time.sleep(1.5)
                response = completion("STALE_RESPONSE")
            elif case == "after_cancel":
                response = completion("AFTER_CANCEL_OK")
            elif case == "malformed":
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"not JSON")
                return
            else:
                raise AssertionError(f"Unexpected case: {case}")
            payload = json.dumps(response).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        except Exception:
            import traceback

            ERRORS.append(traceback.format_exc())
            self.send_response(500)
            self.end_headers()


def inject_windows_mouse(pid):
    import ctypes
    from ctypes import wintypes

    user = ctypes.WinDLL("user32", use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user.IsWindowVisible.argtypes = [wintypes.HWND]
    user.SetForegroundWindow.argtypes = [wintypes.HWND]
    user.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    windows = []

    def collect(hwnd, _data):
        window_pid = wintypes.DWORD()
        user.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
        if window_pid.value == pid and user.IsWindowVisible(hwnd):
            windows.append(hwnd)
        return True

    user.EnumWindows(callback_type(collect), 0)
    if not windows:
        raise RuntimeError("Mouse injection target window is missing")
    hwnd = windows[0]
    if not user.SetForegroundWindow(hwnd):
        raise RuntimeError("Cannot focus the isolated mouse input test window")
    rect = wintypes.RECT()
    user.GetWindowRect(hwnd, ctypes.byref(rect))
    user.SetCursorPos((rect.left + rect.right) // 2, (rect.top + rect.bottom) // 2)

    class MouseInput(ctypes.Structure):
        _fields_ = [
            ("dx", wintypes.LONG),
            ("dy", wintypes.LONG),
            ("data", wintypes.DWORD),
            ("flags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("extra", ctypes.c_size_t),
        ]

    class InputUnion(ctypes.Union):
        _fields_ = [("mouse", MouseInput)]

    class Input(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("value", InputUnion)]

    count = 256
    events = (Input * count)()
    for index, event in enumerate(events):
        event.value.mouse.dx = 1 if index % 2 == 0 else -1
        event.value.mouse.flags = 0x0001 | 0x2000  # MOVE | MOVE_NOCOALESCE
    user.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(Input), ctypes.c_int]
    sent = user.SendInput(count, events, ctypes.sizeof(Input))
    if sent != count:
        raise RuntimeError(f"SendInput failed: {sent}/{count}, error {ctypes.get_last_error()}")
    print("WINDOWS_MOUSE_INPUT_SENT", sent)
    return 0


def main():
    global EXTERNAL
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--godot", type=Path, default=ROOT / "bin/godot.windows.editor.dev.x86_64.dotnet.mono.console.exe"
    )
    parser.add_argument("--backend", choices=["http", "cli"], default="http")
    parser.add_argument(
        "--snapshots",
        action="store_true",
        help="Verify per-turn local file restore, conflicts, approval and restart persistence without Git",
    )
    parser.add_argument("--visible", action="store_true")
    parser.add_argument("--images", action="store_true")
    parser.add_argument("--windows-commands", action="store_true")
    parser.add_argument("--windows-command-cancel-only", action="store_true")
    parser.add_argument(
        "--queue",
        action="store_true",
        help="Verify FIFO messages, busy composer, failure/stop pause and per-Agent restart persistence",
    )
    parser.add_argument(
        "--schedules",
        action="store_true",
        help="Verify periodic tasks, separate Agents, busy FIFO, real minute tick and restart persistence",
    )
    parser.add_argument(
        "--agents",
        action="store_true",
        help="Verify Agent close buttons, cancellation, cleanup and restart persistence",
    )
    parser.add_argument(
        "--history", action="store_true", help="Verify project history across separate editor processes"
    )
    parser.add_argument(
        "--history-performance",
        action="store_true",
        help="Verify typing and asynchronous persistence with 60 MB of synthetic history",
    )
    parser.add_argument(
        "--cleanup", action="store_true", help="Verify completed-turn cleanup, legacy migration and unfinished evidence"
    )
    parser.add_argument(
        "--rename-stress", action="store_true", help="Repeat native Windows Agent popups and check USER handle growth"
    )
    parser.add_argument("--d3d12", action="store_true", help="Use Forward+ with the Windows D3D12 driver")
    parser.add_argument(
        "--raw-input-stress", action="store_true", help="Inject Windows mouse input during popup stress"
    )
    parser.add_argument("--inject-mouse", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.windows_command_cancel_only:
        args.windows_commands = True
    if args.inject_mouse is not None:
        return inject_windows_mouse(args.inject_mouse)
    if args.raw_input_stress:
        args.rename_stress = True
    if args.rename_stress and (os.name != "nt" or not args.visible):
        parser.error("--rename-stress requires Windows and --visible")
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        with tempfile.TemporaryDirectory(prefix="ai_chat_validation_") as directory:
            isolated_editor = macos_editor(args.godot, Path(directory) / "isolated-editor")
            project = Path(directory) / "project"
            project.mkdir()
            external = Path(directory) / "engine source 角色"
            external.mkdir()
            EXTERNAL = external
            (external / "sample.cpp").write_text("int sample() { return 0; }\n", encoding="utf-8", newline="")
            rendering = (
                'renderer/rendering_method="forward_plus"\nrendering_device/driver.windows="d3d12"\n'
                if args.d3d12
                else 'renderer/rendering_method="gl_compatibility"\n'
            )
            (project / "project.godot").write_text(
                'config_version=5\n[application]\nconfig/name="AI Chat Integration"\n[rendering]\n' + rendering,
                encoding="utf-8",
            )
            (project / "fixture.gd").write_text(BEFORE, encoding="utf-8", newline="")
            (project / "history_fixture.txt").write_text("original history\n", encoding="utf-8", newline="")
            (project / "eol_fixture.txt").write_bytes(b"\xef\xbb\xbfheader\r\n\tvalue = 1\r\nfooter\r\n")
            large = "LARGE_BEGIN\n" + "".join(f"{i:04d} " + "x" * 52 + "\n" for i in range(4000)) + "LARGE_END"
            other = "OTHER_BEGIN\n" + "".join(f"{i:04d} " + "数据" * 8 + "\n" for i in range(4000)) + "OTHER_END"
            (project / "large.txt").write_text(large, encoding="utf-8", newline="")
            (project / "large_other.txt").write_text(other, encoding="utf-8", newline="")
            long_range = "".join(f"ROW_{i:03d} " + '"\\\t数据' * 100 + "\n" for i in range(100))
            (project / "long_range.txt").write_text(long_range, encoding="utf-8", newline="")
            command_json = {
                "exit_code": 7,
                "timed_out": True,
                "truncated": False,
                "stdout": 'stdout\n"\\数据' * 8000,
                "stderr": 'stderr\n"\\数据' * 4000,
            }
            (project / "large_command.json").write_text(json.dumps(command_json, ensure_ascii=False), encoding="utf-8")
            (project / "large_array.json").write_text(
                json.dumps(["entry_" + str(i) for i in range(8000)]), encoding="utf-8"
            )
            script = (
                "ai_chat_integration.gd"
                if args.schedules
                or args.queue
                or args.history
                or args.agents
                or args.history_performance
                or args.cleanup
                else "ai_chat_images.gd"
                if args.images
                else "ai_chat_native_files.gd"
                if args.backend == "cli"
                else "ai_chat_integration.gd"
            )
            if args.rename_stress or args.snapshots:
                script = "ai_chat_native_files.gd"
            shutil.copyfile(Path(__file__).with_name(script), project / "integration.gd")
            if args.windows_commands:
                isolated_editor = copy_editor(args.godot.resolve(), project / "private-editor")
                workspace = project / ".fixture"
                (workspace / "tools").mkdir(parents=True)
                request_id = "windows-command-fixture"
                prepare_candidate_fixture(project, workspace, {"number": 891, "request": request_id}, [])
                bridge = workspace / "tools/gonggong_bridge.py"
                bridge.write_text(
                    "import json,sys,runpy\nfrom pathlib import Path\n"
                    "args=sys.argv; action=args[1]; root=Path(args[args.index('--workspace')+1]); out=Path(args[args.index('--out')+1])\n"
                    + f"store=runpy.run_path({str(ROOT / 'customizations/platforms/data-collection/git-files/storage/diting_files.py')!r})\n"
                    + "if action=='flush':\n for p in (root/'.gonggong-outbox/chat').glob('*.json'): store['record'](root,p); p.unlink()\n"
                    + "result={'ok':True,'ready':True,'issue_number':891,'request_id':'windows-command-fixture','url':'https://github.com/fixture/board/issues/891','context':'Offline transport fixture','reporting':{'tenant_id':'fixture','request_ref':'windows-command-fixture','source_ref':'https://github.com/fixture/board/issues/891','agent':{'id':'fixture','version':'1','definition_sha256':'0'*64,'origin':'offline-fixture'}}}\n"
                    + "out.write_text(json.dumps(result),encoding='utf-8')\n",
                    encoding="utf-8",
                )
                shutil.copyfile(bridge, project / "tools/gonggong_bridge.py")
                installed = project / "customizations/components/godot-host/bridge.py"
                installed.parent.mkdir(parents=True)
                shutil.copyfile(bridge, installed)
                configuration = isolated_editor.parent / "editor_data/gonggong/config.json"
                configuration.parent.mkdir(parents=True)
                configuration.write_text(
                    json.dumps({
                        "schema_version": 1,
                        "runtimes": {"workflow_python": sys.executable, "node": shutil.which("node")},
                    }),
                    encoding="utf-8",
                )
            env = os.environ.copy()
            if args.windows_commands:
                env["GONGGONG_RUNTIME_CONFIG"] = str(configuration)
                env["GONGGONG_WORKSPACE"] = str(workspace)
                env["GONGGONG_GIT"] = shutil.which("git") or ""
                env["GONGGONG_GH"] = shutil.which("gh") or ""
            env["AI_CHAT_TEST_PYTHON"] = sys.executable
            env["AI_CHAT_WINDOWS_CANCEL_ONLY"] = "1" if args.windows_command_cancel_only else ""
            env["AI_CHAT_WINDOWS_COMMANDS"] = "1" if args.windows_commands else ""
            env["APPDATA"] = str(project / "appdata")
            env["LOCALAPPDATA"] = str(project / "localappdata")
            if args.windows_commands:
                (project / "appdata").mkdir(exist_ok=True)
                (project / "localappdata").mkdir(exist_ok=True)
            dotnet = ROOT / ".dotnet"
            env["DOTNET_ROOT"] = str(dotnet)
            env["DOTNET_ROOT_X64"] = str(dotnet)
            env["PATH"] = str(dotnet) + os.pathsep + env.get("PATH", "")
            env["DOTNET_CLI_TELEMETRY_OPTOUT"] = "1"
            env["DOTNET_CLI_HOME"] = str(project / "dotnet_home")
            temporary = project / "temp"
            temporary.mkdir()
            env["TEMP"] = str(temporary)
            env["TMP"] = str(temporary)
            env["GODOT_AI_API_KEY"] = ""
            env["AI_CHAT_TEST_URL"] = f"http://127.0.0.1:{server.server_port}/v1/chat/completions"
            env["AI_CHAT_TEST_BACKEND"] = args.backend
            env["AI_CHAT_TEST_EXTERNAL"] = str(EXTERNAL)
            env["AI_CHAT_TEST_PROJECT"] = str(project)
            env["GODOT_ACP_LOG_DIRECTORY"] = str(project / "acp_logs")
            env["AI_CHAT_EXPECTED_AFTER"] = AFTER
            if args.snapshots:
                env["AI_CHAT_SNAPSHOT_STAGE"] = "seed"
            if args.rename_stress:
                env["AI_CHAT_TEST_RENAME_STRESS"] = "1"
                env["AI_CHAT_TEST_PYTHON"] = sys.executable
                env["AI_CHAT_TEST_RUNNER"] = str(Path(__file__).resolve())
                env["AI_CHAT_TEST_RAW_INPUT_STRESS"] = "1" if args.raw_input_stress else "0"
            if args.schedules:
                env["AI_CHAT_SCHEDULE_STAGE"] = "seed"
            if args.queue:
                env["AI_CHAT_QUEUE_STAGE"] = "seed"
            if args.history:
                env["AI_CHAT_HISTORY_STAGE"] = "seed"
            if args.history_performance:
                env["AI_CHAT_HISTORY_PERFORMANCE"] = "stress"
                # Never benchmark with the user's real conversations. Large tool
                # details exercise JSON escaping, UTF-8, backups and all Agents.
                detail = 'synthetic tool result 数据 "\\\\"\n' * 3000 + " test-secret "
                detail += "x" * (150000 - len(detail.encode("utf-8")))
                assert len(detail.encode("utf-8")) == 150000
                agents = []
                for identifier in range(3):
                    records = (
                        [{"role": "work", "content": "Synthetic tool detail", "detail": detail} for _ in range(190)]
                        if identifier < 2
                        else []
                    )
                    agents.append({
                        "id": identifier,
                        "title": f"Agent {identifier}",
                        "backend": 0,
                        "model": "",
                        "cli_model": "",
                        "draft": "",
                        "draft_images": [],
                        "messages": [],
                        "transcript": records,
                    })
                settings = project / ".godot/editor"
                settings.mkdir(parents=True)
                (settings / "ai_chat_history.json").write_text(
                    json.dumps(
                        {"version": 1, "active_agent": 2, "next_agent": 3, "agents": agents}, ensure_ascii=False
                    ),
                    encoding="utf-8",
                )
            if args.cleanup:
                env["AI_CHAT_CLEANUP_STAGE"] = "seed"
                settings = project / ".godot/editor"
                settings.mkdir(parents=True, exist_ok=True)
                detail = "DISCARDED_TOOL_PAYLOAD " + "x" * 140000
                completed = (
                    [{"role": "user", "content": "LEGACY_QUESTION"}]
                    + [{"role": "work", "content": "LEGACY_WORK", "detail": detail} for _ in range(190)]
                    + [
                        {"role": "editor", "content": "LEGACY_RESTART_NOTICE"},
                        {"role": "assistant", "content": "LEGACY_FINAL"},
                    ]
                )
                unfinished = [
                    {"role": "user", "content": "UNFINISHED_QUESTION"},
                    {"role": "work", "content": "KEEP_UNFINISHED_WORK", "detail": "KEEP_UNFINISHED_DETAIL"},
                    {"role": "assistant", "content": "KEEP_INCOMPLETE\n\n[回复未完成，以上仅为中断前收到的正文。]"},
                    {"role": "error", "content": "KEEP_FAILURE"},
                ]
                agents = [
                    {
                        "id": i,
                        "title": f"Agent {i}",
                        "backend": 0,
                        "model": "",
                        "cli_model": "",
                        "draft": "",
                        "draft_images": [],
                        "messages": [],
                        "transcript": records,
                    }
                    for i, records in enumerate([completed, unfinished])
                ]
                agents[0]["messages"] = [
                    {"role": "user", "content": "LEGACY_QUESTION"},
                    {
                        "role": "assistant",
                        "content": "LEGACY_WORK",
                        "tool_calls": [tool("read_file", {"path": "res://fixture.gd"}, "legacy")],
                    },
                    {"role": "tool", "tool_call_id": "legacy", "content": detail},
                    {"role": "assistant", "content": "LEGACY_FINAL"},
                ]
                (settings / "ai_chat_history.json").write_text(
                    json.dumps({"version": 1, "active_agent": 1, "next_agent": 2, "agents": agents}), encoding="utf-8"
                )
            if args.agents:
                env["AI_CHAT_TEST_AGENTS"] = "seed"
            if args.visible:
                env["AI_CHAT_SCREENSHOT"] = str(ROOT / "bin" / "ai_chat_ui.png")
            if args.backend == "cli":
                node = shutil.which("node")
                if not node:
                    raise RuntimeError("Node.js is required for the CLI integration test")
                env["AI_CHAT_TEST_NODE"] = node
                env["AI_CHAT_TEST_BRIDGE"] = str(ROOT / "tools/codebuddy_cli/godot_bridge.js")
                env["AI_CHAT_TEST_ENTRY"] = str(Path(__file__).with_name("mock_codebuddy_cli.js"))
            try:
                result = subprocess.run(
                    [
                        str(isolated_editor),
                        *([] if args.visible else ["--headless"]),
                        "--editor",
                        "--path",
                        str(project),
                        "--script",
                        "res://integration.gd",
                    ],
                    env=env,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=600 if args.windows_commands else 180,
                )
            except subprocess.TimeoutExpired as error:
                for output in (error.stdout, error.stderr):
                    print(output.decode("utf-8", errors="replace") if isinstance(output, bytes) else output or "")
                print("Integration timeout. Cases seen:", sorted(SEEN), "Mock errors:", ERRORS)
                return 1
            print(result.stdout)
            print(result.stderr)
            if args.windows_commands:
                passed = result.returncode == 0 and "WINDOWS_COMMANDS_OK" in result.stdout and not ERRORS
                print("WINDOWS_COMMANDS_SUITE", passed, ERRORS)
                return 0 if passed else 1
            if ERRORS:
                print("Mock service errors:", ERRORS)
            if args.snapshots:
                if result.returncode != 0 or "AI_CHAT_SNAPSHOT_SEED_OK" not in result.stdout or ERRORS:
                    return 1
                env["AI_CHAT_SNAPSHOT_STAGE"] = "restore"
                checked = subprocess.run(
                    [
                        str(isolated_editor),
                        "--headless",
                        "--editor",
                        "--path",
                        str(project),
                        "--script",
                        "res://integration.gd",
                    ],
                    env=env,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=90,
                )
                print(checked.stdout)
                print(checked.stderr)
                passed = checked.returncode == 0 and "AI_CHAT_SNAPSHOT_RESTORE_OK" in checked.stdout and not ERRORS
                if not passed:
                    print("AI_CHAT_SNAPSHOT_SUITE_FAILED", args.backend, "restore exit code:", checked.returncode)
                    return 1
                settings = project / ".godot/editor"
                data = json.loads((settings / "ai_chat_history.json").read_bytes())
                active = next(agent for agent in data["agents"] if agent["id"] == data["active_agent"])
                snapshots = []
                for record in active["transcript"]:
                    if record.get("role") == "user" and record.get("snapshot_id"):
                        file = settings / "ai_chat_snapshots" / (record["snapshot_id"] + ".json")
                        envelope = json.loads(file.read_bytes())
                        snapshot = json.loads(envelope["payload"])
                        if snapshot["files"]:
                            snapshots.append((snapshot, envelope))
                assert len(snapshots) == 6
                assert sum("target_snapshot" in snapshot for snapshot, _ in snapshots) == 3
                assert sum(message.get("godot_snapshot_restore") is True for message in active["messages"]) == 3
                latest, latest_envelope = snapshots[-1]
                assert latest["files"][0]["after"] == "continued after restore\n"
                journal = settings / "ai_chat_version_transaction.json"
                pending = dict(latest, id="f" * 32)
                pending["files"] = [
                    {
                        "path": str(project / "history_fixture.txt").replace("\\", "/"),
                        "existed": True,
                        "before": "continued after restore\n",
                        "after_existed": True,
                        "after": "uncommitted partial install\n",
                    },
                    {
                        "path": str(project / "fixture.gd").replace("\\", "/"),
                        "existed": True,
                        "before": BEFORE,
                        "after_existed": True,
                        "after": BEFORE + "# uncommitted\n",
                    },
                ]
                payload = json.dumps(pending, ensure_ascii=False)
                journal.write_text(
                    json.dumps({"payload": payload, "sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest()}),
                    encoding="utf-8",
                )
                (project / "history_fixture.txt").write_text(
                    "uncommitted partial install\n", encoding="utf-8", newline=""
                )
                for stage in ["verify_uncommitted", "verify_committed"]:
                    if stage == "verify_committed":
                        # The chat commit exists, but one installed file is back at
                        # before. Startup must finish it without duplicating events.
                        journal.write_text(json.dumps(latest_envelope), encoding="utf-8")
                        (project / "history_fixture.txt").write_text(
                            latest["files"][0]["before"], encoding="utf-8", newline=""
                        )
                    env["AI_CHAT_SNAPSHOT_STAGE"] = stage
                    verified = subprocess.run(
                        [
                            str(isolated_editor),
                            "--headless",
                            "--editor",
                            "--path",
                            str(project),
                            "--script",
                            "res://integration.gd",
                        ],
                        env=env,
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        timeout=90,
                    )
                    print(verified.stdout)
                    print(verified.stderr)
                    print("VERSION_TRANSACTION_RECOVERY", stage, "exit code:", verified.returncode)
                    if verified.returncode != 0 or "AI_CHAT_VERSION_RECOVERY_OK" not in verified.stdout or ERRORS:
                        return 1
                print(
                    "AI_CHAT_SNAPSHOT_SUITE_OK",
                    args.backend,
                    "seed exit code:",
                    result.returncode,
                    "restore exit code:",
                    checked.returncode,
                    "transaction recovery exits: 0, 0",
                )
                return 0
            if args.schedules:
                if result.returncode != 0 or "AI_CHAT_SCHEDULE_OK" not in result.stdout or ERRORS:
                    print("Schedule seed failed, exit code:", result.returncode, "mock errors:", ERRORS)
                    return 1
                history = project / ".godot/editor/ai_chat_history.json"
                data = json.loads(history.read_bytes())
                assert len(data["agents"]) == 4 and data["scheduled_tasks"][0]["sequence"] == 4
                assert all(agent.get("scheduled_run", {}).get("state") != "running" for agent in data["agents"])
                # Simulate an offline missed deadline and an interrupted run: neither
                # may execute at startup, but explicitly requested next runs still work.
                data["scheduled_tasks"][0]["enabled"] = True
                data["scheduled_tasks"][0]["next_due"] = int(time.time()) - 3600
                data["agents"][1]["scheduled_run"]["state"] = "waiting"
                history.write_text(json.dumps(data), encoding="utf-8")
                env["AI_CHAT_SCHEDULE_STAGE"] = "restore"
                checked = subprocess.run(
                    [
                        str(isolated_editor),
                        "--headless",
                        "--editor",
                        "--path",
                        str(project),
                        "--script",
                        "res://integration.gd",
                    ],
                    env=env,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=90,
                )
                print(checked.stdout)
                print(checked.stderr)
                passed = checked.returncode == 0 and "AI_CHAT_SCHEDULE_RESTORE_OK" in checked.stdout and not ERRORS
                print(
                    "AI_CHAT_SCHEDULE_SUITE_OK" if passed else "AI_CHAT_SCHEDULE_SUITE_FAILED",
                    args.backend,
                    "seed exit code:",
                    result.returncode,
                    "restart exit code:",
                    checked.returncode,
                )
                return 0 if passed else 1
            if args.queue:
                if result.returncode != 0 or "AI_CHAT_QUEUE_OK" not in result.stdout or ERRORS:
                    print("Queue seed failed, exit code:", result.returncode)
                    return 1
                data = json.loads((project / ".godot/editor/ai_chat_history.json").read_bytes())
                assert len(data["agents"]) == 2
                assert [agent["queued_messages"][0]["content"] for agent in data["agents"]] == [
                    "case:queue_restart_a",
                    "case:queue_restart_b",
                ]
                assert all(agent["queue_paused"] for agent in data["agents"])
                assert data["agents"][0]["queued_messages"][0]["images"]
                assert data["agents"][1]["draft"] == "UNSENT_B"
                assert "queue_deleted" not in SEEN
                env["AI_CHAT_QUEUE_STAGE"] = "restore"
                checked = subprocess.run(
                    [
                        str(isolated_editor),
                        "--headless",
                        "--editor",
                        "--path",
                        str(project),
                        "--script",
                        "res://integration.gd",
                    ],
                    env=env,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=90,
                )
                print(checked.stdout)
                print(checked.stderr)
                required = {
                    "queue_first",
                    "queue_second",
                    "queue_third",
                    "queue_fail",
                    "queue_after_failure",
                    "queue_restart_a",
                    "queue_restart_b",
                }
                passed = (
                    checked.returncode == 0
                    and "AI_CHAT_QUEUE_RESTORE_OK" in checked.stdout
                    and not ERRORS
                    and required <= SEEN
                )
                print(
                    "AI_CHAT_QUEUE_SUITE_OK" if passed else "AI_CHAT_QUEUE_SUITE_FAILED",
                    args.backend,
                    "seed exit code:",
                    result.returncode,
                    "restart exit code:",
                    checked.returncode,
                )
                return 0 if passed else 1
            if args.cleanup:
                if result.returncode != 0 or "AI_CHAT_CLEANUP_OK" not in result.stdout or ERRORS:
                    print("Cleanup failed, exit code:", result.returncode)
                    return 1
                for suffix in ["", ".bak"]:
                    data = json.loads((project / (".godot/editor/ai_chat_history.json" + suffix)).read_bytes())
                    assert data["agents"][0]["transcript"] == [
                        {"role": "user", "content": "LEGACY_QUESTION"},
                        {"role": "assistant", "content": "LEGACY_FINAL"},
                    ]
                    assert data["agents"][0]["messages"] == data["agents"][0]["transcript"]
                    text = json.dumps(data)
                    assert "DISCARDED_TOOL_PAYLOAD" not in text and "LEGACY_RESTART_NOTICE" not in text
                    assert "KEEP_UNFINISHED_DETAIL" in text and "KEEP_FAILURE" in text and "KEEP_INCOMPLETE" in text
                    assert "CLEANUP_FINAL" in text and "CLEANUP_FOLLOW_OK" in text
                env["AI_CHAT_CLEANUP_STAGE"] = "restore"
                checked = subprocess.run(
                    [
                        str(isolated_editor),
                        "--headless",
                        "--editor",
                        "--path",
                        str(project),
                        "--script",
                        "res://integration.gd",
                    ],
                    env=env,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=90,
                )
                print(checked.stdout)
                print(checked.stderr)
                passed = checked.returncode == 0 and "AI_CHAT_CLEANUP_RESTORE_OK" in checked.stdout and not ERRORS
                print(
                    "AI_CHAT_CLEANUP_SUITE_OK" if passed else "AI_CHAT_CLEANUP_SUITE_FAILED",
                    args.backend,
                    "restart exit code:",
                    checked.returncode,
                )
                return 0 if passed else 1
            if args.history_performance:
                if result.returncode != 0 or "AI_CHAT_HISTORY_PERFORMANCE_OK" not in result.stdout:
                    print("AI_CHAT_HISTORY_PERFORMANCE_SUITE_FAILED", "exit code:", result.returncode)
                    return 1
                saved = json.loads((project / ".godot/editor/ai_chat_history.json").read_bytes())
                assert saved["agents"][2]["draft"] == "SHUTDOWN_LATEST_DRAFT"
                assert len(saved["agents"]) == 3
                expected_records = [
                    {
                        "role": "work",
                        "content": "Synthetic tool detail",
                        "detail": detail.replace("test-secret", "[REDACTED]"),
                    }
                    for _ in range(190)
                ]
                # Switching a fixture with no model messages adds an editor notice.
                # Verify every original record, not a total including new notices.
                for agent in saved["agents"][:2]:
                    assert [record for record in agent["transcript"] if record["role"] != "editor"] == expected_records
                assert "test-secret" not in json.dumps(saved, ensure_ascii=False)
                env["AI_CHAT_HISTORY_PERFORMANCE"] = "restore"
                checked = subprocess.run(
                    [
                        str(isolated_editor),
                        "--headless",
                        "--editor",
                        "--path",
                        str(project),
                        "--script",
                        "res://integration.gd",
                    ],
                    env=env,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=90,
                )
                print(checked.stdout)
                print(checked.stderr)
                passed = checked.returncode == 0 and "AI_CHAT_HISTORY_PERFORMANCE_RESTORE_OK" in checked.stdout
                print(
                    "AI_CHAT_HISTORY_PERFORMANCE_SUITE_OK" if passed else "AI_CHAT_HISTORY_PERFORMANCE_SUITE_FAILED",
                    "restart exit code:",
                    checked.returncode,
                )
                return 0 if passed else 1
            if args.rename_stress:
                passed = (
                    result.returncode == 0
                    and "AI_CHAT_AGENT_RENAME_STRESS_OK" in result.stdout
                    and "Failed to create" not in result.stdout + result.stderr
                )
                print(
                    "AI_CHAT_AGENT_RENAME_STRESS_SUITE_OK" if passed else "AI_CHAT_AGENT_RENAME_STRESS_SUITE_FAILED",
                    "exit code:",
                    result.returncode,
                )
                return 0 if passed else 1
            if args.agents:
                if result.returncode != 0 or "AI_CHAT_AGENT_CLOSE_OK" not in result.stdout or ERRORS:
                    print("Agent close test failed, return code:", result.returncode)
                    return 1
                env["AI_CHAT_TEST_AGENTS"] = "restore"
                checked = subprocess.run(
                    [
                        str(isolated_editor),
                        "--headless",
                        "--editor",
                        "--path",
                        str(project),
                        "--script",
                        "res://integration.gd",
                    ],
                    env=env,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=45,
                )
                print(checked.stdout)
                print(checked.stderr)
                passed = checked.returncode == 0 and "AI_CHAT_AGENT_CLOSE_RESTORE_OK" in checked.stdout and not ERRORS
                print(
                    "AI_CHAT_AGENT_CLOSE_SUITE_OK" if passed else "AI_CHAT_AGENT_CLOSE_SUITE_FAILED",
                    args.backend,
                    "restart exit code:",
                    checked.returncode,
                )
                return 0 if passed else 1
            if args.history:
                if result.returncode != 0 or "AI_CHAT_HISTORY_SEED_OK" not in result.stdout or ERRORS:
                    print("History seed failed, return code:", result.returncode)
                    return 1
                history = project / ".godot/editor/ai_chat_history.json"
                backup = history.with_suffix(".json.bak")
                original = history.read_bytes()
                data = json.loads(original)
                assert data["active_agent"] == 1 and len(data["agents"]) == 2
                # Simulate shutdown while waiting on a partially completed tool batch.
                interrupted = json.loads(original)
                interrupted["agents"][0]["messages"].append({
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        tool(
                            "write_file",
                            {"path": "res://should_not_run.txt", "content": "unsafe replay"},
                            "interrupted_history_tool",
                        )
                    ],
                })
                history.write_text(json.dumps(interrupted, ensure_ascii=False), encoding="utf-8")
                command = [
                    str(isolated_editor),
                    "--headless",
                    "--editor",
                    "--path",
                    str(project),
                    "--script",
                    "res://integration.gd",
                ]
                for stage in ["restore", "backup", "corrupt"]:
                    if stage == "backup":
                        history.write_text('{"agents": [{"messages": "invalid schema"}]}', encoding="utf-8")
                        backup.write_bytes(original)
                    elif stage == "corrupt":
                        history.write_bytes(b"broken main history")
                        backup.write_bytes(b"broken backup history")
                    env["AI_CHAT_HISTORY_STAGE"] = stage
                    checked = subprocess.run(
                        command, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90
                    )
                    print(checked.stdout)
                    print(checked.stderr)
                    if (
                        checked.returncode != 0
                        or "AI_CHAT_HISTORY_" + stage.upper() + "_OK" not in checked.stdout
                        or ERRORS
                    ):
                        print("History stage failed:", stage, "exit code:", checked.returncode, "mock errors:", ERRORS)
                        return 1
                    assert not (project / "should_not_run.txt").exists(), "Startup executed an old tool call"
                    if stage == "restore":
                        restored = json.loads(history.read_bytes())
                        assert "HISTORY_A_SEED_OK" in json.dumps(restored["agents"][0]), (
                            "Restoring history lost Agent A"
                        )
                        assert "HISTORY_B_SEED_OK" in json.dumps(restored["agents"][1]), (
                            "Restoring history lost Agent B"
                        )
                    elif stage == "backup":
                        assert json.loads(history.read_bytes())["version"] == 1, (
                            "Recovered backup did not repair primary history"
                        )
                    else:
                        assert (
                            history.read_bytes() == b"broken main history"
                            and backup.read_bytes() == b"broken backup history"
                        ), "Invalid history was overwritten"
                assert {"history_a_seed", "history_b_seed", "history_a_resume", "history_b_resume"} <= SEEN
                print("AI_CHAT_HISTORY_RESTART_SUITE_OK", args.backend)
                return 0
            required = {
                "workflow",
                "incremental_next",
                "context_kept",
                "after_refresh",
                "unsaved",
                "reject",
                "traversal",
                "after_cancel",
                "expanded",
                "malformed",
                "budget",
                "budget_violation",
                "permission_off",
                "budget_resume",
                "large_context",
                "range_context",
                "long_structured_context",
                "range_invalid",
                "large_next",
                "history_fill",
            }
            required.update({"agent_a_seed", "agent_b_seed", "agent_a_resume", "agent_b_resume"})
            if args.images:
                required = {
                    "image_send",
                    "image_only",
                    "image_follow",
                    "image_agent_b",
                    "image_agent_a",
                    "image_agent_b_resume",
                }
                if args.backend == "cli":
                    required.add("image_recovery")
            elif args.backend == "cli":
                # Terminal cases run directly in the ACP mock, not via Handler.
                assert "AI_CHAT_NATIVE_COMMANDS_OK" in result.stdout, "Native terminal checks did not complete"
                required = {
                    "auto_write",
                    "auto_create",
                    "auto_eol_edit",
                    "native_read",
                    "native_write",
                    "native_reject",
                    "native_create",
                    "native_range",
                    "native_large",
                    "native_permission_off",
                    "native_progress",
                    "native_stream_next",
                    "native_progress_error",
                    "native_eol_edit",
                    "native_eol_reject",
                    "native_search_edit",
                    "agent_a_seed",
                    "agent_b_seed",
                    "agent_a_resume",
                    "agent_b_resume",
                }
                if not ERRORS and result.returncode == 0:
                    assert len(TRANSPORTS.get("native_write", [])) == 3, (
                        "Unexpected retries or missing native file callbacks"
                    )
                    assert len(TRANSPORTS.get("native_read", [])) == 2
                    print("CLI_NATIVE_FILE_FLOW", TRANSPORTS["native_write"])
            if args.backend == "cli" and not args.images and result.returncode == 0:
                assert "AI_CHAT_ON_DEMAND_LOGS_OK" in result.stdout
                assert "approvals=16" in result.stdout
            if args.backend == "http" and not args.images:
                required.update({"slow", "auto_write", "auto_execution"})
            if args.visible and not args.images:
                required.add("scroll")
            passed = (
                result.returncode == 0 and "AI_CHAT_INTEGRATION_OK" in result.stdout and not ERRORS and required <= SEEN
            )
            if not passed:
                print("Return code:", result.returncode, "Cases seen:", sorted(SEEN))
                return 1
            if args.backend == "cli":
                log_files = sorted((project / "acp_logs").glob("acp-*.jsonl"))
                assert log_files, "No persistent ACP diagnostics were produced"
                records = []
                for log_file in log_files:
                    assert log_file.stat().st_size <= 8 * 1024 * 1024
                    log_text = log_file.read_text(encoding="utf-8")
                    assert "PRIVATE_" not in log_text, "Private notifications escaped into persistent diagnostics"
                    records.extend(json.loads(line) for line in log_text.splitlines())
                assert any(record["event"] == "model_prompt_sent" for record in records)
                assert any(
                    record["event"] == "file_callback_received" and record.get("operation") == "read_file"
                    for record in records
                )
                assert any(record["event"] == "host_file_result" and record.get("success") for record in records)
                inherited = [
                    record
                    for record in records
                    if record["event"] == "permission_decided" and record.get("kind_source") == "notification"
                ]
                assert any(
                    record.get("kind") == "read" and record.get("decision") == "allow_once" for record in inherited
                ), "Omitted read permission kind was not resolved from the matching notification"
                assert not any(record.get("decision") != "allow_once" for record in inherited), (
                    "Live file permission was incorrectly rejected"
                )
                if not args.images:
                    assert any(
                        record.get("kind") == "edit" and record.get("decision") == "allow_once" for record in inherited
                    ), "Omitted write permission kind was not resolved from the matching notification"
                    assert any(
                        record["event"] == "permission_decided" and record.get("decision") == "allow_once"
                        for record in records
                    )
                    assert any(
                        record["event"] == "host_file_result" and not record.get("success") for record in records
                    )
                    assert any(
                        record["event"] == "request_failed" and record.get("stderr_bytes", 0) > 0 for record in records
                    )
                    assert any(
                        record["event"] == "file_text_view" and record.get("newline") == "crlf" and record.get("bom")
                        for record in records
                    ), "CRLF/BOM read format was not observed"
                    assert any(
                        record["event"] == "file_text_saved" and record.get("newline") == "crlf" and record.get("bom")
                        for record in records
                    ), "CRLF/BOM write format was not restored"
                    searches = [
                        record
                        for record in records
                        if record["event"] == "session_notification" and record.get("native_tool") in {"Glob", "Grep"}
                    ]
                    assert {record["native_tool"] for record in searches} == {"Glob", "Grep"}
                    for search in searches:
                        assert any(
                            record["event"] == "permission_decided"
                            and record.get("call_hash") == search.get("call_hash")
                            and record.get("decision") == "allow_once"
                            for record in records
                        ), "Native read-only source search was denied"
                    assert not any(record.get("code") == "TOOL_ROUND_LIMIT_REACHED" for record in records), (
                        "Unlimited tools still hit a round limit"
                    )
                counts = {
                    event: sum(record["event"] == event for record in records)
                    for event in [
                        "model_prompt_sent",
                        "permission_decided",
                        "file_callback_received",
                        "host_file_result",
                        "request_failed",
                    ]
                }
                print("ACP_DIAGNOSTIC_LOGS_OK", len(log_files), counts)
                if not args.images:
                    assert "AI_CHAT_AGENT_RENAME_OK" in result.stdout
                    restore_env = {**env, "AI_CHAT_TEST_RENAME_RESTORE": "1"}
                    renamed = subprocess.run(
                        [
                            str(isolated_editor),
                            "--headless",
                            "--editor",
                            "--path",
                            str(project),
                            "--script",
                            "res://integration.gd",
                        ],
                        env=restore_env,
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        timeout=45,
                    )
                    print(renamed.stdout)
                    print(renamed.stderr)
                    if renamed.returncode != 0 or "AI_CHAT_AGENT_RENAME_RESTORE_OK" not in renamed.stdout:
                        print("Agent rename restart failed, exit code:", renamed.returncode)
                        return 1
            try:
                startup = subprocess.run(
                    [str(isolated_editor), "--headless", "--editor", "--path", str(project), "--quit-after", "30"],
                    env=env,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=45,
                )
            except subprocess.TimeoutExpired as error:
                for output in (error.stdout, error.stderr):
                    print(output.decode("utf-8", errors="replace") if isinstance(output, bytes) else output or "")
                print("Normal editor startup timed out")
                return 1
            print(startup.stdout)
            print(startup.stderr)
            startup_ok = (
                startup.returncode == 0
                and "Failed to load" not in startup.stderr
                and "were leaked" not in startup.stdout + startup.stderr
            )
            print("NORMAL_EDITOR_STARTUP_OK" if startup_ok else "NORMAL_EDITOR_STARTUP_FAILED")
            return 0 if startup_ok else 1
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


if __name__ == "__main__":
    raise SystemExit(main())
