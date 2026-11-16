"""Real native setup and repair reuse with controlled model transport.

The fixture adds an ordinary UID after setup, never rewrites the setup ledger,
and obtains repair eligibility from a successful independent source read.
"""

import hashlib
import io
import json
import re
from pathlib import Path


def reference(path):
    raw = Path(path).read_bytes()
    return {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()}


def install(batch, observed, fault="", mixed=False):
    previous = batch.ThreadingHTTPServer
    state = observed["repair_reuse"] = {"reviews": [], "fault": fault, "mixed": mixed}

    class RepairServer(previous):
        def __init__(self, address, handler):
            super().__init__(address, handler)
            original = handler.do_POST

            def post(instance):
                raw = instance.rfile.read(int(instance.headers["Content-Length"]))
                body = json.loads(raw)
                prompt = next((m.get("content", "") for m in reversed(body["messages"]) if m["role"] == "user"), "")
                message = None
                if isinstance(prompt, str) and "current_host_design_batch" in prompt:
                    from native_prepared_job_recovery import _parent_message

                    history = json.loads(
                        Path(
                            batch.os.environ["REPAIR_REUSE_WORKSPACE"],
                            "samples/project/.godot/editor/ai_chat_history.json",
                        ).read_text(encoding="utf8")
                    )
                    expected = {
                        str(int(agent["sub_agent"]["number"])): dict(agent["sub_agent"], fixture_agent_id=agent["id"])
                        for agent in history["agents"]
                        if agent.get("sub_agent", {}).get("source") == "design"
                    }
                    assert set(expected) == ({"2", "4", "6"} if mixed else {"2", "4"})
                    message = _parent_message(batch, state, body, raw, prompt, expected_producers=expected)
                elif isinstance(prompt, str) and prompt.startswith("独立只读验收。"):
                    system = "\n".join(m.get("content", "") for m in body["messages"] if m["role"] == "system")
                    root = Path(re.findall(r"Authoritative source to review: ([^\n]+)", system)[-1])
                    criteria = json.loads(prompt.split("\n")[1])
                    terminal_ref = json.loads(prompt.split("\n")[2])
                    repaired = (root / "repair-evidence.txt").exists()
                    results = [m for m in body["messages"] if m["role"] == "tool"]
                    if not results:
                        message = batch.tool_call(
                            "reuse-source-read", "read_file", {"path": str(root / "fixture-input.txt")}
                        )
                        if repaired:
                            message["tool_calls"].append(
                                batch.tool_call(
                                    "reuse-repair-read", "read_file", {"path": str(root / "repair-evidence.txt")}
                                )["tool_calls"][0]
                            )
                    else:
                        assert any("UNTRUSTED_FIXTURE_FILE" in m["content"] for m in results)
                        assert not any(m["content"].startswith("Error:") for m in results)
                        failing = criteria[0]["id"] == "A" and not repaired
                        if failing:
                            assert "original_config" not in state
                            terminal = json.loads(Path(terminal_ref["path"]).read_text(encoding="utf8"))
                            registration = json.loads(Path(terminal["registration"]["path"]).read_text(encoding="utf8"))
                            dispatch = json.loads(
                                Path(registration["dispatch_request"]["path"]).read_text(encoding="utf8")
                            )
                            state["original_config"] = reference(dispatch["config"])
                            state["original_terminal"] = reference(terminal_ref["path"])
                            state["original_registration"] = reference(terminal["registration"]["path"])
                            # A real source-file addition after the initial preparation.
                            # It cannot be reconciled by rewriting the old ledger.
                            workspace = Path(batch.os.environ["REPAIR_REUSE_WORKSPACE"])
                            uid = workspace / "samples/project/recovery-probe.gd.uid"
                            uid.write_text("uid://fixture951recovery\n", encoding="utf8", newline="\n")
                            state["uid"] = reference(uid)
                            if fault == "missing-config":
                                config_file = Path(dispatch["config"])
                                backup = workspace.parent / "withheld-repair-config.json"
                                config_file.rename(backup)
                                state["withheld_config"] = reference(backup)
                        if repaired:
                            assert any("actual repaired execution" in m["content"] for m in results)
                        verdict = {
                            "verdict": "unknown" if failing else "pass",
                            "reason": "Execution evidence remains missing"
                            if failing
                            else "Actual independent source reads succeeded",
                            "criteria": [
                                dict(
                                    id=c["id"],
                                    met=None if failing else True,
                                    evidence=["fixture-input.txt"] + (["repair-evidence.txt"] if repaired else []),
                                    **(
                                        {
                                            "missing_evidence": "Run assigned verification and persist repair-evidence.txt"
                                        }
                                        if failing
                                        else {}
                                    ),
                                )
                                for c in criteria
                            ],
                        }
                        if failing:
                            verdict["unknown_kind"] = "missing_execution_evidence"
                        state["reviews"].append({
                            "criterion": criteria[0]["id"],
                            "repaired": repaired,
                            "verdict": verdict,
                            "terminal": terminal_ref,
                        })
                        message = {"role": "assistant", "content": json.dumps(verdict)}
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

    batch.ThreadingHTTPServer = RepairServer


