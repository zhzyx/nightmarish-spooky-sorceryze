extends SceneTree

const Controller = preload("res://editor/docks/daqian/workflow_controller.gd")

# The source-only fallback tests the domain adapter on an older editor. The
# integrated candidate uses the actual registered service without substitution.
class RuntimeFixture extends RefCounted:
	var runs := {}
	func begin_run(request: Dictionary) -> Dictionary:
		var id := str(runs.size() + 1)
		var run := request.duplicate(true)
		run.merge({"run_id":id, "generation":1, "sequence":1, "state":request.get("initial_state", "running")})
		runs[id] = run
		return {"ok":true, "snapshot":run.duplicate(true)}
	func snapshot(id: String) -> Dictionary:
		return {"ok":runs.has(id), "snapshot":runs.get(id, {}).duplicate(true)}
	func publish(event: Dictionary) -> Dictionary:
		var run: Dictionary = runs[event.run_id]
		if run.state in ["succeeded", "failed", "cancelled"]:
			return {"ok":false, "snapshot":run.duplicate(true)}
		run.state = event.state
		run.sequence += 1
		return {"ok":true, "snapshot":run.duplicate(true)}


class ChatFixture extends RefCounted:
	signal daqian_execution_finished(receipt: Dictionary, error: String, past_preflight: bool)
	signal daqian_work_event(root: String, binding: Dictionary, worker: String, kind: String, stage: String, state: String)
	var launches := 0
	var process_ids := []
	var wrong_receipt := false
	var folder := ""
	var execution_sends := 0
	func open_daqian_chat(_url, _number, _request, message, _consultation, _selection, _direct, _source, _existing, _background := false) -> String:
		if not message.is_empty(): execution_sends += 1
		return ""
	func get_legacy_candidate_failure(_owner: String, _root: String, _number: int) -> String:
		return "fixture candidate failure"
	func launch_daqian_routing(request: Dictionary, _selection: Dictionary) -> Dictionary:
		launches += 1
		var input := folder.path_join(str(launches) + ".request")
		var output := folder.path_join(str(launches) + ".result")
		var file := FileAccess.open(input, FileAccess.WRITE)
		file.store_string(JSON.stringify(request))
		file.close()
		var result := {"ok":true, "url":"issue:one", "number":1, "request_id":request.request_id,
			"revision":"wrong" if wrong_receipt else request.expected_revision, "route":"sinan", "reason":"fixture",
			"ready":true, "scope":[], "acceptance":[], "questions":[]}
		var program := "import pathlib,json,sys,time;time.sleep(.1);pathlib.Path(sys.argv[1]).write_text(sys.argv[2])"
		var pid := OS.create_process(OS.get_environment("DAQIAN_TEST_PYTHON"), ["-c", program, output, JSON.stringify(result)])
		process_ids.append(pid)
		return {"pid":pid, "input":input, "output":output}


var failures := []
var checks := 0
func check(value: bool, reason: String) -> void:
	checks += 1
	if not value:
		failures.append(reason)


func _initialize() -> void:
	run.call_deferred()


