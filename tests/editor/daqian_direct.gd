@tool
extends SceneTree

var errors := []

func _initialize() -> void:
	run.call_deferred()

func check(value: bool, reason: String) -> void:
	if not value:
		errors.append(reason)
		push_error(reason)

func run() -> void:
	await create_timer(1.0).timeout
	var repo := OS.get_environment("DAQIAN_TEST_REPO")
	var settings := EditorInterface.get_editor_settings()
	settings.set_setting("gonggong/workspace", repo)
	settings.set_setting("gonggong/python", OS.get_environment("DAQIAN_TEST_PYTHON"))
	var dock = root.find_child("Daqian", true, false)
	var panel = dock.find_child("DaqianWorkspace", true, false)
	var chat = root.find_child("AI Chat", true, false)
	dock.get_parent().current_tab = dock.get_parent().get_tab_idx_from_control(dock)
	await panel.refresh()
	if OS.get_environment("DAQIAN_TEST_RESTART") == "1":
		await resume_after_restart(panel, chat, dock, repo)
		return
	panel.chat = null
	panel._compose_requirement()
	var source = panel.current
	check(panel.publish_button.text == "发布需求…", "Fresh draft lacks publish action")
	check(not panel.model_options.visible and panel.publish_dialog.get_ok_button().text == "确认需求并建单", "Direct task requires a model")
	check(panel.editor.canvas.has_node("wf-workorder") and not panel.editor.canvas.has_node("wf-analysis"), "Direct draft incorrectly attributed to Yanshi")
	panel.publish_dialog.hide()
	panel.chat = chat
	var backend = chat.get_ai_settings_control().find_child("AIBackend", true, false)
	backend.select(0)
	backend.item_selected.emit(0)
	chat.get_ai_settings_control().find_child("APIEndpoint", true, false).text = "http://127.0.0.1:1/v1/chat/completions"
	panel.publish_button.pressed.emit()
	check(panel.model_options.visible, "Configured backend must expose its model picker in Tianshu")
	panel.model_options.select(panel.model_options.item_count - 1)
	panel.model_options.item_selected.emit(panel.model_options.selected)
	panel.manual_model.text = "chosen-execution-model"
	panel.manual_model.text_changed.emit(panel.manual_model.text)
	panel.requirement_input.text = "Fixture direct task\nKeep the original body."
	panel.requirement_input.text_changed.emit()
	var calls := repo.path_join("tools/calls")
	check(not panel.publish_dialog.get_ok_button().disabled and not FileAccess.file_exists(calls), "Direct creation preconditions")
	panel.publish_dialog.get_ok_button().pressed.emit()
	panel.publish_dialog.get_ok_button().pressed.emit()
	var deadline := Time.get_ticks_msec() + 10000
	while panel.publish_status.text != "先核对发布结果" and Time.get_ticks_msec() < deadline:
		await create_timer(0.05).timeout
	check(panel.category.disabled and not panel.requirement_input.editable, "Unknown publication allows a competing route")
	panel.publish_dialog.hide()
	check(panel.publish_button.text == "核对建单回执", "Draft lost pending request action")
	panel.publish_button.pressed.emit()
	check(panel.publish_dialog.get_ok_button().text == "核对建单回执", "Lost stable reconciliation entry")
	await panel._confirm_publish()
	var binding: Dictionary = panel.saved.get("linked", {}).get(source, {})
	if binding.get("number") != 124:
		push_error("Missing direct Issue receipt: " + panel.publish_status.text)
		quit(1)
		return
	await panel.refresh()
	check(panel.editor.canvas.has_node("wf-prepare") and not panel.editor.canvas.has_node("wf-analysis"), "Bound direct task missing preparation")
	var records := FileAccess.get_file_as_string(calls).strip_edges().split("\n")
	check(records.size() == 3 and JSON.parse_string(records[2])[0] == "issue-route" and JSON.parse_string(records[2])[1].model == "chosen-execution-model" and records[0] == records[1], "Reconciliation changed request, duplicated a click or launched work")
	var first: Array = JSON.parse_string(records[0])
	check(first[0] == "issue-direct" and first[1].get("expected_user") == "42" and first[1].get("draft_id") == source and first[1].get("title") == "Fixture direct task" and first[1].get("category") == "development" and not first[1].has("model"), "Wrong direct host fields")
	var ready_receipt: Dictionary = panel.saved.routing[binding.url]
	panel.saved.routing.erase(binding.url)
	panel._update_direct_action()
	check(panel.publish_button.text == "判断需求" and not panel.publish_button.disabled, "Unjudged issue lacks initial judgment action")
	panel.saved.routing[binding.url] = ready_receipt
	var previous = panel.board.get("issues", []).duplicate(true)
	var altered = {"url":binding.url, "number":binding.number, "request":"different", "status":"in-progress"}
	panel.board.issues = [altered]
	panel._update_direct_action()
	check(panel.publish_button.disabled, "A changed request ID can still start")
	altered.request = binding.request
	altered.closed = true
	panel._update_direct_action()
	check(panel.publish_button.disabled and panel.publish_button.text == "工单已关闭", "Closed task can still start")
	altered.closed = false
	altered.request = "daqian-direct-unrelated"
	panel.current = binding.url
	panel.saved.direct_started = {binding.url:true}
	panel._update_direct_action()
	check(panel.publish_button.text == "开始推进", "URL-only legacy receipt leaked into another request")
	altered.request = binding.request
	panel._update_direct_action()
	check(panel.publish_button.text == "查看推进对话", "Verified legacy binding did not recover")
	panel.saved.direct_started.clear()
	panel.current = source
	panel.board.issues = previous
	panel._update_direct_action()
	chat.get_ai_settings_control().find_child("APIModel", true, false).text = "different-current-model"
	await panel._start_or_view_direct(binding)
	check(panel.publish_button.text == "重试开工" and panel.work_status.text.contains("fixture start unavailable"), "Lost distinct start retry")
	check(panel._routing_receipt(binding).get("ready", false), "Failed start erased ready decision")
	panel.publish_button.pressed.emit()
	panel.publish_button.pressed.emit()
	deadline = Time.get_ticks_msec() + 10000
	while records.size() < 5 and Time.get_ticks_msec() < deadline:
		await create_timer(0.05).timeout
		records = FileAccess.get_file_as_string(calls).strip_edges().split("\n")
	check(panel.publish_button.disabled, "Start in flight allows a second start")
	panel._new_requirement()
	var other: String = panel.current
	FileAccess.open(repo.path_join("tools/release-start"), FileAccess.WRITE).close()
	deadline = Time.get_ticks_msec() + 10000
	while not panel.starting_direct.is_empty() and Time.get_ticks_msec() < deadline:
		await create_timer(0.05).timeout
	check(panel.current == other and not panel.conversation.visible, "Late start mounted another issue's chat")
	check(panel.saved.get("direct_start_receipts", {}).get(binding.url) == binding.request, "Late receipt was lost")
	check(FileAccess.get_file_as_string(calls).strip_edges().split("\n").size() == 5, "Switch or double click dispatched extra work")
	panel._save()
	if errors.is_empty():
		print("DAQIAN_DIRECT_RESTART_READY")
	quit(0 if errors.is_empty() else 1)