def collect(folder, observed):
    state = observed["repair_reuse"]
    state["preserved"] = {
        key: Path(state[key]["path"]).is_file() and reference(state[key]["path"]) == state[key]
        for key in ("original_config", "original_terminal", "original_registration", "uid")
        if key in state
    }
    history = json.loads(
        (folder / "original/samples/project/.godot/editor/ai_chat_history.json").read_text(encoding="utf8")
    )
    state["children"] = [a["sub_agent"] for a in history["agents"] if a.get("sub_agent", {}).get("source") == "design"]
    boundary = folder / "original/samples/project/.godot/editor/mixed-ready-951.json"
    if state.get("mixed", False) and boundary.exists():
        captured = json.loads(boundary.read_text(encoding="utf8"))
        children = {
            int(agent["sub_agent"]["number"]): agent["sub_agent"]
            for agent in captured["agents"]
            if agent.get("sub_agent", {}).get("source") == "design"
        }
        assert children[2]["state"] == "waiting" and children[2]["repair_of"]
        assert children[4]["acceptance"] and children[6]["state"] == "waiting"
        observed["mixed_ready_boundary"] = children
        observed["mixed_ready_history_reference"] = reference(boundary)
    race = folder / "preparation-control/config-race-result.json"
    if race.exists():
        state["config_race"] = json.loads(race.read_text(encoding="utf8"))
    state["accepted"] = []
    for agent in history["agents"]:
        child = agent.get("sub_agent", {})
        if child.get("source") == "design" and child.get("acceptance"):
            accepted = child["acceptance"]
            actual = reference(accepted["evidence"])
            assert actual["sha256"] == accepted["decision_file_sha256"]
            envelope = json.loads(Path(accepted["evidence"]).read_text(encoding="utf8"))
            assert (
                hashlib.sha256(envelope["payload"].encode()).hexdigest()
                == envelope["sha256"]
                == accepted["decision_sha256"]
            )
            decision = json.loads(envelope["payload"])
            assert decision["verdict"] == "pass" and decision["criteria"]
            assert all(
                c["evidence"] and all(e["path"] and len(e["sha256"]) == 64 for e in c["evidence"])
                for c in decision["criteria"]
            )
            state["accepted"].append({"producer_id": agent["id"], "acceptance": accepted, "decision": decision})
    state["dispatches"] = []
    for file in sorted((folder / "original/data-collection/outbox").glob("parallel-*.json")):
        if file.name.endswith(".result.json"):
            continue
        value = json.loads(file.read_text(encoding="utf8"))
        if "workers" in value and "config" in value:
            state["dispatches"].append(value)
    state["setup_requests"] = len(list((folder / "original/data-collection/outbox").glob("setup-*.json")))
    state["setup_requests"] -= len(list((folder / "original/data-collection/outbox").glob("setup-*.result.json")))


