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
	if mode.begins_with("issue_guide_status"):
		var direct_status = mode.begins_with("issue_guide_status_direct")
		var prompt = "请在天枢工单详情中刷新状态" if direct_status else "确认开工：回复"
		if not await _wait_shown(dock, prompt):
			return false
		if dock.get_meta("gonggong_status", "") != "issue_guide":
			return false
		await create_timer(0.1).timeout
		# Retry re-reads the same rejected Issue; it is not permission to start.
		var fixture = OS.get_environment("GONGGONG_TEST_WORKSPACE").path_join("fixtures")
		if not direct_status:
			# Reusing the same binding exercises the manual history checkpoint.
			# It must return to the status gate without implicitly starting work.
			_reply(dock, "#42 guide-e2e-1")
			var rebound := false
			for attempt in range(400):
				await create_timer(0.05).timeout
				if dock.get_meta("gonggong_status", "") == "issue_guide" and dock.find_child("Send", true, false).text == "发送":
					rebound = true
					break
			if not rebound:
				return false
		var before_retry = JSON.parse_string(FileAccess.get_file_as_string(fixture.path_join("gh-state.json")))
		DirAccess.copy_absolute(fixture.path_join("gh-state.json"), fixture.path_join("before-retry.json"))
		_reply(dock, "已更新")
		var reread = false
		for attempt in range(400):
			await create_timer(0.05).timeout
			var state = JSON.parse_string(FileAccess.get_file_as_string(fixture.path_join("gh-state.json")))
			if state != null and state.calls.size() > before_retry.calls.size() and dock.get_meta("gonggong_status", "") == "issue_guide" and dock.find_child("Send", true, false).text == "发送":
				reread = true
				break
		if not reread:
			push_error("Retry did not re-read the same rejected Issue")
			return false
		DirAccess.copy_absolute(fixture.path_join("gh-state.json"), fixture.path_join("before-start.json"))
		if _shown(dock, "GONGGONG_FIXTURE_REPLY"):
			push_error("Rejected status reached the model before explicit Start")
			return false
		if direct_status:
			if mode == "issue_guide_status_direct_retry_failure":
				# Fault only this private editor's cache, before the intake child starts.
				var cache = EditorInterface.get_editor_paths().get_cache_dir()
				var private_root = OS.get_environment("GONGGONG_TEST_WORKSPACE").replace("\\", "/")
				if not cache.begins_with(private_root + "/"):
					return false
				var saved_cache = cache + ".status-recovery-test"
				if DirAccess.rename_absolute(cache, saved_cache) != OK:
					return false
				var blocked_cache = FileAccess.open(cache, FileAccess.WRITE)
				if blocked_cache == null:
					DirAccess.rename_absolute(saved_cache, cache)
					return false
				blocked_cache.store_string("isolated request-write failure")
				blocked_cache.close()
				_reply(dock, "重试")
				var failed_before_launch = await _wait_shown(dock, "无法保存 GongGong 校验请求")
				DirAccess.remove_absolute(cache)
				var restored = DirAccess.rename_absolute(saved_cache, cache)
				if not failed_before_launch or restored != OK:
					return false
			# Neither generic Start nor a new binding can replace the verified board confirmation.
			_reply(dock, "开始")
			_reply(dock, "#43 other-task")
			if _shown(dock, "确认开工：回复") or _shown(dock, "请重新核对当前账号、工单来源及状态"):
				return false
			var calls_before = JSON.parse_string(FileAccess.get_file_as_string(fixture.path_join("gh-state.json"))).calls.size()
			_reply(dock, "重试")
			var retry_complete = false
			for attempt in range(400):
				await create_timer(0.05).timeout
				var state = JSON.parse_string(FileAccess.get_file_as_string(fixture.path_join("gh-state.json")))
				if state.calls.size() > calls_before and dock.get_meta("gonggong_status", "") == "issue_guide" and dock.find_child("Send", true, false).text == "发送":
					retry_complete = true
					break
			if not retry_complete:
				return false
			_reply(dock, "取消")
			return _shown(dock, "已退出工单引导") and _shown(dock, "Isolated GongGong gate validation")
		_reply(dock, "开始")
		var guard_fault := OS.get_environment("GONGGONG_TEST_GUARD_FAULT")
		if not guard_fault.is_empty():
			var diagnostic := "stage=output_limit" if guard_fault == "output-limit" else ("stage=json_parse" if guard_fault == "invalid-json" else "nExitCode=7")
			if not await _wait_shown(dock, diagnostic, 40.0):
				return false
			if guard_fault == "nonzero" and not _shown(dock, "stderr=fixture-guard-stderr"):
				return false
			return not _shown(dock, "GONGGONG_FIXTURE_REPLY")
		if not await _wait_shown(dock, "GONGGONG_FIXTURE_REPLY", 40.0):
			return false
		for attempt in range(200):
			if dock.get_meta("gonggong_reporting", "") == "recorded_file":
				return true
			await create_timer(0.05).timeout
		return false
	# Unbound send must stay in the conversation, without any model request.
	if not await _wait_shown(dock, "绑定本仓库的真实工单"):
		return false
	if _shown(dock, "GongGong 阻止本次发送") or dock.get_meta("gonggong_status", "") != "issue_guide":
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
	steps.append(["开始", "GONGGONG_FIXTURE_REPLY"])
	for step in steps:
		if mode == "issue_guide_login" and step[1] == "Issue #42":
			if not _shown(dock, "尚未登录 github.com") or not _shown(dock, "auth login --hostname github.com"):
				push_error("Logged-out gh did not show login guidance")
				return false
			# Stands in for the user finishing `gh auth login` in a terminal.
			var flag = FileAccess.open(OS.get_environment("GONGGONG_TEST_WORKSPACE").path_join("fixtures/gh-logged-in"), FileAccess.WRITE)
			flag.store_string("fixture")
			flag.close()
		_reply(dock, step[0])
		if not await _wait_shown(dock, step[1], 40.0):
			return false
	var settings = EditorInterface.get_editor_settings()
	if str(settings.get_setting("gonggong/issue_number")) != "42" or settings.get_setting("gonggong/request_id") != "guide-e2e-1":
		push_error("Guide did not persist the Issue binding")
		return false
	for attempt in range(200):
		if dock.get_meta("gonggong_reporting", "") == "recorded_file":
			return true
		await create_timer(0.05).timeout
	push_error("Guided turn did not record its file receipt")
	return false

