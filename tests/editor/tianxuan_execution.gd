extends SceneTree
## Actual entry coordination with an explicitly deterministic installed runtime.

var checks: Array[String] = []


func _initialize() -> void:
	run.call_deferred()


func check(value: bool, description: String) -> bool:
	if not value:
		push_error("Native execution fixture: " + description)
		quit(1)
		return false
	checks.append(description)
	return true


func wait_until(predicate: Callable, seconds := 90.0) -> bool:
	var deadline := Time.get_ticks_msec() + int(seconds * 1000)
	while not predicate.call() and Time.get_ticks_msec() < deadline:
		await create_timer(0.025).timeout
	return predicate.call()


func load_source(name: String) -> GDScript:
	var script := GDScript.new()
	script.source_code = FileAccess.get_file_as_string(OS.get_environment("TX_SOURCE").path_join("editor/docks/tianxuan/" + name + ".gd"))
	return script if script.reload() == OK else null


func run() -> void:
	await process_frame
	await process_frame
	var native := OS.get_environment("TX_NATIVE_SHELL") == "1"
	var session: Node
	var controller: Node
	var main: Control
	if native:
		root.size = Vector2i(1600, 1000)
		main = EditorInterface.get_base_control().find_child("TianxuanWorkspaceView", true, false)
		if not check(main != null, "compiled native execution host is installed"):
			return
		controller = main.get_meta("controller")
		session = controller.session
	else:
		session = load_source("session_controller").new()
		session.origin = OS.get_environment("TX_API")
		root.add_child(session)
		controller = load_source("workspace_controller").new()
		controller.set_meta("session_controller", session)
		controller.set_meta("execution_script", load_source("execution_controller"))
		controller.storage_root = OS.get_environment("TX_DRAFTS")
		root.add_child(controller)
	await session.authenticate("first@example.invalid", OS.get_environment("TX_PASSWORD"), "workspace")
	var capabilities: Dictionary = await session.api_request(HTTPClient.METHOD_GET, "/api/v1/native/entry/capabilities")
	if not check(capabilities.status == 200 and capabilities.data.mode == "deterministic-test", "execution test explicitly identifies its installed deterministic role programs"):
		return
	var requirement: Dictionary = await session.api_request(HTTPClient.METHOD_POST, "/api/v1/requirements", {"request_id": "native-execution-" + controller.new_id(), "title": "Native execution fixture", "outcome": "Output", "scope": "Text", "acceptance": "output must equal deterministic accepted output"})
	if not check(requirement.status == 200, "execution fixture creates a real requirement through the authenticated service"):
		return
	var model: Node = controller.execution
	var watcher := Node.new()
	root.add_child(watcher)
	model.observe(watcher, true)
	var entry_id := ""
	for increment in 2:
		var started: Dictionary = await session.api_request(HTTPClient.METHOD_POST, "/api/v1/native/entry/execute", {"requirement": requirement.data.id, "call_id": "native-ui-entry-%d" % increment, "scopes": ["text"], "model": "installed"})
		if not check(started.status == 200, "explicit installed execution request accepted for increment %d" % increment):
			return
		entry_id = str(started.data.entry)
		await model.select(entry_id)
		var completed := await wait_until(func(): return not model.loading and (model.settled() or not model.observation.get("failures", []).is_empty()))
		if not completed:
			print(JSON.stringify({"state": model.observation, "status": model.status}))
		if not check(completed and not model.loading and model.settled() and model.observation.progress.percent == 100 and model.observation.failures.is_empty(), "actual entry coordinator, producer, checker and reviewer finish increment %d" % increment):
			return
		await model.refresh()
		if not check(not model.loading, "execution history read completes before inspecting releases for increment %d" % increment):
			return
	if not check(model.releases.events.size() >= 2 and model.releases.events.filter(func(event: Dictionary): return event.accepted).size() >= 2, "execution history exposes accepted immutable releases produced by the actual workflow"):
		return
	var target := ""
	for event in model.releases.events:
		if event.accepted and event.selection != model.releases.head:
			target = event.selection
			break
	var previous := str(model.releases.head)
	if native:
		controller.navigate("execution", entry_id)
		var view = main._page_instances.execution
		if not check(await wait_until(func(): return not model.loading and view._target.item_count >= 2, 8.0), "compiled native observation page presents the accepted release choices"):
			return
		if not check(view._tasks.get_child_count() >= 1 and view._roles.get_child_count() >= 1 and view.counts({"totalTokens": 0, "inputTokens": -1}) == "总令牌 0", "native observations preserve reported zero usage and omit invalid or unreported counts"):
			return
		for index in view._target.item_count:
			if view._target.get_item_metadata(index) == target:
				view._target.select(index)
		view._rollback.pressed.emit()
		if not check(view._dialog.visible and model.releases.head == previous, "native content rollback waits for confirmation of the exact current and historical releases"):
			return
		view._dialog.confirmed.emit()
		view._dialog.hide()
		if not check(await wait_until(func(): return not model.saving and not model.loading and model.releases.get("head") != previous, 10.0), "confirmed native rollback reads the new stable selection and its receipt"):
			return
	else:
		await wait_until(func(): return not model.loading)
		await model.rollback(target, model.snapshot())
	if model.pending().is_empty() and model.releases.head != model.receipt:
		print(JSON.stringify({"rollback_status": model.status, "receipt": model.receipt, "releases": model.releases}))
	if not check(model.pending().is_empty() and model.releases.head == model.receipt and model.releases.events[0].restored_from == target, "rollback verifies the new stable head against the original accepted source"):
		return
	var replay_payload := {"call_id": controller.new_id(), "expected": model.releases.head, "selection": target}
	var acknowledged: Dictionary = await session.api_request(HTTPClient.METHOD_POST, model.route() + "/rollback", replay_payload)
	if not check(acknowledged.status == 200, "rollback replay fixture records an actual acknowledged release operation"):
		return
	controller.save_draft("execution:rollback:" + entry_id, replay_payload)
	await model.retry_rollback()
	if not check(model.receipt == acknowledged.data.selection and model.releases.head == acknowledged.data.selection and model.pending().is_empty(), "lost rollback acknowledgement reuses the exact call ID without creating another release"):
		return
	model.observe(watcher, false)
	watcher.queue_free()
	print(JSON.stringify({"passed": true, "checks": checks}))
	quit(0)
