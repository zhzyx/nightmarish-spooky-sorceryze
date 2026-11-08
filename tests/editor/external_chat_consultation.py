"""Offline native UDS consultation cases; invoked by run_external_chat_submit."""

import json
import subprocess
import sys
import time
from pathlib import Path

from run_design_batch import tool_call


def consultation_reply(body, target, hold_started, release_hold):
    prompt = next(x["content"] for x in reversed(body["messages"]) if x["role"] == "user")
    tools = {x["function"]["name"] for x in body.get("tools", [])}
    user_index = max(i for i, x in enumerate(body["messages"]) if x["role"] == "user")
    results = {x.get("tool_call_id"): x["content"] for x in body["messages"][user_index + 1 :] if x["role"] == "tool"}
    if prompt == "CONSULTATION_NO_TOOLS":
        assert not tools
        return {"role": "assistant", "content": "CONSULTATION_NO_TOOLS_OK"}
    if prompt == "CONSULTATION_NO_TOOLS_ATTACK":
        assert not tools and not results
        return tool_call("no-permission-read", "read_file", {"path": str(target)})
    if prompt in ("CONSULTATION_NO_TOOLS", "CONSULTATION_ALLOWED_READ"):
        read_allowed = prompt == "CONSULTATION_ALLOWED_READ"
        assert ("read_file" in tools) == read_allowed
        assert not tools.intersection({
            "write_file",
            "run_command",
            "build_engine",
            "delegate_review",
            "complete_delivery",
            "editor_action",
        })
        forbidden = {
            "write_file": {"path": str(target), "content": "FORBIDDEN"},
            "run_command": {"command": "touch forbidden-command", "cwd": str(target.parent)},
            "build_engine": {},
            "restart_engine": {},
            "delegate_review": {"task": "FORBIDDEN"},
            "complete_delivery": {"acceptance_items": []},
            "editor_action": {"action": "chat_set_runtime_field", "field": "node", "value": "FORBIDDEN"},
        }
        if not results:
            if read_allowed:
                hold_started.set()
                assert release_hold.wait(30)
            message = tool_call("consult-read", "read_file", {"path": str(target)})
            for name, arguments in forbidden.items():
                message["tool_calls"].extend(tool_call("consult-" + name, name, arguments)["tool_calls"])
            return message
        assert len(results) == 8, results
        if read_allowed:
            assert "CONSULTATION_READ_SENTINEL" in results["consult-read"]
        else:
            assert "Local tool permission is disabled" in results["consult-read"]
        for name in forbidden:
            assert "Consultation only permits read tools" in results["consult-" + name]
        return {"role": "assistant", "content": prompt + "_OK"}
    if prompt == "CONSULTATION_QUEUE_HOLD":
        hold_started.set()
        assert release_hold.wait(30)
        return {"role": "assistant", "content": "CONSULTATION_CANCELLED_HOLD"}
    raise AssertionError("Unexpected consultation fixture request: " + prompt[:100])


