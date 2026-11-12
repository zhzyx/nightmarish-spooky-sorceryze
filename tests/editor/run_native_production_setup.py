"""Normal native production controls, real setup/runner, isolated CLI transport.

The HTTP design and GitHub authority transports come from native acceptance.
Codex/CodeBuddy discovery uses shipped bridges and protocol fixtures. Worker
commands execute real isolated processes. This test stops before independent
review: provider authentication/model quality/business acceptance are excluded.
No production config, worktree mapping or ledger is supplied by the fixture.
"""

import json
import sys
from pathlib import Path
from typing import Any

import native_acceptance_parallel as parallel
import run_native_acceptance as acceptance

REVIEW_RECOVERY = ""
if "--review-recovery" in sys.argv:
    at = sys.argv.index("--review-recovery")
    REVIEW_RECOVERY = sys.argv[at + 1]
    del sys.argv[at : at + 2]
    if REVIEW_RECOVERY not in {"warm", "cold"}:
        raise SystemExit("--review-recovery must be warm or cold")
    sys.argv.append("--complete-game")

BACKEND = "codebuddy"
GAME_WORKSPACE = "--game-workspace" in sys.argv
COMPLETE_GAME = "--complete-game" in sys.argv
COLD_GAME = "--cold-game" in sys.argv
if COLD_GAME:
    sys.argv.remove("--cold-game")
    COMPLETE_GAME = True
if COMPLETE_GAME:
    if "--complete-game" in sys.argv:
        sys.argv.remove("--complete-game")
    GAME_WORKSPACE = True
if "--game-workspace" in sys.argv:
    sys.argv.remove("--game-workspace")
REBIND_PYTHON = ""
if "--rebind-python" in sys.argv:
    at = sys.argv.index("--rebind-python")
    REBIND_PYTHON = str(Path(sys.argv[at + 1]).resolve())
    del sys.argv[at : at + 2]
if "--backend" in sys.argv:
    at = sys.argv.index("--backend")
    BACKEND = sys.argv[at + 1]
    del sys.argv[at : at + 2]
if BACKEND not in {"codebuddy", "codex"}:
    raise SystemExit("--backend must be codebuddy or codex")

batch = acceptance.batch
batch.GAME_WORKSPACE = GAME_WORKSPACE
batch.COMPLETE_GAME = COMPLETE_GAME
batch.FINALIZED = batch.FINALIZED.replace("- 依赖: 1\n", "")
observed: dict[str, Any] = {}

CLI = r"""import fs from 'node:fs';
import crypto from 'node:crypto';
import readline from 'node:readline';
const events=process.env.NATIVE_SETUP_EVENTS;
const event=(phase, extra={})=>fs.appendFileSync(events,JSON.stringify({phase,pid:process.pid,time:Date.now(),root:process.cwd(),...extra})+'\n');
const discover=async()=>{
  event('discovery');
  const count=fs.readFileSync(events,'utf8').trim().split('\n').map(JSON.parse).filter(e=>e.phase==='discovery').length;
  if(process.env.NATIVE_SETUP_REBIND && count===2){
    fs.writeFileSync(process.env.DESIGN_BATCH_PROJECT+'/setup-discovery-ready','ready');
    while(!fs.existsSync(process.env.DESIGN_BATCH_PROJECT+'/setup-discovery-release'))await new Promise(resolve=>setTimeout(resolve,20));
  }
};
if(process.argv.includes('login')) {
  event('login-status');console.log('Fixture authenticated');
} else if(process.argv.includes('app-server')) {
  const lines=readline.createInterface({input:process.stdin});
  lines.on('line',async line=>{const request=JSON.parse(line);
    if(request.method==='initialize')console.log(JSON.stringify({id:request.id,result:{}}));
    if(request.method==='model/list'){await discover();console.log(JSON.stringify({id:request.id,result:{data:[{id:'fixture-native-setup',model:'fixture-native-setup',displayName:'Isolated transport fixture'}]}}));}
  });
} else if(process.argv.includes('--input-format')) {
  const lines=readline.createInterface({input:process.stdin});
  lines.on('line',async line=>{const request=JSON.parse(line);await discover();
    console.log(JSON.stringify({type:'control_response',response:{request_id:request.request_id,subtype:'success',response:{models:[{id:'fixture-native-setup',name:'Isolated transport fixture'}]}}}));});
} else if(process.argv.includes('--acp')) {
  event('review-boundary'); process.exit(2);
} else {
  let prompt='';for await(const chunk of process.stdin)prompt+=chunk;
  if(!prompt.includes('Issue #441'))throw Error('Missing mandate');
  const bound=prompt.match(/Current Godot editor runtime supplied by the native host \(data\): (\{[^\n]+\})/);
  if(!bound)throw Error('Missing actual editor runtime in worker prompt');
  const editor=JSON.parse(bound[1]);
  if(fs.realpathSync(editor.executable)!==fs.realpathSync(process.env.NATIVE_SETUP_EDITOR))throw Error('Wrong editor runtime');
  if(crypto.createHash('sha256').update(fs.readFileSync(editor.executable)).digest('hex')!==editor.sha256)throw Error('Editor bytes changed');
  if(process.argv[process.argv.indexOf('--model')+1]!=='fixture-native-setup')throw Error('Model selection lost');
  event('start',{editor_runtime_bound:true});await new Promise(resolve=>setTimeout(resolve,1500));
  fs.writeFileSync('fixture-input.txt','UNTRUSTED_FIXTURE_FILE actual normal native setup worker\n');
  event('finish');console.log(JSON.stringify({result:'Fixture worker completed',is_error:false}));
}
"""

