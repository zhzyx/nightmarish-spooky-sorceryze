@tool
extends SceneTree

var dock

func _initialize():
	_run.call_deferred()

func shown(text):
	for label in dock.find_children("*", "RichTextLabel", true, false):
		if text in label.get_parsed_text():
			return true
	return false

func send(text, expected):
	dock.find_child("ChatInput", true, false).text = text
	dock.find_child("Send", true, false).pressed.emit()
	# The checkbox controls the next message, never the active round's permissions.
	dock.find_child("ConsultationOnly", true, false).button_pressed = false
	for i in range(600):
		await create_timer(0.05).timeout
		if shown(expected) and dock.find_child("Stop", true, false).disabled:
			return true
	for label in dock.find_children("*", "RichTextLabel", true, false):
		print(label.get_parsed_text())
	return false

func _run():
	dock = root.find_child("AI Chat", true, false)
	var settings = EditorInterface.get_editor_settings()
	settings.set_setting("gonggong/workspace", OS.get_environment("CONSULT_ABSENT"))
	settings.set_setting("gonggong/python", "missing-python")
	settings.set_setting("gonggong/issue_number", "")
	settings.set_setting("gonggong/request_id", "")
	var backend = dock.find_child("AIBackend", true, false)
	backend.select(2)
	backend.item_selected.emit(2)
	dock.find_child("CLINode", true, false).text = OS.get_environment("CONSULT_NODE")
	dock.find_child("CodexEntry", true, false).text = OS.get_environment("CONSULT_ENTRY")
	for name in ["AllowTools", "AutoApplyFileChanges", "AutoExecuteCommands", "EngineAutoRestart"]:
		dock.find_child(name, true, false).button_pressed = true
	var check = dock.find_child("ConsultationOnly", true, false)
	assert(not check.button_pressed)
	assert(check.get_index() + 1 == dock.find_child("Send", true, false).get_index())
	check.button_pressed = true
	if not await send("ATTACK", "invalid action"):
		quit(1)
		return
	check.button_pressed = true
	dock.find_child("ChatInput", true, false).text = "CANCEL"
	dock.find_child("Send", true, false).pressed.emit()
	check.button_pressed = false
	var cancellation_started = false
	for i in range(600):
		await create_timer(0.05).timeout
		if '"prompt":"CANCEL"' in FileAccess.get_file_as_string(OS.get_environment("CONSULT_WIRE")):
			cancellation_started = true
			break
	assert(cancellation_started)
	dock.find_child("Stop", true, false).pressed.emit()
	await create_timer(0.2).timeout
	check.button_pressed = true
	if not await send("READ", "CODEX_CONSULTATION_READ_OK"):
		quit(1)
		return
	# Returning to development must invoke the Issue/environment gate again.
	if not await send("DEVELOPMENT_MUST_GATE", "已触发本地配置点火器"):
		quit(1)
		return
	print("CODEX_CONSULTATION_NATIVE_OK")
	quit(0)