def valid(observed):
    state = observed["repair_reuse"]
    starts = [e for e in observed.get("events", []) if e["phase"] == "start"]
    finishes = [e for e in observed.get("events", []) if e["phase"] == "finish"]
    dispatches = state["dispatches"]
    if state["fault"]:
        preserved = {key: value for key, value in state["preserved"].items() if key != "original_config"}
        safe = (
            preserved == dict.fromkeys(("original_terminal", "original_registration", "uid"), True)
            and state["preserved"]["original_config"] is False
            and state["setup_requests"] == 1
            and len(starts) == len(finishes) == 2
            and len(state["reviews"]) == 2
        )
        if state["fault"] == "missing-config":
            return (
                safe
                and len(dispatches) == 1
                and any(
                    c.get("production_preparation", {}).get("reason") == "repair_configuration_or_predecessor_changed"
                    for c in state["children"]
                )
                and state["withheld_config"]["sha256"] == state["original_config"]["sha256"]
            )
        race = state.get("config_race", {})
        return (
            safe
            and len(dispatches) == 2
            and race.get("exit") == 1
            and "Dispatch configuration changed" in race.get("stderr", "")
            and race["config_before"] == state["original_config"]["sha256"]
            and race["config_before"] != race["config_after"]
            and any(c["state"] == "interrupted" and c.get("repair_of") for c in state["children"])
        )
    return (
        state["preserved"]
        == dict.fromkeys(("original_config", "original_terminal", "original_registration", "uid"), True)
        and state["setup_requests"] == 1
        and len(starts) == len(finishes) == (4 if state["mixed"] else 3)
        and len(state["reviews"]) == (4 if state["mixed"] else 3)
        and len([r for r in state["reviews"] if r["criterion"] == "A" and r["repaired"]]) == 1
        and len(state["accepted"]) == (3 if state["mixed"] else 2)
        and (not state["mixed"] or bool(observed.get("mixed_ready_boundary")))
        and len(dispatches) == (3 if state["mixed"] else 2)
        and all(
            not any(w.get("repairOf") for w in d["workers"]) or all(w.get("repairOf") for w in d["workers"])
            for d in dispatches
        )
        and all(d["configSha256"] == state["original_config"]["sha256"] for d in dispatches)
        and len([w for d in dispatches for w in d["workers"] if w.get("repairOf")]) == 1
    )


CONTROL = """
func _wait_repair_reuse_951():
\tvar deadline := Time.get_ticks_msec() + 180000
\twhile Time.get_ticks_msec() < deadline:
\t\tvar history = JSON.parse_string(FileAccess.get_file_as_string("res://.godot/editor/ai_chat_history.json"))
\t\tvar accepted := 0
\t\tvar blocked := false
\t\tvar mixed := OS.get_environment("NATIVE_REPAIR_REUSE_MIXED") == "1"
\t\tvar mixed_blocked := false
\t\tvar fault := OS.get_environment("NATIVE_REPAIR_REUSE_FAULT")
\t\tif history is Dictionary:
\t\t\tvar ready_children := {}
\t\t\tfor agent in history.get("agents", []):
\t\t\t\tvar child: Dictionary = agent.get("sub_agent", {})
\t\t\t\tif child.get("source", "") == "design":
\t\t\t\t\tready_children[int(child.number)] = child
\t\t\t\tif mixed and child.get("production_preparation", {}).get("reason", "") == "repair_configuration_or_predecessor_changed":
\t\t\t\t\tmixed_blocked = true
\t\t\t\tif fault == "missing-config" and child.get("production_preparation", {}).get("reason", "") == "repair_configuration_or_predecessor_changed":
\t\t\t\t\tblocked = true
\t\t\t\tif fault == "config-race" and child.get("state", "") == "interrupted" and child.has("repair_of") and FileAccess.file_exists(OS.get_environment("NATIVE_PREPARATION_CONTROL").path_join("config-race-result.json")):
\t\t\t\t\tblocked = true
\t\t\t\tif child.get("source", "") == "design" and child.has("acceptance"):
\t\t\t\t\taccepted += 1
\t\t\tif mixed and ready_children.get(2, {}).get("state", "") == "waiting" and ready_children.get(2, {}).has("repair_of") and ready_children.get(4, {}).has("acceptance") and ready_children.get(6, {}).get("state", "") == "waiting" and not FileAccess.file_exists("res://.godot/editor/mixed-ready-951.json"):
\t\t\t\tvar boundary := FileAccess.open("res://.godot/editor/mixed-ready-951.json", FileAccess.WRITE)
\t\t\t\tif not _check(boundary != null, "Cannot preserve actual mixed ready boundary"):
\t\t\t\t\treturn
\t\t\t\tboundary.store_string(JSON.stringify(history))
\t\t\t\tboundary.close()
\t\tvar can_continue: bool = not dock.find_child("SpawnWorkOrderAgents", true, false).disabled
\t\tif mixed_blocked and can_continue and not dock.get_meta("history_saving", false):
\t\t\t_check(false, "Mixed ready repair and ordinary producer blocked the whole batch")
\t\t\treturn
\t\tvar parent_checked: bool = "PREPARED_JOB_PARENT_RECEIPTS_CHECKED" in _text()
\t\tif ((accepted == (3 if mixed else 2) and parent_checked) or blocked) and can_continue and not dock.get_meta("history_saving", false):
\t\t\treturn
\t\tawait process_frame
\t_check(false, "Reused repair never reached actual persisted independent acceptance")
"""
