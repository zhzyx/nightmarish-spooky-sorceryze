"""Ordinary-game cold recovery: real native tools, controlled model transport."""

import hashlib
import json
from pathlib import Path


def control(source):
    source = source.replace(
        'await _wait_file("native-setup-runner-finished", 150.0)',
        'await _wait_marker("ORDINARY_GAME_APPLIED_FOR_RESTART", 180.0)',
    )
    marker = '\tvar mode := OS.get_environment("DESIGN_BATCH_CASE")\n\tif OS.get_environment("DESIGN_BATCH_PHASE")'
    branch = """\tvar mode := OS.get_environment("DESIGN_BATCH_CASE")
\tif OS.get_environment("DESIGN_BATCH_PHASE") == "ordinary-game-cold":
\t\tvar ready_deadline := Time.get_ticks_msec() + 45000
\t\twhile dock.find_child("Send", true, false).disabled and Time.get_ticks_msec() < ready_deadline:
\t\t\tawait create_timer(0.05).timeout
\t\t_check(dock.find_child("Stop", true, false).disabled, "Cold editor did not become idle after model discovery")
\t\t_send("ORDINARY_GAME_COLD_RECOVERY")
\t\tawait _wait_marker("ORDINARY_GAME_COLD_RECOVERED", 120.0)
\t\t_finish()
\t\treturn
\tif OS.get_environment("DESIGN_BATCH_PHASE")"""
    assert marker in source
    return source.replace(marker, branch, 1)


def respond(instance, body, batch, observed):
    try:
        results, pending = {}, {}
        # Only this explicit cold request's results; saved earlier history is
        # untrusted context, not the result of these probes.
        start = max(
            i
            for i, m in enumerate(body["messages"])
            if m.get("role") == "user" and m.get("content") == "ORDINARY_GAME_COLD_RECOVERY"
        )
        for item in body["messages"][start:]:
            for call in item.get("tool_calls", []):
                function = call["function"]
                arguments = function["arguments"]
                if isinstance(arguments, str):
                    arguments = json.loads(arguments)
                pending[call["id"]] = arguments.get("action")
            if item.get("role") == "tool" and item.get("tool_call_id") in pending:
                results[pending[item["tool_call_id"]]] = json.loads(item["content"])
        cold = observed["cold"]
        if "journal_at_explicit_request" not in cold:
            journal = Path(cold["workspace"]) / "data-collection/outbox/project-integration"
            cold["journal_at_explicit_request"] = {
                str(p.relative_to(journal)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in journal.rglob("*")
                if p.is_file()
            }
            assert cold["journal_at_explicit_request"] == cold["journal_before"], (
                "Journal changed before explicit recovery"
            )
        cold["results"] = results
        producer = None
        action = "list"
        if "list" in results:
            producers = results["list"]["producers"]
            assert len(producers) == 2 and all(p["live_independent_acceptance"] is False for p in producers), producers
            producer = next(p for p in producers if p["work_order"] == 1)
            cold["restored_integration"] = producer["integration"]
            assert producer["integration"]["state"] == "applied", producer
            action = None
            for probe in ["plan", "apply", "rollback"]:
                if probe not in results:
                    action = probe
                    break
                answer = results[probe]
                if probe != "rollback":
                    assert answer.get("error") == "current_independent_acceptance_required" and not answer.get("ok"), (
                        answer
                    )
                else:
                    assert answer.get("ok") is True and answer["state"] == "rolled_back", answer
                    assert answer["plan_sha256"] == observed["integration"]["apply"]["plan_sha256"], answer
                    assert not Path(cold["target_output"]).exists()
                    observed["rollback_removed_output"] = True
                    cold["ok"] = True
        if action:
            arguments = {"action": action}
            if producer:
                arguments["producer_id"] = producer["producer_id"]
            message = batch.tool_call("cold-" + action, "integrate_production_result", arguments)
        else:
            message = {"role": "assistant", "content": "ORDINARY_GAME_COLD_RECOVERED"}
        data = json.dumps({"choices": [{"message": message, "finish_reason": "stop"}]}).encode()
        instance.send_response(200)
    except Exception as error:
        observed.setdefault("integration_errors", []).append(repr(error))
        data = json.dumps({"error": str(error)}).encode()
        instance.send_response(500)
    instance.send_header("Content-Type", "application/json")
    instance.send_header("Content-Length", str(len(data)))
    instance.end_headers()
    instance.wfile.write(data)


def restart(run, command, args, kwargs, observed):
    env = kwargs["env"]
    project = Path(env["DESIGN_BATCH_PROJECT"])
    workspace = Path(env["DESIGN_BATCH_ROOT"])
    report = project / "design-batch-report.json"
    initial = report.read_bytes()
    assert json.loads(initial)["ok"]
    output = project / "production-output.gd"
    assert output.exists()
    journal = workspace / "data-collection/outbox/project-integration"
    files = {
        str(p.relative_to(journal)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in journal.rglob("*")
        if p.is_file()
    }
    assert files, "Application journal missing before cold restart"
    cold = observed["cold"] = {
        "ok": False,
        "target_output": str(output),
        "workspace": str(workspace),
        "journal_before": files,
        "initial_editor": json.loads(initial),
        "applied_output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "binary_sha256": hashlib.sha256(Path(command[0]).read_bytes()).hexdigest(),
        "no_manual_recovery_copy": True,
    }
    cold_kwargs = dict(kwargs, env=dict(env, DESIGN_BATCH_PHASE="ordinary-game-cold"), timeout=180)
    restored = run(command, *args, **cold_kwargs)
    cold["exit_code"] = restored.returncode
    cold["editor"] = json.loads(report.read_bytes())
    cold["stdout"] = restored.stdout
    cold["stderr"] = restored.stderr
    cold["journal_after"] = {
        str(p.relative_to(journal)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in journal.rglob("*")
        if p.is_file()
    }
    cold["ok"] = cold["ok"] and restored.returncode == 0 and cold["editor"]["ok"]
    report.with_name("ordinary-game-cold-report.json").write_bytes(report.read_bytes())
    report.write_bytes(initial)
    return restored
