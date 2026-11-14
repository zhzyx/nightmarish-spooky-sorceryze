extends SceneTree

const Controller = preload("res://editor/docks/daqian/workflow_controller.gd")


class RuntimeFixture extends RefCounted:
	var runs := {}
	var serial := 0

	func begin_run(workflow: String, scope: String, request: String, model: Dictionary, binding: Dictionary) -> Dictionary:
		serial += 1
		var event := {"schema_version":1, "workflow":workflow, "scope":scope, "run_id":str(serial),
			"request_id":request, "generation":serial, "sequence":1, "kind":"run_started", "state":"running",
			"model":model.duplicate(true), "binding":binding.duplicate(true), "payload":{}}
		runs[event.run_id] = event
		return event.duplicate(true)

	func publish(id: String, generation: int, kind: String, payload: Dictionary, state: String) -> Dictionary:
		var event: Dictionary = runs.get(id, {})
		if event.is_empty() or event.generation != generation or event.state in ["succeeded", "failed", "cancelled"]:
			return {}
		event.sequence += 1
		event.kind = kind
		event.payload = payload.duplicate(true)
		event.state = event.state if state.is_empty() else state
		return event.duplicate(true)

	func snapshot(id: String) -> Dictionary:
		return runs.get(id, {}).duplicate(true)

	func cancel(id: String) -> Dictionary:
		return publish(id, int(runs[id].generation), "cancelled", {}, "cancelled")


class Host extends RefCounted:
	var binding := {"number":1086, "url":"https://github.com/fixture/repo/issues/1086", "request":"ai-unified-framework",
		"status":"planned", "updated":"revision-1", "source_sha256":"source-1"}
	var state := {"root":"fixture-root", "actor":{"user_id":"42"}, "board":{}, "other_board":{}, "fresh_progress":true, "progress_directory":""}
	var opened := []
	var fail_open := false
	var change_scope := false
	var route_calls := 0

	func read_context() -> Dictionary:
		return state

	func access() -> bool:
		return true

	func current_binding() -> Dictionary:
		return binding

	func catalog() -> Dictionary:
		return {"backend":0, "current":"fixture-model"}

	func open_session(source: String, number: int, request: String, message: String, preview: bool, selection: Dictionary,
			embedded: bool, receipt: String, existing: bool, background: bool) -> String:
		opened = [source, number, request, message, preview, selection, embedded, receipt, existing, background]
		return "fixture unavailable" if fail_open else ""

	func launch_route(request: Dictionary, _selection: Dictionary) -> Dictionary:
		route_calls += 1
		var path := OS.get_user_data_dir().path_join("controller-route-" + str(route_calls) + ".json")
		var file := FileAccess.open(path, FileAccess.WRITE)
		file.store_string(JSON.stringify({"ok":true, "url":binding.url, "number":binding.number, "request_id":binding.request,
			"revision":request.expected_revision, "route":"sinan", "ready":true, "scope":["Implement"], "acceptance":["Verify"], "questions":[], "reason":"fixture"}))
		file.close()
		if change_scope:
			state.actor = {"user_id":"other"}
		return {"pid":-1, "input":"", "output":path}


var failures := []
var events := []


func check(condition: bool, message: String) -> void:
	if not condition:
		failures.append(message)


func _initialize() -> void:
	run.call_deferred()