func _run():
	var dock = root.find_child("AI Chat", true, false)
	if dock == null or root.find_child("GongGongPage", true, false) == null:
		push_error("Missing native AI/GongGong dock")
		quit(1)
		return
	var settings = EditorInterface.get_editor_settings()
	settings.set_setting("gonggong/workspace", OS.get_environment("GONGGONG_TEST_WORKSPACE"))
	root.find_child("AI Chat", true, false).set_runtime_field("workflow_python", OS.get_environment("GONGGONG_PYTHON"))
	var backend = dock.find_child("AIBackend", true, false)
	backend.select(0)
	backend.item_selected.emit(0)
	dock.get_ai_settings_control().find_child("APIEndpoint", true, false).text = OS.get_environment("GONGGONG_TEST_ENDPOINT")
	dock.find_child("APIModel", true, false).text = "isolated-test"
	process_frame.connect(_measure_frame)
	var mode = OS.get_environment("GONGGONG_TEST_MODE")
	if not mode.begins_with("issue_guide"):
		settings.set_setting("gonggong/issue_number", "6")
		settings.set_setting("gonggong/request_id", "isolated-gate")
	if mode.begins_with("issue_guide_status"):
		dock.get_ai_settings_control().find_child("AllowTools", true, false).button_pressed = false
		# Private account fixture: exercise the real workbench-bound manual send.
		var workspace = OS.get_environment("GONGGONG_TEST_WORKSPACE")
		settings.set_project_metadata("daqian_access", workspace.sha256_text(), {"actor": {
			"repo_id": "fixture-repo", "user_id": "fixture-user", "repo": "test/repo"
		}})
		var request_id = "daqian-direct-0123456789abcdef0123" if mode.begins_with("issue_guide_status_direct") else "guide-e2e-1"
		var error = dock.open_daqian_chat("https://github.com/test/repo/issues/42", 42, request_id, "", false)
		if not error.is_empty():
			push_error(error)
			quit(1)
			return
	if not mode.begins_with("recovery"):
		dock.find_child("ChatInput", true, false).text = "Isolated GongGong gate validation"
		dock.find_child("Send", true, false).pressed.emit()
	if mode.begins_with("issue_guide"):
		var guided = await _run_issue_guide(dock, mode)
		print("GONGGONG_FRAME_GAP=", max_frame_gap if frame_count > 1 else -1.0)
		if guided:
			print("GONGGONG_CHAT_ISSUE_GUIDE_CANCEL_OK" if mode == "issue_guide_cancel" else "GONGGONG_CHAT_ISSUE_GUIDE_OK")
		quit(0 if guided else 1)
		return
	if mode == "recovery_cancel":
		dock.find_child("Stop", true, false).pressed.emit()
		await create_timer(4).timeout
		dock.find_child("ChatInput", true, false).text = "Isolated GongGong gate validation"
		dock.find_child("Send", true, false).pressed.emit()
		mode = "accepted"
	if mode == "cancel":
		dock.find_child("Stop", true, false).pressed.emit()
		await create_timer(4).timeout
		if dock.get_meta("gonggong_status", "") != "context_ready":
			print("GONGGONG_FRAME_GAP=", max_frame_gap if frame_count > 1 else -1.0)
			print("GONGGONG_CHAT_CANCEL_OK")
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
			if dock.get_meta("gonggong_status", "") == "context_ready" and dock.get_meta("gonggong_reporting", "") == "queued":
				dock.find_child("Stop", true, false).pressed.emit()
				await create_timer(4).timeout
				print("GONGGONG_FRAME_GAP=", max_frame_gap if frame_count > 1 else -1.0)
				print("GONGGONG_CHAT_RECEIPT_CANCEL_OK")
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
					print("GONGGONG_FRAME_GAP=", max_frame_gap if frame_count > 1 else -1.0)
					print("GONGGONG_CHAT_RECOVERY_RECEIPT_FAILURE_OK")
					quit(0)
					return
		if mode == "receipt_failure" and dock.get_meta("gonggong_reporting", "") == "pending_retry" and not dock.find_child("Send", true, false).disabled:
			print("GONGGONG_FRAME_GAP=", max_frame_gap if frame_count > 1 else -1.0)
			print("GONGGONG_CHAT_RECEIPT_FAILURE_OK")
			quit(0)
			return
		if mode == "recovery" and dock.get_meta("gonggong_reporting", "") == "recorded_file" and not FileAccess.file_exists("res://.godot/editor/ai_chat_resume.json"):
			print("GONGGONG_FRAME_GAP=", max_frame_gap if frame_count > 1 else -1.0)
			print("GONGGONG_CHAT_RECOVERY_OK")
			quit(0)
			return
		if mode in ["accepted", "tool"] and dock.get_meta("gonggong_reporting", "") == "recorded_file":
			for label in dock.find_children("*", "RichTextLabel", true, false):
				if "GONGGONG_FIXTURE_REPLY" in label.get_parsed_text():
					print("GONGGONG_FRAME_GAP=", max_frame_gap if frame_count > 1 else -1.0)
					print("GONGGONG_CHAT_FIXTURE_ACCEPTED_OK")
					quit(0)
					return
		if mode in ["rejected", "recovery_rejected"] and _shown(dock, "需求建单尚未完成"):
			print("GONGGONG_CHAT_FAIL_CLOSED_OK")
			quit(0)
			return
		if dock.get_meta("gonggong_status", "") == "blocked":
			print("GONGGONG_FRAME_GAP=", max_frame_gap if frame_count > 1 else -1.0)
			print("GONGGONG_CHAT_FAIL_CLOSED_OK")
			quit(0)
			return
	push_error("GongGong did not return a rejection")
	print("GATE_STATUS=", dock.get_meta("gonggong_status", "unset"))
	for label in dock.find_children("*", "RichTextLabel", true, false):
		print(label.get_parsed_text())
	quit(1)
