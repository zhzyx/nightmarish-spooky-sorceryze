"""Warm/cold recovery of an unstarted job from an actual original native setup.

Only model transport and isolated filesystem faults are controlled. Native
review receipts, repair eligibility, history, dependency proofs and runner
registrations are never supplied by this fixture.
"""

import base64
import hashlib
import io
import json
import re
import time
import uuid
from pathlib import Path

import native_preparation_repair as repair


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf8"))


def _ref(path):
    raw = Path(path).read_bytes()
    return {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def _embedded(raw):
    return {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "base64": base64.b64encode(raw).decode("ascii"),
    }


def _native_parent_pair(messages, summary_sha256):
    anchors = [
        index
        for index, entry in enumerate(messages)
        if entry.get("role") == "user"
        and isinstance(entry.get("content"), str)
        and hashlib.sha256(entry["content"].encode("utf8")).hexdigest() == summary_sha256
    ]
    assert len(anchors) == 1, "No unique current parent summary anchor"
    calls = []
    results = []
    for index, entry in enumerate(messages[anchors[0] + 1 :]):
        if entry.get("role") == "assistant":
            calls.extend((index, call) for call in entry.get("tool_calls", []))
        if entry.get("role") == "tool":
            results.append((index, entry))
    assert len(calls) == len(results) == 1 and calls[0][0] < results[0][0], (
        "No unique ordered native list call/result pair"
    )
    call, result = calls[0][1], results[0][1]
    assert isinstance(call.get("id"), str) and call["id"] and call["id"] == result.get("tool_call_id"), (
        "Native list call/result identity differs"
    )
    function = call["function"]
    arguments = function["arguments"]
    if isinstance(arguments, str):
        arguments = json.loads(arguments)
    assert function["name"] == "integrate_production_result" and arguments == {"action": "list"}
    return call, result


def _parent_message(batch, state, body, raw, prompt, expected_producers=None):
    """Consume only the real parent's read-only list response for our issued call."""
    # The parent runner serializes observed even on failure and after Temp cleanup.
    state.setdefault("parent_http_rounds", []).append(_embedded(raw))
    folder = Path(batch.os.environ["REPAIR_REUSE_WORKSPACE"]).parent / "prepared-job-recovery"
    folder.mkdir(exist_ok=True)
    if "parent_list_call" not in state:
        summary = folder / "parent-summary.txt"
        with summary.open("xb") as stream:
            stream.write(prompt.encode("utf8"))
        state["parent_summary"] = _ref(summary)
        state["parent_summary_bytes"] = _embedded(prompt.encode("utf8"))
        message = batch.tool_call(
            "prepared-parent-list-" + uuid.uuid4().hex, "integrate_production_result", {"action": "list"}
        )
        state["parent_list_call"] = message["tool_calls"][0]
        return message
    # Preserve the received round before checking its semantics, including failures.
    received = folder / "parent-list-tool-round.json"
    with received.open("xb") as stream:
        stream.write(raw)
    state["parent_tool_round"] = _ref(received)
    # CLI transport maps the fixture proposal to actions; the native adapter owns
    # its real call ID (for example cli_0). Bind that ID within this exact summary.
    call, result = _native_parent_pair(body["messages"], state["parent_summary"]["sha256"])
    state["parent_id_boundary"] = {"fixture_proposal_id": state["parent_list_call"]["id"], "native_call_id": call["id"]}
    state["parent_pair"] = {"call": call, "result": result}
    answer = json.loads(result["content"])
    state["parent_listing"] = answer
    assert answer.get("ok") is True
    producers = answer["producers"]
    expected = state["snapshots"]["blocked"]["children"] if expected_producers is None else expected_producers
    expected_orders = {int(number) for number in expected}
    assert expected_orders in ({2, 4}, {2, 4, 6}) and len(expected_orders) == len(expected)
    assert len({child["fixture_agent_id"] for child in expected.values()}) == len(expected)
    assert len(producers) == len(expected) and {int(p["work_order"]) for p in producers} == expected_orders
    assert all(
        p["live_independent_acceptance"] is True
        and p["producer_id"] == expected[str(int(p["work_order"]))]["fixture_agent_id"]
        for p in producers
    ), "Parent list did not expose the original producers' live independent acceptance"
    return {"role": "assistant", "content": "PREPARED_JOB_PARENT_RECEIPTS_CHECKED"}


def install(batch, observed, *, foreign_job=False, warm=False, legacy=False):
    assert not legacy or (not warm and not foreign_job)
    previous = batch.ThreadingHTTPServer
    state = observed["prepared_job_recovery"] = {
        "foreign_job": foreign_job,
        "warm": warm,
        "legacy": legacy,
        "reviews": [],
        "snapshots": {},
        "scope": "Controlled reviewer transport; actual native setup, public Continue, repair and dependency execution",
    }

    class PreparedJobServer(previous):
        def __init__(self, address, handler):
            super().__init__(address, handler)
            original = handler.do_POST

            def post(instance):
                raw = instance.rfile.read(int(instance.headers["Content-Length"]))
                body = json.loads(raw)
                prompt = next((m.get("content", "") for m in reversed(body["messages"]) if m["role"] == "user"), "")
                message = None
                if isinstance(prompt, str) and prompt.startswith("独立只读验收。"):
                    system = "\n".join(m.get("content", "") for m in body["messages"] if m["role"] == "system")
                    root = Path(re.findall(r"Authoritative source to review: ([^\n]+)", system)[-1])
                    criteria = json.loads(prompt.split("\n")[1])
                    terminal_ref = json.loads(prompt.split("\n")[2])
                    repaired = (root / "repair-evidence.txt").exists()
                    results = [m for m in body["messages"] if m["role"] == "tool"]
                    if not results:
                        message = batch.tool_call(
                            "prepared-source-read", "read_file", {"path": str(root / "fixture-input.txt")}
                        )
                        if repaired:
                            message["tool_calls"].extend(
                                batch.tool_call(
                                    "prepared-repair-read", "read_file", {"path": str(root / "repair-evidence.txt")}
                                )["tool_calls"]
                            )
                    else:
                        assert any("UNTRUSTED_FIXTURE_FILE" in m["content"] for m in results)
                        assert not any(m["content"].startswith("Error:") for m in results)
                        failing = criteria[0]["id"] in {"A", "C"} and not repaired
                        if failing and criteria[0]["id"] == "A":
                            assert "original_config" not in state, "Original A review repeated"
                            terminal = _read(terminal_ref["path"])
                            registration = _read(terminal["registration"]["path"])
                            dispatch = _read(registration["dispatch_request"]["path"])
                            config = Path(dispatch["config"])
                            workspace = Path(batch.os.environ["REPAIR_REUSE_WORKSPACE"])
                            assert config.resolve().is_relative_to(workspace.resolve())
                            state["original_config"] = _ref(config)
                            state["original_terminal"] = _ref(terminal_ref["path"])
                            state["original_registration"] = _ref(terminal["registration"]["path"])
                            state["original_dispatch"] = _ref(registration["dispatch_request"]["path"])
                            state["initial_config"] = _read(config)
                            ledger = config.parent / "receipt.json"
                            state["original_setup_receipt"] = _ref(ledger)
                            requests = [
                                p
                                for p in (workspace / "data-collection/outbox").glob("setup-*.json")
                                if not p.name.endswith(".result.json")
                            ]
                            assert len(requests) == 1
                            state["original_setup_request"] = _ref(requests[0])
                            state["original_setup_result"] = _ref(Path(str(requests[0]) + ".result.json"))
                            assert set(_read(requests[0])["orders"]) == {2, 4, 6}
                            assert {int(job["order"]) for job in state["initial_config"]["jobs"]} == {2, 4, 6}
                            uid = workspace / "samples/project/prepared-job-recovery.gd.uid"
                            assert not uid.exists(), "Fault must add a new isolated UID"
                            state["uid_before_exists"] = False
                            with uid.open("x", encoding="utf8", newline="\n") as stream:
                                stream.write("uid://fixture951preparedjob\n")
                            state["uid"] = _ref(uid)
                            assert state["initial_config"]["capacity"] == 2
                            control = workspace.parent / "prepared-job-control"
                            request = control / "capacity-change-request.json"
                            temporary = control / "capacity-change-request.tmp"
                            assert not request.exists()
                            with temporary.open("x", encoding="utf8") as stream:
                                json.dump({"capacity": 3, "config_sha256": state["original_config"]["sha256"]}, stream)
                            temporary.rename(request)
                            state["capacity_request"] = _ref(request)
                            ack = control / "capacity-changed.json"
                            deadline = time.monotonic() + 30
                            while not ack.exists() and time.monotonic() < deadline:
                                time.sleep(0.02)
                            assert ack.is_file(), "Public capacity control did not acknowledge fault injection"
                            change = _read(ack)
                            assert change["request_sha256"] == state["capacity_request"]["sha256"]
                            assert change["before"] == "2" and change["after"] == "3"
                            state["capacity_change"] = {"reference": _ref(ack), "readback": change}
                            assert _ref(config) == state["original_config"], "Fault must not alter native review inputs"
                        if repaired:
                            assert any("actual repaired execution" in m["content"] for m in results)
                        verdict = {
                            "verdict": "unknown" if failing else "pass",
                            "reason": "Assigned execution evidence remains missing"
                            if failing
                            else "Actual source reads succeeded",
                            "criteria": [
                                dict(
                                    id=c["id"],
                                    met=None if failing else True,
                                    evidence=["fixture-input.txt"] + (["repair-evidence.txt"] if repaired else []),
                                    **(
                                        {
                                            "missing_evidence": "Persist repair-evidence.txt from the assigned verification"
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
                elif isinstance(prompt, str) and "current_host_design_batch" in prompt:
                    message = _parent_message(batch, state, body, raw, prompt)
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

    batch.ThreadingHTTPServer = PreparedJobServer


def checkpoint(folder, observed, name):
    """Copy an actual persisted history, without changing the editor's history."""
    assert name in {"blocked", "cold", "warm", "final"}
    state = observed["prepared_job_recovery"]
    assert name not in state["snapshots"]
    source = folder / "original/samples/project/.godot/editor/ai_chat_history.json"
    raw = source.read_bytes()
    history = json.loads(raw)
    agents = [a for a in history["agents"] if a.get("sub_agent", {}).get("source") == "design"]
    assert len(agents) == 3
    children = {str(int(a["sub_agent"]["number"])): dict(a["sub_agent"], fixture_agent_id=a["id"]) for a in agents}
    assert set(children) == {"2", "4", "6"}, "Expected only the original A/B/C jobs"
    target = folder / "prepared-job-recovery" / (name + "-history.json")
    target.parent.mkdir(exist_ok=True)
    with target.open("xb") as stream:
        stream.write(raw)
    snapshot = {"history": _ref(target), "children": children}
    state["snapshots"][name] = snapshot
    return snapshot


def prepare_restart(folder, observed, first_exit):
    """Called only after the first isolated editor naturally exits successfully."""
    assert first_exit == 0
    state = observed["prepared_job_recovery"]
    assert not state["warm"]
    state["first_exit"] = first_exit
    _check_configuration(folder, observed)
    if state["legacy"]:
        state["legacy_setup_before"] = _legacy_setup_records(folder, state)
        assert len(state["legacy_setup_before"]) >= 2
        assert any(
            "Preparation baseline changed" in record["result"]["error"] for record in state["legacy_setup_before"]
        )
        control = folder / "prepared-job-control"
        acknowledgement = _read(control / "legacy-quiescence-checked")
        assert (
            acknowledgement.get("ok") is True
            and acknowledgement.get("scope") == "fixture_setup_processes"
            and acknowledgement.get("pending") == []
        )
        state["legacy_process_observation"] = {
            "reference": _ref(control / "legacy-quiescence-checked"),
            "source": "Parent fixture monitor; not inferred from Stop or absent leases",
            "acknowledgement": acknowledgement,
        }
        stopped = _read(control / "legacy-stop.json")
        assert stopped.get("stop_pressed") is True
        before = stopped["before"]
        after = state["snapshots"]["blocked"]["children"]
        assert before["2"]["repair_of"] == after["2"]["repair_of"]
        assert before["2"]["acceptance_repairs"] == after["2"]["acceptance_repairs"] == 1
        assert before["4"]["terminal_receipt"] == after["4"]["terminal_receipt"]
        state["legacy_stop"] = _ref(control / "legacy-stop.json")


def prepare_resume(folder, observed):
    """Check this fixture's original config at its actual idle preparation gate."""
    state = observed["prepared_job_recovery"]
    assert state["warm"]
    ready = _read(folder / "prepared-job-control/warm-ready")
    assert ready["continue_enabled"] is True and ready["history_saving"] is False
    _check_configuration(folder, observed, ready["children"])
    checkpoint(folder, observed, "warm")


def _check_configuration(folder, observed, expected_children=None):
    state = observed["prepared_job_recovery"]
    snapshot = checkpoint(folder, observed, "blocked")
    if expected_children is not None:
        assert expected_children == {
            number: {key: value for key, value in child.items() if key != "fixture_agent_id"}
            for number, child in snapshot["children"].items()
        }
    a, b, c = (snapshot["children"][str(n)] for n in (2, 4, 6))
    assert a.get("repair_of")
    if state["legacy"]:
        assert not any(child.get("production_preparation") for child in (a, b, c))
    else:
        assert a.get("production_preparation", {}).get("state") == "blocked"
        assert a["production_preparation"]["reason"] == "repair_runtime_selection_changed"
        assert a["production_preparation"]["launch_state"] == "not_started"
    assert b.get("acceptance") and not c.get("parallel_assignment") and not c.get("terminal_receipt")
    assert c["state"] in {"waiting", "interrupted"}
    config = Path(state["original_config"]["path"])
    assert _ref(config) == state["original_config"]
    state["config_at_gate"] = _ref(config)
    if state["foreign_job"]:
        changed = _read(config)
        jobs = [job for job in changed["jobs"] if int(job["order"]) == 6]
        assert len(jobs) == 1
        jobs[0]["order"] = 6006
        config.write_text(json.dumps(changed), encoding="utf8")
        state["changed_config"] = _ref(config)
        assert state["changed_config"]["sha256"] != state["original_config"]["sha256"]
        state["negative_scope"] = "Isolated config/job drift; no new business job or history identity was created"


def _legacy_setup_records(folder, state):
    initial = _read(state["original_setup_request"]["path"])
    paths = sorted(
        p
        for p in (folder / "original/data-collection/outbox").glob("setup-*.json")
        if not p.name.endswith(".result.json")
    )
    assert 2 <= len(paths) <= 16, "Legacy setup observation exceeded its bounded request scope"
    records = []
    for path in paths:
        request = _read(path)
        assert all(
            request[key] == initial[key] for key in ("workspace", "issue", "requestId", "designSha256", "authorityRef")
        )
        result_path = Path(str(path) + ".result.json")
        result = _read(result_path)  # Missing/partial/unknown outcome is not a terminal.
        assert result.get("state") in {"ready", "blocked"}
        records.append({
            "request": _ref(path),
            "result_reference": _ref(result_path),
            "result": {"state": result["state"], "error": result.get("error", "")},
        })
    assert len([record for record in records if record["result"]["state"] == "ready"]) == 1
    return records


def collect(folder, observed):
    state = observed["prepared_job_recovery"]
    checkpoint(folder, observed, "final")
    # Reuse only receipt verification/collection, not its UID-mutating transport.
    prior = observed.get("repair_reuse")
    observed["repair_reuse"] = state
    try:
        repair.collect(folder, observed)
    finally:
        if prior is None:
            del observed["repair_reuse"]
        else:
            observed["repair_reuse"] = prior
    state["preserved"] = {
        key: Path(state[key]["path"]).is_file() and _ref(state[key]["path"]) == state[key]
        for key in ("original_config", "original_terminal", "original_registration", "uid")
    }
    state["setup_receipt_preserved"] = _ref(state["original_setup_receipt"]["path"]) == state["original_setup_receipt"]
    state["original_dispatch_preserved"] = _ref(state["original_dispatch"]["path"]) == state["original_dispatch"]
    state["capacity_observations_preserved"] = (
        _ref(state["capacity_request"]["path"]) == state["capacity_request"]
        and _ref(state["capacity_change"]["reference"]["path"]) == state["capacity_change"]["reference"]
    )
    state["setup_sources_preserved"] = all(
        _ref(state[key]["path"]) == state[key] for key in ("original_setup_request", "original_setup_result")
    )
    state["control_result"] = _read(folder / "prepared-job-control/continue-result.json")
    if state["warm"]:
        readonly_path = folder / "prepared-job-control/readonly-continue-result.json"
        state["readonly_continue"] = {"reference": _ref(readonly_path), "result": _read(readonly_path)}
    state["setup_files"] = [
        _ref(path) for path in sorted((folder / "original/data-collection/outbox").glob("setup-*.json"))
    ]
    if state["legacy"]:
        state["legacy_setup_after"] = _legacy_setup_records(folder, state)


def valid(observed):
    state = observed["prepared_job_recovery"]
    snapshots = state.get("snapshots", {})
    middle = "warm" if state["warm"] else "cold"
    if set(snapshots) != {"blocked", middle, "final"}:
        return False
    blocked, resumed, final = (snapshots[name]["children"] for name in ("blocked", middle, "final"))
    stable = ("fixture_agent_id", "parent", "number", "work_order", "request_id", "scope_sha256", "design_approval")
    if not all(
        all(key in child for key in stable)
        and all(_integer(child[key], 0) for key in ("fixture_agent_id", "parent"))
        and all(_integer(child[key], 1) for key in ("number", "work_order"))
        and all(isinstance(child[key], str) and child[key] for key in ("request_id", "scope_sha256"))
        and isinstance(child["design_approval"], dict)
        and child["design_approval"]
        for child in blocked.values()
    ):
        return False
    if not all(
        all(stage[n].get(k) == blocked[n].get(k) for k in stable) for stage in (resumed, final) for n in blocked
    ):
        return False
    exit_ok = (
        state.get("single_exit") == 0
        if state["warm"]
        else state.get("first_exit") == 0 and state.get("second_exit") == 0
    )
    if not (
        resumed["6"].get("state") == ("waiting" if state["warm"] else "interrupted")
        and not resumed["6"].get("parallel_assignment")
        and not resumed["6"].get("terminal_receipt")
        and resumed["2"].get("repair_of") == blocked["2"].get("repair_of")
        and resumed["4"].get("acceptance") == blocked["4"].get("acceptance")
        and exit_ok
        and state["setup_requests"] == (len(state["legacy_setup_before"]) if state["legacy"] else 1)
        and state["setup_receipt_preserved"]
        and state["original_dispatch_preserved"]
        and state["capacity_observations_preserved"]
        and state["capacity_change"]["readback"]["before"] == "2"
        and state["capacity_change"]["readback"]["after"] == "3"
        and state["setup_sources_preserved"]
        and state["control_result"].get("continue_pressed") is True
        and state["control_result"].get("continue_enabled") is True
        and state["control_result"].get("capacity_before_continue") == "2"
    ):
        return False
    if state["legacy"] and not (
        state["legacy_setup_before"] == state["legacy_setup_after"]
        and _ref(state["legacy_process_observation"]["reference"]["path"])
        == state["legacy_process_observation"]["reference"]
        and _ref(state["legacy_stop"]["path"]) == state["legacy_stop"]
        and not any("production_preparation" in child for child in blocked.values())
    ):
        return False
    if state["warm"]:
        readonly = state.get("readonly_continue", {})
        result = readonly.get("result", {})
        before, after = result.get("before", {}), result.get("after", {})
        if (
            not readonly.get("reference", {}).get("path")
            or _ref(readonly["reference"]["path"]) != readonly["reference"]
            or _read(readonly["reference"]["path"]) != result
            or result.get("consultation_enabled_readback") is not True
            or result.get("consultation_disabled_readback") is not True
            or result.get("continue_pressed") is not True
            or before.get("observation", {}).get("continue_enabled") is not True
            or before.get("observation", {}).get("capacity") != "2"
            or before.get("history") != after.get("history")
            or before.get("dispatch_files") != after.get("dispatch_files")
            or before.get("observation", {}).get("children") != after.get("observation", {}).get("children")
            or before.get("history", {}).get("active_agent") != blocked["2"]["parent"]
            or not before.get("observation", {}).get("children", {}).get("4", {}).get("acceptance")
            or before.get("observation", {}).get("history_sha256") != after.get("observation", {}).get("history_sha256")
        ):
            return False
    starts = [event for event in observed.get("events", []) if event["phase"] == "start"]
    finishes = [event for event in observed.get("events", []) if event["phase"] == "finish"]
    dispatches = state["dispatches"]
    if state["foreign_job"]:
        return (
            len(starts) == len(finishes) == 2
            and len(dispatches) == 1
            and len(state["accepted"]) == 1
            and len(state["reviews"]) == 2
            and not final["6"].get("parallel_assignment")
            and not final["6"].get("terminal_receipt")
            and final["2"].get("repair_of") == blocked["2"].get("repair_of")
            and state["preserved"]["original_config"] is False
            and all(value for key, value in state["preserved"].items() if key != "original_config")
        )
    candidate_dispatches = dispatches
    if state["legacy"]:
        original = state["original_dispatch"]
        config = state["original_config"]
        if _ref(original["path"]) != original or _ref(config["path"]) != config:
            return False
        original_dispatch = _read(original["path"])
        legacy_native = observed.get("legacy_native", {})
        if (
            sum(dispatch == original_dispatch for dispatch in dispatches) != 1
            or "configSha256" in original_dispatch
            or original_dispatch.get("config") != config["path"]
            or original_dispatch.get("editorRuntime", {}).get("sha256") != legacy_native.get("old_sha256")
            or not legacy_native.get("old_sha256")
            or not legacy_native.get("candidate_sha256")
            or legacy_native["old_sha256"] == legacy_native["candidate_sha256"]
        ):
            return False
        original_workers = original_dispatch.get("workers", [])
        if len(original_workers) != 2 or {worker.get("order") for worker in original_workers} != {2, 4}:
            return False
        for worker in original_workers:
            child = blocked[str(int(worker["order"]))]
            assignment = child.get("parallel_assignment", {})
            if (
                assignment.get("config_path") != config["path"]
                or assignment.get("config_sha256") != config["sha256"]
                or assignment.get("order") != worker["order"]
                or child.get("fixture_agent_id") != worker.get("id")
                or child.get("terminal_receipt", {}).get("batch") != original_dispatch.get("batchId")
                or worker.get("repairOf")
                or worker.get("preparedJob")
            ):
                return False
        candidate_dispatches = [dispatch for dispatch in dispatches if dispatch != original_dispatch]
        if not all(
            dispatch.get("editorRuntime", {}).get("sha256") == legacy_native["candidate_sha256"]
            for dispatch in candidate_dispatches
        ):
            return False
    if not (
        len(starts) == len(finishes) == 5
        and len(dispatches) == 4
        and len(state["accepted"]) == 3
        and len(state["reviews"]) == (5 if state["warm"] else 6)
        and len([r for r in state["reviews"] if r["criterion"] == "A" and r["repaired"]]) == 1
        and len([r for r in state["reviews"] if r["criterion"] == "C" and r["repaired"]]) == 1
        and len([r for r in state["reviews"] if r["criterion"] == "B"]) == (1 if state["warm"] else 2)
        and all(state["preserved"].values())
        and all(d.get("configSha256") == state["original_config"]["sha256"] for d in candidate_dispatches)
        and final["4"].get("terminal_receipt") == blocked["4"].get("terminal_receipt")
        and (
            final["4"].get("acceptance") == blocked["4"].get("acceptance")
            if state["warm"]
            else final["4"].get("acceptance") != blocked["4"].get("acceptance")
            and blocked["4"]["acceptance"] in final["4"].get("acceptance_history", [])
        )
    ):
        return False
    parent_listing = state.get("parent_listing", {})
    pair = state.get("parent_pair", {})
    if not (
        parent_listing.get("ok") is True
        and len(parent_listing.get("producers", [])) == 3
        and pair.get("call", {}).get("id")
        == state.get("parent_id_boundary", {}).get("native_call_id")
        == pair.get("result", {}).get("tool_call_id")
        and _ref(state["parent_summary"]["path"]) == state["parent_summary"]
        and _ref(state["parent_tool_round"]["path"]) == state["parent_tool_round"]
        and state["control_result"].get("parent_marker_seen") is True
    ):
        return False
    if len(state.get("parent_http_rounds", [])) != 2:
        return False
    for record in state["parent_http_rounds"] + [state["parent_summary_bytes"]]:
        if _embedded(base64.b64decode(record["base64"], validate=True)) != record:
            return False
    if (
        state["parent_http_rounds"][1]["sha256"] != state["parent_tool_round"]["sha256"]
        or state["parent_summary_bytes"]["sha256"] != state["parent_summary"]["sha256"]
    ):
        return False
    if not all(
        p.get("live_independent_acceptance") is True
        and str(int(p["work_order"])) in final
        and p.get("producer_id") == final[str(int(p["work_order"]))]["fixture_agent_id"]
        for p in parent_listing["producers"]
    ):
        return False
    workers = [worker for dispatch in dispatches for worker in dispatch["workers"]]
    c_workers = [worker for worker in workers if int(worker["order"]) == 6]
    repairs = [worker for worker in workers if worker.get("repairOf")]
    if len(c_workers) != 2 or len(repairs) != 2 or {int(worker["order"]) for worker in repairs} != {2, 6}:
        return False
    original_c = [worker for worker in c_workers if not worker.get("repairOf")]
    repaired_c = [worker for worker in c_workers if worker.get("repairOf")]
    if (
        len(original_c) != 1
        or len(repaired_c) != 1
        or not original_c[0].get("preparedJob")
        or "preparedJob" in repaired_c[0]
    ):
        return False
    history = final["6"].get("prepared_job_history", [])
    if (
        "prepared_job_reference" in final["6"]
        or len(history) != 1
        or history[0].get("reference") != original_c[0]["preparedJob"]
    ):
        return False
    first_c = history[0].get("terminal_receipt", {})
    if (
        first_c.get("available") is not True
        or not first_c.get("path")
        or _ref(first_c["path"])["sha256"] != first_c.get("file_sha256")
    ):
        return False
    first_c_record = _read(first_c["path"])
    if (
        not first_c.get("execution_id")
        or not first_c.get("worker_id")
        or first_c_record.get("execution_id") != first_c["execution_id"]
        or first_c_record.get("worker_id") != first_c["worker_id"]
        or first_c_record.get("state") != "review"
        or first_c_record.get("transport_completed") is not True
        or first_c_record.get("exit_code") != 0
        or first_c_record.get("cancel_requested") is not False
    ):
        return False
    missing_c = [r for r in state["reviews"] if r["criterion"] == "C" and not r["repaired"]]
    if (
        len(missing_c) != 1
        or missing_c[0]["terminal"] != first_c
        or missing_c[0]["verdict"].get("unknown_kind") != "missing_execution_evidence"
    ):
        return False
    # Native history keeps the full terminal identity; repairOf carries its
    # exact content-addressed reference plus the separate predecessor execution.
    first_c_reference = {"path": first_c["path"], "sha256": first_c["file_sha256"]}
    if (
        repaired_c[0]["repairOf"].get("terminal_receipt") != first_c_reference
        or repaired_c[0]["repairOf"].get("execution_id") != first_c["execution_id"]
        or final["6"].get("terminal_receipt") == first_c
    ):
        return False
    for worker in c_workers:
        dependencies = worker.get("dependency_preflight", [])
        if {int(source["order"]) for source in dependencies} != {2, 4} or len(dependencies) != 2:
            return False
        for source in dependencies:
            upstream = final[str(int(source["order"]))]
            if (
                source["terminal_receipt"] != upstream["terminal_receipt"]
                or source["decision_sha256"] != upstream["acceptance"]["decision_sha256"]
            ):
                return False
            proof = source.get("candidate_check", {})
            if not proof.get("path") or _ref(proof["path"])["sha256"] != proof.get("sha256"):
                return False
    return final["2"]["terminal_receipt"] != blocked["2"]["terminal_receipt"]


def _integer(value, minimum):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value >= minimum and value % 1 == 0


CONTROL = """
func _prepared_job_records_951() -> Dictionary:
\tif dock.get_meta("history_saving", false):
\t\treturn {}
\tvar history = JSON.parse_string(FileAccess.get_file_as_string("res://.godot/editor/ai_chat_history.json"))
\tvar records := {}
\tif history is Dictionary:
\t\tfor agent in history.get("agents", []):
\t\t\tvar child: Dictionary = agent.get("sub_agent", {})
\t\t\tif child.get("source", "") == "design":
\t\t\t\trecords[str(int(child.number))] = child
\treturn records

func _prepared_job_signal_951(control: String, name: String, payload: Dictionary) -> bool:
\tvar temporary := control.path_join(name + ".tmp")
\tvar output := FileAccess.open(temporary, FileAccess.WRITE)
\tif not _check(output != null, "Cannot write prepared job observation"):
\t\treturn false
\toutput.store_string(JSON.stringify(payload))
\toutput.flush()
\toutput.close()
\treturn _check(DirAccess.rename_absolute(temporary, control.path_join(name)) == OK, "Cannot publish prepared job observation")

func _prepared_job_capacity_fault_951(control: String) -> bool:
\tvar request := control.path_join("capacity-change-request.json")
\tif not FileAccess.file_exists(request) or FileAccess.file_exists(control.path_join("capacity-changed.json")):
\t\treturn true
\tvar value = JSON.parse_string(FileAccess.get_file_as_string(request))
\tif not _check(value is Dictionary and value.get("capacity", 0) == 3, "Invalid isolated capacity fault request"):
\t\treturn false
\tvar capacity = dock.get_ai_settings_control().find_child("ProductionCapacity", true, false)
\tif not _check(capacity is LineEdit and capacity.editable and capacity.text == "2", "Public production capacity control unavailable or changed"):
\t\treturn false
\tvar before: String = capacity.text
\tcapacity.text = "3"
\tif not _check(capacity.text == "3", "Capacity fault did not reach the actual public control"):
\t\treturn false
\treturn _prepared_job_signal_951(control, "capacity-changed.json", {"request_sha256": FileAccess.get_sha256(request), "before": before, "after": capacity.text})

func _prepared_job_save_951() -> bool:
\tvar count: int = dock.get_meta("history_save_stats", {}).get("count", 0)
\tvar input = dock.find_child("ChatInput", true, false)
\tif not _check(input != null, "Prepared job draft input missing"):
\t\treturn false
\tinput.text = "Draft only: preserve original prepared jobs " + str(count)
\tinput.text_changed.emit()
\tvar deadline := Time.get_ticks_msec() + 15000
\twhile (int(dock.get_meta("history_save_stats", {}).get("count", 0)) <= count or dock.get_meta("history_saving", false)) and Time.get_ticks_msec() < deadline:
\t\tawait process_frame
\treturn _check(int(dock.get_meta("history_save_stats", {}).get("count", 0)) > count and not dock.get_meta("history_saving", false), "Prepared job history save failed")

func _prepared_job_observation_951(stop, resume) -> Dictionary:
\tvar history_path := "res://.godot/editor/ai_chat_history.json"
\tvar saving: bool = dock.get_meta("history_saving", false)
\tvar history = null
\tvar history_sha256 := ""
\t# FileAccess readers deny Windows replacement. Observe only between writes,
\t# synchronously before the next await can start another history save.
\tif not saving:
\t\thistory = JSON.parse_string(FileAccess.get_file_as_string(history_path))
\t\thistory_sha256 = FileAccess.get_sha256(history_path)
\tvar binding := {}
\tif history is Dictionary:
\t\tbinding["persisted_active_agent"] = history.get("active_agent", -1)
\t\tfor agent in history.get("agents", []):
\t\t\tif agent.get("id", -2) == history.get("active_agent", -1):
\t\t\t\tbinding["persisted_conversation_id"] = agent.get("conversation_id", "")
\tvar capacity = dock.get_ai_settings_control().find_child("ProductionCapacity", true, false)
\treturn {"tick": Time.get_ticks_msec(), "binding": binding, "history_sha256": history_sha256, "history_saving": saving, "history_save_stats": dock.get_meta("history_save_stats", {}), "continue_enabled": not resume.disabled, "stop_disabled": stop.disabled, "capacity": capacity.text if capacity is LineEdit else "missing", "children": _prepared_job_records_951(), "ui_text": _text()}

func _prepared_legacy_workers_951() -> bool:
\tvar records := _prepared_job_records_951()
\tif records.size() != 3 or records.get("6", {}).has("parallel_assignment") or records.get("6", {}).has("terminal_receipt"):
\t\treturn false
\tfor number in ["2", "4"]:
\t\tvar child: Dictionary = records.get(number, {})
\t\tvar receipt: Dictionary = child.get("terminal_receipt", {})
\t\tvar path: String = receipt.get("path", "")
\t\tif not receipt.get("available", false) or path.is_empty() or not FileAccess.file_exists(path) or FileAccess.get_sha256(path) != receipt.get("file_sha256", ""):
\t\t\treturn false
\t\tvar terminal = JSON.parse_string(FileAccess.get_file_as_string(path))
\t\tif not terminal is Dictionary or terminal.get("state", "") != "review" or terminal.get("transport_completed", false) != true or terminal.get("exit_code", -1) != 0 or terminal.get("cancel_requested", true) != false:
\t\t\treturn false
\t\tif terminal.get("execution_id", "") != receipt.get("execution_id", "") or terminal.get("worker_id", "") != receipt.get("worker_id", "") or child.get("parallel_receipt", {}).get("execution_id", "") != terminal.get("execution_id", ""):
\t\t\treturn false
\treturn records.get("2", {}).has("repair_of") and records.get("4", {}).has("acceptance")

func _prepared_legacy_setups_951() -> Dictionary:
\tvar directory: String = dock.get_production_workspace().path_join("data-collection/outbox")
\tvar requests := []
\tvar receipts := {}
\tvar complete := true
\tvar baseline_failed := false
\tfor name in DirAccess.get_files_at(directory):
\t\tif not name.begins_with("setup-") or not name.ends_with(".json") or name.ends_with(".result.json"):
\t\t\tcontinue
\t\trequests.append(name)
\t\tvar result_path := directory.path_join(name + ".result.json")
\t\tif not FileAccess.file_exists(result_path):
\t\t\tcomplete = false
\t\t\tcontinue
\t\tvar value = JSON.parse_string(FileAccess.get_file_as_string(result_path))
\t\tif not value is Dictionary or value.get("state", "") not in ["ready", "blocked"]:
\t\t\tcomplete = false
\t\t\tcontinue
\t\treceipts[name] = {"request_sha256": FileAccess.get_sha256(directory.path_join(name)), "result_sha256": FileAccess.get_sha256(result_path), "state": value.state}
\t\tif value.get("state", "") == "blocked" and "Preparation baseline changed" in str(value.get("error", "")):
\t\t\tbaseline_failed = true
\trequests.sort()
\treturn {"requests": requests, "receipts": receipts, "complete": complete, "baseline_failed": baseline_failed}

func _prepared_job_legacy_stop_951(control: String, stop, resume):
\tvar deadline := Time.get_ticks_msec() + 180000
\tvar records := {}
\tvar setups := {}
\tvar ready := false
\twhile Time.get_ticks_msec() < deadline:
\t\tif not _prepared_job_capacity_fault_951(control):
\t\t\t_finish()
\t\t\treturn
\t\trecords = _prepared_job_records_951()
\t\tsetups = _prepared_legacy_setups_951()
\t\tif not _check(setups.requests.size() <= 16, "Legacy preparation exceeded bounded retry observation"):
\t\t\t_finish()
\t\t\treturn
\t\tready = records.size() == 3 and records.get("2", {}).has("repair_of") and records.get("4", {}).has("acceptance") and setups.requests.size() >= 2 and setups.baseline_failed
\t\tif ready:
\t\t\tbreak
\t\tawait process_frame
\tif not _check(ready and not stop.disabled and not records.get("6", {}).has("parallel_assignment") and not records.get("6", {}).has("terminal_receipt"), "Old native host did not expose its actual pending repair/baseline failure"):
\t\t_finish()
\t\treturn
\tfor child in records.values():
\t\tif not _check(not child.has("production_preparation"), "Legacy fixture unexpectedly contains new preparation metadata"):
\t\t\t_finish()
\t\t\treturn
\tvar before := records.duplicate(true)
\tif not _prepared_job_signal_951(control, "legacy-stop-before.json", _prepared_job_observation_951(stop, resume)):
\t\t_finish()
\t\treturn
\tstop.pressed.emit()
\tif not _prepared_job_signal_951(control, "legacy-stop-immediate.json", {"stop_pressed": true, "before": before, "observation": _prepared_job_observation_951(stop, resume)}):
\t\t_finish()
\t\treturn
\tawait process_frame
\tif not await _prepared_job_save_951():
\t\t_finish()
\t\treturn
\tdeadline = Time.get_ticks_msec() + 90000
\tvar previous_setups := {}
\tvar stable := false
\twhile Time.get_ticks_msec() < deadline:
\t\tsetups = _prepared_legacy_setups_951()
\t\tstable = setups.complete and setups == previous_setups and _prepared_legacy_workers_951() and not dock.get_meta("history_saving", false)
\t\tif stable:
\t\t\tbreak
\t\tprevious_setups = setups.duplicate(true)
\t\tawait process_frame
\tif not _check(stable and setups.requests.size() >= 2 and setups.requests.size() <= 16 and setups.baseline_failed, "Old setup has a missing result or in-flight native work; no successful restart allowed"):
\t\t_finish()
\t\treturn
\tif not _prepared_job_signal_951(control, "legacy-stop.json", {"stop_pressed": true, "before": before, "after": _prepared_job_records_951(), "setups": setups, "observation": _prepared_job_observation_951(stop, resume)}):
\t\t_finish()
\t\treturn
\tif not _prepared_job_signal_951(control, "legacy-quiescence-ready", {"setups": setups, "continue_enabled": not resume.disabled, "workers_known_terminal": _prepared_legacy_workers_951(), "observation": _prepared_job_observation_951(stop, resume)}):
\t\t_finish()
\t\treturn
\tdeadline = Time.get_ticks_msec() + 45000
\twhile not FileAccess.file_exists(control.path_join("legacy-quiescence-checked")) and Time.get_ticks_msec() < deadline:
\t\tawait process_frame
\tif not _check(FileAccess.file_exists(control.path_join("legacy-quiescence-checked")), "Parent fixture did not verify actual legacy setup processes ended"):
\t\t_finish()
\t\treturn
\tvar acknowledgement = JSON.parse_string(FileAccess.get_file_as_string(control.path_join("legacy-quiescence-checked")))
\t_check(acknowledgement is Dictionary and acknowledgement.get("ok", false) == true and acknowledgement.get("scope", "") == "fixture_setup_processes" and acknowledgement.get("pending", ["unknown"]) == [] and _prepared_legacy_setups_951() == setups and _prepared_legacy_workers_951() and not dock.get_meta("history_saving", false), "Legacy setup process outcome unknown or a new preparation appeared")
\t_finish()

func _prepared_readonly_boundary_951(stop, resume) -> Dictionary:
\tif dock.get_meta("history_saving", false):
\t\treturn {"history": null, "dispatch_files": {}, "observation": _prepared_job_observation_951(stop, resume)}
\tvar history = JSON.parse_string(FileAccess.get_file_as_string("res://.godot/editor/ai_chat_history.json"))
\tvar directory: String = dock.get_production_workspace().path_join("data-collection/outbox")
\tvar dispatch_files := {}
\tfor name in DirAccess.get_files_at(directory):
\t\tif (name.begins_with("parallel-") or name.begins_with("setup-")) and name.ends_with(".json"):
\t\t\tdispatch_files[name] = FileAccess.get_sha256(directory.path_join(name))
\treturn {"history": history, "dispatch_files": dispatch_files, "observation": _prepared_job_observation_951(stop, resume)}

func _prepared_readonly_continue_951(control: String, stop, resume) -> bool:
\tvar consultation = dock.find_child("ConsultationOnly", true, false)
\tif not _check(consultation is CheckBox and not consultation.disabled and not consultation.button_pressed and not resume.disabled, "Warm public consultation/Continue controls unavailable"):
\t\treturn false
\tconsultation.button_pressed = true
\tif not _check(consultation.button_pressed and not resume.disabled, "Consultation toggle did not reach the public Continue boundary"):
\t\treturn false
\tvar enabled_readback: bool = consultation.button_pressed
\tvar before := _prepared_readonly_boundary_951(stop, resume)
\tvar parent = before.observation.children.get("2", {}).get("parent", -1)
\tif not _check(before.history is Dictionary and before.history.get("active_agent", -2) == parent and before.observation.capacity == "2" and before.observation.children.get("4", {}).has("acceptance"), "Read-only rejection is not at the original parent after B acceptance"):
\t\treturn false
\tif not _prepared_job_signal_951(control, "readonly-continue-before.json", before):
\t\treturn false
\tif not _check(consultation.button_pressed and not resume.disabled, "Read-only Continue became unavailable before invocation"):
\t\treturn false
\tresume.pressed.emit()
\tif not _prepared_job_signal_951(control, "readonly-continue-returned.json", _prepared_readonly_boundary_951(stop, resume)):
\t\treturn false
\tawait process_frame
\tvar after := _prepared_readonly_boundary_951(stop, resume)
\tvar unchanged: bool = before.history == after.history and before.dispatch_files == after.dispatch_files and before.observation.children == after.observation.children and before.observation.history_sha256 == after.observation.history_sha256
\tconsultation.button_pressed = false
\tvar restored: bool = not consultation.button_pressed
\tif not _prepared_job_signal_951(control, "readonly-continue-result.json", {"continue_pressed": true, "consultation_enabled_readback": enabled_readback, "consultation_disabled_readback": restored, "before": before, "after": after, "unchanged": unchanged}):
\t\treturn false
\treturn _check(unchanged and restored and not resume.disabled, "Consultation Continue advanced production or normal control was not restored")

func _prepared_job_recovery_951(cold := false):
\tvar control := OS.get_environment("NATIVE_PREPARED_CONTROL")
\tvar foreign := OS.get_environment("NATIVE_PREPARED_FOREIGN") == "1"
\tvar warm := OS.get_environment("NATIVE_PREPARED_WARM") == "1"
\tvar stop = dock.find_child("Stop", true, false)
\tvar resume = dock.find_child("SpawnWorkOrderAgents", true, false)
\tif not _check(stop != null and resume != null, "Prepared job public controls missing"):
\t\t_finish()
\t\treturn
\tvar deadline := Time.get_ticks_msec() + 180000
\tvar records := {}
\tif not cold and OS.get_environment("NATIVE_PREPARED_LEGACY") == "1":
\t\tawait _prepared_job_legacy_stop_951(control, stop, resume)
\t\treturn
\tif not cold:
\t\twhile Time.get_ticks_msec() < deadline:
\t\t\tif not _prepared_job_capacity_fault_951(control):
\t\t\t\t_finish()
\t\t\t\treturn
\t\t\trecords = _prepared_job_records_951()
\t\t\tif records.size() == 3 and records.get("2", {}).get("production_preparation", {}).get("state", "") == "blocked" and records.get("2", {}).get("production_preparation", {}).get("launch_state", "") == "not_started" and records.get("2", {}).has("repair_of") and records.get("4", {}).has("acceptance") and not resume.disabled and not dock.get_meta("history_saving", false):
\t\t\t\tbreak
\t\t\tawait process_frame
\t\tif not _check(records.size() == 3 and records.get("2", {}).get("production_preparation", {}).get("state", "") == "blocked" and records.get("2", {}).get("production_preparation", {}).get("launch_state", "") == "not_started" and records.get("2", {}).has("repair_of") and records.get("4", {}).has("acceptance") and not resume.disabled, "A repair did not reach an actual blocked boundary with B accepted"):
\t\t\t_finish()
\t\t\treturn
\t\tif not _check(not records["6"].has("parallel_assignment") and not records["6"].has("terminal_receipt"), "C executed before upstream repair") or not await _prepared_job_save_951():
\t\t\t_finish()
\t\t\treturn
\t\tif not warm:
\t\t\t_finish()
\t\t\treturn
\telse:
\t\tawait _select_normal_setup_951()
\t\tif not await _prepared_job_save_951():
\t\t\t_finish()
\t\t\treturn
\trecords = _prepared_job_records_951()
\tvar expected_state := "waiting" if warm else "interrupted"
\tif not _check(records.size() == 3 and records.get("6", {}).get("state", "") == expected_state and not records.get("6", {}).has("parallel_assignment"), "Original C was not preserved as an unstarted job"):
\t\t_finish()
\t\treturn
\tvar signal_prefix := "warm" if warm else "cold"
\tif not _prepared_job_signal_951(control, signal_prefix + "-ready", {"children": records, "stop_disabled": stop.disabled, "continue_enabled": not resume.disabled, "history_saving": dock.get_meta("history_saving", false)}):
\t\t_finish()
\t\treturn
\tdeadline = Time.get_ticks_msec() + 30000
\twhile not FileAccess.file_exists(control.path_join(signal_prefix + "-checked")) and Time.get_ticks_msec() < deadline:
\t\tawait process_frame
\tif not _check(FileAccess.file_exists(control.path_join(signal_prefix + "-checked")) and not resume.disabled, "Source readback or normal Continue unavailable"):
\t\t_finish()
\t\treturn
\tvar capacity = dock.get_ai_settings_control().find_child("ProductionCapacity", true, false)
\tif not _check(capacity is LineEdit and capacity.editable, "Public production capacity restore unavailable"):
\t\t_finish()
\t\treturn
\tif warm:
\t\tif not _check(capacity.text == "3", "Warm capacity fault changed before explicit restoration"):
\t\t\t_finish()
\t\t\treturn
\t\tcapacity.text = "2"
\tif not _check(capacity.text == "2", "Normal production capacity was not restored before Continue"):
\t\t_finish()
\t\treturn
\tif warm and not await _prepared_readonly_continue_951(control, stop, resume):
\t\t_finish()
\t\treturn
\tvar capacity_before_continue: String = capacity.text
\tif not _check(not resume.disabled and capacity.text == "2", "Continue changed before actual invocation") or not _prepared_job_signal_951(control, "continue-before.json", _prepared_job_observation_951(stop, resume)):
\t\t_finish()
\t\treturn
\tif not _check(not resume.disabled and capacity.text == "2", "Continue changed while recording invocation"):
\t\t_finish()
\t\treturn
\tresume.pressed.emit()
\tif not _prepared_job_signal_951(control, "continue-returned.json", _prepared_job_observation_951(stop, resume)):
\t\t_finish()
\t\treturn
\tawait process_frame
\tif not _prepared_job_signal_951(control, "continue-wait-start.json", _prepared_job_observation_951(stop, resume)):
\t\t_finish()
\t\treturn
\tif foreign:
\t\tif not await _prepared_job_save_951():
\t\t\t_finish()
\t\t\treturn
\t\tvar after := _prepared_job_records_951()
\t\t_check(after == records and after.get("2", {}).get("production_preparation", {}).get("state", "") == "blocked" and after.get("2", {}).get("production_preparation", {}).get("launch_state", "") == "not_started" and not after.get("6", {}).has("parallel_assignment") and not after.get("6", {}).has("terminal_receipt") and not resume.disabled, "Changed configuration crossed or changed the prepared job gate")
\telse:
\t\tdeadline = Time.get_ticks_msec() + 180000
\t\tvar accepted := 0
\t\tvar previous_observation := ""
\t\tvar observation_number := 0
\t\twhile Time.get_ticks_msec() < deadline:
\t\t\tif dock.get_meta("history_saving", false):
\t\t\t\tawait process_frame
\t\t\t\tcontinue
\t\t\tvar observation := _prepared_job_observation_951(stop, resume)
\t\t\tvar observation_key := str(observation.history_sha256) + str(observation.continue_enabled) + str(observation.stop_disabled) + str(observation.ui_text)
\t\t\tif observation_key != previous_observation and observation_number < 32:
\t\t\t\tif not _prepared_job_signal_951(control, "continue-wait-%02d.json" % observation_number, observation):
\t\t\t\t\t_finish()
\t\t\t\t\treturn
\t\t\t\tprevious_observation = observation_key
\t\t\t\tobservation_number += 1
\t\t\taccepted = 0
\t\t\tfor child in _prepared_job_records_951().values():
\t\t\t\tif child.has("acceptance"):
\t\t\t\t\taccepted += 1
\t\t\tif accepted == 3 and "PREPARED_JOB_PARENT_RECEIPTS_CHECKED" in _text() and not resume.disabled and not dock.get_meta("history_saving", false):
\t\t\t\tbreak
\t\t\tawait process_frame
\t\t_check(accepted == 3 and "PREPARED_JOB_PARENT_RECEIPTS_CHECKED" in _text() and not resume.disabled and not dock.get_meta("history_saving", false), "Original A/C repairs or parent receipt readback did not finish")
\t_prepared_job_signal_951(control, "continue-result.json", {"continue_pressed": true, "continue_enabled": not resume.disabled, "stop_disabled": stop.disabled, "parent_marker_seen": "PREPARED_JOB_PARENT_RECEIPTS_CHECKED" in _text(), "capacity_before_continue": capacity_before_continue, "foreign": foreign, "warm": warm, "children": _prepared_job_records_951(), "ui_text": _text()})
\t_finish()
"""
