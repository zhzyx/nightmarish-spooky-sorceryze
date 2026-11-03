@tool
extends SceneTree

var frame_count := 0
var last_frame_usec := 0
var max_frame_gap := 0.0

func _measure_frame():
	frame_count += 1
	var now = Time.get_ticks_usec()
	if last_frame_usec:
		max_frame_gap = max(max_frame_gap, float(now-last_frame_usec)/1000000.0)
	last_frame_usec = now

func _initialize():
	_run.call_deferred()

func _reply(dock, text):
	dock.find_child("ChatInput", true, false).text = text
	dock.find_child("Send", true, false).pressed.emit()

func _shown(dock, needle):
	for label in dock.find_children("*", "RichTextLabel", true, false):
		if needle in label.get_parsed_text():
			return true
	return false

func _wait_shown(dock, needle, seconds = 20.0):
	for attempt in range(int(seconds * 20)):
		if _shown(dock, needle):
			return true
		await create_timer(0.05).timeout
	push_error("Issue guide did not show: " + needle)
	for label in dock.find_children("*", "RichTextLabel", true, false):
		print(label.get_parsed_text())
	return false

func _run_issue_guide(dock, mode):
	# Unbound send must stay in the conversation, without any model request.
	if not await _wait_shown(dock, "绑定本仓库的真实工单"):
		return false
	if _shown(dock, "Olympus 阻止本次发送") or dock.get_meta("olympus_status", "") != "issue_guide":
		push_error("Unbound send was blocked instead of guided")
		return false
	if mode == "issue_guide_cancel":
		_reply(dock, "取消")
		return await _wait_shown(dock, "已退出工单引导")
	var steps = [
		["新建", "新建工单 1/3"],
		["1", "新建工单 2/3"],
		["默认", "新建工单 3/3"],
		["guide-e2e-1", "已生成需求文档"],
	]
	if mode == "issue_guide_login":
		# gh is installed but logged out: the guide must explain login and create nothing.
		steps.append(["确认", "未创建远程 Issue"])
	steps.append(["确认", "Issue #42"])
	steps.append(["开始", "OLYMPUS_FIXTURE_REPLY"])
	for step in steps:
		if mode == "issue_guide_login" and step[1] == "Issue #42":
			if not _shown(dock, "尚未登录 github.com") or not _shown(dock, "auth login --hostname github.com"):
				push_error("Logged-out gh did not show login guidance")
				return false
			# Stands in for the user finishing `gh auth login` in a terminal.
			var flag = FileAccess.open(OS.get_environment("OLYMPUS_TEST_WORKSPACE").path_join("fixtures/gh-logged-in"), FileAccess.WRITE)
			flag.store_string("fixture")
			flag.close()
		_reply(dock, step[0])
		if not await _wait_shown(dock, step[1], 40.0):
			return false
	var settings = EditorInterface.get_editor_settings()
	if str(settings.get_setting("olympus/issue_number")) != "42" or settings.get_setting("olympus/request_id") != "guide-e2e-1":
		push_error("Guide did not persist the Issue binding")
		return false
	for attempt in range(200):
		if dock.get_meta("olympus_reporting", "") == "recorded_file":
			return true
		await create_timer(0.05).timeout
	push_error("Guided turn did not record its file receipt")
	return false

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
	process_frame.connect(_measure_frame)
	var mode = OS.get_environment("OLYMPUS_TEST_MODE")
	if not mode.begins_with("recovery"):
		dock.find_child("ChatInput", true, false).text = "Isolated Olympus gate validation"
		dock.find_child("Send", true, false).pressed.emit()
	if mode.begins_with("issue_guide"):
		var guided = await _run_issue_guide(dock, mode)
		print("OLYMPUS_FRAME_GAP=", max_frame_gap if frame_count > 1 else -1.0)
		if guided:
			print("OLYMPUS_CHAT_ISSUE_GUIDE_CANCEL_OK" if mode == "issue_guide_cancel" else "OLYMPUS_CHAT_ISSUE_GUIDE_OK")
		quit(0 if guided else 1)
		return
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
			print("OLYMPUS_FRAME_GAP=", max_frame_gap if frame_count > 1 else -1.0)
			print("OLYMPUS_CHAT_CANCEL_OK")
			quit(0)
			return
	if mode == "receipt_retry":
		var failed = false
		for attempt in range(200):
			await create_timer(0.05).timeout
			for label in dock.find_children("*", "RichTextLabel", true, false):
				if "文件回执失败" in label.get_parsed_text():
					failed = true
			if failed and not dock.find_child("Send", true, false).disabled:
				break
		if not failed:
			push_error("Missing failed receipt before explicit retry")
			quit(1)
			return
		dock.find_child("ChatInput", true, false).text = "Explicit retry after failed receipt"
		dock.find_child("Send", true, false).pressed.emit()
		mode = "accepted"
	if mode == "receipt_cancel":
		for attempt in range(200):
			await create_timer(0.01).timeout
			if dock.get_meta("olympus_status", "") == "context_ready" and dock.get_meta("olympus_reporting", "") == "queued":
				dock.find_child("Stop", true, false).pressed.emit()
				await create_timer(4).timeout
				print("OLYMPUS_FRAME_GAP=", max_frame_gap if frame_count > 1 else -1.0)
				print("OLYMPUS_CHAT_RECEIPT_CANCEL_OK")
				quit(0)
				return
		push_error("Did not observe cancellable receipt wait")
		quit(1)
		return
	for attempt in range(400):
		await create_timer(0.1).timeout
		if mode == "recovery_receipt_failure":
			for label in dock.find_children("*", "RichTextLabel", true, false):
				if "文件回执失败" in label.get_parsed_text():
					await create_timer(1.5).timeout
					if not FileAccess.file_exists("res://.godot/editor/ai_chat_resume.json"):
						push_error("Failed recovery receipt lost journal")
						quit(1)
						return
					print("OLYMPUS_FRAME_GAP=", max_frame_gap if frame_count > 1 else -1.0)
					print("OLYMPUS_CHAT_RECOVERY_RECEIPT_FAILURE_OK")
					quit(0)
					return
		if mode == "receipt_failure" and dock.get_meta("olympus_reporting", "") == "pending_retry" and not dock.find_child("Send", true, false).disabled:
			print("OLYMPUS_FRAME_GAP=", max_frame_gap if frame_count > 1 else -1.0)
			print("OLYMPUS_CHAT_RECEIPT_FAILURE_OK")
			quit(0)
			return
		if mode == "recovery" and dock.get_meta("olympus_reporting", "") == "recorded_file" and not FileAccess.file_exists("res://.godot/editor/ai_chat_resume.json"):
			print("OLYMPUS_FRAME_GAP=", max_frame_gap if frame_count > 1 else -1.0)
			print("OLYMPUS_CHAT_RECOVERY_OK")
			quit(0)
			return
		if mode in ["accepted", "tool"] and dock.get_meta("olympus_reporting", "") == "recorded_file":
			for label in dock.find_children("*", "RichTextLabel", true, false):
				if "OLYMPUS_FIXTURE_REPLY" in label.get_parsed_text():
					print("OLYMPUS_FRAME_GAP=", max_frame_gap if frame_count > 1 else -1.0)
					print("OLYMPUS_CHAT_FIXTURE_ACCEPTED_OK")
					quit(0)
					return
		if dock.get_meta("olympus_status", "") == "blocked":
			print("OLYMPUS_FRAME_GAP=", max_frame_gap if frame_count > 1 else -1.0)
			print("OLYMPUS_CHAT_FAIL_CLOSED_OK")
			quit(0)
			return
	push_error("Olympus did not return a rejection")
	print("GATE_STATUS=", dock.get_meta("olympus_status", "unset"))
	for label in dock.find_children("*", "RichTextLabel", true, false):
		print(label.get_parsed_text())
	quit(1)
