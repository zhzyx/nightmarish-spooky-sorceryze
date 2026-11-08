@tool
extends SceneTree

var dock: Node
var approval_events: Array = []

func _initialize():
	_run.call_deferred()

func _text() -> String:
	var result := ""
	for label in dock.find_children("*", "RichTextLabel", true, false):
		result += label.get_parsed_text() + "\n"
	return result

func _send(text: String):
	dock.find_child("ChatInput", true, false).text = text
	dock.find_child("Send", true, false).pressed.emit()

func _finish(ok: bool, detail := ""):
	FileAccess.open("res://delivery-report.json", FileAccess.WRITE).store_string(JSON.stringify({
		"ok": ok, "detail": detail, "status": dock.get_meta("gonggong_status", ""),
		"reporting": dock.get_meta("gonggong_reporting", ""), "text": _text(),
		"approval_events": approval_events,
	}))
	quit(0 if ok else 1)

func _run():
	dock = root.find_child("AI Chat", true, false)
	var settings = EditorInterface.get_editor_settings()
	settings.set_setting("gonggong/workspace", OS.get_environment("DELIVERY_FIXTURE_ROOT"))
	var central_config := FileAccess.file_exists(OS.get_environment("DELIVERY_FIXTURE_SOURCE").path_join("editor/docks/gonggong_runtime_config.h"))
	# In the combined build only the private central file has a usable Python;
	# successful candidate/guard/finalizer execution proves no legacy fallback.
	settings.set_setting("gonggong/python", OS.get_environment("DELIVERY_FIXTURE_ROOT").path_join("missing-legacy-python") if central_config else OS.get_environment("DELIVERY_FIXTURE_PYTHON"))
	settings.set_setting("ai_chat/parallel_work_orders_config", "")
	var ai = dock.get_ai_settings_control()
	var environment = dock.get_environment_settings_control()
	var backend = ai.find_child("AIBackend", true, false)
	backend.select(0)
	backend.item_selected.emit(0)
	ai.find_child("APIEndpoint", true, false).text = OS.get_environment("DELIVERY_FIXTURE_ENDPOINT")
	ai.find_child("APIModel", true, false).text = "offline-delivery-fixture"
	ai.find_child("APIKey", true, false).text = "offline-fixture-key"
	var node = environment.find_child("CLINode", true, false)
	node.text = OS.get_environment("DELIVERY_FIXTURE_NODE")
	node.text_changed.emit(node.text)
	environment.find_child("CLIBridge", true, false).text = OS.get_environment("DELIVERY_FIXTURE_SOURCE").path_join("tools/codebuddy_cli/godot_bridge.js")
	var mode := OS.get_environment("DELIVERY_FIXTURE_CASE")
	var retry_case := mode.begins_with("retry")
	if retry_case and OS.get_environment("DELIVERY_FIXTURE_PHASE") == "restore":
		await _retry_commands()
		return
	if OS.get_environment("DELIVERY_FIXTURE_PHASE") == "cold":
		await create_timer(2.0).timeout
		_finish(dock.get_meta("gonggong_status", "") != "delivery_completed", "Cold history does not restore a live terminal capability")
		return
	ai.find_child("AllowTools", true, false).button_pressed = mode != "disabled"
	dock.find_child("ConsultationOnly", true, false).button_pressed = mode == "consultation"
	ai.find_child("AutoApplyFileChanges", true, false).button_pressed = true
	ai.find_child("AutoExecuteCommands", true, false).button_pressed = mode not in ["approval", "inline-approval"]
	# Wait for actual readiness rather than racing the deferred model refresh.
	for unused in 1000:
		if dock.find_child("Stop", true, false).disabled and not dock.find_child("Send", true, false).disabled:
			break
		await create_timer(0.02).timeout
	var approval = dock.find_child("AIFileApproval", true, false)
	approval.visibility_changed.connect(func(): approval_events.append({"visible": approval.visible, "embedded": approval.is_embedded(), "window_id": approval.get_window_id()}))
	_send("DELIVERY_COMPLETE_START")
	var boundary_applied := false
	var deadline := Time.get_ticks_msec() + 90000
	while Time.get_ticks_msec() < deadline:
		await create_timer(0.02).timeout
		if mode == "inline-approval":
			var bindings: Dictionary = settings.get_project_metadata("daqian", "bindings", {})
			for owner in bindings:
				bindings[owner]["issue_url"] = "https://github.com/example/test/issues/390"
			settings.set_project_metadata("daqian", "bindings", bindings)
			var operation: Dictionary = dock.get_daqian_approval()
			if not operation.is_empty():
				if dock.confirm_daqian_approval("wrong-token"):
					_finish(false, "Unrelated approval token authorized delivery")
					return
				dock.find_child("Stop", true, false).pressed.emit()
				boundary_applied = true
		if mode == "approval":
			if approval.visible:
				approval.hide()
				approval.canceled.emit()
				boundary_applied = true
		if not boundary_applied and FileAccess.file_exists(OS.get_environment("DELIVERY_FIXTURE_STAGE")):
			if mode == "stop":
				dock.find_child("Stop", true, false).pressed.emit()
			else:
				_send("QUEUED_AFTER_DELIVERY_MUST_REMAIN_PAUSED")
			boundary_applied = true
		var status: String = dock.get_meta("gonggong_status", "")
		var idle: bool = dock.find_child("Stop", true, false).disabled
		if retry_case:
			FileAccess.open("res://retry-progress.json", FileAccess.WRITE).store_string(JSON.stringify({"status": status, "idle": idle, "text": _text()}))
		if retry_case and status == "delivery_pending" and idle:
			await _retry_commands()
			return
		if mode in ["normal", "cold"] and status == "delivery_completed" and idle:
			await create_timer(0.3).timeout
			_finish(boundary_applied and "交付已回读" in _text())
			return
		if mode == "activation-pending" and status == "delivery_pending" and idle:
			_finish(boundary_applied and "启动入口更新仍待核实" in _text() and not "启动入口已核验更新" in _text())
			return
		if mode == "receipt-failure" and idle and "GongGong 文件回执失败" in _text():
			_finish(boundary_applied and not "交付已回读" in _text())
			return
		if mode == "partial-failure" and idle and status == "delivery_pending":
			_finish(boundary_applied and "交付收尾未得到完整回执" in _text())
			return
		if mode == "stop" and boundary_applied and idle:
			await create_timer(1.0).timeout
			_finish(status != "delivery_completed")
			return
		if mode == "disabled" and idle and "本地工具权限已关闭，未执行本次操作" in _text():
			_finish(status != "delivery_completed")
			return
		if mode == "inline-approval" and boundary_applied and idle:
			_finish(status != "delivery_completed", "Explicit-source host approval rejected unrelated token; Stop cancelled without execution")
			return
		if mode in ["forged-stdout", "reject-before-mutation", "approval", "consultation", "disabled"] and idle and "SAFE_BOUNDARY_OK" in _text():
			_finish(status != "delivery_completed" and (mode != "approval" or boundary_applied))
			return
		if idle and ("The service did not" in _text() or "AI request failed" in _text() or "交付收尾未得到完整回执" in _text()):
			_finish(false, "Unexpected fixture or worker failure")
			return
	_finish(false, "Timed out: " + mode)