func run() -> void:
	var controller := Controller.new()
	root.add_child(controller)
	var native := ClassDB.can_instantiate("AIWorkflowRuntime")
	# An isolated real adapter also works in a test SceneTree, where the global
	# editor-only singleton intentionally cannot be retrieved. Editor startup is
	# checked separately without replacing its main loop.
	controller.runtime = ClassDB.instantiate("AIWorkflowRuntime") if native else RuntimeFixture.new()
	var runtime := controller.runtime
	var folder := OS.get_user_data_dir().path_join("tianshu-controller")
	DirAccess.make_dir_recursive_absolute(folder)
	var chat := ChatFixture.new()
	chat.folder = folder
	controller.attach_chat(chat)
	var item := {"url":"issue:one", "number":1, "request":"request-one", "updated":"revision-one", "source_sha256":"source-one", "status":"planned"}
	var store := {}
	var context := {"root":"fixture", "actor":{"user_id":"actor", "repo_id":"repo"}, "saved":store,
		"board":{"issues":[item]}, "fresh_progress":true, "cache_path":folder.path_join("state.cache")}
	controller.configure(context)
	check(controller.bind_conversation(item, false).is_empty(), "conversation binding uses the domain service")
	var selection := {"backend":0, "id":"frozen-model", "api_key":"must-not-publish"}
	var preparation := controller.prepare_execution(item, selection, "message")
	check(preparation.get("ok", false), "execution run accepted")
	var token: String = preparation.get("token", "")
	selection.id = "changed-model"
	var snapshot := controller.query_run(token)
	check(snapshot.model.id == "frozen-model" and not snapshot.model.has("api_key"), "public model frozen without credentials")
	var sequence: int = snapshot.sequence
	controller.query_run(token)
	check(controller.query_run(token).sequence == sequence and chat.launches == 0, "query does not execute or mutate")
	chat.daqian_execution_finished.emit({"token":token}, "", true)
	check(controller.query_run(token).state == "reconciling", "legacy empty error does not prove success")
	var cancelled := controller.prepare_execution(item, selection, "cancel")
	chat.daqian_execution_finished.emit({"token":cancelled.token, "terminal_state":"cancelled"}, "", true)
	check(controller.query_run(cancelled.token).state == "cancelled", "explicit cancellation preserved")
	chat.daqian_execution_finished.emit({"token":cancelled.token, "terminal_state":"succeeded"}, "", true)
	check(controller.query_run(cancelled.token).state == "cancelled", "late completion cannot resurrect cancelled run")
	var succeeded := controller.prepare_execution(item, selection, "finish")
	chat.daqian_execution_finished.emit({"token":succeeded.token, "terminal_state":"succeeded"}, "", true)
	check(controller.query_run(succeeded.token).state == "succeeded", "explicit terminal receipt completes its own run")
	var executed := controller.execute(item, selection, "bound execution", false, true, false)
	check(executed.get("ok", false) and chat.execution_sends == 1, "execution request is actually launched by Controller without View")
	check(store.direct_started[item.url] == item.request, "Controller owns accepted execution binding")
	chat.daqian_execution_finished.emit({"token":executed.token, "terminal_state":"succeeded"}, "", true)
	check(controller.query_run(executed.token).state == "succeeded", "launched execution receipt updates same public run")
	var start_script := folder.path_join("start.py")
	var script_file := FileAccess.open(start_script, FileAccess.WRITE)
	script_file.store_string("import argparse,json,pathlib,time\np=argparse.ArgumentParser();p.add_argument('--out');p.add_argument('--request');a=p.parse_args();time.sleep(.1);pathlib.Path(a.out).write_text(json.dumps({'ok':True,'status':'status:in-progress'}))\n")
	script_file.close()
	var start_configuration := {"workflow_python":OS.get_environment("DAQIAN_TEST_PYTHON")}
	controller.start_issue(item, selection, [start_script], start_configuration, folder)
	var duplicate: Dictionary = await controller.start_issue(item, selection, [start_script], start_configuration, folder)
	check(duplicate.has("error"), "concurrent start cannot launch another source mutation")
	var deadline := Time.get_ticks_msec() + 5000
	while not controller.starting_direct.is_empty() and Time.get_ticks_msec() < deadline:
		await process_frame
	check(controller.starting_direct.is_empty() and store.get("direct_start_receipts", {}).get(item.url) == item.request, "Controller validates and stores actual host start receipt")
	var result: Dictionary = await controller.judge(item, selection)
	check(result.get("ok", false) and chat.launches == 1, "real process route receipt accepted")
	check(store.get("routing", {}).get(item.url, {}).get("revision") == item.updated, "verified receipt applied to original store")
	check(FileAccess.file_exists(context.cache_path), "receipt persisted without any View")
	check(not FileAccess.file_exists(folder.path_join("1.request")) and not FileAccess.file_exists(folder.path_join("1.result")), "consumed host request and result cleaned")
	var detached := context.duplicate(true)
	detached.saved = {"drafts":{"retained":"draft"}}
	controller.configure(detached)
	check(detached.saved.get("routing", {}).has(item.url) and detached.saved.drafts.retained == "draft", "View reattach retains authoritative receipt and independent draft")
	check(chat.launches == 1, "reattach never resubmits")
	chat.wrong_receipt = true
	result = await controller.judge(item, selection)
	check(result.revision == "wrong" and controller.saved.routing[item.url].revision == item.updated, "wrong source receipt cannot replace verified route")
	check(not controller.saved.get("routing_errors", {}).is_empty(), "unverified receipt exposes recovery state")
	var last_identity: String = controller.runs.keys().back()
	check(controller.query_run(last_identity).state == "reconciling", "unknown route result stays reconciling")
	var binding := {"source_ref":item.url, "source_sha256":"source-one", "actor":"actor", "request_ref":item.request}
	chat.daqian_work_event.emit("fixture", binding, "worker", "request", "implement", "running")
	check(controller.chat_work.get(item.url, {}).has("worker"), "worker event owns source-scoped activity")
	var worker_identity: String = controller.worker_runs.keys().back()
	chat.daqian_work_event.emit("fixture", binding, "worker", "request_end", "implement", "failed")
	check(controller.query_run(worker_identity).state == "failed", "worker terminal maps to same public run")
	var late := binding.duplicate(true)
	late.source_sha256 = "other-revision"
	chat.daqian_work_event.emit("fixture", late, "worker", "request", "implement", "running")
	check(controller.chat_work[item.url].is_empty(), "changed revision cannot revive original worker")
	var recovery := item.duplicate(true)
	recovery.request = "daqian-direct-0123456789abcdef0123"
	recovery.status = "in-progress"
	var recovery_context := context.duplicate(true)
	recovery_context.root = folder
	recovery_context.saved = {}
	controller.configure(recovery_context)
	var receipt_folder := folder.path_join("gonggong-diting-data/events/fixture/" + recovery.request)
	DirAccess.make_dir_recursive_absolute(receipt_folder)
	var receipt_path := receipt_folder.path_join("godot-event-fixture.json")
	var event_file := FileAccess.open(receipt_path, FileAccess.WRITE)
	event_file.store_string(JSON.stringify({"kind":"request_end", "request_id":recovery.request,
		"source_ref":recovery.url, "occurred_at":"2026-11-14T00:00:00Z", "payload":{"status":"failed",
		"binding":{"actor":"actor", "source_ref":recovery.url, "request_ref":recovery.request,
			"source_sha256":recovery.source_sha256, "authority_ref":"godot-editor:user-chat:0123456789abcdef0123456789abcdef"}}}))
	event_file.close()
	await controller.restore_execution_failure(recovery, "fixture")
	check(controller.saved.get("execution_errors", {}).get(controller._execution_key(recovery)) == "fixture candidate failure", "Controller restores authoritative legacy failure without a View")
	DirAccess.remove_absolute(receipt_path)
	for directory in [receipt_folder, receipt_folder.get_base_dir(), receipt_folder.get_base_dir().get_base_dir(), folder.path_join("gonggong-diting-data")]:
		DirAccess.remove_absolute(directory)
	controller.configure({"root":"other", "actor":{"user_id":"other"}, "saved":{}, "board":{"issues":[item]}})
	chat.daqian_work_event.emit("fixture", binding, "worker", "request", "implement", "running")
	check(controller.saved.is_empty(), "old account event cannot mutate new store")
	for pid in chat.process_ids:
		if OS.is_process_running(pid):
			OS.kill(pid)
	controller.free()
	if native:
		runtime.free()
	for name in DirAccess.get_files_at(folder):
		DirAccess.remove_absolute(folder.path_join(name))
	DirAccess.remove_absolute(folder)
	print(JSON.stringify({"checks":checks, "failures":failures, "native_runtime":native}))
	quit(0 if failures.is_empty() else 1)