if COMPLETE_GAME:
    import native_game_integration as game_integration

    game_integration.COLD_GAME = COLD_GAME
    CLI = game_integration.cli(CLI)
    game_integration.install(batch, acceptance, observed)
    if REVIEW_RECOVERY:
        import native_review_recovery

        native_review_recovery.install(batch, observed)

CONTROL = """
var setup_confirmation_started := false
func _confirm_normal_setup(confirmation):
\tif setup_confirmation_started:
\t\treturn
\tsetup_confirmation_started = true
\tvar ai = dock.get_ai_settings_control()
\tvar env = dock.get_environment_settings_control()
\tenv.find_child("CLIEntry", true, false).text = OS.get_environment("NATIVE_SETUP_CLI")
\tenv.find_child("CLIBridge", true, false).text = OS.get_environment("NATIVE_SETUP_BRIDGE")
\tvar backend = ai.find_child("AIBackend", true, false)
\tvar backend_index := 2 if OS.get_environment("NATIVE_SETUP_BACKEND") == "codex" else 1
\tif backend_index == 2:
\t\t_check(dock.set_runtime_field("codex", OS.get_environment("NATIVE_SETUP_CLI")).is_empty(), "Cannot set private Codex fixture")
\t\tenv.find_child("CodexEntry", true, false).text = OS.get_environment("NATIVE_SETUP_CLI")
\tbackend.select(backend_index)
\tbackend.item_selected.emit(backend_index)
\tvar picker = ai.find_child("ModelPicker", true, false)
\tvar deadline := Time.get_ticks_msec() + 45000
\tvar found := -1
\twhile found < 0 and Time.get_ticks_msec() < deadline:
\t\tfor index in range(picker.item_count):
\t\t\tif str(picker.get_item_metadata(index)) == "fixture-native-setup":
\t\t\t\tfound = index
\t\tawait create_timer(0.05).timeout
\tif not _check(found >= 0, "CLI model discovery did not populate normal picker"):
\t\t_finish()
\t\treturn
\tpicker.select(found)
\tpicker.item_selected.emit(found)
\tai.find_child("ProductionSetup", true, false).button_pressed = true
\tai.find_child("ProductionCapacity", true, false).text = "2"
\t_check(EditorInterface.get_editor_settings().get_setting("ai_chat/parallel_work_orders_config") == "", "Manual configuration unexpectedly present")
\tconfirmation.get_ok_button().pressed.emit()
\tif not OS.get_environment("NATIVE_SETUP_REBIND").is_empty():
\t\tif not await _wait_file("setup-discovery-ready", 45.0):
\t\t\t_finish()
\t\t\treturn
\t\t_check(dock.set_runtime_field("workflow_python", OS.get_environment("NATIVE_SETUP_REBIND")).is_empty(), "Cannot change Python during preparation")
\t\t_file("setup-discovery-release")
"""

