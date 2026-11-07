@tool
extends SceneTree

var dock: Node
var report := {}
var failure := ""

func _initialize():
	_run.call_deferred()

func _check(ok: bool, message: String) -> bool:
	if not ok:
		failure = message if failure.is_empty() else failure + "; " + message
		push_error(message)
	return ok

func _text() -> String:
	var result := ""
	for label in dock.find_children("*", "RichTextLabel", true, false):
		result += label.get_parsed_text()
	return result

func _history() -> Dictionary:
	var path := "res://.godot/editor/ai_chat_history.json"
	if not FileAccess.file_exists(path):
		return {}
	var source := FileAccess.get_file_as_string(path)
	if source.is_empty():
		return {}
	var value = JSON.parse_string(source)
	return value if value is Dictionary else {}

func _send(text: String):
	dock.find_child("ChatInput", true, false).text = text
	dock.find_child("Send", true, false).pressed.emit()

func _finish():
	report["failure"] = failure
	report["passed"] = failure.is_empty()
	FileAccess.open("res://steering-report.json", FileAccess.WRITE).store_string(JSON.stringify(report))
	print("STEERING_REPORT=", JSON.stringify(report))
	quit(0 if failure.is_empty() else 2)

func _run():
	await create_timer(1.0).timeout
	dock = root.find_child("AI Chat", true, false)
	if not _check(dock != null, "AI Chat dock not found"):
		_finish()
		return
	var setup = dock.find_child("GongGongRuntimeSetup", true, false)
	if setup != null:
		setup.hide()
	EditorInterface.set_main_screen_editor("AI Chat")
	var backend = dock.find_child("AIBackend", true, false)
	backend.select(0)
	backend.item_selected.emit(0)
	dock.find_child("APIEndpoint", true, false).text = OS.get_environment("STEERING_ENDPOINT")
	dock.find_child("APIKey", true, false).text = "isolated-fixture-key"
	dock.find_child("APIModel", true, false).text = "fixture"
	if OS.get_environment("STEERING_CODEX") == "1":
		backend.select(2)
		backend.item_selected.emit(2)
		dock.find_child("CLINode", true, false).text = OS.get_environment("STEERING_NODE")
		dock.find_child("CLIBridge", true, false).text = OS.get_environment("STEERING_BRIDGE")
		dock.find_child("CodexEntry", true, false).text = OS.get_environment("STEERING_CODEX_ENTRY")
		dock.find_child("CodexModel", true, false).text = "fixture"
	var consultation = dock.find_child("ConsultationOnly", true, false)
	consultation.button_pressed = true
	dock.find_child("AllowTools", true, false).button_pressed = false
	var mode := OS.get_environment("STEERING_CASE")
	dock.find_child("AllowTools", true, false).button_pressed = mode == "tools"
	if mode == "restore":
		await create_timer(0.5).timeout
		report["restored_count"] = dock.get_meta("queued_message_count", -1)
		_check(report.restored_count == 2, "Restart lost pending supplements")
		_check(dock.get_meta("queue_paused", false), "Restart resumed pending supplements automatically")
		_check(dock.find_child("Stop", true, false).disabled, "Restart unexpectedly started work")
		var saved := _history()
		if not saved.get("agents", []).is_empty():
			report["snapshot"] = saved.agents[0].get("snapshot_id", "")
		_finish()
		return
	_send("STEERING_ORIGINAL")
	var deadline := Time.get_ticks_msec() + 15000
	while not FileAccess.file_exists("res://server-waiting") and Time.get_ticks_msec() < deadline:
		await process_frame
	if not _check(FileAccess.file_exists("res://server-waiting"), "Delayed request was not reached"):
		_finish()
		return
	var initial_reply_count := dock.find_children("AIReply*", "VBoxContainer", true, false).size()
	var initial_snapshot := ""
	while initial_snapshot.is_empty() and Time.get_ticks_msec() < deadline:
		var history := _history()
		if not history.get("agents", []).is_empty():
			initial_snapshot = history.agents[0].get("snapshot_id", "")
		await process_frame
	report["initial_snapshot"] = initial_snapshot
	if mode == "mode":
		consultation.button_pressed = false
		_send("DEVELOPMENT_MUST_STAY_SEPARATE")
	else:
		_send("STEERING_ADDITION_ONE")
		_send("STEERING_ADDITION_TWO")
	report["accepted_count"] = dock.get_meta("queued_message_count", -1)
	report["received_status"] = dock.find_child("MessageQueueStatus", true, false).text
	if mode in ["steering", "tools", "stop", "cancel"]:
		_check("已收到" in report.received_status and "等待安全边界" in report.received_status, "Pending supplement is not labelled as received but not applied")
	elif mode == "mode":
		_check("独立任务" in report.received_status, "Different-mode input is not labelled as a separate task")
	var count_expected := 1 if mode == "mode" else 2
	if not _check(report.accepted_count == count_expected, "Busy input was lost or not queued"):
		_finish()
		return
	if mode in ["steering", "tools"]:
		FileAccess.open("res://release-response", FileAccess.WRITE).store_string("release")
		deadline = Time.get_ticks_msec() + 15000
		while not dock.find_child("Stop", true, false).disabled and Time.get_ticks_msec() < deadline:
			await process_frame
		_check(dock.find_child("Stop", true, false).disabled, "Steered task did not finish")
		_check("STEERING_APPLIED_OK" in _text(), "Updated answer not displayed")
		_check("已应用补充要求" in _text(), "Applied supplement acknowledgement missing")
		_check(not "STALE_ORIGINAL_REPLY" in _text(), "Superseded answer was displayed")
		_check(dock.get_meta("queued_message_count", -1) == 0, "Applied inputs remain queued")
		report["initial_reply_count"] = initial_reply_count
		report["final_reply_count"] = dock.find_children("AIReply*", "VBoxContainer", true, false).size()
		_check(report.final_reply_count == initial_reply_count, "Supplement started a separate AI turn")
	else:
		if mode == "cancel":
			_send("停止")
		else:
			dock.find_child("Stop", true, false).pressed.emit()
		_check(dock.get_meta("queue_paused", false), "Stop did not pause pending inputs")
		_check(dock.get_meta("queued_message_count", -1) == count_expected, "Stop lost pending inputs")
		FileAccess.open("res://release-response", FileAccess.WRITE).store_string("release")
		await create_timer(0.5).timeout
		_check(not "STALE_ORIGINAL_REPLY" in _text(), "Stopped response was displayed")
	# Wait for the asynchronous history writer before checking persistence.
	deadline = Time.get_ticks_msec() + 10000
	var final_history := {}
	while Time.get_ticks_msec() < deadline:
		final_history = _history()
		if not final_history.get("agents", []).is_empty():
			var agent: Dictionary = final_history.agents[0]
			if (mode in ["steering", "tools"] and agent.get("messages", []).any(func(m): return m.get("content", "") == "STEERING_APPLIED_OK")) or (not mode in ["steering", "tools"] and agent.get("queue_paused", false) and agent.get("queued_messages", []).size() == count_expected):
				break
		await process_frame
	if _check(not final_history.get("agents", []).is_empty(), "History not saved"):
		var agent: Dictionary = final_history.agents[0]
		report["final_snapshot"] = agent.get("snapshot_id", "")
		_check(not initial_snapshot.is_empty() and report.final_snapshot == initial_snapshot, "Supplement changed task snapshot")
		if mode in ["steering", "tools"]:
			_check(agent.get("queued_messages", []).is_empty(), "Applied queue persisted")
		else:
			_check(agent.get("queue_paused", false), "Pause not persisted")
			_check(agent.get("queued_messages", []).size() == count_expected, "Pending inputs not persisted")
	_finish()
