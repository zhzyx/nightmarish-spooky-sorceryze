"""Controlled model responses for ordinary-game setup/review/integration.

Only the model transport proposes actions. The editor executes reads, verifies
independent acceptance, applies a host plan, runs the game and rolls it back.
This is not a real-provider or first-Issue-publication acceptance test.
"""

import io
import json
import os
from pathlib import Path

COLD_GAME = False


def cli(source):
    source = source.replace(
        "if(request.method==='initialize')",
        "if(request.method==='account/read')console.log(JSON.stringify({id:request.id,result:{account:null}}));\n"
        "    if(request.method==='initialize')",
    )
    source = source.replace(
        "if(!prompt.includes('Issue #441'))",
        """if(prompt.startsWith('You are the Godot editor assistant.')) {
    const input=JSON.parse(prompt.slice(prompt.indexOf('\\n')+1));
    event('model-turn');
    const response=await fetch(process.env.DESIGN_BATCH_ENDPOINT+'/chat/completions',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({messages:input.messages,tools:input.available_tools})});
    const data=await response.json();if(!response.ok)throw Error(JSON.stringify(data));
    const message=data.choices[0].message;
    const answer={content:message.content||'',actions:(message.tool_calls||[]).map(t=>({name:t.function.name,arguments:JSON.parse(t.function.arguments)}))};
    console.log(JSON.stringify({type:'item.completed',item:{type:'agent_message',text:JSON.stringify(answer)}}));
    console.log(JSON.stringify({type:'turn.completed',usage:{}}));process.exit(0);
  }
  if(!prompt.includes('Issue #441'))""",
    )
    script = 'extends SceneTree\nfunc _initialize():\n\tprint("ORDINARY_GAME_EXECUTED")\n\tquit()\n'
    return source.replace(
        "event('finish');console.log",
        "fs.writeFileSync('samples/project/production-output.gd'," + json.dumps(script) + ");\n"
        "  event('finish');console.log",
    )


def control(source):
    if COLD_GAME:
        import native_game_cold

        return native_game_cold.control(source)
    return source.replace(
        'await _wait_file("native-setup-runner-finished", 150.0)',
        'await _wait_marker("ORDINARY_GAME_INTEGRATION_ROLLED_BACK", 180.0)',
    )


def install(batch, acceptance, observed):
    previous_server = batch.ThreadingHTTPServer

    class GameIntegrationServer(previous_server):
        def __init__(self, address, handler):
            super().__init__(address, handler)
            original = handler.do_POST

            def post(instance):
                raw = instance.rfile.read(int(instance.headers["Content-Length"]))
                body = json.loads(raw)
                prompt = next((m.get("content", "") for m in reversed(body["messages"]) if m["role"] == "user"), "")
                if COLD_GAME and prompt == "ORDINARY_GAME_COLD_RECOVERY":
                    import native_game_cold

                    return native_game_cold.respond(instance, body, batch, observed)
                if not isinstance(prompt, str) or "current_host_design_batch" not in prompt:
                    instance.rfile = io.BytesIO(raw)
                    return original(instance)
                try:
                    result, pending = {}, {}
                    # CLI-generated IDs may repeat across turns. Associate each
                    # result with its preceding proposal instead of guessing IDs.
                    for entry in body["messages"]:
                        for call in entry.get("tool_calls", []):
                            function = call.get("function", {})
                            arguments = function.get("arguments", {})
                            if isinstance(arguments, str):
                                arguments = json.loads(arguments)
                            stage = (
                                arguments.get("action")
                                if function.get("name") == "integrate_production_result"
                                else "run"
                                if function.get("name") == "run_command"
                                else None
                            )
                            pending[call["id"]] = stage
                        if entry["role"] == "tool" and pending.get(entry.get("tool_call_id")):
                            result["ordinary-" + pending[entry["tool_call_id"]]] = entry["content"]
                    project = Path(os.environ["ORDINARY_GAME_PROJECT"])

                    def value(action):
                        answer = json.loads(result["ordinary-" + action])
                        assert answer.get("ok") is True, answer
                        observed.setdefault("integration", {})[action] = answer
                        return answer

                    if "ordinary-list" not in result:
                        message = batch.tool_call("ordinary-list", "integrate_production_result", {"action": "list"})
                    else:
                        producers = value("list")["producers"]
                        assert len([p for p in producers if p["live_independent_acceptance"]]) == 2, producers
                        producer = next(p["producer_id"] for p in producers if p["work_order"] == 1)
                        message = None
                        for action, state in (("plan", "planned"), ("apply", "applied")):
                            if "ordinary-" + action not in result:
                                message = batch.tool_call(
                                    "ordinary-" + action,
                                    "integrate_production_result",
                                    {"action": action, "producer_id": producer},
                                )
                                break
                            answer = value(action)
                            assert answer["state"] == state, answer
                            if action == "plan":
                                assert answer["changed_files"] == ["production-output.gd"], answer
                        if message is None:
                            if "ordinary-run" not in result:
                                command = [
                                    os.environ["ORDINARY_GAME_BINARY"],
                                    "--headless",
                                    "--path",
                                    str(project),
                                    "--script",
                                    "res://production-output.gd",
                                ]
                                code = (
                                    "import subprocess; p=subprocess.run("
                                    + repr(command)
                                    + ",capture_output=True,text=True,timeout=30); print(p.stdout); print(p.stderr); raise SystemExit(p.returncode)"
                                )
                                message = batch.tool_call(
                                    "ordinary-run", "run_command", {"command": batch.python_command(code)}
                                )
                            else:
                                run = json.loads(result["ordinary-run"])
                                assert run["exit_code"] == 0 and "ORDINARY_GAME_EXECUTED" in json.dumps(run), run
                                observed["game_run"] = run
                                if COLD_GAME:
                                    message = {"role": "assistant", "content": "ORDINARY_GAME_APPLIED_FOR_RESTART"}
                                elif "ordinary-rollback" not in result:
                                    message = batch.tool_call(
                                        "ordinary-rollback",
                                        "integrate_production_result",
                                        {"action": "rollback", "producer_id": producer},
                                    )
                                else:
                                    answer = value("rollback")
                                    assert answer["state"] == "rolled_back", answer
                                    assert not (project / "production-output.gd").exists()
                                    observed["rollback_removed_output"] = True
                                    message = {"role": "assistant", "content": "ORDINARY_GAME_INTEGRATION_ROLLED_BACK"}
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

            handler.do_POST = post

    batch.ThreadingHTTPServer = GameIntegrationServer


def valid(observed, acceptance):
    observed["independent_review_calls"] = acceptance.review_calls
    return (
        len([r for r in acceptance.review_calls if r["completed"]]) == 2
        and observed.get("rollback_removed_output") is True
        and bool(observed.get("game_run"))
        and not observed.get("integration_errors")
        and (not COLD_GAME or observed.get("cold", {}).get("ok") is True)
    )