old_copy = batch.shutil.copyfile


def copy(source, target, *args, **kwargs):
    result = old_copy(source, target, *args, **kwargs)
    if Path(source).name == "design_batch.gd":
        script = Path(target).read_text(encoding="utf8")
        # This scenario refreshes the CLI via its normal source-change signal;
        # the base scenario's independent HTTP wakeup perturbation is unrelated.
        script = script.replace('if mode.begins_with("models-initial-"):', "if false:")
        script = script.replace(
            "_confirm_fixture_design.call_deferred(design_confirmation)",
            "_confirm_normal_setup.call_deferred(design_confirmation)",
        )
        # Keep the real HTTP warmup/design path, then observe the actual runner.
        start = script.index('\n\tif mode.begins_with("parallel-"):', script.index('\t_send("DESIGN_BATCH_START")'))
        script = (
            script[:start]
            + """
\tawait _wait_file("native-setup-runner-finished", 150.0)
\t_finish()
"""
            + CONTROL
        )
        if COMPLETE_GAME:
            script = game_integration.control(script)
            if REVIEW_RECOVERY:
                script = native_review_recovery.control(script, REVIEW_RECOVERY)
        Path(target).write_text(script, encoding="utf8")
    return result


batch.shutil.copyfile = copy

old_run = batch.subprocess.run


