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
		if _contains(dock, "INTAKE_WORK_REPLY_" + str(number)) and dock.get_meta("gonggong_reporting", "") == "recorded_file":
			return true
		if attempt == 150 or (number == 1 and _contains(dock, "尚未完成")):
			for label in dock.find_children("*", "RichTextLabel", true, false):
				print("NATIVE_INTAKE_DIAGNOSTIC ", label.get_parsed_text())
			if number == 1 and _contains(dock, "尚未完成"):
				return false
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
	var folder := OS.get_environment("GONGGONG_TEST_WORKSPACE")
	var settings = EditorInterface.get_editor_settings()
	settings.set_setting("gonggong/workspace", folder)
	settings.set_setting("gonggong/python", OS.get_environment("GONGGONG_PYTHON"))
	settings.set_setting("gonggong/issue_number", "")
	settings.set_setting("gonggong/request_id", "")
	var backend = dock.find_child("AIBackend", true, false)
	backend.select(0)
	backend.item_selected.emit(0)
	dock.find_child("APIEndpoint", true, false).text = OS.get_environment("GONGGONG_TEST_ENDPOINT")
	dock.find_child("APIModel", true, false).text = "fixture"
	dock.find_child("APIKey", true, false).text = "intake-unit-session-secret"
	var runtime_source = OS.get_environment("GONGGONG_TEST_RUNTIME_SOURCE")
	if not runtime_source.is_empty():
		settings.set_setting("gonggong/python", folder.path_join("missing-python.exe"))
	_send(dock, "Create first feature button")
	if not runtime_source.is_empty():
		await create_timer(0.2).timeout
		var setup = dock.find_child("GongGongRuntimeSetup", true, false)
		if not setup.visible:
			push_error("Missing Python did not open the local environment igniter")
			quit(1)
			return
		if "Python" not in setup.find_child("GongGongMissingComponents", true, false).text:
			push_error("Igniter did not list the missing component")
			quit(1)
			return
		setup.find_child("GongGongRuntimeSource", true, false).text = runtime_source
		setup.get_ok_button().pressed.emit()
	var intake_waiting := false
	for attempt in range(1000):
		await create_timer(0.02).timeout
		if FileAccess.file_exists(folder.path_join("first_intake_waiting")):
			intake_waiting = true
			break
	if not intake_waiting:
		for label in dock.find_children("*", "RichTextLabel", true, false):
			print("NATIVE_INTAKE_START_DIAGNOSTIC ", label.get_parsed_text())
		push_error("First requirements request never reached the isolated model fixture")
		quit(1)
		return
	_send(dock, "Refine first feature during requirements phase")
	if dock.get_meta("queued_message_count", 0) != 1:
		push_error("Supplement sent during intake was not retained until the safe boundary")
		quit(1)
		return
	if dock.find_child("Stop", true, false).disabled:
		push_error("Requirements intake incorrectly appears idle and cannot be stopped")
		quit(1)
		return
	if not await _wait_reply(dock, 1):
		quit(1)
		return
	var prompts = ["Refine current feature", "Create second feature label", "Create second feature label"]
	for i in range(prompts.size()):
		_send(dock, prompts[i])
		if not await _wait_reply(dock, i + 2):
			quit(1)
			return
	_send(dock, "Cancel pending feature")
	for attempt in range(500):
		await create_timer(0.02).timeout
		if FileAccess.file_exists(folder.path_join("model_waiting")):
			break
	_send(dock, "取消")
	await create_timer(2).timeout
	if dock.get_meta("gonggong_status", "") != "issue_guide_cancelled":
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
	_send(dock, "Clarify pending requirement")
	for attempt in range(500):
		await create_timer(0.02).timeout
		if _contains(dock, "INTAKE_CLARIFICATION_REQUIRED"):
			break
	if not _contains(dock, "INTAKE_CLARIFICATION_REQUIRED") or not dock.find_child("Stop", true, false).disabled:
		push_error("Requirements clarification did not release the active turn")
		quit(1)
		return
	_send(dock, "补充验收：点击后出现状态文字")
	if not await _wait_reply(dock, 7):
		quit(1)
		return
	dock.find_child("GongGongEnvironmentSetup", true, false).pressed.emit()
	if not dock.find_child("GongGongRuntimeSetup", true, false).visible:
		push_error("Manual environment repair is unavailable after setup")
		quit(1)
		return
	print("REQUIREMENTS_AGENT_NATIVE_OK")
	quit(0)
