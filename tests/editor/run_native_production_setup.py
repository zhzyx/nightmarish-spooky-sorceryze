"""Normal native production controls, real setup/runner, isolated CLI transport.

The HTTP design and GitHub authority transports come from native acceptance.
Codex/CodeBuddy discovery uses shipped bridges and protocol fixtures. Worker
commands execute real isolated processes. This test stops before independent
review: provider authentication/model quality/business acceptance are excluded.
No production config, worktree mapping or ledger is supplied by the fixture.
"""

import base64
import json
import sys
from pathlib import Path
from typing import Any

import native_acceptance_parallel as parallel
import run_native_acceptance as acceptance

PREPARED_JOB_RECOVERY = ""
if "--prepared-job-recovery" in sys.argv:
    at = sys.argv.index("--prepared-job-recovery")
    PREPARED_JOB_RECOVERY = sys.argv[at + 1]
    del sys.argv[at : at + 2]
    if PREPARED_JOB_RECOVERY not in {"warm", "cold", "config-drift", "legacy"}:
        raise SystemExit("Unknown prepared job recovery boundary")
    sys.argv.append("--repair-reuse")

LEGACY_GODOT = None
if "--legacy-godot" in sys.argv:
    at = sys.argv.index("--legacy-godot")
    LEGACY_GODOT = Path(sys.argv[at + 1]).resolve()
    del sys.argv[at : at + 2]
if (PREPARED_JOB_RECOVERY == "legacy") != (LEGACY_GODOT is not None):
    raise SystemExit("Legacy recovery requires an explicit old native binary")

REPAIR_REUSE_MIXED = "--repair-reuse-mixed" in sys.argv
if REPAIR_REUSE_MIXED:
    sys.argv.remove("--repair-reuse-mixed")
    sys.argv.append("--repair-reuse")

REPAIR_REUSE_FAULT = ""
if "--repair-reuse-fault" in sys.argv:
    at = sys.argv.index("--repair-reuse-fault")
    REPAIR_REUSE_FAULT = sys.argv[at + 1]
    del sys.argv[at : at + 2]
    if REPAIR_REUSE_FAULT not in {"config-race", "missing-config"}:
        raise SystemExit("Unknown repair configuration boundary")
    sys.argv.append("--repair-reuse")

REPAIR_REUSE = "--repair-reuse" in sys.argv
if REPAIR_REUSE:
    sys.argv.remove("--repair-reuse")
    sys.argv.append("--game-workspace")

PREPARATION_RECOVERY = ""
if "--preparation-recovery" in sys.argv:
    at = sys.argv.index("--preparation-recovery")
    PREPARATION_RECOVERY = sys.argv[at + 1]
    del sys.argv[at : at + 2]
    if PREPARATION_RECOVERY not in {
        "warm",
        "cold",
        "missing-result",
        "cancel",
        "malformed-result",
        "cold-running",
        "cancel-missing",
        "baseline",
    }:
        raise SystemExit("Unknown preparation recovery boundary")

REVIEW_RECOVERY = ""
if "--review-recovery" in sys.argv:
    at = sys.argv.index("--review-recovery")
    REVIEW_RECOVERY = sys.argv[at + 1]
    del sys.argv[at : at + 2]
    if REVIEW_RECOVERY not in {"warm", "cold"}:
        raise SystemExit("--review-recovery must be warm or cold")
    sys.argv.append("--complete-game")

BACKEND = "codebuddy"
GAME_WORKSPACE = "--game-workspace" in sys.argv or PREPARATION_RECOVERY == "baseline"
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
if REPAIR_REUSE_MIXED:
    batch.FINALIZED += "6. DESIGN_BATCH_CHILD_3 depends only on independently accepted B\n- 依赖: 4\n- 验收: C | fixture-input.txt was read successfully\n"
if PREPARED_JOB_RECOVERY:
    batch.FINALIZED += "6. DESIGN_BATCH_CHILD_3 requires independently accepted A and B\n- 依赖: 2, 4\n- 验收: C | fixture-input.txt was read successfully\n"
observed: dict[str, Any] = {}

CLI = r"""import fs from 'node:fs';
import crypto from 'node:crypto';
import readline from 'node:readline';
const events=process.env.NATIVE_SETUP_EVENTS;
const event=(phase, extra={})=>fs.appendFileSync(events,JSON.stringify({phase,pid:process.pid,time:Date.now(),root:process.cwd(),...extra})+'\n');
const discover=async()=>{
  event('discovery');
  const count=fs.readFileSync(events,'utf8').trim().split('\n').map(JSON.parse).filter(e=>e.phase==='discovery').length;
  if(process.env.NATIVE_PREPARATION_MODE && count===2){
    event('preparation-discovery-started');
    fs.writeFileSync(process.env.NATIVE_PREPARATION_CONTROL+'/started','ready');
    while(!fs.existsSync(process.env.NATIVE_PREPARATION_CONTROL+'/release'))await new Promise(resolve=>setTimeout(resolve,20));
    if(!process.env.NATIVE_PREPARATION_MODE.startsWith('cancel') && process.env.NATIVE_PREPARATION_MODE!=='baseline')process.exit(17);
  }
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

if REPAIR_REUSE:
    import native_game_integration as repair_transport
    import native_preparation_repair

    if BACKEND != "codex" or COMPLETE_GAME or PREPARATION_RECOVERY:
        raise SystemExit("--repair-reuse requires Codex and its own native scenario")
    CLI = (
        repair_transport
        .cli(CLI)
        .replace("process.env.DESIGN_BATCH_ENDPOINT+'/chat/completions'", "process.env.DESIGN_BATCH_ENDPOINT")
        .replace(
            "event('finish');console.log",
            "if(prompt.includes('Bound failed review data')||prompt.includes('Bound missing execution evidence'))fs.writeFileSync('repair-evidence.txt','actual repaired execution');\n  event('finish');console.log",
        )
    )
    if PREPARED_JOB_RECOVERY:
        import native_prepared_job_recovery

        native_prepared_job_recovery.install(
            batch,
            observed,
            foreign_job=PREPARED_JOB_RECOVERY == "config-drift",
            warm=PREPARED_JOB_RECOVERY == "warm",
            legacy=PREPARED_JOB_RECOVERY == "legacy",
        )
    else:
        native_preparation_repair.install(batch, observed, REPAIR_REUSE_FAULT, REPAIR_REUSE_MIXED)

CONTROL = """
var setup_confirmation_started := false
func _confirm_normal_setup(confirmation):
\tif setup_confirmation_started:
\t\treturn
\tsetup_confirmation_started = true
\tawait _select_normal_setup_951()
\tconfirmation.get_ok_button().pressed.emit()
\tif not OS.get_environment("NATIVE_SETUP_REBIND").is_empty():
\t\tif not await _wait_file("setup-discovery-ready", 45.0):
\t\t\t_finish()
\t\t\treturn
\t\t_check(dock.set_runtime_field("workflow_python", OS.get_environment("NATIVE_SETUP_REBIND")).is_empty(), "Cannot change Python during preparation")
\t\t_file("setup-discovery-release")

