@tool
extends SceneTree

var checks := []
var failures := []
var processes := []
var diagnostics := {}
const ISSUE := "https://github.com/fixture/project/issues/42"
const HELPERS := "customizations/components/godot-host/daqian/"
const HEADER := '''extends RefCounted
const HOST_RECEIPT_POLL_SECONDS := 0.01
const DEBUG_MODELS := ["调试 · GPT"]
var actor := {"user_id":"42","repo_id":"1"}
var offline := false
var board := {"repo":"fixture/project"}
var editor_session := "private-session"
var scope_epoch := 1
var selection_epoch := 1
var forgotten := 0
var root_path := ProjectSettings.globalize_path("res://project-data")
var host_path := ProjectSettings.globalize_path("res://installed-host")
var watcher_exited := false
var watcher := {}
var watch_config := {}
var watcher_error := ""
var progress_directory := ""
var notice := {"text":""}
var current := "https://github.com/fixture/project/issues/42"
var debug_sessions := {}
var debug_serial := 0
var debug_buffer := PackedByteArray()
var debug_process := {}
var debug_timer := DummyTimer.new()
var editor := DummyEditor.new()
var rules := DummyRules.new()
class DummyTimer:
    extends RefCounted
    func start(): pass
class DummyRules:
    extends RefCounted
    func new_plan() -> Dictionary: return {"nodes":{},"edges":[]}
    func reconcile_snapshot(_a, _b, _c) -> Dictionary: return {}
    func changes_error(_a, _b, _c) -> String: return ""
class DummyEditor:
    extends RefCounted
    var revision := "rev1"
    var applying := false
    var answers := {}
    var workflow := {}
    func refresh_states(): pass
    func await_graph_projection(): pass
    var context := {}
    var baseline := {}
    var draft := {"nodes":{"task":{"kind":"task","title":"Local fixture","value":"fixture"}},"edges":[]}
    var debug_models := {"task":"调试 · GPT"}
    var debug_active := false
    func draw_graph(_preserve = false): pass
func get_tree(): return Engine.get_main_loop()
func _repo() -> String: return root_path
func _host_root() -> String: return host_path
func _runtime_paths() -> Dictionary: return JSON.parse_string(FileAccess.get_file_as_string("res://fixture.json"))
func _fresh_access() -> bool: return true
func _forget(_reason: String):
    forgotten += 1
    actor = {}
    selection_epoch += 1
    scope_epoch += 1
func _select_debug(_target): pass
func _sync_debug_actions(): pass
'''
const CALLER_HEADER := '''
var host: Object
var loading_project := false
var project_mode := false
var project_snapshot := {"user_id":"42","repo_id":"1"}
var personal_snapshot := {}
var scope_picker := DummyWidget.new()
var project_anchor := DummyWidget.new()
var search := DummyWidget.new()
var status := DummyWidget.new()
var creator_filter := DummyWidget.new()
var overview := DummyWidget.new()
var zoom_anchor := Vector2.ZERO
var zoom_crossed := false
var far_depth := 0.0
class DummyWidget:
    extends RefCounted
    var zoom := 0.0
    var scroll_offset := Vector2.ZERO
    func select(_index): pass
    func hide(): pass
    func clear(): pass
func _board_command(_access, _user, _project = false) -> Dictionary: return {}
func _note_layer_read(_project, _response): pass
func _leave_issue_inspector(): pass
func _draw_board(): pass
func _show_issue(target, snapshot):
    current = target
    editor.revision = snapshot.revision
    selection_epoch += 1
func _sync_workflow(_arg = false): pass
func _queue_save(): pass
'''
const DELAYED_TRANSPORT := '''
signal release
var calls := []
var delayed := false
func _host_command(args: PackedStringArray, flag: String, request: Dictionary) -> Dictionary:
    calls.append({"args":args,"flag":flag,"request":request.duplicate(true)})
    if delayed: await release
    return {"denied":delayed,"error":"controlled denial"}
'''

func _initialize():
	create_timer(60.0).timeout.connect(func():
		failures.append("native routing test timed out")
		finish())
	run.call_deferred()

func check(condition: bool, name: String):
	if condition:
		checks.append(name)
	else:
		failures.append(name)
		push_error(name)

func method(source: String, name: String) -> String:
	var start := source.find("func " + name + "(")
	if start < 0:
		return ""
	var end := source.find("\nfunc ", start + 1)
	return source.substr(start, end - start if end >= 0 else -1).strip_edges() + "\n\n"

func script_for(source: String, names: Array, transport := "") -> GDScript:
	var script := GDScript.new()
	script.source_code = (HEADER + transport).replace("    ", "\t")
	for name in names:
		script.source_code += method(source, name)
	if script.reload() != OK:
		failures.append("probe compiles")
		return null
	return script

func stream_until(process: Dictionary, wanted: String) -> String:
	var received := ""
	for tick in 500:
		var pipe: FileAccess = process.stdio
		if pipe.get_length() > 0:
			received += pipe.get_buffer(pipe.get_length()).get_string_from_utf8()
		if wanted in received:
			return received
		await create_timer(0.01).timeout
	return received

