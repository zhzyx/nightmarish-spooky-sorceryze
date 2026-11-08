@tool
extends SceneTree

# All actions enter through the same native controls as the editor user. The
# runner owns a private editor copy, project, Git repository and HTTP service.
var dock: Node
var failure := ""
var stages: Array[String] = []
var selected_after_boundary := -1
var boundary_scheduled := false
var approval_seen := false
var retry_refused_while_receipt_pending := false
var model_source_changed_idle := false
var models_loading_observed := false
var terminal_receipt_recorded_during_models := false
var models_stall_observed := false
var models_stop_applied := false

func _work_event(_workspace: String, _binding: Dictionary, _worker: String, kind: String, _phase: String, status: String):
	# This public lifecycle signal precedes the host's deferred completion
	# callback. Schedule a normal control action first, then let completion run.
	if not boundary_scheduled and kind == "request_end" and status == "completed" and FileAccess.file_exists("res://child-final-about-to-return"):
		var mode := OS.get_environment("DESIGN_BATCH_CASE")
		if mode in ["unrelated", "late-stop", "binding-drift", "stale-retry", "stale-retry-terminal-failure", "close-child", "close-parent"] or mode.begins_with("models-return-"):
			boundary_scheduled = true
			_completion_boundary.call_deferred()

func _completion_boundary():
	var mode := OS.get_environment("DESIGN_BATCH_CASE")
	var tabs = dock.find_child("AgentTabs", true, false)
	if mode == "unrelated":
		dock.find_child("AddAgent", true, false).pressed.emit()
		selected_after_boundary = int(tabs.get_tab_metadata(tabs.current_tab))
		_check(not tabs.is_tab_hidden(tabs.current_tab) and tabs.current_tab != 0, "Unrelated parent was not selected")
	elif mode.begins_with("models-return-"):
		_change_model_source()
	elif mode == "binding-drift":
		var settings = EditorInterface.get_editor_settings()
		var bindings: Dictionary = settings.get_project_metadata("daqian", "bindings", {})
		var changed := false
		for owner in bindings:
			if bindings[owner].get("request_id", "") == "design-batch-fixture":
				bindings[owner]["request_id"] = "design-batch-drift"
				changed = true
		settings.set_project_metadata("daqian", "bindings", bindings)
		_check(changed, "Fixture parent binding was unavailable for drift")
	elif mode in ["stale-retry", "stale-retry-terminal-failure"]:
		dock.find_child("SpawnWorkOrderAgents", true, false).pressed.emit()
		retry_refused_while_receipt_pending = "结束回执仍在处理" in _text()
		_check(retry_refused_while_receipt_pending, "Explicit retry replaced the source while its terminal receipt was pending")
	elif mode in ["close-child", "close-parent"]:
		var closing_index: int = tabs.current_tab if mode == "close-child" else 0
		tabs.tab_close_pressed.emit(closing_index)
		var confirmation = dock.find_child("AgentCloseConfirmation", true, false)
		if _check(confirmation.visible, "Native close confirmation did not appear"):
			confirmation.get_ok_button().pressed.emit()
	else:
		dock.find_child("Stop", true, false).pressed.emit()
	_file("completion-boundary-applied")

func _initialize():
	_run.call_deferred()

func _check(ok: bool, detail: String) -> bool:
	if not ok:
		failure = detail if failure.is_empty() else failure + "; " + detail
		push_error(detail)
	return ok

func _text() -> String:
	var result := ""
	for label in dock.find_children("*", "RichTextLabel", true, false):
		result += label.get_parsed_text() + "\n"
	return result

func _send(text: String):
	dock.find_child("ChatInput", true, false).text = text
	dock.find_child("Send", true, false).pressed.emit()

func _file(name: String, content := "ready"):
	FileAccess.open("res://" + name, FileAccess.WRITE).store_string(content)

func _change_model_source():
	var field = dock.get_ai_settings_control().find_child("APIEndpoint", true, false)
	model_source_changed_idle = field.editable and dock.find_child("Stop", true, false).disabled and not dock.find_child("Send", true, false).disabled
	if not _check(model_source_changed_idle, "Model source change did not occur at a legal idle control boundary"):
		return
	field.text = field.text.replace("/v1/", "/v2/")
	field.text_changed.emit(field.text)
	_file("model-source-changed")