func _setup_catalog_ready_951(snapshot: Dictionary, backend_index: int) -> bool:
\tif snapshot.get("state", "") != "ready" or not snapshot.get("catalog_current", false) or snapshot.get("loading", true) or int(snapshot.get("backend", -1)) != backend_index:
\t\treturn false
\tvar source := "codex_model_list" if backend_index == 2 else "codebuddy_model_list"
\tfor option in snapshot.get("options", []):
\t\tif option.get("id", "") == "fixture-native-setup" and option.get("source", "") == source:
\t\t\treturn true
\treturn false

func _setup_selection_snapshot_951(phase: String) -> Dictionary:
\tvar ai = dock.get_ai_settings_control()
\tvar view = dock.find_child("ChatLayout", true, false)
\tvar record := {"phase": phase, "catalog": dock.get_model_catalog_snapshot(), "backend": view.find_child("AIBackend", true, false).selected, "capacity": ai.find_child("ProductionCapacity", true, false).text, "continue_enabled": not dock.find_child("SpawnWorkOrderAgents", true, false).disabled}
\tvar control := OS.get_environment("NATIVE_PREPARATION_CONTROL")
\tif not control.is_empty():
\t\tFileAccess.open(control.path_join("catalog-probe-" + str(Time.get_ticks_usec()) + ".json"), FileAccess.WRITE).store_string(JSON.stringify(record))
\treturn record

func _select_normal_setup_951():
\tif not OS.get_environment("NATIVE_PREPARATION_NODE").is_empty():
\t\t_check(dock.set_runtime_field("node", OS.get_environment("NATIVE_PREPARATION_NODE")).is_empty(), "Cannot set isolated native helper transport")
\tvar ai = dock.get_ai_settings_control()
\tvar env = dock.get_environment_settings_control()
\tenv.find_child("CLIEntry", true, false).text = OS.get_environment("NATIVE_SETUP_CLI")
\tenv.find_child("CLIBridge", true, false).text = OS.get_environment("NATIVE_SETUP_BRIDGE")
\tvar view = dock.find_child("ChatLayout", true, false)
\tif not _check(view != null, "Normal setup requires live ChatLayout under AI Chat"):
\t\t_finish()
\t\treturn
\tvar backend = view.find_child("AIBackend", true, false)
\tif not _check(backend != null, "Normal setup connection selector missing from ChatLayout"):
\t\t_finish()
\t\treturn
\tvar backend_index := 2 if OS.get_environment("NATIVE_SETUP_BACKEND") == "codex" else 1
\tif backend_index == 2:
\t\t_check(dock.set_runtime_field("codex", OS.get_environment("NATIVE_SETUP_CLI")).is_empty(), "Cannot set private Codex fixture")
\t\tenv.find_child("CodexEntry", true, false).text = OS.get_environment("NATIVE_SETUP_CLI")
\tbackend.select(backend_index)
\tbackend.item_selected.emit(backend_index)
\tvar picker = view.find_child("ModelPicker", true, false)
\tif not _check(picker != null, "Normal setup model selector missing from ChatLayout"):
\t\t_finish()
\t\treturn
\tvar deadline := Time.get_ticks_msec() + 45000
\tvar found := -1
\twhile found < 0 and Time.get_ticks_msec() < deadline:
\t\tvar snapshot: Dictionary = dock.get_model_catalog_snapshot()
\t\tif _setup_catalog_ready_951(snapshot, backend_index):
\t\t\tfor index in range(picker.item_count):
\t\t\t\tif str(picker.get_item_metadata(index)) == "fixture-native-setup":
\t\t\t\t\tfound = index
\t\tif found < 0:
\t\t\tawait create_timer(0.05).timeout
\tif not _check(found >= 0, "CLI model discovery did not provide a current ready catalog"):
\t\t_setup_selection_snapshot_951("selection_failed")
\t\t_finish()
\t\treturn
\tpicker.select(found)
\tpicker.item_selected.emit(found)
\tai.find_child("ProductionSetup", true, false).button_pressed = true
\tai.find_child("ProductionCapacity", true, false).text = "2"
\tvar selected := _setup_selection_snapshot_951("selected")
\t_check(_setup_catalog_ready_951(selected.catalog, backend_index) and selected.catalog.get("current", "") == "fixture-native-setup" and int(selected.backend) == backend_index and selected.capacity == "2", "Selected model or capacity did not match the ready catalog")
\t_check(EditorInterface.get_editor_settings().get_setting("ai_chat/parallel_work_orders_config") == "", "Manual configuration unexpectedly present")