func _retry_commands():
	FileAccess.open("res://retry-ready.json", FileAccess.WRITE).store_string(JSON.stringify({"pid": OS.get_process_id()}))
	var last_id := 0
	var deadline := Time.get_ticks_msec() + 120000
	while Time.get_ticks_msec() < deadline:
		await create_timer(0.02).timeout
		if not FileAccess.file_exists("res://retry-command.json"):
			continue
		var command = JSON.parse_string(FileAccess.get_file_as_string("res://retry-command.json"))
		if not command is Dictionary or int(command.get("id", 0)) <= last_id:
			continue
		last_id = int(command.id)
		match command.name:
			"tools":
				dock.get_ai_settings_control().find_child("AllowTools", true, false).button_pressed = command.value
			"automatic":
				dock.get_ai_settings_control().find_child("AutoExecuteCommands", true, false).button_pressed = command.value
			"consultation":
				dock.find_child("ConsultationOnly", true, false).button_pressed = command.value
			"draft":
				dock.find_child("ChatInput", true, false).text = command.value
			"child":
				dock.find_child("AddSubAgent", true, false).pressed.emit()
			"parent":
				dock.find_child("SubAgentTabs", true, false).tab_selected.emit(0)
			"stop":
				dock.find_child("Stop", true, false).pressed.emit()
			"quit":
				_finish(true, "Private terminal retry fixture completed")
				return
			"finish":
				_finish(dock.get_meta("gonggong_status", "") == "delivery_completed", "Actual host retry terminal status")
				return
		FileAccess.open("res://retry-command-result.json", FileAccess.WRITE).store_string(JSON.stringify({"id": last_id, "status": dock.get_meta("gonggong_status", "")}))
	_finish(false, "Private retry fixture timed out")