func _observe_models(mode: String):
	if not await _wait_file("models-v2-started"):
		return
	models_loading_observed = dock.find_child("Send", true, false).disabled and not dock.find_child("Stop", true, false).disabled
	_check(models_loading_observed, "Slow model-list request did not hold the native loading controls")
	var deadline := Time.get_ticks_msec() + 1500
	while Time.get_ticks_msec() < deadline and dock.get_meta("gonggong_reporting", "") != "recorded_file":
		await create_timer(0.02).timeout
	terminal_receipt_recorded_during_models = dock.get_meta("gonggong_reporting", "") == "recorded_file" and dock.find_child("Send", true, false).disabled
	_check(terminal_receipt_recorded_during_models, "Terminal source receipt did not settle while model loading blocked dispatch")
	if mode == "models-initial-stop":
		dock.find_child("Stop", true, false).pressed.emit()
		models_stop_applied = true
	if not await _wait_file("models-v2-finished"):
		return
	if OS.get_environment("DESIGN_BATCH_EXPECT_STALLED") == "1":
		await create_timer(1.0).timeout
		models_stall_observed = dock.find_child("Stop", true, false).disabled and not dock.find_child("Send", true, false).disabled and not "DESIGN_BATCH_PARENT_VERIFIED_OK" in _text()
		_check(models_stall_observed, "Expected-stall observation was not idle after the model response")
	elif mode in ["models-initial-stop", "models-no-live"]:
		await create_timer(1.0).timeout
		_check(dock.find_child("Stop", true, false).disabled, "Model-list completion started work beyond the live authorization")
		if mode == "models-no-live":
			var tabs = dock.find_child("AgentTabs", true, false)
			_check(tabs.tab_count == 1 and dock.get_meta("queued_message_count", -1) == 0, "Model-list completion manufactured work without a live batch")
	else:
		await _wait_marker("DESIGN_BATCH_PARENT_VERIFIED_OK")
	var status: String = dock.get_ai_settings_control().find_child("ModelStatus", true, false).text
	if mode.ends_with("-fail"):
		_check("获取失败" in status, "Model-list failure was not retained in native status")
	elif mode != "models-initial-stop":
		_check("已获取" in status, "Successful model-list completion was not retained in native status")

func _wait_file(name: String, seconds := 60.0) -> bool:
	var deadline := Time.get_ticks_msec() + int(seconds * 1000)
	while Time.get_ticks_msec() < deadline:
		if FileAccess.file_exists("res://" + name):
			return true
		await create_timer(0.05).timeout
	return _check(false, "Missing fixture coordination file: " + name)

func _wait_marker(marker: String, seconds := 90.0) -> bool:
	var deadline := Time.get_ticks_msec() + int(seconds * 1000)
	while Time.get_ticks_msec() < deadline:
		if marker in _text() and dock.find_child("Stop", true, false).disabled:
			# Completion callbacks and the asynchronous evidence writer get an idle
			# boundary before the next user action changes conversations.
			await create_timer(0.3).timeout
			stages.append(marker)
			return true
		await create_timer(0.05).timeout
	return _check(false, "Missing native reply: " + marker)

func _finish():
	var tabs = dock.find_child("AgentTabs", true, false)
	var children: Array = []
	for index in range(tabs.tab_count):
		children.append({"id": tabs.get_tab_metadata(index), "title": tabs.get_tab_title(index), "hidden": tabs.is_tab_hidden(index)})
	var report := {
		"ok": failure.is_empty(), "failure": failure, "stages": stages,
		"case": OS.get_environment("DESIGN_BATCH_CASE"), "phase": OS.get_environment("DESIGN_BATCH_PHASE"),
		"selected_agent": tabs.get_tab_metadata(tabs.current_tab), "selected_after_boundary": selected_after_boundary,
		"completion_boundary_scheduled": boundary_scheduled,
		"approval_seen": approval_seen,
		"retry_refused_while_receipt_pending": retry_refused_while_receipt_pending,
		"model_source_changed_idle": model_source_changed_idle,
		"models_loading_observed": models_loading_observed,
		"terminal_receipt_recorded_during_models": terminal_receipt_recorded_during_models,
		"models_stall_observed": models_stall_observed,
		"models_stop_applied": models_stop_applied,
		"model_status": dock.get_ai_settings_control().find_child("ModelStatus", true, false).text,
		"queue_paused": dock.get_meta("queue_paused", false), "queued_count": dock.get_meta("queued_message_count", -1),
		"tabs": children, "text": _text(), "reporting": dock.get_meta("gonggong_reporting", ""),
	}
	_file("design-batch-report.json", JSON.stringify(report))
	quit(0 if failure.is_empty() else 1)