"""

PREPARATION_CONTROL = """
func _preparation_records_951() -> Dictionary:
\tif dock.get_meta("history_saving", false):
\t\treturn {}
\tvar value = JSON.parse_string(FileAccess.get_file_as_string("res://.godot/editor/ai_chat_history.json"))
\tvar records := {}
\tif value is Dictionary:
\t\tfor agent in value.get("agents", []):
\t\t\tvar child: Dictionary = agent.get("sub_agent", {})
\t\t\tif child.has("production_preparation"):
\t\t\t\trecords[str(agent.id)] = child
\treturn records

func _preparation_requests_951() -> Array:
\tvar files := []
\tvar folder: String = dock.get_production_workspace().path_join("data-collection/outbox")
\tfor name in DirAccess.get_files_at(folder):
\t\tif name.begins_with("setup-") and name.ends_with(".json") and not name.ends_with(".result.json"):
\t\t\tfiles.append(name)
\treturn files

func _preparation_save_probe_951(before: Dictionary, cold_restore := false, request_count := 1) -> bool:
\tvar stats_before: Dictionary = dock.get_meta("history_save_stats", {}).duplicate(true)
\tvar count: int = stats_before.get("count", 0)
\tvar input = dock.find_child("ChatInput", true, false)
\tinput.text = "Draft only: do not retry preparation " + str(count)
\tinput.text_changed.emit()
\tvar deadline := Time.get_ticks_msec() + 15000
\twhile (int(dock.get_meta("history_save_stats", {}).get("count", 0)) <= count or dock.get_meta("history_saving", false)) and Time.get_ticks_msec() < deadline:
\t\tawait process_frame
\tvar stats_after: Dictionary = dock.get_meta("history_save_stats", {}).duplicate(true)
\tvar saving: bool = dock.get_meta("history_saving", false)
\tvar expected := before.duplicate(true)
\tif cold_restore:
\t\tfor child in expected.values():
\t\t\tif child.state == "waiting":
\t\t\t\tchild.state_before_restore = "waiting"
\t\t\t\tchild.state = "interrupted"
\tvar after := _preparation_records_951()
\tvar requests := _preparation_requests_951()
\tFileAccess.open(OS.get_environment("NATIVE_PREPARATION_CONTROL").path_join("save-probe-" + str(Time.get_ticks_usec()) + ".json"), FileAccess.WRITE).store_string(JSON.stringify({"before": before, "expected": expected, "after": after, "requests": requests, "count_before": count, "count_after": stats_after.get("count", 0), "stats_before": stats_before, "stats_after": stats_after, "history_saving": saving}))
\treturn _check(int(stats_after.get("count", 0)) > count and not saving and int(stats_after.get("error", -1)) == OK and after == expected and requests.size() == request_count, "History save failed, retried or changed blocked preparation")