def run_consultation(client, fixture, check, rejected, wait_text, calls, report, hold_started, release_hold, tcp):
    initial = client.context()
    context = initial["context"]
    report["initial_peer_reply"] = initial
    check("kernel_verified_desktop_peer", initial["ok"] and initial["authenticated_desktop_peer"])
    check(
        "selected_unbound_top_level_consultation",
        context["top_level_parent"]
        and context["consultation"]
        and not context["owner"]
        and not context["snapshot_id"]
        and context["instruction_available"],
    )
    check("stale_global_issue_is_not_production_authority", context["issue_number"] == 999)
    check("tools_off_text_admitted", not context["tools_allowed"] and context["automatic_execution"])
    fixture("consultation", False)
    cold = client.context()["context"]
    check(
        "cold_ui_mode_unchanged_readonly_route_available",
        not cold["consultation"] and not cold["instruction_available"] and cold["consultation_instruction_available"],
    )
    for value in (False, 1, "true", None):
        malformed = client.request({
            "protocol_version": 1,
            "kind": "submit",
            "request_id": "invalid-readonly-" + str(value),
            "text": "NEVER_SEND",
            "expected": cold,
            "consultation_only": value,
        })
        check("strict_readonly_flag_" + str(value), malformed.get("error") == "invalid_instruction_message")
    cli = Path(__file__).resolve().parents[2] / "tools/editor_instruction_client.py"
    expected_path = client.project / "readonly-context.json"
    text_path = client.project / "readonly-text.txt"
    expected_path.write_text(json.dumps(cold))
    text_path.write_text("CONSULTATION_NO_TOOLS")
    cli_result = subprocess.run(
        [
            sys.executable,
            "-B",
            str(cli),
            "--project",
            str(client.project),
            "--instance",
            str(client.instance),
            "submit",
            "--consultation-only",
            "--expected",
            str(expected_path),
            "--text-file",
            str(text_path),
            "--request-id",
            "cold-readonly",
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    readonly = json.loads(cli_result.stdout)
    report["actual_readonly_cli_result"] = readonly
    check("actual_readonly_cli_exit_zero", cli_result.returncode == 0)
    check("explicit_message_readonly_without_ui_mode", readonly["ok"] and readonly["instruction_submitted"])
    cold_state = wait_text("CONSULTATION_NO_TOOLS_OK")
    check(
        "per_message_readonly_never_changes_mode_or_tools", not cold_state["consultation"] and not cold_state["tools"]
    )
    readonly_repeat = client.submit("CONSULTATION_NO_TOOLS", cold, "cold-readonly", consultation_only=True)
    check("readonly_flag_in_durable_idempotency", readonly_repeat["ok"] and readonly_repeat["idempotent"])
    upgrade = client.submit("CONSULTATION_NO_TOOLS", cold, "cold-readonly")
    check("same_id_cannot_drop_readonly_intent", upgrade.get("error") == "request_id_conflict")
    fixture("consultation", True)
    context = client.context()["context"]
    first = client.submit("CONSULTATION_NO_TOOLS", context, "consultation-no-tools")
    check(
        "actual_read_only_text_submitted",
        first["ok"] and first["instruction_submitted"] and first["business_completed"] is False,
    )
    state = wait_text("CONSULTATION_NO_TOOLS_OK")
    check("consultation_and_tools_flags_preserved", state["consultation"] and not state["tools"])
    count = len(calls)
    duplicate = client.submit("CONSULTATION_NO_TOOLS", context, "consultation-no-tools")
    check("consultation_idempotent_no_second_send", duplicate["ok"] and duplicate["idempotent"] and len(calls) == count)
    conflict = client.submit("OTHER", context, "consultation-no-tools")
    check("consultation_id_conflict_refused", conflict.get("error") == "request_id_conflict" and len(calls) == count)
    attack = client.submit(
        "CONSULTATION_NO_TOOLS_ATTACK", client.context()["context"], "consultation-no-permission-attack"
    )
    check("no_permission_attack_submitted_only_as_text", attack["ok"])
    wait_text("本地工具权限已关闭，未执行本次操作。")
    check("tools_off_refuses_unsolicited_read_without_execution", calls.count("CONSULTATION_NO_TOOLS_ATTACK") == 1)
    tcp_result = tcp.route({
        "intent": "engine_operation",
        "source": "fixture",
        "request_id": "ordinary-http-consultation",
        "operation": {"action": "chat_send_message", "value": "NEVER_SEND"},
    })
    check(
        "ordinary_http_write_still_refused", not tcp_result.get("ok") and tcp_result.get("error") == "permission_denied"
    )
    tcp_trusted = tcp.route({
        "intent": "engine_operation",
        "source": "desktop.codex",
        "request_id": "forged-http-trust",
        "operation": {
            "action": "chat_submit_instruction",
            "value": {"text": "NEVER_SEND", "expected": client.context()["context"]},
        },
    })
    check("http_cannot_claim_desktop_trust", tcp_trusted.get("error") == "permission_denied")
    stale = client.context()["context"]
    fixture("draft", "unsent consultation draft")
    rejected(client, "consult-draft-race", "NEVER_SEND", stale, "chat_instruction_state_changed")
    rejected(client, "consult-draft-present", "NEVER_SEND", client.context()["context"], "draft_not_empty")
    check("consultation_human_draft_preserved", fixture("read")["draft"] == "unsent consultation draft")
    fixture("draft", "")
    fixture("attachment")
    rejected(client, "consult-attachment-preserved", "NEVER_SEND", client.context()["context"], "draft_images_present")
    fixture("remove_attachment")
    fixture("automatic", False)
    rejected(client, "consult-auto-opt-in-required", "NEVER_SEND", client.context()["context"], "permission_denied")
    fixture("automatic", True)
    stale = client.context()["context"]
    fixture("tools", True)
    rejected(client, "consult-tools-context-changed", "NEVER_SEND", stale, "chat_instruction_state_changed")
    stale = client.context()["context"]
    fixture("consultation", False)
    rejected(client, "consult-cannot-upgrade-production", "NEVER_SEND", stale, "known_work_order_owner_required")
    fixture("consultation", True)
    for field, value in (("engine_pid", context["engine_pid"] + 1), ("host_instance_id", "0" * 32)):
        stale = dict(client.context()["context"])
        stale[field] = value
        rejected(client, "consult-stale-" + field, "NEVER_SEND", stale, "chat_instruction_state_changed")
    fixture("child")
    rejected(client, "consult-child-refused", "NEVER_SEND", client.context()["context"], "parent_session_required")
    fixture("parent")
    fixture("close_prompt")
    rejected(client, "consult-close-pending", "NEVER_SEND", client.context()["context"], "parent_close_pending")
    fixture("close_cancel")
    hold_started.clear()
    release_hold.clear()
    allowed = client.submit("CONSULTATION_ALLOWED_READ", client.context()["context"], "consultation-tools-bounded")
    check("consultation_existing_read_tools_supported", allowed["ok"] and hold_started.wait(20))
    rejected(client, "consult-busy-no-steering", "NEVER_SEND", client.context()["context"], "consultation_busy")
    # Changing the next-message mode cannot upgrade the captured read-only turn.
    fixture("consultation", False)
    release_hold.set()
    wait_text("CONSULTATION_ALLOWED_READ_OK")
    check(
        "captured_consultation_denies_write_command_build_review_completion_config",
        calls.count("CONSULTATION_ALLOWED_READ") == 2,
    )
    rejected(
        client,
        "production-still-needs-owner",
        "NEVER_SEND",
        client.context()["context"],
        "known_work_order_owner_required",
    )
    fixture("consultation", True)
    hold_started.clear()
    release_hold.clear()
    held = client.submit("CONSULTATION_QUEUE_HOLD", client.context()["context"], "consultation-queue-hold")
    check("queue_boundary_started", held["ok"] and hold_started.wait(20))
    fixture("consultation", False)
    fixture("queue")
    fixture("stop")
    fixture("consultation", True)
    release_hold.set()
    for unused in range(100):
        queued = client.context()["context"]
        if not queued["busy"]:
            break
        time.sleep(0.03)
    check("production_queue_remains_paused", queued["queue_count"] == 1 and queued["queue_paused"])
    rejected(client, "consult-cannot-resume-production-queue", "NEVER_SEND", queued, "consultation_queue_pending")
    check(
        "rejected_submit_keeps_old_queue",
        client.context()["context"]["queue_count"] == 1 and "FIXTURE_QUEUED_MESSAGE" not in calls,
    )
    fixture("remove_queue")
    check("explicit_queue_removal_restores_consultation", client.context()["context"]["instruction_available"])
    check("no_rejected_message_reached_model", "NEVER_SEND" not in calls)
    report["tool_policy"] = (
        "Existing manual consultation policy: no tools when off; bounded reads when on; production actions always refused."
    )