func _run():
	dock = root.find_child("AI Chat", true, false)
	if dock == null:
		push_error("AI Chat dock not found")
		quit(1)
		return
	var settings = EditorInterface.get_editor_settings()
	var mode := OS.get_environment("DESIGN_BATCH_CASE")
	if OS.get_environment("DESIGN_BATCH_PHASE") == "review-restore":
		await create_timer(0.5).timeout
		_check(dock.find_child("Stop", true, false).disabled, "Cold review replayed without user resume")
		dock.get_ai_settings_control().find_child("APIKey", true, false).text = "design-batch-isolated-secret"
		dock.find_child("ConsultationOnly", true, false).button_pressed = false
		dock.find_child("ResumeMessageQueue", true, false).pressed.emit()
		await _wait_marker("REVIEW_TAMPER_ACTUAL_READ_OK")
		_finish()
		return
	if OS.get_environment("DESIGN_BATCH_PHASE") == "restore":
		await create_timer(2.0).timeout
		_check(dock.find_child("Stop", true, false).disabled, "Cold history started a request")
		_check(dock.get_meta("queue_paused", false), "Cold history did not preserve the paused queue")
		_check(dock.get_meta("queued_message_count", 0) > 0, "Cold history lost the pending message")
		var history = JSON.parse_string(FileAccess.get_file_as_string("res://.godot/editor/ai_chat_history.json"))
		var internal_markers := 0
		if history is Dictionary:
			for agent in history.get("agents", []):
				for message in agent.get("queued_messages", []):
					if message.has("design_batch_return"):
						internal_markers += 1
		_check(internal_markers == 0, "Cold history retained an internal parent-return token")
		_finish()
		return
	settings.set_setting("gonggong/workspace", OS.get_environment("DESIGN_BATCH_ROOT"))
	settings.set_setting("gonggong/python", OS.get_environment("DESIGN_BATCH_PYTHON"))
	_check(dock.set_runtime_field("node", OS.get_environment("DESIGN_BATCH_NODE")).is_empty(), "Cannot seed private Node configuration")
	_check(dock.set_runtime_field("workflow_python", OS.get_environment("DESIGN_BATCH_PYTHON")).is_empty(), "Cannot seed private workflow Python")
	_check(dock.set_runtime_field("build_python", OS.get_environment("DESIGN_BATCH_PYTHON")).is_empty(), "Cannot seed private build Python")
	_check(dock.set_runtime_field("codex", OS.get_environment("DESIGN_BATCH_NODE")).is_empty(), "Cannot seed private Codex entry")
	settings.set_setting("gonggong/issue_number", "999")
	settings.set_setting("gonggong/request_id", "design-batch-global-sentinel")
	settings.set_setting("ai_chat/parallel_work_orders_config", "")
	dock.connect("daqian_work_event", _work_event)
	var setup = dock.find_child("GongGongRuntimeSetup", true, false)
	if setup != null:
		setup.hide()
	var backend = dock.get_ai_settings_control().find_child("AIBackend", true, false)
	if backend.selected != 0:
		backend.select(0)
		backend.item_selected.emit(0)
	dock.get_ai_settings_control().find_child("APIEndpoint", true, false).text = OS.get_environment("DESIGN_BATCH_ENDPOINT")
	dock.get_ai_settings_control().find_child("APIModel", true, false).text = "design-batch-fixture"
	dock.get_ai_settings_control().find_child("APIKey", true, false).text = "design-batch-isolated-secret"
	dock.get_environment_settings_control().find_child("CLINode", true, false).text = OS.get_environment("DESIGN_BATCH_NODE")
	dock.get_environment_settings_control().find_child("CLIBridge", true, false).text = OS.get_environment("DESIGN_BATCH_SOURCE").path_join("tools/codebuddy_cli/godot_bridge.js")
	dock.get_environment_settings_control().find_child("CodexEntry", true, false).text = OS.get_environment("DESIGN_BATCH_NODE")
	dock.get_environment_settings_control().find_child("EngineBuildPython", true, false).text = OS.get_environment("DESIGN_BATCH_PYTHON")
	dock.get_ai_settings_control().find_child("AllowTools", true, false).button_pressed = true
	dock.get_ai_settings_control().find_child("AutoApplyFileChanges", true, false).button_pressed = true
	dock.get_ai_settings_control().find_child("AutoExecuteCommands", true, false).button_pressed = true
	dock.find_child("ConsultationOnly", true, false).button_pressed = false
	if dock.get_ai_settings_control().find_child("RefreshModels", true, false) == null:
		# The private settings file already binds READY to the loopback server.
		# Wait for that startup query instead of losing the warmup queue behind it.
		if not await _wait_file("models-v1-finished"):
			_finish()
			return
		for attempt in range(200):
			if dock.find_child("Stop", true, false).disabled and not dock.find_child("Send", true, false).disabled:
				break
			await create_timer(0.02).timeout
	_send("DESIGN_BATCH_WARMUP")
	if not await _wait_marker("DESIGN_BATCH_WARMUP_OK"):
		_finish()
		return
	if mode == "models-no-live":
		_change_model_source()
		await _observe_models(mode)
		_finish()
		return
	if mode.begins_with("models-initial-"):
		_change_model_source()
	if mode == "no-tools":
		dock.get_ai_settings_control().find_child("AllowTools", true, false).button_pressed = false
	if mode == "approval-stop":
		dock.get_ai_settings_control().find_child("AutoExecuteCommands", true, false).button_pressed = false
	if mode == "consultation":
		dock.find_child("ConsultationOnly", true, false).button_pressed = true
	if mode == "unknown-runtime":
		dock.find_child("ConsultationOnly", true, false).button_pressed = true
		settings.set_setting("gonggong/python", "")
		for name in ["node", "workflow_python", "build_python", "codex"]:
			_check(dock.set_runtime_field(name, "").is_empty(), "Cannot clear private runtime field")
		dock.get_environment_settings_control().find_child("CLINode", true, false).text = ""
		dock.get_environment_settings_control().find_child("CodexEntry", true, false).text = ""
		dock.get_environment_settings_control().find_child("EngineBuildPython", true, false).text = ""
	if mode == "runtime-invalid":
		dock.find_child("ConsultationOnly", true, false).button_pressed = true
		settings.set_setting("gonggong/python", "res://fake")
		_check(dock.set_runtime_field("node", "relative-node").is_empty(), "Cannot seed invalid Node draft")
		_check(dock.set_runtime_field("workflow_python", "res://fake").is_empty(), "Cannot seed invalid Python draft")
		_check(dock.set_runtime_field("codex", OS.get_environment("DESIGN_BATCH_ROOT")).is_empty(), "Cannot seed non-file Codex draft")
		_check(dock.set_runtime_field("build_python", OS.get_environment("DESIGN_BATCH_ROOT").path_join("missing-python")).is_empty(), "Cannot seed missing Python draft")
		dock.get_environment_settings_control().find_child("CLINode", true, false).text = "relative-node"
		dock.get_environment_settings_control().find_child("CodexEntry", true, false).text = OS.get_environment("DESIGN_BATCH_ROOT")
		dock.get_environment_settings_control().find_child("EngineBuildPython", true, false).text = OS.get_environment("DESIGN_BATCH_ROOT").path_join("missing-python")
	if mode.begins_with("review"):
		settings.set_setting("ai_chat/parallel_work_orders_config", "res://must-not-dispatch-production.json")
	_send("DESIGN_BATCH_START")
	if mode in ["review-stop", "review-parent-stop"]:
		if not await _wait_file("review-running" if mode == "review-stop" else "review-parent-waiting"):
			_finish()
			return
		dock.find_child("Stop", true, false).pressed.emit()
		await create_timer(2.5).timeout
		_check(dock.find_child("Stop", true, false).disabled, "Stopped review started another request")
		_check(not "DESIGN_BATCH_PARENT_VERIFIED_OK" in _text(), "Stopped review returned as accepted")
		_finish()
		return
	if mode.begins_with("models-"):
		await _observe_models(mode)
		_finish()
		return
	if mode == "approval-stop":
		var confirmation = dock.find_child("AIFileApproval", true, false)
		var deadline := Time.get_ticks_msec() + 60000
		while Time.get_ticks_msec() < deadline and not confirmation.visible:
			await create_timer(0.05).timeout
		approval_seen = confirmation.visible
		if _check(approval_seen, "Child command did not reach native approval"):
			_send("停止")
			await _wait_marker("DESIGN_BATCH_APPROVAL_REJECTED_OK")
			await create_timer(1.0).timeout
			_check(not confirmation.visible, "Recognized cancellation left approval visible")
		_finish()
		return
	if mode in ["receipt-failure", "terminal-failure", "parent-terminal-failure", "stale-retry-terminal-failure"]:
		var coordination := "child-result-produced" if mode == "receipt-failure" else "terminal-result-produced"
		if not await _wait_file(coordination):
			_finish()
			return
		var deadline := Time.get_ticks_msec() + 30000
		while Time.get_ticks_msec() < deadline:
			if dock.find_child("Stop", true, false).disabled and dock.get_meta("gonggong_reporting", "") == "pending_retry":
				break
			await create_timer(0.05).timeout
		_check(dock.find_child("Stop", true, false).disabled, "Failed evidence gate left model execution running")
		_check(dock.get_meta("gonggong_reporting", "") == "pending_retry", "Forced evidence failure was not retained")
		await create_timer(1.0).timeout
		_finish()
		return
	if mode in ["no-tools", "consultation", "unknown-runtime", "runtime-invalid"]:
		await _wait_marker("DESIGN_BATCH_PARENT_DESIGN_OK")
		await create_timer(1.0).timeout
		var tabs = dock.find_child("AgentTabs", true, false)
		_check(tabs.current_tab == 0, "Permission boundary switched to a child")
		_check(tabs.tab_count == 1, "Permission boundary created a child conversation")
		_check(dock.get_meta("queued_message_count", -1) == 0, "Permission boundary created pending work")
		_finish()
		return
	if mode in ["unrelated", "late-stop", "binding-drift", "close-child", "close-parent"]:
		if not await _wait_file("completion-boundary-applied"):
			_finish()
			return
		await create_timer(2.0).timeout
		_check(dock.find_child("Stop", true, false).disabled, "Deferred completion started another request after the boundary")
		var tabs = dock.find_child("AgentTabs", true, false)
		if mode == "unrelated":
			_check(int(tabs.get_tab_metadata(tabs.current_tab)) == selected_after_boundary, "Child completion stole the unrelated conversation")
		_finish()
		return
	if mode in ["stop", "paused", "cold"]:
		if not await _wait_file("child-command-running"):
			_finish()
			return
		var tabs = dock.find_child("AgentTabs", true, false)
		if mode in ["paused", "cold"]:
			# A differently scoped message stays queued instead of steering the
			# running child; Stop must preserve its pause across deferred events.
			dock.find_child("ConsultationOnly", true, false).button_pressed = true
			_send("DESIGN_BATCH_PENDING_MUST_NOT_RUN")
		dock.find_child("Stop", true, false).pressed.emit()
		_file("release-child-command")
		await create_timer(2.0).timeout
		_check(dock.find_child("Stop", true, false).disabled, "Cancellation started another request")
		if mode in ["paused", "cold"]:
			_check(dock.get_meta("queue_paused", false), "Stop failed to keep the pending queue paused")
			_check(dock.get_meta("queued_message_count", 0) == 1, "Stop lost or executed the pending message")
		_finish()
		return
	if await _wait_marker("DESIGN_BATCH_PARENT_VERIFIED_OK"):
		await create_timer(1.0).timeout
		var tabs = dock.find_child("AgentTabs", true, false)
		_check(tabs.current_tab == 0, "Batch did not return to its original parent")
	_finish()