func _preparation_recovery_951(cold := false):
\tvar control := OS.get_environment("NATIVE_PREPARATION_CONTROL")
\tvar mode := OS.get_environment("NATIVE_PREPARATION_MODE")
\tvar deadline := Time.get_ticks_msec() + 90000
\tif not cold:
\t\twhile not FileAccess.file_exists(control.path_join("started")) and Time.get_ticks_msec() < deadline:
\t\t\tawait process_frame
\t\tif not _check(FileAccess.file_exists(control.path_join("started")), "Actual setup discovery did not start"):
\t\t\t_finish()
\t\t\treturn
\t\tif mode.begins_with("cancel"):
\t\t\tif not _check(not dock.find_child("Stop", true, false).disabled, "Started setup Stop unavailable"):
\t\t\t\t_finish()
\t\t\t\treturn
\t\t\tdock.find_child("Stop", true, false).pressed.emit()
\t\tif mode == "missing-result":
\t\t\twhile not FileAccess.file_exists(control.path_join("obstruction-ready")) and Time.get_ticks_msec() < deadline:
\t\t\t\tawait process_frame
\t\t\tif not _check(FileAccess.file_exists(control.path_join("obstruction-ready")), "Actual setup result storage obstruction not installed"):
\t\t\t\t_finish()
\t\t\t\treturn
\t\tFileAccess.open(control.path_join("release"), FileAccess.WRITE).store_string("release controlled discovery")
\tif mode == "cold-running" and not cold:
\t\twhile not FileAccess.file_exists(control.path_join("fault-result.json")) and Time.get_ticks_msec() < deadline:
\t\t\tawait process_frame
\t\tif not _check(FileAccess.file_exists(control.path_join("fault-result.json")), "Actual setup never reached the held result boundary"):
\t\t\t_finish()
\t\t\treturn
\tvar records := {}
\tvar expected_state := "running" if mode == "cold-running" else "cancelled" if mode.begins_with("cancel") else "blocked"
\tvar unknown_result := mode in ["missing-result", "malformed-result", "cold-running", "cancel-missing"]
\twhile Time.get_ticks_msec() < deadline:
\t\trecords = _preparation_records_951()
\t\tif records.size() == 2 and not dock.get_meta("history_saving", false):
\t\t\tvar attempt: Dictionary = records.values()[0].production_preparation
\t\t\tif attempt.state == expected_state and (unknown_result or attempt.launch_state == "completed"):
\t\t\t\tbreak
\t\tawait process_frame
\tif not _check(records.size() == 2 and records.values()[0].production_preparation.state == expected_state, "Preparation terminal gate was not persisted"):
\t\t_finish()
\t\treturn
\tif mode == "cancel-missing":
\t\tvar fault_finished := false
\t\twhile Time.get_ticks_msec() < deadline:
\t\t\tif FileAccess.file_exists(control.path_join("fault-result.json")) and FileAccess.file_exists(control.path_join("actual-setup-result.json")):
\t\t\t\tvar fault = JSON.parse_string(FileAccess.get_file_as_string(control.path_join("fault-result.json")))
\t\t\t\tif fault is Dictionary and fault.get("original_state", "") == "ready" and fault.get("actual_setup_exit", -1) == 0 and not OS.is_process_running(int(fault.get("wrapper_pid", -1))):
\t\t\t\t\tfault_finished = true
\t\t\t\t\tbreak
\t\t\tawait process_frame
\t\tif not _check(fault_finished and not FileAccess.file_exists(records.values()[0].production_preparation.result_path), "Cancelled setup did not finish its actual withheld-result boundary"):
\t\t\t_finish()
\t\t\treturn
\t\tvar cancelled_attempt: String = records.values()[0].production_preparation.attempt_id
\t\tvar host_observed_exit := false
\t\twhile Time.get_ticks_msec() < deadline:
\t\t\trecords = _preparation_records_951()
\t\t\thost_observed_exit = records.size() == 2 and not dock.get_meta("history_saving", false)
\t\t\tfor child in records.values():
\t\t\t\tvar attempt: Dictionary = child.production_preparation
\t\t\t\thost_observed_exit = host_observed_exit and attempt.attempt_id == cancelled_attempt and attempt.state == "cancelled" and attempt.launch_state == "unknown" and attempt.reason == "preparation_completed_after_parent_changed"
\t\t\tif host_observed_exit:
\t\t\t\tbreak
\t\t\tawait process_frame
\t\tif not _check(host_observed_exit, "Native host did not persist the actual cancelled wrapper exit"):
\t\t\t_finish()
\t\t\treturn
\tif not await _preparation_save_probe_951(records, cold):
\t\t_finish()
\t\treturn
\trecords = _preparation_records_951()
\tif not await _preparation_save_probe_951(records):
\t\t_finish()
\t\treturn
\tFileAccess.open(control.path_join("cold-held" if cold else "warm-held"), FileAccess.WRITE).store_string(JSON.stringify(records))
\tif mode in ["cold", "cold-running", "baseline"] and not cold:
\t\t_finish()
\t\treturn
\tif mode.begins_with("cancel"):
\t\t_check(_preparation_requests_951().size() == 1, "Cancelled setup dispatched after late ready result")
\t\t_finish()
\t\treturn
\tvar setup = dock.get_ai_settings_control().find_child("ProductionSetup", true, false)
\tvar resume = dock.find_child("SpawnWorkOrderAgents", true, false)
\tif not _check(not resume.disabled, "Explicit preparation Continue unavailable"):
\t\t_finish()
\t\treturn
\tsetup.button_pressed = false
\tresume.pressed.emit()
\tawait process_frame
\tif not await _preparation_save_probe_951(records):
\t\t_finish()
\t\treturn
\tsetup.button_pressed = true
\tif cold:
\t\tawait _select_normal_setup_951()
\t\tif not await _preparation_save_probe_951(records):
\t\t\t_finish()
\t\t\treturn
\tif not _check(not resume.disabled, "Preparation retry control disabled"):
\t\t_finish()
\t\treturn
\tif mode == "cold-running":
\t\t_check(not OS.is_process_running(int(records.values()[0].production_preparation.process_id)), "Prior setup process is still live after cold restart")
\tvar selection := _setup_selection_snapshot_951("before_continue")
\tvar selected_backend := 2 if OS.get_environment("NATIVE_SETUP_BACKEND") == "codex" else 1
\tif not _check(_setup_catalog_ready_951(selection.catalog, selected_backend) and selection.catalog.get("current", "") == "fixture-native-setup" and int(selection.backend) == selected_backend and selection.capacity == "2", "Continue model catalog or capacity is not ready"):
\t\t_finish()
\t\treturn
\tresume.pressed.emit()
\tawait process_frame
\tif unknown_result:
\t\tawait _preparation_save_probe_951(records)
\t\t_check("preparation_launch_outcome_unknown" in _text(), "Missing actual result was treated as known terminal")
\t\t_finish()
\t\treturn
\tif mode == "baseline":
\t\tvar prior_attempt: String = records.values()[0].production_preparation.attempt_id
\t\twhile Time.get_ticks_msec() < deadline:
\t\t\tvar next := _preparation_records_951()
\t\t\tif next.size() == 2 and next.values()[0].production_preparation.attempt_id != prior_attempt and next.values()[0].production_preparation.state == "blocked" and next.values()[0].production_preparation.launch_state == "completed" and not dock.get_meta("history_saving", false):
\t\t\t\trecords = next
\t\t\t\tbreak
\t\t\tawait process_frame
\t\t_check(records.values()[0].production_preparation.attempt_id != prior_attempt, "Explicit baseline retry never reached a distinct actual result")
\t\tawait _preparation_save_probe_951(records, false, 2)
\telse:
\t\tawait _wait_file("native-setup-runner-finished", 150.0)
\t_check(_preparation_requests_951().size() == 2, "Explicit Continue did not own exactly one new preparation")
\t_finish()
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
        if REPAIR_REUSE:
            script = script.replace(
                'await _wait_file("native-setup-runner-finished", 150.0)',
                "await _wait_repair_reuse_951()",
            )
            script += native_preparation_repair.CONTROL
        if PREPARED_JOB_RECOVERY:
            script = script.replace("await _wait_repair_reuse_951()", "await _prepared_job_recovery_951()", 1)
            anchor = '\tif OS.get_environment("DESIGN_BATCH_PHASE") == "review-restore":'
            assert script.count(anchor) == 1
            script = script.replace(
                anchor,
                '\tif OS.get_environment("DESIGN_BATCH_PHASE") == "prepared-job-cold":\n\t\tawait _prepared_job_recovery_951(true)\n\t\treturn\n'
                + anchor,
                1,
            )
            script += native_prepared_job_recovery.CONTROL
        if COMPLETE_GAME:
            script = game_integration.control(script)
            if REVIEW_RECOVERY:
                script = native_review_recovery.control(script, REVIEW_RECOVERY)
        if PREPARATION_RECOVERY:
            script = script.replace(
                '\tawait _wait_file("native-setup-runner-finished", 150.0)\n\t_finish()',
                "\tawait _preparation_recovery_951()",
                1,
            )
            anchor = '\tif OS.get_environment("DESIGN_BATCH_PHASE") == "review-restore":'
            assert script.count(anchor) == 1
            script = script.replace(
                anchor,
                '\tif OS.get_environment("DESIGN_BATCH_PHASE") == "preparation-cold":\n\t\tawait _preparation_recovery_951(true)\n\t\treturn\n'
                + anchor,
                1,
            )
            script += PREPARATION_CONTROL
        Path(target).write_text(script, encoding="utf8")
    return result


