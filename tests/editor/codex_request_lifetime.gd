@tool
extends SceneTree

var dock: Node
var folder: String
var cases: Array = []

func _initialize():
	_run.call_deferred()

func contains(text: String) -> bool:
	for label in dock.find_children("*", "RichTextLabel", true, false):
		if text in label.get_parsed_text():
			return true
	return false

func finish(ok: bool, reason := ""):
	var file = FileAccess.open(folder.path_join("result.json"), FileAccess.WRITE)
	file.store_string(JSON.stringify({"ok": ok, "error": reason, "cases": cases}))
	file.close()
	if not ok:
		for label in dock.find_children("*", "RichTextLabel", true, false):
			print(label.get_parsed_text())
	quit(0 if ok else 1)

func request_files() -> Array:
	var found: Array = []
	for name in DirAccess.get_files_at(OS.get_environment("TEMP")):
		if name.begins_with("godot_codex_request-"):
			found.append(name)
	return found

func _run():
	await create_timer(1).timeout
	folder = OS.get_environment("GONGGONG_TEST_WORKSPACE")
	dock = root.find_child("AI Chat", true, false)
	if dock == null:
		quit(1)
		return
	var settings = EditorInterface.get_editor_settings()
	settings.set_setting("gonggong/workspace", folder)
	root.find_child("AI Chat", true, false).set_runtime_field("workflow_python", OS.get_environment("GONGGONG_PYTHON"))
	settings.set_setting("gonggong/issue_number", "6")
	settings.set_setting("gonggong/request_id", "isolated-gate")
	var backend = dock.get_ai_settings_control().find_child("AIBackend", true, false)
	backend.select(0)
	backend.item_selected.emit(0)
	dock.get_ai_settings_control().find_child("APIEndpoint", true, false).text = OS.get_environment("LIFETIME_ENDPOINT")
	dock.get_ai_settings_control().find_child("APIModel", true, false).text = "lifetime-fixture"
	dock.get_ai_settings_control().find_child("APIKey", true, false).text = "fixture-key"
	backend.select(2)
	backend.item_selected.emit(2)
	dock.get_environment_settings_control().find_child("CLINode", true, false).text = OS.get_environment("GONGGONG_NODE")
	dock.get_environment_settings_control().find_child("CLINode", true, false).text_changed.emit(dock.get_environment_settings_control().find_child("CLINode", true, false).text)
	dock.get_environment_settings_control().find_child("CodexEntry", true, false).text = folder.path_join("entry.js")
	dock.get_environment_settings_control().find_child("CodexEntry", true, false).text_changed.emit(dock.get_environment_settings_control().find_child("CodexEntry", true, false).text)
	dock.get_ai_settings_control().find_child("CodexModel", true, false).text = "lifetime-fixture"
	for name in ["success", "failure", "cancel", "start_failure"]:
		dock.find_child("ChatInput", true, false).text = name
		dock.find_child("Send", true, false).pressed.emit()
		var deadline = Time.get_ticks_msec() + 20000
		var wire = folder.path_join("wire/" + name + ".json")
		while Time.get_ticks_msec() < deadline:
			await create_timer(0.02).timeout
			# Let requirements intake start with a valid Node, then fail only the native chat launch.
			if name == "start_failure" and FileAccess.file_exists(folder.path_join("wire/intake-start_failure.json")):
				dock.get_environment_settings_control().find_child("CLINode", true, false).text = folder.path_join("not-executable.exe")
			if FileAccess.file_exists(folder.path_join("wire/missing.json")):
				var failure = JSON.parse_string(FileAccess.get_file_as_string(folder.path_join("wire/missing.json")))
				if not failure is Dictionary:
					finish(false, "invalid missing-request receipt")
					return
				var read_error_code = str(failure.get("code", ""))
				var missing = read_error_code == "ENOENT"
				cases.append({"name": name, "request_missing_after_return": missing, "read_error_code": read_error_code, "cleanup": request_files().is_empty(), "remaining_request_files": request_files().size()})
				finish(OS.get_environment("LIFETIME_EXPECT_MISSING") == "1" and missing, "request_missing_after_return" if missing else "unexpected request read error")
				return
			if name == "start_failure":
				if contains("无法启动 Codex 桥接"):
					break
			elif FileAccess.file_exists(wire):
				break
		if Time.get_ticks_msec() >= deadline:
			finish(false, "missing outcome: " + name)
			return
		if name != "start_failure":
			var receipt = JSON.parse_string(FileAccess.get_file_as_string(wire))
			if not receipt.exists or not FileAccess.file_exists(receipt.request):
				finish(false, "request not retained while bridge active: " + name)
				return
			if name == "cancel":
				dock.find_child("Stop", true, false).pressed.emit()
		while Time.get_ticks_msec() < deadline and not dock.find_child("Stop", true, false).disabled:
			await create_timer(0.02).timeout
		await create_timer(0.1).timeout
		var clean = request_files().is_empty()
		if not clean or not dock.find_child("Stop", true, false).disabled:
			finish(false, "terminal cleanup failed: " + name)
			return
		if name == "success" and not contains("LIFETIME_SUCCESS"):
			finish(false, "missing successful response")
			return
		if name == "failure" and not contains("Codex bridge exited with code 23"):
			finish(false, "missing expected failure")
			return
		cases.append({"name": name, "cleanup": clean, "request_retained": name != "start_failure", "remaining_request_files": request_files().size()})
		# Failed/cancelled queues stay paused. Explicitly resume only this empty fixture queue.
		dock.find_child("ResumeMessageQueue", true, false).pressed.emit()
	finish(true)
