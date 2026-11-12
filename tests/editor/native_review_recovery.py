"""Retry an actual failed native review through normal warm/cold editor controls.

Only model/authority transport is controlled. No terminal, acceptance, history,
candidate or worker registration is injected. The original workers must not rerun.
"""

import io
import json
import re
from pathlib import Path


def control(source, mode):
    resume = """
\t\tvar deadline := Time.get_ticks_msec() + 45000
\t\twhile (not dock.find_child("Stop", true, false).disabled or dock.find_child("SpawnWorkOrderAgents", true, false).disabled) and Time.get_ticks_msec() < deadline:
\t\t\tawait create_timer(0.05).timeout
\t\tif not _check(dock.find_child("Stop", true, false).disabled and not dock.find_child("SpawnWorkOrderAgents", true, false).disabled, "Review return never became ready to resume"):
\t\t\t_finish()
\t\t\treturn
\t\tdock.get_ai_settings_control().find_child("ProductionSetup", true, false).button_pressed = true
\t\tdock.find_child("SpawnWorkOrderAgents", true, false).pressed.emit()
\t\tawait _wait_marker("ORDINARY_GAME_INTEGRATION_ROLLED_BACK", 180.0)
"""
    marker = '\tvar mode := OS.get_environment("DESIGN_BATCH_CASE")\n\tif OS.get_environment("DESIGN_BATCH_PHASE")'
    branch = (
        """\tvar mode := OS.get_environment("DESIGN_BATCH_CASE")
\tif OS.get_environment("DESIGN_BATCH_PHASE") == "review-recovery-cold":
\t\tawait create_timer(2.0).timeout
"""
        + resume
        + """\t\t_finish()
\t\treturn
\tif OS.get_environment("DESIGN_BATCH_PHASE")"""
    )
    assert marker in source
    source = source.replace(marker, branch, 1)
    target = '\tawait _wait_marker("ORDINARY_GAME_INTEGRATION_ROLLED_BACK", 180.0)\n\t_finish()'
    replacement = '\tawait _wait_marker("REVIEW_RECOVERY_READY", 180.0)\n'
    if mode == "warm":
        replacement += "\tif true:\n" + resume
    replacement += "\t_finish()"
    assert target in source
    return source.replace(target, replacement, 1)


def install(batch, observed):
    previous = batch.ThreadingHTTPServer
    state = observed["review_recovery"] = {"first_review_finished": False, "parent_returned": False}

    class RecoveryServer(previous):
        def __init__(self, address, handler):
            super().__init__(address, handler)
            original = handler.do_POST

            def post(instance):
                raw = instance.rfile.read(int(instance.headers["Content-Length"]))
                body = json.loads(raw)
                prompt = next((m.get("content", "") for m in reversed(body["messages"]) if m["role"] == "user"), "")
                message = None
                if (
                    isinstance(prompt, str)
                    and prompt.startswith("独立只读验收。")
                    and not state["first_review_finished"]
                ):
                    system = "\n".join(m.get("content", "") for m in body["messages"] if m["role"] == "system")
                    root = re.findall(r"Authoritative source to review: ([^\n]+)", system)[-1]
                    if not any(m["role"] == "tool" for m in body["messages"]):
                        message = batch.tool_call(
                            "missing-proof", "read_file", {"path": str(Path(root) / "missing-proof.txt")}
                        )
                    else:
                        state["first_review_finished"] = True
                        criteria = json.loads(prompt.split("\n")[1])
                        message = {
                            "role": "assistant",
                            "content": json.dumps({
                                "verdict": "unknown",
                                "reason": "The requested evidence file could not be read",
                                "criteria": [
                                    {"id": c["id"], "met": False, "evidence": ["missing-proof.txt"]} for c in criteria
                                ],
                            }),
                        }
                elif isinstance(prompt, str) and "current_host_design_batch" in prompt and not state["parent_returned"]:
                    assert state["first_review_finished"]
                    assert "review_tool_receipt_unverified" in prompt, prompt
                    state["parent_returned"] = True
                    message = {"role": "assistant", "content": "REVIEW_RECOVERY_READY"}
                if message is None:
                    instance.rfile = io.BytesIO(raw)
                    return original(instance)
                data = json.dumps({"choices": [{"message": message, "finish_reason": "stop"}]}).encode()
                instance.send_response(200)
                instance.send_header("Content-Type", "application/json")
                instance.send_header("Content-Length", str(len(data)))
                instance.end_headers()
                instance.wfile.write(data)

            handler.do_POST = post

    batch.ThreadingHTTPServer = RecoveryServer


def restart(run, command, args, kwargs, observed):
    env = dict(kwargs["env"])
    project = Path(env["DESIGN_BATCH_PROJECT"])
    report = project / "design-batch-report.json"
    initial = json.loads(report.read_text(encoding="utf8"))
    assert initial["ok"] and observed["review_recovery"]["parent_returned"]
    observed["review_recovery"]["first_editor"] = initial
    before = Path(env["NATIVE_SETUP_EVENTS"]).read_bytes()
    env["DESIGN_BATCH_PHASE"] = "review-recovery-cold"
    result = run(command, *args, **dict(kwargs, env=env))
    after = Path(env["NATIVE_SETUP_EVENTS"]).read_bytes()
    assert after.startswith(before), "Prior actual worker observations were rewritten"
    observed["review_recovery"]["cold_exit"] = result.returncode
    return result


def validate(observed, diagnostics):
    state = observed["review_recovery"]
    failed = []
    for entry in diagnostics:
        if entry["path"].endswith(".tool-receipts.json"):
            envelope = json.loads(entry["body"])
            payload = json.loads(envelope["payload"])
            if payload.get("failed_receipt_count"):
                failed.append(payload)
    assert len(failed) == 1, failed
    first = failed[0]["first_unverified_receipt"]
    assert first["tool"] == "read_file" and first["ok"] is False
    state["original_failure_preserved"] = True
    assert state["first_review_finished"] and state["parent_returned"]
    assert len([e for e in observed["events"] if e["phase"] == "start"]) == 2, "Recovery duplicated producers"