batch.shutil.copyfile = copy

old_run = batch.subprocess.run


def legacy_setup_processes(folder):
    """Read actual Windows process identity; never terminate a setup process."""
    assert batch.os.name == "nt", "The explicit old Windows native requires Windows process observations"
    script = """
$ErrorActionPreference = 'Stop'
$records = @(Get-CimInstance Win32_Process -Filter "Name='node.exe'" | ForEach-Object {
    @{pid=$_.ProcessId; parent=$_.ParentProcessId; executable=$_.ExecutablePath;
      started=$_.CreationDate.ToUniversalTime().ToString('o'); command=$_.CommandLine}
})
ConvertTo-Json -InputObject $records -Depth 4 -Compress
"""
    result = old_run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf8",
        timeout=20,
    )
    records = json.loads(result.stdout)
    assert isinstance(records, list)
    root = str(folder.resolve()).replace("\\", "/").lower() + "/"
    return [
        record
        for record in records
        if root in str(record.get("command", "")).replace("\\", "/").lower()
        and "/tools/godot_parallel/setup.mjs" in str(record.get("command", "")).replace("\\", "/").lower()
    ]


def preserve_prepared_receipts(folder, observed, output):
    """Keep this isolated consumer's actual oracle inputs before automatic cleanup."""
    destination = output.with_suffix(".private-artifacts")
    destination.mkdir(exist_ok=True)
    objects = destination / "objects"
    objects.mkdir(exist_ok=True)
    records = []
    for relative in (
        "original/data-collection/outbox",
        "original/samples/project/.godot/editor",
        "prepared-job-recovery",
        "prepared-job-control",
        "installation/isolated-editor/editor_data/cache/gonggong-dependency-evidence",
    ):
        directory = folder / relative
        if not directory.exists():
            continue
        for path in directory.rglob("*"):
            if (
                path.is_symlink()
                or not path.is_file()
                or (
                    relative not in {"prepared-job-recovery", "prepared-job-control"}
                    and path.suffix not in {".json", ".txt", ".jsonl"}
                )
            ):
                continue
            assert path.resolve().is_relative_to(folder.resolve())
            assert path.stat().st_size <= 32 * 1024 * 1024
            raw = path.read_bytes()
            digest = batch.hashlib.sha256(raw).hexdigest()
            target = objects / digest
            if not target.exists():
                target.write_bytes(raw)
            records.append({
                "path": str(path),
                "bytes": len(raw),
                "sha256": digest,
                "copied_at_ns": batch.time.time_ns(),
            })
            assert len(records) <= 4096
    manifest = destination / "manifest.json"
    manifest.write_text(json.dumps(records, ensure_ascii=True, indent=2) + "\n", encoding="utf8", newline="\n")
    observed["private_receipt_archive"] = {
        "path": str(manifest),
        "sha256": batch.hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "files": len(records),
        "scope": "Actual isolated fixture bytes copied before cleanup, including failed attempts",
    }