def run(command, *args, **kwargs):
    # Reuse the existing isolated installed host copy, never its manual setup.
    if "mklink" in command and Path(command[-2]).name == "tools":
        previous = acceptance.SCENARIO
        acceptance.SCENARIO = "parallel"
        try:
            return old_run(command, *args, **kwargs)
        finally:
            acceptance.SCENARIO = previous
    env = kwargs.get("env")
    if env and "DESIGN_BATCH_PROJECT" in env and "--editor" in command:
        import threading

        env = dict(env)
        # Frozen installed adapters are byte-pinned. Only ordinary inputs such
        # as the design exercise Windows checkout conversion.
        Path(env["DESIGN_BATCH_ROOT"], ".gitattributes").write_text(
            "framework/** -text\nCURRENT_FRAMEWORK.json -text\ncustomizations/** -text\nintegrations/** -text\n",
            encoding="utf8",
        )
        old_run(["git", "-C", env["DESIGN_BATCH_ROOT"], "add", ".gitattributes"], check=True)
        if GAME_WORKSPACE:
            root = Path(env["DESIGN_BATCH_ROOT"])
            installation = root.parent / "installation"
            native = Path(
                "tools/codebuddy_cli/node_modules/@tencent-ai/codebuddy-code/bin/native/win32-x64/job-object.node"
            )
            (installation / native).parent.mkdir(parents=True, exist_ok=True)
            batch.shutil.copyfile(batch.os.environ["NATIVE_ACCEPTANCE_JOB_OBJECT"], installation / native)
            old_run(
                ["git", "-C", str(root), "add", "samples/project", ".gitattributes"], check=True, capture_output=True
            )
            old_run(
                ["git", "-C", str(root), "commit", "-m", "ordinary isolated game inputs"],
                check=True,
                capture_output=True,
            )
            old_run(["git", "-C", str(root), "push", "origin", "HEAD:main"], check=True, capture_output=True)
            env["PATH"] = str(Path(env["DESIGN_BATCH_NODE"]).parent) + batch.os.pathsep + env["PATH"]
            observed["ordinary_game"] = {
                "host_separate_from_project": not root.is_relative_to(installation),
                "forbidden_host_paths_absent": all(
                    not (root / p).exists()
                    for p in ["SConstruct", "tools", "framework", "customizations", "CURRENT_FRAMEWORK.json"]
                ),
                "mocked_actions": ["issue-agent", "chat", "flush"],
            }
        else:
            parallel.prepare(env, manual_config=False)
        # Only the requirement/model-context transport is isolated here.
        # Setup, worktrees, runner, registration and terminal receipts use
        # the actual installed implementation; B contains no host code.
        bridge = (
            root.parent / "installation" if GAME_WORKSPACE else Path(env["DESIGN_BATCH_ROOT"]).parent
        ) / "customizations/components/godot-host/bridge.py"
        text = bridge.read_text(encoding="utf8")
        marker = 'if __name__ == "__main__":'
        assert text.count(marker) == 1
        transport = (
            "if __name__ == '__main__' and sys.argv[1] in {'issue-agent', 'chat', 'flush'}:\n"
            "    exec(" + repr(batch.BRIDGE) + ")\n    sys.exit(0)\n\n"
        )
        bridge.write_text(text.replace(marker, transport + marker), encoding="utf8")
        old_run(["git", "-C", env["DESIGN_BATCH_ROOT"], "config", "core.autocrlf", "true"], check=True)
        old_run(["git", "-C", env["DESIGN_BATCH_ROOT"], "config", "core.longpaths", "false"], check=True)
        folder = Path(env["DESIGN_BATCH_ROOT"]).parent
        cli = folder / "fixture-codebuddy.mjs"
        cli.write_text(CLI, encoding="utf8")
        if BACKEND == "codex":
            cli = batch.fixture_program(
                folder / "fixture-codex",
                "import subprocess,sys\nsys.exit(subprocess.call("
                + repr([env["DESIGN_BATCH_NODE"], str(cli)])
                + "+sys.argv[1:]))\n",
            )
        env["NATIVE_SETUP_CLI"] = str(cli)
        env["NATIVE_SETUP_BACKEND"] = BACKEND
        installation = folder / "installation" if GAME_WORKSPACE else folder
        env["NATIVE_SETUP_BRIDGE"] = str(installation / "tools/codebuddy_cli/godot_bridge.js")
        env["NATIVE_SETUP_EVENTS"] = str(folder / "setup-events.jsonl")
        env["NATIVE_SETUP_EDITOR"] = str(command[0]).replace(".console.exe", ".exe")
        env["NATIVE_SETUP_REBIND"] = REBIND_PYTHON
        if COMPLETE_GAME:
            batch.os.environ["ORDINARY_GAME_BINARY"] = str(command[0])
            batch.os.environ["ORDINARY_GAME_PROJECT"] = env["DESIGN_BATCH_PROJECT"]
        kwargs["env"] = env
        stop = threading.Event()

        def monitor():
            while not stop.wait(0.2):
                pattern = (
                    "original/data-collection/outbox/parallel-*.result.json"
                    if GAME_WORKSPACE
                    else "godot-candidate-*/data-collection/outbox/parallel-*.result.json"
                )
                for path in folder.glob(pattern):
                    try:
                        # Windows readers can prevent rename. Observe only
                        # after the real runner removes its completion marker.
                        if Path(str(path) + ".running").exists():
                            continue
                        result = json.loads(path.read_text(encoding="utf8"))
                        if len(result.get("workers", [])) == 2:
                            observed["runner"] = result
                            Path(env["DESIGN_BATCH_PROJECT"], "native-setup-runner-finished").touch()
                    except (ValueError, OSError):
                        pass

        thread = threading.Thread(target=monitor, daemon=True)
        thread.start()
        try:
            result = old_run(command, *args, **kwargs)
            if REVIEW_RECOVERY == "cold" and result.returncode == 0:
                result = native_review_recovery.restart(old_run, command, args, kwargs, observed)
            if COLD_GAME and result.returncode == 0:
                import native_game_cold

                result = native_game_cold.restart(old_run, command, args, kwargs, observed)
            observed["process_exit"] = result.returncode
            if "runner" in observed:
                observed["bound_receipts"] = []
                for worker in observed["runner"]["workers"]:
                    for field in ["registration", "terminal_receipt"]:
                        bound = worker.get(field)
                        if bound:
                            raw = Path(bound["path"]).read_bytes()
                            observed["bound_receipts"].append({
                                "kind": field,
                                "sha256": batch.hashlib.sha256(raw).hexdigest(),
                                "expected": bound["sha256"],
                                "body": json.loads(raw),
                            })
            observed["git_core_longpaths_after"] = old_run(
                ["git", "-C", env["DESIGN_BATCH_ROOT"], "config", "--local", "core.longpaths"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            observed["events"] = (
                [json.loads(line) for line in Path(env["NATIVE_SETUP_EVENTS"]).read_text().splitlines()]
                if Path(env["NATIVE_SETUP_EVENTS"]).exists()
                else []
            )
            observed["setup"] = []
            for file in (folder / "original/data-collection/outbox").glob("production-setup-*/receipt.json"):
                receipt = json.loads(file.read_text())
                configs = list(file.parent.glob("config.json.*.json"))
                observed["setup"].append({
                    "receipt": receipt,
                    "configs": [json.loads(p.read_text()) for p in configs],
                    "outputs": [
                        Path(j["worktree"], "fixture-input.txt").read_text()
                        if Path(j["worktree"], "fixture-input.txt").exists()
                        else None
                        for j in receipt["jobs"]
                    ],
                })
            observed["manual_config_absent"] = not (folder / "parallel-config.json").exists()
            return result
        finally:
            stop.set()
            thread.join()
    return old_run(command, *args, **kwargs)


batch.subprocess.run = run

if __name__ == "__main__":
    # Base fixture assertions concern serial review and intentionally do not
    # represent this scenario. Retain them as diagnostics; evaluate our scope.
    try:
        batch.main()
    except SystemExit:
        pass
    output = Path(sys.argv[sys.argv.index("--out") + 1])
    base = json.loads(output.read_text(encoding="utf8"))
    starts = [e for e in observed.get("events", []) if e["phase"] == "start"]
    finishes = [e for e in observed.get("events", []) if e["phase"] == "finish"]
    setups = observed.get("setup", [])
    valid = (
        observed.get("process_exit") == 0
        and base.get("editor", {}).get("ok")
        and not base.get("errors")
        and observed.get("manual_config_absent")
        and len(setups) == 1
        and len(starts) == len(finishes) == 2
        and all(event.get("editor_runtime_bound") is True for event in starts)
        and len([e for e in observed.get("events", []) if e["phase"] == "discovery"]) >= 2
        and max(e["time"] for e in starts) < min(e["time"] for e in finishes)
        and all(
            w.get("state") == "review" and w.get("transport_completed") is True and w.get("exitCode") == 0
            for w in observed.get("runner", {}).get("workers", [])
        )
        and all(content and "actual normal native setup worker" in content for content in setups[0]["outputs"])
        and setups[0]["configs"][0]["capacity"] == 2
    )
    valid = valid and observed.get("git_core_longpaths_after") == "true"
    if GAME_WORKSPACE:
        valid = valid and all(
            observed.get("ordinary_game", {}).get(key) is True
            for key in ["host_separate_from_project", "forbidden_host_paths_absent"]
        )
    if REBIND_PYTHON:
        valid = (
            valid
            and len([e for e in observed.get("events", []) if e["phase"] == "discovery"]) >= 3
            and len(setups[0]["configs"]) == 2
            and any(Path(c["python"]).resolve() == Path(REBIND_PYTHON) for c in setups[0]["configs"])
        )
    valid = (
        valid
        and len(observed.get("bound_receipts", [])) == 4
        and all(r["sha256"] == r["expected"] for r in observed["bound_receipts"])
    )
    if COMPLETE_GAME:
        valid = valid and game_integration.valid(observed, acceptance)
    if REVIEW_RECOVERY:
        diagnostics = json.loads(output.with_suffix(".diagnostics-report.json").read_text(encoding="utf8"))
        native_review_recovery.validate(observed, diagnostics)
    output.write_text(
        json.dumps(
            {
                "ok": bool(valid),
                "backend": BACKEND,
                "rebind_python": bool(REBIND_PYTHON),
                "game_workspace": GAME_WORKSPACE,
                "complete_game": COMPLETE_GAME,
                "git_core_longpaths_before": False,
                "scope": game_integration.__doc__ if COMPLETE_GAME else __doc__,
                "observed": observed,
                "base_diagnostics": base,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf8",
    )
    print(
        json.dumps({
            "native_production_setup": bool(valid),
            "backend": BACKEND,
            "scope": "controlled setup, independent review, integration, game execution and rollback"
            if COMPLETE_GAME
            else "normal setup and worker transport, not business acceptance",
        })
    )
    raise SystemExit(0 if valid else 1)
