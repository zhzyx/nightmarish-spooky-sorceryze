@tool
extends SceneTree

func _initialize():
	_run.call_deferred()

func _contains(dock, text: String) -> bool:
	for label in dock.find_children("*", "RichTextLabel", true, false):
		if text in label.get_parsed_text():
			return true
	return false

func _wait_reply(dock, number: int) -> bool:
	for attempt in range(900):
		await create_timer(0.1).timeout
		if _contains(dock, "INTAKE_WORK_REPLY_" + str(number)) and dock.get_meta("olympus_reporting", "") == "recorded_file":
			return true
	push_error("Missing native intake completion " + str(number))
	return false

func _send(dock, text: String):
	dock.find_child("ChatInput", true, false).text = text
	dock.find_child("Send", true, false).pressed.emit()

func _run():
	var dock = root.find_child("AI Chat", true, false)
	if dock == null:
		quit(1)
		return
	var folder := OS.get_environment("OLYMPUS_TEST_WORKSPACE")
	var settings = EditorInterface.get_editor_settings()
	settings.set_setting("olympus/workspace", folder)
	settings.set_setting("olympus/python", OS.get_environment("OLYMPUS_PYTHON"))
	settings.set_setting("olympus/issue_number", "")
	settings.set_setting("olympus/request_id", "")
	var backend = dock.find_child("AIBackend", true, false)
	backend.select(0)
	backend.item_selected.emit(0)
	dock.find_child("APIEndpoint", true, false).text = OS.get_environment("OLYMPUS_TEST_ENDPOINT")
	dock.find_child("APIModel", true, false).text = "fixture"
	dock.find_child("APIKey", true, false).text = "intake-unit-session-secret"
	var prompts = ["Create first feature button", "Refine current feature", "Create second feature label", "Create second feature label"]
	for i in range(prompts.size()):
		_send(dock, prompts[i])
		if not await _wait_reply(dock, i + 1):
			quit(1)
			return
	_send(dock, "Cancel pending feature")
	for attempt in range(500):
		await create_timer(0.02).timeout
		if FileAccess.file_exists(folder.path_join("model_waiting")):
			break
	_send(dock, "取消")
	await create_timer(2).timeout
	if dock.get_meta("olympus_status", "") != "issue_guide_cancelled":
		push_error("Cancelled intake did not remain cancelled")
		quit(1)
		return
	_send(dock, "API failure feature")
	for attempt in range(500):
		await create_timer(0.02).timeout
		if _contains(dock, "Requirements model API failed"):
			break
	if not _contains(dock, "Requirements model API failed"):
		quit(1)
		return
	FileAccess.open(folder.path_join("api_fixed"), FileAccess.WRITE).store_string("fixed")
	_send(dock, "重试")
	if not await _wait_reply(dock, 5):
		quit(1)
		return
	FileAccess.open(folder.path_join("gh_disabled"), FileAccess.WRITE).store_string("disabled")
	_send(dock, "GitHub repair feature")
	for attempt in range(500):
		await create_timer(0.02).timeout
		if _contains(dock, "gh_unauthenticated"):
			break
	if not _contains(dock, "gh_unauthenticated"):
		quit(1)
		return
	DirAccess.remove_absolute(folder.path_join("gh_disabled"))
	_send(dock, "重试")
	if not await _wait_reply(dock, 6):
		quit(1)
		return
	print("REQUIREMENTS_AGENT_NATIVE_OK")
	quit(0)