func run() -> void:
	var controller := Controller.new()
	var host := Host.new()
	host.state.board = {"issues":[host.binding]}
	controller.context_reader = host.read_context
	controller.access_refresher = host.access
	controller.binding_reader = host.current_binding
	controller.catalog_reader = host.catalog
	controller.session_opener = host.open_session
	controller.routing_launcher = host.launch_route
	var native := ClassDB.class_exists("AIWorkflowRuntime")
	controller.runtime = ClassDB.instantiate("AIWorkflowRuntime") if native else RuntimeFixture.new()
	controller.event_received.connect(func(event): events.append(event))
	var selection := {"backend":0, "id":"fixture-model"}
	check(controller.bind_conversation(host.binding).is_empty(), "Binding required a UI control")
	check(host.opened[0] == host.binding.url and host.opened[1] == 1086 and host.opened[3].is_empty(), "Session binding changed")
	check(controller.submit_execution(host.binding, "Implement", selection, false, true, false).is_empty(), "Background execution failed")
	var receipt: Dictionary = host.opened[5].execution_receipt
	check(host.opened[9] and controller.execution_turns.has(receipt.token), "Run ownership was tied to foreground navigation")
	check(controller.finish_execution(receipt, "preflight", false), "Execution receipt was lost")
	check(not controller.finish_execution(receipt, "duplicate", false), "Terminal receipt was replayed")
	check(events.back().kind == "failed" and events.back().state == "failed", "Failure omitted the common event")
	host.fail_open = true
	check(controller.submit_execution(host.binding, "Retry", selection, false, false, true) == "fixture unavailable", "Host failure was hidden")
	check(controller.execution_turns.is_empty(), "Host rejection retained a live execution")
	host.fail_open = false
	check(controller.open_conversation("preview", 0, "", "Assess", true, selection, true, "preview-receipt").is_empty(), "Preview did not use the workflow runtime")
	check(not controller.finish_preview("preview-receipt", "Preview result").is_empty(), "Preview completion was lost")
	check(controller.finish_preview("preview-receipt", "Repeated result").is_empty(), "Preview terminal was replayed")
	check(controller.open_conversation("draft", 0, "", "First preview", true, selection, true).is_empty(), "First same-source preview failed")
	var original_receipt: String = host.opened[7]
	host.fail_open = true
	check(not controller.open_conversation("draft", 0, "", "Duplicate preview", true, selection, true).is_empty(), "Busy host was ignored")
	check(controller.finish_preview(original_receipt, "Original result").get("source") == "draft", "Rejected duplicate swallowed the original preview")
	host.fail_open = false
	check(controller.open_conversation("draft", 0, "", "Before reset", true, selection, true).is_empty(), "Preview before reset failed")
	var old_receipt: String = host.opened[7]
	controller.reset_runtime()
	check(controller.open_conversation("draft", 0, "", "After reset", true, selection, true).is_empty(), "Preview after reset failed")
	var new_receipt: String = host.opened[7]
	check(old_receipt != new_receipt and controller.finish_preview(old_receipt, "Stale").is_empty(), "Old preview completed a new run after reset")
	check(controller.finish_preview(new_receipt, "Fresh").get("source") == "draft", "Fresh preview was lost after reset")
	var last_opened: Array = host.opened.duplicate(true)
	var cancel_started := func(event: Dictionary):
		if event.kind == "run_started":
			controller.runtime.cancel(event.run_id)
	controller.event_received.connect(cancel_started)
	check(not controller.submit_execution(host.binding, "Cancelled before start", selection, false, false, false).is_empty(), "Reentrant cancellation still launched a provider")
	check(host.opened == last_opened, "Cancelled start reached the session host")
	controller.event_received.disconnect(cancel_started)
	var original_binding := host.binding.duplicate(true)
	var mutate_started := func(event: Dictionary):
		if event.kind == "run_started":
			host.binding.url = "changed-after-start"
			selection.id = "changed-after-start"
	controller.event_received.connect(mutate_started)
	check(controller.submit_execution(host.binding, "Frozen input", selection, false, false, false).is_empty(), "Frozen request failed")
	check(host.opened[0] == original_binding.url and host.opened[5].id == "fixture-model", "Host request diverged from the frozen runtime input")
	controller.event_received.disconnect(mutate_started)
	host.binding = original_binding
	host.state.board = {"issues":[host.binding]}
	selection.id = "fixture-model"
	controller.finish_execution(host.opened[5].execution_receipt, "", true)
	var first: Dictionary = await controller.judge_requirement(host.binding)
	check(first.get("verified", false) and controller.routing_receipt(host.binding).ready, "Valid routing result was rejected")
	var second: Dictionary = await controller.judge_requirement(host.binding, "", true)
	check(second.get("verified", false) and host.route_calls == 2, "Authorized retry reused a terminal run")
	var invalid := host.binding.duplicate()
	invalid.updated = "new-revision"
	invalid.erase("routing_receipt")
	check(controller.routing_receipt(invalid).is_empty(), "Routing result escaped its revision")
	host.change_scope = true
	var stale: Dictionary = await controller.judge_requirement(host.binding, "", true)
	check(stale.is_empty() and controller.routing_in_flight.is_empty(), "Late route crossed an actor change")
	host.state.actor = {"user_id":"42"}
	var work := {"source_ref":host.binding.url, "request_ref":host.binding.request, "source_sha256":"source-1", "actor":"42"}
	check(not controller.consume_work_event("fixture-root", work, "worker", "request", "chat", "running").is_empty(), "Worker start was dropped")
	var wrong := work.duplicate()
	wrong.actor = "other"
	check(controller.consume_work_event("fixture-root", wrong, "worker", "request_end", "chat", "failed").is_empty(), "Foreign worker altered state")
	controller.reset_runtime()
	check(controller.execution_turns.is_empty() and controller.chat_work.is_empty(), "Reset retained old ownership")
	check(events.back().kind == "cancelled", "Reset omitted common cancellation")
	for message in failures:
		push_error(message)
	if failures.is_empty():
		print("DAQIAN_WORKFLOW_CONTROLLER_OK ", "native" if native else "injected transport fixture")
	quit(0 if failures.is_empty() else 1)
