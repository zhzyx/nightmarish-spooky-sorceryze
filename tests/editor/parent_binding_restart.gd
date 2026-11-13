@tool
extends SceneTree

func _initialize():
	_run.call_deferred()

func _write(name: String, value: Dictionary):
	var file := FileAccess.open(OS.get_environment("GONGGONG_TEST_WORKSPACE").path_join(name), FileAccess.WRITE)
	file.store_string(JSON.stringify(value))
	file.close()

func _run():
	var dock = root.find_child("AI Chat", true, false)
	if dock == null:
		quit(1)
		return
	var settings = EditorInterface.get_editor_settings()
	var folder := OS.get_environment("GONGGONG_TEST_WORKSPACE")
	if OS.get_environment("GONGGONG_TEST_BINDING_PHASE") == "cold":
		var expected: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(folder.path_join("binding-before.json")))
		var restored: Dictionary = settings.get_project_metadata("daqian", "bindings", {})
		var actual: Dictionary = restored.get(expected.conversation, {})
		var history: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://.godot/editor/ai_chat_history.json"))
		var parent_restored := false
		for agent in history.get("agents", []):
			if agent.get("conversation_id", "") == expected.conversation:
				parent_restored = true
		var passed: bool = actual == expected.binding and parent_restored
		_write("binding-cold.json", {"ok": passed, "binding": actual, "parent_history_restored": parent_restored})
		quit(0 if passed else 1)
		return

	settings.set_setting("gonggong/workspace", folder)
	settings.set_setting("gonggong/issue_number", "")
	settings.set_setting("gonggong/request_id", "")
	if not dock.set_runtime_field("workflow_python", OS.get_environment("GONGGONG_TEST_PYTHON")).is_empty():
		quit(1)
		return
	var backend = dock.find_child("AIBackend", true, false)
	backend.select(0)
	backend.item_selected.emit(0)
	var ai_settings = dock.get_ai_settings_control()
	ai_settings.find_child("APIEndpoint", true, false).text = OS.get_environment("GONGGONG_TEST_ENDPOINT")
	dock.find_child("APIModel", true, false).text = "fixture"
	var key = ai_settings.find_child("APIKey", true, false)
	key.text = "binding-fixture-not-a-credential"
	key.text_changed.emit(key.text)
	var deadline := Time.get_ticks_msec() + 20000
	while Time.get_ticks_msec() < deadline:
		var catalog: Dictionary = dock.get_model_catalog_snapshot()
		if catalog.get("state", "") == "ready" and catalog.get("catalog_current", false) and not catalog.get("loading", true) and not dock.find_child("Send", true, false).disabled:
			break
		await process_frame
	if dock.find_child("Send", true, false).disabled:
		quit(1)
		return
	dock.find_child("ChatInput", true, false).text = "Clarify pending parent binding feature"
	dock.find_child("Send", true, false).pressed.emit()
	deadline = Time.get_ticks_msec() + 90000
	while Time.get_ticks_msec() < deadline:
		await process_frame
		var bindings: Dictionary = settings.get_project_metadata("daqian", "bindings", {})
		for conversation in bindings:
			var bound: Dictionary = bindings[conversation]
			if str(bound.get("issue_number", "")) != "8001":
				continue
			var disk := ConfigFile.new()
			var loaded := disk.load("res://.godot/editor/project_metadata.cfg")
			var durable: Dictionary = disk.get_value("daqian", "bindings", {}) if loaded == OK else {}
			_write("binding-before.json", {"conversation": conversation, "binding": bound, "durable_before_crash": durable.get(conversation, {}) == bound})
			# The controller terminates this editor without its normal shutdown save.
			return
	for label in dock.find_children("*", "RichTextLabel", true, false):
		print("PARENT_BINDING_DIAGNOSTIC ", label.get_parsed_text())
	quit(1)
