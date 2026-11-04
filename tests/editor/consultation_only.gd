@tool
extends SceneTree

func _initialize():
	_run.call_deferred()

func _shown(dock, text):
	for label in dock.find_children("*", "RichTextLabel", true, false):
		if text in label.get_parsed_text():
			return true
	return false

func _count(dock, text):
	var count = 0
	for label in dock.find_children("*", "RichTextLabel", true, false):
		count += label.get_parsed_text().count(text)
	return count

func _wait(dock, text):
	for i in range(600):
		await create_timer(0.05).timeout
		if _shown(dock, text):
			return true
	for label in dock.find_children("*", "RichTextLabel", true, false):
		print(label.get_parsed_text())
	return false

func _send(dock, text):
	dock.find_child("ChatInput", true, false).text = text
	dock.find_child("Send", true, false).pressed.emit()

func _run():
	var dock = root.find_child("AI Chat", true, false)
	var check = dock.find_child("ConsultationOnly", true, false)
	assert(not check.button_pressed)
	assert(check.get_index() + 1 == dock.find_child("Send", true, false).get_index())
	var settings = EditorInterface.get_editor_settings()
	settings.set_setting("gonggong/workspace", OS.get_environment("GONGGONG_TEST_WORKSPACE"))
	settings.set_setting("gonggong/python", "missing-python")
	settings.set_setting("gonggong/issue_number", "")
	settings.set_setting("gonggong/request_id", "")
	var backend = dock.find_child("AIBackend", true, false)
	backend.select(0)
	backend.item_selected.emit(0)
	dock.find_child("APIEndpoint", true, false).text = OS.get_environment("GONGGONG_TEST_ENDPOINT")
	dock.find_child("APIModel", true, false).text = "fixture"
	for name in ["AllowTools", "AutoApplyFileChanges", "AutoExecuteCommands", "EngineAutoRestart"]:
		dock.find_child(name, true, false).button_pressed = true
	_send(dock, "INITIAL_DEVELOPMENT_MUST_GATE")
	if not await _wait(dock, "已触发本地配置点火器"):
		quit(1)
		return
	assert(dock.find_child("GongGongRuntimeSetup", true, false).visible)
	dock.find_child("GongGongRuntimeSetup", true, false).hide()
	check.button_pressed = true
	_send(dock, "CONSULTATION_ATTACK")
	# Changing the next-message checkbox cannot upgrade the active turn.
	check.button_pressed = false
	if not await _wait(dock, "CONSULTATION_READ_OK"):
		quit(1)
		return
	await create_timer(0.2).timeout
	check.button_pressed = true
	backend.select(1)
	backend.item_selected.emit(1)
	_send(dock, "CLI_MUST_NOT_START")
	if not await _wait(dock, "原生 CLI 不执行此请求"):
		quit(1)
		return
	# Return to API and explicitly resume the rejected queued consultation.
	backend.select(0)
	backend.item_selected.emit(0)
	dock.find_child("ResumeMessageQueue", true, false).pressed.emit()
	if not await _wait(dock, "CONSULTATION_QUEUE_OK"):
		quit(1)
		return
	await create_timer(0.2).timeout
	check.button_pressed = false
	var previous_gate = _count(dock, "已触发本地配置点火器")
	_send(dock, "DEVELOPMENT_MUST_GATE")
	await create_timer(2).timeout
	if _count(dock, "已触发本地配置点火器") <= previous_gate:
		push_error("Development did not re-enter its gate after consultation")
		quit(1)
		return
	print("CONSULTATION_NATIVE_OK")
	quit(0)
