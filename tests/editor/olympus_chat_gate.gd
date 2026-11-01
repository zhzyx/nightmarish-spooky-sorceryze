@tool
extends SceneTree

func _initialize():
	_run.call_deferred()

func _run():
	var dock = root.find_child("AI Chat", true, false)
	if dock == null or root.find_child("OlympusPage", true, false) == null:
		push_error("Missing native AI/Olympus dock")
		quit(1)
		return
	var settings = EditorInterface.get_editor_settings()
	settings.set_setting("olympus/workspace", OS.get_environment("OLYMPUS_TEST_WORKSPACE"))
	settings.set_setting("olympus/python", OS.get_environment("OLYMPUS_PYTHON"))
	var backend = dock.find_child("AIBackend", true, false)
	backend.select(0)
	backend.item_selected.emit(0)
	dock.find_child("APIEndpoint", true, false).text = OS.get_environment("OLYMPUS_TEST_ENDPOINT")
	dock.find_child("APIModel", true, false).text = "isolated-test"
	var mode = OS.get_environment("OLYMPUS_TEST_MODE")
	if not mode.begins_with("recovery"):
		dock.find_child("ChatInput", true, false).text = "Isolated Olympus gate validation"
		dock.find_child("Send", true, false).pressed.emit()
	if mode == "recovery_cancel":
		dock.find_child("Stop", true, false).pressed.emit()
		await create_timer(4).timeout
		dock.find_child("ChatInput", true, false).text = "Isolated Olympus gate validation"
		dock.find_child("Send", true, false).pressed.emit()
		mode = "accepted"
	if mode == "cancel":
		dock.find_child("Stop", true, false).pressed.emit()
		await create_timer(4).timeout
		if dock.get_meta("olympus_status", "") != "context_ready":
			print("OLYMPUS_CHAT_CANCEL_OK")
			quit(0)
			return
	for attempt in range(400):
		await create_timer(0.1).timeout
		if mode == "recovery" and dock.get_meta("olympus_reporting", "") == "recorded_file" and not FileAccess.file_exists("res://.godot/editor/ai_chat_resume.json"):
			print("OLYMPUS_CHAT_RECOVERY_OK")
			quit(0)
			return
		if mode in ["accepted", "tool"] and dock.get_meta("olympus_reporting", "") == "recorded_file":
			for label in dock.find_children("*", "RichTextLabel", true, false):
				if "OLYMPUS_FIXTURE_REPLY" in label.get_parsed_text():
					print("OLYMPUS_CHAT_FIXTURE_ACCEPTED_OK")
					quit(0)
					return
		if dock.get_meta("olympus_status", "") == "blocked":
			print("OLYMPUS_CHAT_FAIL_CLOSED_OK")
			quit(0)
			return
	push_error("Olympus did not return a rejection")
	print("GATE_STATUS=", dock.get_meta("olympus_status", "unset"))
	for label in dock.find_children("*", "RichTextLabel", true, false):
		print(label.get_parsed_text())
	quit(1)