func finish():
	for process in processes:
		if OS.is_process_running(process.pid):
			OS.kill(process.pid)
	var quiet := true
	for process in processes:
		quiet = quiet and not OS.is_process_running(process.pid)
		process.clear()
	var file := FileAccess.open("res://result.json", FileAccess.WRITE)
	file.store_string(JSON.stringify({"ok":failures.is_empty(),"checks":checks,"failures":failures,"diagnostics":diagnostics,"helper_processes_quiet":quiet}))
	file.close()
	quit(0 if failures.is_empty() else 1)

func receive_denial(guard, result: Dictionary):
	result.merge(await guard._graph_command(ISSUE, "read", {}))

func run():
	for frame in 8:
		await process_frame
	var workspace = root.find_child("DaqianWorkspace", true, false)
	if not workspace:
		failures.append("native workspace exists")
		finish()
		return
	var source: String = workspace.get_script().source_code
	var expected := FileAccess.get_file_as_string("res://expected-workspace.txt")
	var methods := ["_installed_daqian_entry", "_graph_command", "_access_denied", "_host_command", "_host_result", "_start_progress_watch", "_start_debug", "_update_board_sync_notice"]
	var caller_methods := ["_set_project", "_open_issue", "read_graph", "_graph_command", "_installed_daqian_entry", "_access_denied"]
	for name in methods + ["_set_project", "_open_issue", "read_graph"]:
		check(not method(source, name).is_empty() and method(source, name) == method(expected, name), "native method matches candidate: " + name)
	var guarded := script_for(source, ["_installed_daqian_entry", "_graph_command", "_access_denied"], DELAYED_TRANSPORT)
	var launching := script_for(source, methods)
	var callers := script_for(source, caller_methods, CALLER_HEADER + DELAYED_TRANSPORT)
	if not guarded or not launching or not callers:
		finish()
		return
	var guard = guarded.new()
	for change in ["root", "actor", "epoch", "unchanged"]:
		guard = guarded.new()
		guard.delayed = true
		var denied_result := {}
		receive_denial(guard, denied_result)
		check(guard.calls.size() == 1, "denial test actually awaits transport: " + change)
		if change == "root": guard.root_path += "-new"
		if change == "actor": guard.actor.user_id = "43"
		if change == "epoch": guard.scope_epoch += 1
		guard.release.emit()
		await process_frame
		check(guard.forgotten == (1 if change == "unchanged" else 0), "late denial context: " + change)
		check(denied_result.get("denied", false), "denial returned to original request: " + change)
	for change in ["scope", "actor_repository", "unchanged"]:
		var caller = callers.new()
		caller.delayed = true
		caller._open_issue({"url":ISSUE,"number":42,"title":"Fixture","updated":"rev1"})
		for frame in 3:
			await process_frame
		check(caller.calls.size() == 1, "issue caller awaits graph transport: " + change)
		var selection_before: int = caller.selection_epoch
		if change == "scope":
			await caller._set_project(true)
			check(caller.scope_epoch == 3 and caller.selection_epoch == selection_before, "actual project scope switch keeps issue selection")
		if change == "actor_repository":
			caller.actor.repo_id = "2"
		caller.release.emit()
		await process_frame
		check(caller.forgotten == (1 if change == "unchanged" else 0), "issue caller respects current access scope: " + change)
	var retired = callers.new()
	retired.delayed = true
	retired._open_issue({"url":ISSUE,"number":42,"title":"Fixture","updated":"rev1"})
	await retired._set_project(true)
	for frame in 3:
		await process_frame
	check(retired.calls.is_empty() and retired.forgotten == 0, "scope switch before graph launch retires old request")
	guard = guarded.new()
	guard.offline = true
	check((await guard._graph_command(ISSUE, "read", {})).has("error") and guard.calls.is_empty(), "offline rejects before transport")
	guard.offline = false
	guard.actor = {}
	check((await guard._graph_command(ISSUE, "read", {})).has("error") and guard.calls.is_empty(), "missing actor rejects before transport")
	guard.actor = {"user_id":"42","repo_id":"1"}
	for target in ["https://github.com/other/project/issues/42", "https://github.com/fixture/project/issues/0", "https://github.com/fixture/project/issues/no"]:
		check((await guard._graph_command(target, "read", {})).has("error") and guard.calls.is_empty(), "invalid Issue rejects: " + target.get_file())
	guard.root_path = "relative-project"
	check((await guard._graph_command(ISSUE, "read", {})).has("error") and guard.calls.is_empty(), "relative project rejects before transport")
	guard = guarded.new()
	for host in ["", "relative-host", ProjectSettings.globalize_path("res://missing-host")]:
		guard.host_path = host
		var denied: Dictionary = await guard._graph_command(ISSUE, "read", {})
		check(str(denied.get("error", "")).contains("安装宿主") and guard.calls.is_empty(), "missing or invalid installed host rejects without project fallback: " + host.get_file())
	var live = launching.new()
	for action in ["read", "answer", "apply"]:
		var payload := {} if action == "read" else {"revision":"rev1","execution_revision":"exec1","node":"question","value":"answer","plan":{"nodes":{},"edges":[]}}
		var response: Dictionary = await live._graph_command(ISSUE, action, payload)
		check(response.get("implementation") == "installed-host", "real Python uses installed graph helper: " + action)
		var args: Array = response.get("args", [])
		check(args.size() >= 9 and args.slice(0, 9) == ["--repo",live._repo(),"--number","42","--expected-user","42","--editor-session","private-session",action] and response.get("request") == payload, "graph preserves project/Issue/actor/session/request: " + action)
	DirAccess.rename_absolute(live._repo().path_join(HELPERS + "graph_host.py"), live._repo().path_join(HELPERS + "graph_host.py.disabled"))
	for action in ["read", "answer", "apply"]:
		check((await live._graph_command(ISSUE, action, {"revision":"rev1"})).get("implementation") == "installed-host", "graph works without project helper: " + action)
	DirAccess.rename_absolute(live._repo().path_join(HELPERS + "graph_host.py.disabled"), live._repo().path_join(HELPERS + "graph_host.py"))
	var config: Dictionary = live._runtime_paths()
	config.directory = ProjectSettings.globalize_path("res://receipts")
	live._start_progress_watch(config)
	check(not live.watcher.is_empty(), "actual watcher launches")
	if not live.watcher.is_empty():
		processes.append(live.watcher)
		var ready: String = await stream_until(live.watcher, "ready")
		check(ready.strip_edges() == "ready", "installed watcher wins over conflicting project helper")
		var event := FileAccess.open(config.directory.path_join("daqian-direct/daqian-direct-aaaaaaaaaaaaaaaaaaaa/state.json"), FileAccess.WRITE)
		event.store_string("{}")
		event.close()
		check("source:daqian-direct-aaaaaaaaaaaaaaaaaaaa" in await stream_until(live.watcher, "source:"), "real watcher observes configured receipt directory and source-events")
	await live._start_debug()
	check(not live.debug_process.is_empty(), "actual debug process launches")
	if not live.debug_process.is_empty():
		processes.append(live.debug_process)
		var output: String = await stream_until(live.debug_process, '"idle":true')
		diagnostics.debug_output = output
		var errors: FileAccess = live.debug_process.stderr
		if errors.get_length() > 0:
			diagnostics.debug_stderr = errors.get_buffer(errors.get_length()).get_string_from_utf8()
		check('"scope":"synthetic_loopback"' in output and '"state":"completed"' in output and '"issue":"' + ISSUE + '"' in output and not "PROJECT_HELPER" in output, "installed debug runs real loopback Node/Python task with bound Issue")
	# The installed files go missing while project conflicts remain: never execute project code.
	for name in ["graph_host.py", "watch_progress.mjs", "debug_session.mjs"]:
		var entry: String = live._host_root().path_join(HELPERS + name)
		DirAccess.rename_absolute(entry, entry + ".disabled")
	var absent = launching.new()
	var response: Dictionary = await absent._graph_command(ISSUE, "read", {})
	check("工单流程组件缺失" in str(response.get("error", "")), "missing graph helper has actionable error")
	absent._start_progress_watch(config)
	check(absent.watcher.is_empty() and "进度监听组件缺失" in absent.notice.text, "missing watcher rejects with actionable error")
	absent.current = ""
	absent._update_board_sync_notice()
	check("进度监听组件缺失" in absent.notice.text, "board sync preserves missing watcher diagnosis")
	absent.current = ISSUE
	await absent._start_debug()
	check(absent.debug_process.is_empty() and "调试组件缺失" in absent.notice.text, "missing debug helper rejects with actionable error")
	var watch_entry: String = live._host_root().path_join(HELPERS + "watch_progress.mjs")
	DirAccess.rename_absolute(watch_entry + ".disabled", watch_entry)
	DirAccess.remove_absolute(live._repo().path_join(HELPERS + "watch_progress.mjs"))
	absent._start_progress_watch(config)
	check(not absent.watcher.is_empty(), "explicit refresh retries restored watcher without project helper")
	absent.current = ""
	absent._update_board_sync_notice()
	check(absent.watcher_error.is_empty() and not "组件缺失" in absent.notice.text, "successful watcher retry clears stale diagnosis")
	absent.current = ISSUE
	if not absent.watcher.is_empty():
		processes.append(absent.watcher)
		check((await stream_until(absent.watcher, "ready")).strip_edges() == "ready", "retried watcher is real installed implementation")
	var debug_entry: String = live._host_root().path_join(HELPERS + "debug_session.mjs")
	DirAccess.rename_absolute(debug_entry + ".disabled", debug_entry)
	DirAccess.remove_absolute(live._repo().path_join(HELPERS + "debug_session.mjs"))
	await absent._start_debug()
	check(not absent.debug_process.is_empty(), "debug launches without project helper")
	if not absent.debug_process.is_empty():
		processes.append(absent.debug_process)
		var retried: String = await stream_until(absent.debug_process, '"idle":true')
		check('"state":"completed"' in retried, "debug completes loopback task without project helper")
	finish()
