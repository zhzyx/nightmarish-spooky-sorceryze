@tool
extends SceneTree

var stages: Array[String] = []

func _initialize():
	_run.call_deferred()

func _text(dock) -> String:
	var text := ""
	for label in dock.find_children("*", "RichTextLabel", true, false):
		text += label.get_parsed_text() + "\n"
	return text

func _send(dock, text: String):
	dock.find_child("ChatInput", true, false).text = text
	dock.find_child("Send", true, false).pressed.emit()

func _command_is_running(pid: int) -> bool:
	# The command is a child of the guard, so Godot's child-only PID table
	# cannot answer this. Signal zero checks the actual OS process instead.
	var output: Array = []
	return OS.execute("/bin/kill", PackedStringArray(["-0", str(pid)]), output, true) == 0

func _wait_reply(dock, marker: String) -> bool:
	for attempt in range(1500):
		await create_timer(0.1).timeout
		var text := _text(dock)
		if marker in text and dock.find_child("Stop", true, false).disabled and dock.get_meta("gonggong_reporting", "") == "recorded_file":
			stages.append(marker)
			return true
		if ("未通过" in text or "The service did not" in text or "candidate_issue_mismatch" in text or "AI request failed" in text or "GongGong 文件回执失败" in text) and dock.find_child("Stop", true, false).disabled:
			break
	push_error("Missing candidate fixture stage: " + marker)
	return false

func _finish(dock, ok: bool, detail: String = ""):
	var settings = EditorInterface.get_editor_settings()
	FileAccess.open("res://runtime-report.json", FileAccess.WRITE).store_string(JSON.stringify({
		"ok": ok,
		"text": _text(dock),
		"stages": stages,
		"detail": detail,
		"bindings": settings.get_project_metadata("daqian", "bindings", {}),
		"global_issue": settings.get_setting("gonggong/issue_number"),
		"global_request": settings.get_setting("gonggong/request_id"),
	}))
	quit(0 if ok else 1)

func _run():
	var dock = root.find_child("AI Chat", true, false)
	var settings = EditorInterface.get_editor_settings()
	settings.set_setting("gonggong/workspace", OS.get_environment("CANDIDATE_FIXTURE_ROOT"))
	root.find_child("AI Chat", true, false).set_runtime_field("workflow_python", OS.get_environment("CANDIDATE_FIXTURE_PYTHON"))
	# Ordinary conversations must retain their own bindings without replacing
	# the separately configured global default, even after another chat binds.
	settings.set_setting("gonggong/issue_number", "999")
	settings.set_setting("gonggong/request_id", "fixture-global-sentinel")
	settings.set_setting("ai_chat/parallel_work_orders_config", "")
	var backend = dock.get_ai_settings_control().find_child("AIBackend", true, false)
	backend.select(0)
	backend.item_selected.emit(0)
	dock.get_ai_settings_control().find_child("APIEndpoint", true, false).text = OS.get_environment("CANDIDATE_FIXTURE_ENDPOINT")
	dock.get_ai_settings_control().find_child("APIModel", true, false).text = "fixture"
	dock.get_ai_settings_control().find_child("APIKey", true, false).text = "fixture-key"
	dock.get_environment_settings_control().find_child("CLINode", true, false).text = OS.get_environment("CANDIDATE_FIXTURE_NODE")
	dock.get_environment_settings_control().find_child("CLINode", true, false).text_changed.emit(dock.get_environment_settings_control().find_child("CLINode", true, false).text)
	dock.get_environment_settings_control().find_child("CLIBridge", true, false).text = OS.get_environment("CANDIDATE_FIXTURE_SOURCE").path_join("tools/codebuddy_cli/godot_bridge.js")
	dock.get_ai_settings_control().find_child("AllowTools", true, false).button_pressed = true
	dock.get_ai_settings_control().find_child("AutoApplyFileChanges", true, false).button_pressed = true
	dock.get_ai_settings_control().find_child("AutoExecuteCommands", true, false).button_pressed = true
	_send(dock, "CANDIDATE_START")
	if not await _wait_reply(dock, "CANDIDATE_BOUNDARY_OK"):
		_finish(dock, false, "initial tool boundaries")
		return
	_send(dock, "CANDIDATE_CANCEL")
	for attempt in range(200):
		if FileAccess.file_exists("res://cancel-ready"):
			break
		await create_timer(0.1).timeout
	if not FileAccess.file_exists("res://cancel-ready"):
		_finish(dock, false, "guarded command did not start for cancellation")
		return
	var command_pid := FileAccess.get_file_as_string("res://cancel-ready").to_int()
	dock.find_child("Stop", true, false).pressed.emit()
	for attempt in range(50):
		if not _command_is_running(command_pid):
			break
		await create_timer(0.1).timeout
	if _command_is_running(command_pid):
		_finish(dock, false, "Stop left the guarded command running")
		return
	# Allow the same guard to finish source verification and receipt delivery.
	await create_timer(0.5).timeout
	stages.append("CANDIDATE_CANCEL_OK")
	_send(dock, "CANDIDATE_SECOND")
	if not await _wait_reply(dock, "CANDIDATE_SECOND_OK"):
		_finish(dock, false, "same Issue second-turn intake")
		return
	var tabs = dock.find_child("AgentTabs", true, false)
	var first_index: int = tabs.current_tab
	dock.find_child("AddAgent", true, false).pressed.emit()
	if tabs.current_tab == first_index:
		_finish(dock, false, "second parent conversation was not selected")
		return
	_send(dock, "CANDIDATE_OTHER")
	if not await _wait_reply(dock, "CANDIDATE_OTHER_OK"):
		_finish(dock, false, "second parent Issue")
		return
	tabs.current_tab = first_index
	var confirmation = dock.find_child("WorkOrderConfirmation", true, false)
	confirmation.visibility_changed.connect(func():
		if confirmation.visible and confirmation.title == "确认设计定版":
			confirmation.get_ok_button().call_deferred("emit_signal", "pressed")
	)
	_send(dock, "CANDIDATE_RESUME")
	if not await _wait_reply(dock, "CANDIDATE_RESUMED_OK"):
		_finish(dock, false, "first parent after second parent binding")
		return
	# The resumed intake finalizes one work order in the candidate only. The
	# real completion callback must discover it and dispatch an isolated child.
	if not await _wait_reply(dock, "CANDIDATE_CHILD_OK"):
		_finish(dock, false, "child did not inherit the latest candidate requirement")
		return
	var bindings: Dictionary = settings.get_project_metadata("daqian", "bindings", {})
	var requests: Array = []
	for binding in bindings.values():
		requests.append(binding.get("request_id", ""))
	var isolated_bindings := "runtime-candidate-fixture" in requests and "runtime-candidate-other" in requests
	var global_unchanged: bool = str(settings.get_setting("gonggong/issue_number")) == "999" and settings.get_setting("gonggong/request_id") == "fixture-global-sentinel"
	_finish(dock, isolated_bindings and global_unchanged, "" if isolated_bindings and global_unchanged else "conversation bindings replaced the global default")