def run_native_phase(command, args, kwargs, observed, phase):
    """Record the native outcome before any collector can raise another error."""
    record = {"phase": phase, "started_at_ns": batch.time.time_ns()}
    observed.setdefault("native_runs", []).append(record)
    try:
        result = old_run(command, *args, **kwargs)
        record.update(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr, timed_out=False)
        return result
    except batch.subprocess.TimeoutExpired as error:
        record["timed_out"] = True
        record["timeout_seconds"] = error.timeout
        for name in ("stdout", "stderr"):
            value = getattr(error, name)
            record[name] = (
                {"base64": base64.b64encode(value).decode("ascii"), "bytes": len(value)}
                if isinstance(value, bytes)
                else value
            )
        raise
    finally:
        record["finished_at_ns"] = batch.time.time_ns()
        report = Path(kwargs["env"]["DESIGN_BATCH_PROJECT"]) / "design-batch-report.json"
        if report.exists():
            raw = report.read_bytes()
            record["actual_report"] = {
                "path": str(report),
                "base64": base64.b64encode(raw).decode("ascii"),
                "bytes": len(raw),
                "sha256": batch.hashlib.sha256(raw).hexdigest(),
                "modified_at_ns": report.stat().st_mtime_ns,
                "written_during_phase": report.stat().st_mtime_ns >= record["started_at_ns"],
            }


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
        if REPAIR_REUSE:
            batch.os.environ["REPAIR_REUSE_WORKSPACE"] = env["DESIGN_BATCH_ROOT"]
            env["NATIVE_REPAIR_REUSE_FAULT"] = REPAIR_REUSE_FAULT
            env["NATIVE_REPAIR_REUSE_MIXED"] = "1" if REPAIR_REUSE_MIXED else "0"
        # The generic normal-case parser probe adds a dependency after FINALIZED
        # is assembled. This fixture explicitly tests two independent workers.
        env["DESIGN_BATCH_FINALIZED"] = env["DESIGN_BATCH_FINALIZED"].replace("   - 依赖：工单 2。\n", "")
        # Frozen installed adapters are byte-pinned. Only ordinary inputs such
        # as the design exercise Windows checkout conversion.
        Path(env["DESIGN_BATCH_ROOT"], ".gitattributes").write_text(
            "framework/** -text\nCURRENT_FRAMEWORK.json -text\ncustomizations/** -text\nintegrations/** -text\n",
            encoding="utf8",
        )
        old_run(["git", "-C", env["DESIGN_BATCH_ROOT"], "add", ".gitattributes"], check=True)
        if GAME_WORKSPACE:
            root = Path(env["DESIGN_BATCH_ROOT"])
            project = Path(env["DESIGN_BATCH_PROJECT"])
            # Match the normal Godot project wizard's Git metadata. Runtime
            # caches are not production inputs; source files and UID files are.
            (project / ".gitignore").write_text(".godot/\n", encoding="utf8", newline="\n")
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
        if PREPARED_JOB_RECOVERY:
            control = folder / "prepared-job-control"
            control.mkdir()
            env["NATIVE_PREPARED_CONTROL"] = str(control)
            env["NATIVE_PREPARED_FOREIGN"] = "1" if PREPARED_JOB_RECOVERY == "config-drift" else "0"
            env["NATIVE_PREPARED_WARM"] = "1" if PREPARED_JOB_RECOVERY == "warm" else "0"
            env["NATIVE_PREPARED_LEGACY"] = "1" if PREPARED_JOB_RECOVERY == "legacy" else "0"
            if PREPARED_JOB_RECOVERY in {"cold", "warm"}:
                import native_preparation_faults

                env["NATIVE_PREPARATION_CONTROL"] = str(control)
                native_preparation_faults.install(batch, env, folder, "observe")
        candidate_backup = None
        if LEGACY_GODOT is not None:
            binary = Path(command[0]).resolve()
            assert binary.is_relative_to(folder.resolve()) and not binary.name.endswith(".console.exe")
            candidate_backup = folder / "candidate-editor-before-legacy.exe"
            old_copy(binary, candidate_backup)
            old_copy(LEGACY_GODOT, binary)
            observed["legacy_native"] = {
                "old_sha256": batch.hashlib.sha256(binary.read_bytes()).hexdigest(),
                "candidate_sha256": batch.hashlib.sha256(candidate_backup.read_bytes()).hexdigest(),
                "host_scope": "Current isolated host tools with explicit old native, not a complete old installation",
            }
        if PREPARATION_RECOVERY or REPAIR_REUSE_FAULT:
            env["NATIVE_PREPARATION_MODE"] = PREPARATION_RECOVERY
            control = folder / "preparation-control"
            control.mkdir()
            env["NATIVE_PREPARATION_CONTROL"] = str(control)
            import native_preparation_faults

            native_preparation_faults.install(batch, env, folder, PREPARATION_RECOVERY or REPAIR_REUSE_FAULT)
        if COMPLETE_GAME:
            batch.os.environ["ORDINARY_GAME_BINARY"] = str(command[0])
            batch.os.environ["ORDINARY_GAME_PROJECT"] = env["DESIGN_BATCH_PROJECT"]
        kwargs["env"] = env
        stop = threading.Event()

        def monitor():
            while not stop.wait(0.2):
                if LEGACY_GODOT is not None and not (control / "legacy-quiescence-checked").exists():
                    try:
                        processes = legacy_setup_processes(folder)
                        observation = {
                            "at_ns": batch.time.time_ns(),
                            "processes": processes,
                            "quiescence_ready": (control / "legacy-quiescence-ready").exists(),
                        }
                        with (control / "legacy-process-observations.jsonl").open("a", encoding="utf8") as stream:
                            stream.write(json.dumps(observation, ensure_ascii=True) + "\n")
                        if observation["quiescence_ready"] and not processes:
                            acknowledgement = {
                                "ok": True,
                                "scope": "fixture_setup_processes",
                                "pending": [],
                                "observations": str(control / "legacy-process-observations.jsonl"),
                                "observations_sha256": batch.hashlib.sha256(
                                    (control / "legacy-process-observations.jsonl").read_bytes()
                                ).hexdigest(),
                                "at_ns": observation["at_ns"],
                            }
                            temporary = control / "legacy-quiescence-checked.tmp"
                            temporary.write_text(json.dumps(acknowledgement), encoding="utf8", newline="\n")
                            temporary.replace(control / "legacy-quiescence-checked")
                    except (OSError, ValueError, batch.subprocess.SubprocessError) as error:
                        observed["legacy_process_error"] = type(error).__name__
                if (
                    PREPARED_JOB_RECOVERY == "warm"
                    and (control / "warm-ready").exists()
                    and not (control / "warm-checked").exists()
                ):
                    native_prepared_job_recovery.prepare_resume(folder, observed)
                    (control / "warm-checked").touch()
                if (
                    PREPARED_JOB_RECOVERY
                    and (control / "cold-ready").exists()
                    and not (control / "cold-checked").exists()
                ):
                    try:
                        native_prepared_job_recovery.checkpoint(folder, observed, "cold")
                        (control / "cold-checked").touch()
                    except (OSError, ValueError, KeyError):
                        continue
                if REPAIR_REUSE_MIXED and "mixed_ready_boundary" not in observed:
                    history = Path(env["DESIGN_BATCH_PROJECT"], ".godot/editor/ai_chat_history.json")
                    try:
                        state = json.loads(history.read_text(encoding="utf8"))
                        children = {
                            int(a["sub_agent"]["number"]): a["sub_agent"]
                            for a in state["agents"]
                            if a.get("sub_agent", {}).get("source") == "design"
                        }
                        if (
                            children.get(2, {}).get("repair_of")
                            and children.get(2, {}).get("state") == "waiting"
                            and children.get(4, {}).get("acceptance")
                            and children.get(6, {}).get("state") == "waiting"
                        ):
                            observed["mixed_ready_boundary"] = children
                    except (OSError, ValueError, KeyError):
                        pass
                if PREPARATION_RECOVERY == "missing-result" and (control / "started").exists():
                    if not (control / "obstruction-ready").exists():
                        requests = list(
                            folder.glob(
                                "original/data-collection/outbox/setup-*.json"
                                if GAME_WORKSPACE
                                else "godot-candidate-*/data-collection/outbox/setup-*.json"
                            )
                        )
                        requests = [p for p in requests if not p.name.endswith(".result.json")]
                        if len(requests) == 1:
                            Path(str(requests[0]) + ".result.json").mkdir()
                            (control / "obstruction-ready").touch()
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
            result = run_native_phase(command, args, kwargs, observed, "initial")
            if PREPARED_JOB_RECOVERY == "warm":
                observed["prepared_job_recovery"]["single_exit"] = result.returncode
            elif PREPARED_JOB_RECOVERY and result.returncode == 0:
                native_prepared_job_recovery.prepare_restart(folder, observed, result.returncode)
                if candidate_backup is not None:
                    assert not observed.get("legacy_process_error")
                    assert not legacy_setup_processes(folder), "Legacy setup became active before native replacement"
                    old_copy(candidate_backup, command[0])
                    assert (
                        batch.hashlib.sha256(Path(command[0]).read_bytes()).hexdigest()
                        == observed["legacy_native"]["candidate_sha256"]
                    )
                result = run_native_phase(
                    command,
                    args,
                    dict(kwargs, env=dict(env, DESIGN_BATCH_PHASE="prepared-job-cold")),
                    observed,
                    "prepared-job-cold",
                )
                observed["prepared_job_recovery"]["second_exit"] = result.returncode
            if PREPARATION_RECOVERY in {"cold", "cold-running", "baseline"} and result.returncode == 0:
                first = json.loads(
                    Path(env["DESIGN_BATCH_PROJECT"], "design-batch-report.json").read_text(encoding="utf8")
                )
                assert first["ok"] and (control / "warm-held").exists(), first.get("failure")
                observed["preparation_first_editor"] = first
                before = Path(env["NATIVE_SETUP_EVENTS"]).read_bytes()
                result = old_run(command, *args, **dict(kwargs, env=dict(env, DESIGN_BATCH_PHASE="preparation-cold")))
                assert Path(env["NATIVE_SETUP_EVENTS"]).read_bytes().startswith(before)
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
            if PREPARED_JOB_RECOVERY:
                collected = native_prepared_job_recovery.collect(folder, observed)
                observed["prepared_job_oracle"] = {
                    "passed": collected and native_prepared_job_recovery.valid(observed),
                    "phase": "after_collect_before_fixture_cleanup",
                    "source_sha256": batch.hashlib.sha256(
                        Path(native_prepared_job_recovery.__file__).read_bytes()
                    ).hexdigest(),
                }
            elif REPAIR_REUSE:
                native_preparation_repair.collect(folder, observed)
            if PREPARATION_RECOVERY:
                observed["preparation_holds"] = {
                    name: json.loads((control / name).read_text(encoding="utf8"))
                    for name in ("warm-held", "cold-held")
                    if (control / name).exists()
                }
                observed["preparation_save_probes"] = [
                    json.loads(p.read_text(encoding="utf8")) for p in sorted(control.glob("save-probe-*.json"))
                ]
                observed["preparation_requests"] = []
                for path in sorted(
                    folder.glob(
                        "original/data-collection/outbox/setup-*.json"
                        if GAME_WORKSPACE
                        else "godot-candidate-*/data-collection/outbox/setup-*.json"
                    ),
                    key=lambda p: p.stat().st_mtime_ns,
                ):
                    if path.name.endswith(".result.json"):
                        continue
                    outcome = Path(str(path) + ".result.json")
                    result_value = None
                    malformed = False
                    if outcome.is_file():
                        try:
                            result_value = json.loads(outcome.read_text(encoding="utf8"))
                        except ValueError:
                            malformed = True
                    observed["preparation_requests"].append({
                        "request_sha256": batch.hashlib.sha256(path.read_bytes()).hexdigest(),
                        "result": result_value,
                        "result_invalid_json": malformed,
                        "result_sha256": batch.hashlib.sha256(outcome.read_bytes()).hexdigest()
                        if outcome.is_file()
                        else None,
                        "result_is_directory": outcome.is_dir(),
                    })
            if PREPARATION_RECOVERY:
                observed["baseline_attempts"] = [
                    json.loads(p.read_text(encoding="utf8")) for p in sorted(control.glob("baseline-attempt-*.json"))
                ]
                fault = control / "fault-result.json"
                if fault.exists():
                    observed["preparation_fault"] = json.loads(fault.read_text(encoding="utf8"))
                    original_result = (control / "actual-setup-result.json").read_bytes()
                    assert (
                        batch.hashlib.sha256(original_result).hexdigest()
                        == observed["preparation_fault"]["original_sha256"]
                    )
                    observed["preparation_fault"]["original_result"] = json.loads(original_result)
            return result
        finally:
            stop.set()
            thread.join()
            output = Path(sys.argv[sys.argv.index("--out") + 1])
            if PREPARATION_RECOVERY or PREPARED_JOB_RECOVERY in {"cold", "warm"}:
                observed.update(native_preparation_faults.collect_snapshot_traces(control))
                observed["preparation_catalog_probes"] = []
                for path in sorted(control.glob("catalog-probe-*.json")):
                    try:
                        observed["preparation_catalog_probes"].append(json.loads(path.read_text(encoding="utf8")))
                    except (OSError, ValueError) as error:
                        observed["preparation_catalog_probes"].append({
                            "file": path.name,
                            "error": type(error).__name__,
                        })
            if PREPARED_JOB_RECOVERY:
                if "prepared_job_oracle" not in observed:
                    error_type = sys.exc_info()[0]
                    observed["prepared_job_oracle"] = {
                        "passed": False,
                        "phase": "incomplete_before_fixture_cleanup",
                        "secondary_error": error_type.__name__ if error_type else None,
                    }
                try:
                    preserve_prepared_receipts(folder, observed, output)
                except (OSError, AssertionError) as error:
                    observed["private_receipt_archive_error"] = type(error).__name__
            output.with_suffix(".setup-observed.json").write_text(
                json.dumps(observed, ensure_ascii=False, indent=2), encoding="utf8"
            )
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
    if PREPARED_JOB_RECOVERY:
        valid = (
            observed.get("process_exit") == 0
            and base.get("editor", {}).get("ok")
            and not base.get("errors")
            and not observed.get("private_receipt_archive_error")
            and observed.get("prepared_job_oracle", {}).get("passed") is True
        )
    elif REPAIR_REUSE:
        valid = (
            observed.get("process_exit") == 0
            and base.get("editor", {}).get("ok")
            and not base.get("errors")
            and native_preparation_repair.valid(observed)
        )
    if COMPLETE_GAME:
        valid = valid and game_integration.valid(observed, acceptance)
    if REVIEW_RECOVERY:
        diagnostics = json.loads(output.with_suffix(".diagnostics-report.json").read_text(encoding="utf8"))
        native_review_recovery.validate(observed, diagnostics)
    if PREPARATION_RECOVERY:
        attempts = observed.get("preparation_requests", [])
        holds = observed.get("preparation_holds", {})
        held = holds.get("warm-held", {})
        assert len(held) == 2 and len({c["production_preparation"]["attempt_id"] for c in held.values()}) == 1
        assert len([e for e in observed["events"] if e["phase"] == "preparation-discovery-started"]) == 1
        if PREPARATION_RECOVERY == "baseline":
            baseline = observed["baseline_attempts"]
            valid = (
                observed.get("process_exit") == 0
                and base.get("editor", {}).get("ok")
                and not base.get("errors")
                and not starts
                and not finishes
                and len(attempts) == 2
                and len(holds.get("cold-held", {})) == 2
                and len(baseline) == 2
            )
            valid = valid and all(
                a["result"]["state"] == "blocked" and "Preparation baseline changed" in a["result"]["error"]
                for a in attempts
            )
            valid = (
                valid
                and all(a["original_references_unchanged"] and a["seed"]["seed_exit"] == 0 for a in baseline)
                and baseline[0]["seed"] == baseline[1]["seed"]
            )
        elif PREPARATION_RECOVERY in {"warm", "cold"}:
            valid = (
                valid
                and len(attempts) == 2
                and attempts[0]["result"]["state"] == "blocked"
                and attempts[1]["result"]["state"] == "ready"
            )
            if PREPARATION_RECOVERY == "cold":
                assert len(holds.get("cold-held", {})) == 2
        else:
            valid = (
                observed.get("process_exit") == 0
                and base.get("editor", {}).get("ok")
                and not base.get("errors")
                and not starts
                and not finishes
                and len(attempts) == 1
            )
            if PREPARATION_RECOVERY in {
                "missing-result",
                "malformed-result",
                "cold-running",
                "cancel-missing",
                "baseline",
            }:
                valid = valid and all(c["production_preparation"]["launch_state"] == "unknown" for c in held.values())
                if PREPARATION_RECOVERY == "missing-result":
                    valid = valid and attempts[0]["result_is_directory"]
                elif PREPARATION_RECOVERY == "malformed-result":
                    valid = (
                        valid
                        and attempts[0]["result_invalid_json"]
                        and observed["preparation_fault"]["original_state"] == "blocked"
                    )
                elif PREPARATION_RECOVERY == "cold-running":
                    valid = (
                        valid
                        and len(holds.get("cold-held", {})) == 2
                        and attempts[0]["result"] is None
                        and all(c["production_preparation"]["state"] == "running" for c in held.values())
                    )
                else:
                    valid = (
                        valid
                        and observed["preparation_fault"]["original_state"] == "ready"
                        and attempts[0]["result"] is None
                    )
            else:
                valid = (
                    valid
                    and attempts[0]["result"]["state"] == "ready"
                    and all(c["production_preparation"]["state"] == "cancelled" for c in held.values())
                )
    output.write_text(
        json.dumps(
            {
                "ok": bool(valid),
                "backend": BACKEND,
                "preparation_recovery": PREPARATION_RECOVERY,
                "repair_reuse": REPAIR_REUSE,
                "prepared_job_recovery": PREPARED_JOB_RECOVERY,
                "rebind_python": bool(REBIND_PYTHON),
                "game_workspace": GAME_WORKSPACE,
                "complete_game": COMPLETE_GAME,
                "git_core_longpaths_before": False,
                "scope": native_prepared_job_recovery.__doc__
                if PREPARED_JOB_RECOVERY
                else native_preparation_repair.__doc__
                if REPAIR_REUSE
                else "Actual native preparation failure, persistence, explicit retry and cancellation with controlled CLI transport; no original production or business acceptance"
                if PREPARATION_RECOVERY
                else game_integration.__doc__
                if COMPLETE_GAME
                else __doc__,
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
            "scope": "controlled native setup and existing repair with actual independent source acceptance, not full parent/business completion"
            if REPAIR_REUSE
            else "controlled native preparation recovery, not business acceptance"
            if PREPARATION_RECOVERY
            else "controlled setup, independent review, integration, game execution and rollback"
            if COMPLETE_GAME
            else "normal setup and worker transport, not business acceptance",
        })
    )
    raise SystemExit(0 if valid else 1)
