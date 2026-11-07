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

func _wait_reply(dock, marker: String) -> bool:
	for attempt in range(1500):
		await create_timer(0.1).timeout
		var text := _text(dock)
		if marker in text and dock.find_child("Stop", true, false).disabled and dock.get_meta("gonggong_reporting", "") == "recorded_file":
			stages.append(marker)
			return true
		if ("未通过" in text or "The service did not" in text or "candidate_issue_mismatch" in text) and dock.find_child("Stop", true, false).disabled:
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
	settings.set_setting("gonggong/python", OS.get_environment("CANDIDATE_FIXTURE_PYTHON"))
	# Ordinary conversations must retain their own bindings without replacing
	# the separately configured global default, even after another chat binds.
	settings.set_setting("gonggong/issue_number", "999")
	settings.set_setting("gonggong/request_id", "fixture-global-sentinel")
	settings.set_setting("ai_chat/parallel_work_orders_config", "")
	var backend = dock.find_child("AIBackend", true, false)
	backend.select(0)
	backend.item_selected.emit(0)
	dock.find_child("APIEndpoint", true, false).text = OS.get_environment("CANDIDATE_FIXTURE_ENDPOINT")
	dock.find_child("APIModel", true, false).text = "fixture"
	dock.find_child("APIKey", true, false).text = "fixture-key"
	dock.find_child("CLINode", true, false).text = OS.get_environment("CANDIDATE_FIXTURE_NODE")
	dock.find_child("CLIBridge", true, false).text = OS.get_environment("CANDIDATE_FIXTURE_SOURCE").path_join("tools/codebuddy_cli/godot_bridge.js")
	dock.find_child("AllowTools", true, false).button_pressed = true
	dock.find_child("AutoApplyFileChanges", true, false).button_pressed = true
	dock.find_child("AutoExecuteCommands", true, false).button_pressed = true
	_send(dock, "CANDIDATE_START")
	if not await _wait_reply(dock, "CANDIDATE_BOUNDARY_OK"):
		_finish(dock, false, "initial tool boundaries")
		return
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