func resume_after_restart(panel, chat, dock, repo: String) -> void:
	var calls := repo.path_join("tools/calls")
	var records := FileAccess.get_file_as_string(calls).strip_edges().split("\n")
	var source: String = JSON.parse_string(records[0])[1].draft_id
	var binding: Dictionary = panel.saved.get("linked", {}).get(source, {})
	check(panel.current != source and panel.publish_button.text == "发布需求…", "Restart applied receipt to wrong draft")
	panel._show_issue(source, {"revision":"", "plan":panel.rules.new_plan(), "context":{}})
	check(panel.publish_button.text == "继续推进对话", "Restart lost confirmed start")
	panel.publish_button.pressed.emit()
	var deadline := Time.get_ticks_msec() + 10000
	while records.size() < 6 and Time.get_ticks_msec() < deadline:
		await create_timer(0.05).timeout
		records = FileAccess.get_file_as_string(calls).strip_edges().split("\n")
	var started: Array = JSON.parse_string(records[-1])
	var decision: Array = JSON.parse_string(records[-2])
	check(decision[0] == "issue-start" and decision[1].expected_revision == "fixture-revision" and decision[1].expected_user == "42", "Missing explicit start transition")
	check(records.size() == 6 and started[0] == "chat" and started[1].get("agent_id") == "sinan" and started[1].get("issue_number") == 124 and started[1].get("request_id") == binding.request, "Start did not use exact bound Issue with Sinan")
	check(panel.conversation.is_visible_in_tree() and dock.is_visible_in_tree(), "Start left Tianshu")
	check(chat.get_daqian_models().current == "chosen-execution-model", "Start ignored model chosen at creation")
	panel._leave_conversation()
	panel._update_direct_action()
	check(panel.publish_button.text == "查看推进对话", "Existing chat cannot be reopened")
	var closed := binding.duplicate()
	closed.closed = true
	panel.board.issues = [closed]
	panel._update_direct_action()
	panel.publish_button.pressed.emit()
	check(panel.publish_button.disabled and not panel.conversation.visible, "Closed issue with start receipt can dispatch")
	# Replay an unstarted external route into the same linked draft.
	panel.saved.direct_started.clear()
	panel.saved.direct_start_receipts.clear()
	var row: Dictionary = binding.duplicate()
	row.updated = binding.get("revision", "fixture-revision")
	row.source_sha256 = "verified-source"
	var judged: Dictionary = panel.saved.routing[binding.url].duplicate(true)
	row.routing_receipt = judged
	panel.saved.routing.clear()
	panel.board.issues = [row]
	panel.current = source
	panel.fresh_progress = true
	panel._sync_workflow()
	check(panel.editor.canvas.has_node("wf-prepare") and panel.editor.canvas.has_node("wf-worker"), "Receipt projection missing from linked draft")
	check(panel.work_status.text.contains("等待开始推进"), "Readiness incorrectly implied execution")
	var provenance := {"actor":panel.actor.user_id, "request_ref":row.request, "source_ref":row.url, "source_sha256":row.source_sha256}
	panel._chat_work_event(repo, provenance, "sinan · AI Chat #1", "request", "chat", "running")
	check(panel.work_status.text.contains("司南 · AI Chat #1"), "Running worker missing")
	panel._chat_work_event(repo, provenance, "sinan · AI Chat #1", "step", "confirmation", "waiting")
	check(panel.work_status.text.contains("等待操作确认"), "Human approval shown as running")
	row.source_sha256 = "edited-source"
	panel._sync_workflow()
	check(not panel.work_status.text.contains("AI Chat #1"), "Old worker leaked across source revisions")
	panel._chat_work_event(repo, provenance, "sinan · AI Chat #1", "request_end", "chat", "completed")
	check(panel.chat_work[row.url].is_empty(), "Old terminal did not clear original work")
	row.routing_receipt = {}
	panel.saved.routing[row.url] = judged
	check(panel._routing_receipt(row).is_empty(), "Revoked receipt revived by private cache")
	if errors.is_empty():
		print("DAQIAN_DIRECT_OK")
	quit(0 if errors.is_empty() else 1)
