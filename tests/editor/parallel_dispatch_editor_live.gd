@tool
extends SceneTree

func _initialize():
	_run.call_deferred()

func _run():
	await create_timer(1.0).timeout
	var workspace = OS.get_environment("ISSUE72_WORKSPACE")
	var request_id = "yanluo-issue-9-source-host-binding-20261105"
	var dock = root.find_child("AI Chat", true, false)
	if dock == null:
		push_error("Native AI Chat dock missing")
		quit(1)
		return
	var settings = EditorInterface.get_editor_settings()
	var directory = workspace.path_join("data-collection/outbox")
	var previous_results = DirAccess.get_files_at(directory)
	settings.set_setting("gonggong/workspace", workspace)
	settings.set_setting("gonggong/issue_number", "90")
	settings.set_setting("gonggong/request_id", request_id)
	settings.set_setting("ai_chat/parallel_work_orders_config", OS.get_environment("ISSUE72_PARALLEL_CONFIG"))
	dock.find_child("CLINode", true, false).text = OS.get_environment("ISSUE72_NODE")
	dock.find_child("ConsultationOnly", true, false).button_pressed = false
	for control in ["AllowTools", "AutoApplyFileChanges", "AutoExecuteCommands"]:
		dock.find_child(control, true, false).button_pressed = true
	dock.find_child("SpawnWorkOrderAgents", true, false).pressed.emit()
	var result_path = ""
	var deadline = Time.get_ticks_msec() + 600000
	while Time.get_ticks_msec() < deadline:
		await create_timer(0.2).timeout
		if result_path.is_empty():
			for file in DirAccess.get_files_at(directory):
				if file not in previous_results and file.begins_with("parallel-" + request_id + "-") and file.ends_with(".result.json"):
					result_path = directory.path_join(file)
		if result_path.is_empty():
			continue
		var result = JSON.parse_string(FileAccess.get_file_as_string(result_path))
		if not result is Dictionary or result.get("requestId", "") != request_id:
			continue
		var workers = result.get("workers", [])
		if workers.size() != 2:
			continue
		var done = true
		for worker in workers:
			if worker.get("state", "") not in ["review", "blocked", "reconcile_required"]:
				done = false
		if not done:
			continue
		await create_timer(0.5).timeout
		var tabs = dock.find_child("SubAgentTabs", true, false) as TabBar
		var receipt = {"result_path": result_path, "workers": workers, "child_tabs": tabs.tab_count, "exit_scope": "CLI exit enters review; host independently validates task output"}
		var output = FileAccess.open(OS.get_environment("ISSUE72_UI_RECEIPT"), FileAccess.WRITE)
		output.store_string(JSON.stringify(receipt))
		output.close()
		print("ISSUE72_EDITOR_LIVE_DISPATCH_RETURNED")
		quit(0 if tabs.tab_count == 3 else 1)
		return
	push_error("No terminal receipt from actual editor dispatch")
	quit(1)
