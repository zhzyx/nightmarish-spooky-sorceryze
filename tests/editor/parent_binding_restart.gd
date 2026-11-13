@tool
extends SceneTree

func _initialize():
	_run.call_deferred()

func _write(name: String, value: Dictionary):
	var file := FileAccess.open(OS.get_environment("GONGGONG_TEST_WORKSPACE").path_join(name), FileAccess.WRITE)
	file.store_string(JSON.stringify(value))
	file.close()

func _shown(dock, text: String) -> bool:
	for label in dock.find_children("*", "RichTextLabel", true, false):
		if text in label.get_parsed_text():
			return true
	return false

func _send(dock, text: String):
	dock.find_child("ChatInput", true, false).text = text
	dock.find_child("Send", true, false).pressed.emit()

func _retry_checkpoint(dock, settings, previous_history: String, previous_bindings: Dictionary) -> bool:
	var deadline := Time.get_ticks_msec() + 90000
	while Time.get_ticks_msec() < deadline:
		await process_frame
		if _shown(dock, "聊天记录保存失败") and dock.find_child("Stop", true, false).disabled:
			break
	if not _shown(dock, "聊天记录保存失败") or not _shown(dock, "8001"):
		push_error("Binding checkpoint failure did not expose a recoverable Issue identity")
		return false
	var folder := OS.get_environment("GONGGONG_TEST_WORKSPACE")
	var original_issues := FileAccess.get_file_as_string(folder.path_join("fake-issues.json"))
	var original_calls := FileAccess.get_file_as_string(folder.path_join("fake-gh-calls.log"))
	# These replies must neither recreate the Issue, change its status, nor
	# replace the pending binding. Retry while the write fault still exists too.
	for reply in ["确认", "开始", "#8002 different-requirement", "重试"]:
		_send(dock, reply)
		await process_frame
		if settings.get_project_metadata("daqian", "bindings", {}) != previous_bindings:
			push_error("Failed checkpoint published or changed the pending binding")
			return false
		if FileAccess.get_file_as_string("res://.godot/editor/ai_chat_history.json") != previous_history:
			push_error("Failed checkpoint damaged the last valid history")
			return false
		if FileAccess.get_file_as_string(folder.path_join("fake-issues.json")) != original_issues or FileAccess.get_file_as_string(folder.path_join("fake-gh-calls.log")) != original_calls:
			push_error("Local checkpoint recovery repeated a remote Issue operation")
			return false
		if not dock.find_child("Stop", true, false).disabled:
			push_error("Failed checkpoint started production or a replacement requirements call")
			return false
	if DirAccess.remove_absolute("res://.godot/editor/ai_chat_history.json.tmp") != OK:
		return false
	_send(dock, "重试")
	return true

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
		var input_restored := false
		for agent in history.get("agents", []):
			if agent.get("conversation_id", "") == expected.conversation:
				parent_restored = true
				for message in agent.get("messages", []):
					if message.get("role", "") == "user" and message.get("content", "") == "Clarify pending parent binding feature":
						input_restored = true
		var passed: bool = actual == expected.binding and parent_restored and input_restored
		_write("binding-cold.json", {"ok": passed, "binding": actual, "parent_history_restored": parent_restored, "original_input_restored": input_restored})
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
	var fail_checkpoint := OS.get_environment("GONGGONG_TEST_CHECKPOINT_FAILURE") == "1"
	var previous_history := ""
	var previous_bindings: Dictionary = settings.get_project_metadata("daqian", "bindings", {}).duplicate(true)
	if fail_checkpoint:
		# Wait for a valid old snapshot, then make the actual atomic-write path
		# unwritable on all platforms without changing permission assumptions.
		dock.find_child("ChatInput", true, false).text = "Preserve old draft"
		dock.find_child("ChatInput", true, false).text_changed.emit()
		deadline = Time.get_ticks_msec() + 10000
		while Time.get_ticks_msec() < deadline:
			await process_frame
			if FileAccess.file_exists("res://.godot/editor/ai_chat_history.json") and not dock.get_meta("history_saving", false):
				previous_history = FileAccess.get_file_as_string("res://.godot/editor/ai_chat_history.json")
				if "Preserve old draft" in previous_history:
					break
		if "Preserve old draft" not in previous_history or DirAccess.make_dir_absolute("res://.godot/editor/ai_chat_history.json.tmp") != OK:
			push_error("Could not establish the real history write failure fixture")
			quit(1)
			return
	_send(dock, "Clarify pending parent binding feature")
	if fail_checkpoint and not await _retry_checkpoint(dock, settings, previous_history, previous_bindings):
		quit(1)
		return
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
			_write("binding-before.json", {"conversation": conversation, "binding": bound, "durable_before_crash": durable.get(conversation, {}) == bound, "checkpoint_failure_verified": fail_checkpoint})
			# The controller terminates this editor without its normal shutdown save.
			return
	for label in dock.find_children("*", "RichTextLabel", true, false):
		print("PARENT_BINDING_DIAGNOSTIC ", label.get_parsed_text())
	quit(1)
