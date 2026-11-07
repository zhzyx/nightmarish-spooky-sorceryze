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
	var backend = dock.find_child("AIBackend", true, false)
	backend.select(0)
	backend.item_selected.emit(0)
	dock.find_child("APIEndpoint", true, false).text = OS.get_environment("DELIVERY_FIXTURE_ENDPOINT")
	dock.find_child("APIModel", true, false).text = "offline-delivery-fixture"
	dock.find_child("APIKey", true, false).text = "offline-fixture-key"
	dock.find_child("CLINode", true, false).text = OS.get_environment("DELIVERY_FIXTURE_NODE")
	dock.find_child("CLIBridge", true, false).text = OS.get_environment("DELIVERY_FIXTURE_SOURCE").path_join("tools/codebuddy_cli/godot_bridge.js")
	var mode := OS.get_environment("DELIVERY_FIXTURE_CASE")
	if OS.get_environment("DELIVERY_FIXTURE_PHASE") == "cold":
		await create_timer(2.0).timeout
		_finish(dock.get_meta("gonggong_status", "") != "delivery_completed", "Cold history does not restore a live terminal capability")
		return
	dock.find_child("AllowTools", true, false).button_pressed = mode != "disabled"
	dock.find_child("ConsultationOnly", true, false).button_pressed = mode == "consultation"
	dock.find_child("AutoApplyFileChanges", true, false).button_pressed = true
	dock.find_child("AutoExecuteCommands", true, false).button_pressed = mode not in ["approval", "inline-approval"]
	# Model setting refreshes must finish before this fixture starts its turn.
	await create_timer(0.5).timeout
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
