@tool
extends SceneTree

var failed := false

func _initialize() -> void:
	run.call_deferred()

func check(value: bool, message: String) -> void:
	if not value:
		push_error(message)
		failed = true

func check_replaced_button(panel, row: Dictionary, op: Dictionary) -> void:
	var details = panel.details_script.new()
	root.add_child(details)
	details.build()
	var confirmed := []
	details.confirmation_requested.connect(func(token): confirmed.append(token))
	var item := {"number":row.number}
	details.display(item, op, Callable())
	var old_button: Button = details.details_confirm
	var next := op.duplicate()
	next.token = "replacement"
	details.display(item, next, Callable())
	old_button.pressed.emit()
	details.details_confirm.pressed.emit()
	var closed_button: Button = details.details_confirm
	details.dismiss()
	closed_button.pressed.emit()
	check(confirmed == ["replacement"], "A replaced or closed detail button confirmed a different operation")
	details.queue_free()


func run() -> void:
	await create_timer(1).timeout
	var repo := OS.get_environment("DAQIAN_TEST_REPO")
	var settings := EditorInterface.get_editor_settings()
	settings.set_setting("gonggong/workspace", "")
	var dock = root.find_child("Daqian", true, false)
	var panel = dock.find_child("DaqianWorkspace", true, false)
	var chat = root.find_child("AI Chat", true, false)
	dock.get_parent().current_tab = dock.get_parent().get_tab_idx_from_control(dock)
	await panel.refresh()
	check(panel.connection_button.is_visible_in_tree(), "Workspace connection is unreachable before binding")
	panel.connection_button.pressed.emit()
	await process_frame
	var settings_page = root.find_child("UnifiedSettings", true, false)
	var categories = settings_page.find_child("UnifiedSettingsCategories", true, false)
	var environment = chat.get_environment_settings_control()
	check(settings_page.is_visible_in_tree() and categories.current_tab == 1 and environment.is_visible_in_tree(), "Workspace connection must navigate to the shared environment category")
	environment.find_child("GongGongWorkspace", true, false).text = repo
	environment.find_child("GongGongPython", true, false).text = OS.get_environment("DAQIAN_TEST_PYTHON")
	environment.find_child("SaveGongGongEnvironment", true, false).pressed.emit()
	await process_frame
	dock.get_parent().current_tab = dock.get_parent().get_tab_idx_from_control(dock)
	await panel.refresh()
	var row: Dictionary = panel.board.issues[0]
	await panel._open_issue(row)
	# Tianshu owns the task; model configuration uses the shared native settings page.
	var backend = chat.get_ai_settings_control().find_child("AIBackend", true, false)
	backend.select(0)
	backend.item_selected.emit(0)
	chat.get_ai_settings_control().find_child("APIModel", true, false).text = ""
	await panel._start_or_view_direct(row)
	if not panel.conversation.is_visible_in_tree() or not dock.is_visible_in_tree():
		push_error("Missing model did not open a configuration surface inside Tianshu: " + panel.notice.text)
		quit(1)
		return
	var view = panel.conversation
	var advanced = view.find_child("AdvancedToggle", true, false)
	advanced.pressed.emit()
	await process_frame
	var ai_settings = chat.get_ai_settings_control()
	var endpoint = ai_settings.find_child("APIEndpoint", true, false)
	check(settings_page.is_visible_in_tree() and categories.current_tab == 0 and endpoint.is_visible_in_tree() and chat.find_child("ChatSettingsDialog", true, false) == null and not view.is_ancestor_of(ai_settings), "Embedded conversation must navigate to the unique central AI form")
	endpoint.text = OS.get_environment("DAQIAN_TEST_ENDPOINT")
	ai_settings.find_child("AutoExecuteCommands", true, false).button_pressed = false
	ai_settings.find_child("AllowTools", true, false).button_pressed = true
	endpoint.text_changed.emit(endpoint.text)
	var picker = ai_settings.find_child("ModelPicker", true, false)
	var limit := Time.get_ticks_msec() + 10000
	while not chat.get_daqian_models().options.any(func(option): return option.id == "fixture") and Time.get_ticks_msec() < limit:
		await create_timer(0.05).timeout
	for i in picker.item_count:
		if picker.get_item_metadata(i) == "fixture":
			picker.select(i)
			picker.item_selected.emit(i)
	check(chat.get_daqian_models().current == "fixture", "Refreshed model missing")
	dock.get_parent().current_tab = dock.get_parent().get_tab_idx_from_control(dock)
	await process_frame
	check(panel.conversation.is_visible_in_tree() and dock.is_visible_in_tree() and settings_page.is_ancestor_of(ai_settings), "Returning from settings must retain the embedded conversation and central form ownership")
	await panel._apply_issue_model()
	check(panel.saved.get("execution_models", {}).get(row.url, {}).get("id") == "fixture", "Issue model was not saved")
	check(panel.publish_button.text == "开始推进", "Bound model was not used for the requirement decision")
	await panel._start_or_view_direct(panel._direct_binding())
	check(panel.conversation.is_visible_in_tree() and dock.is_visible_in_tree(), "Starting the issue left Tianshu")
	var deadline := Time.get_ticks_msec() + 20000
	while chat.get_daqian_approval().is_empty() and Time.get_ticks_msec() < deadline:
		await create_timer(0.05).timeout
	var op: Dictionary = chat.get_daqian_approval()
	if op.is_empty():
		for label in chat.find_children("*", "RichTextLabel", true, false):
			print(label.get_parsed_text().right(300))
		push_error("Bound tool never offered an inline approval")
		quit(1)
		return
	while not panel.editor.canvas.has_node("wf-operation") and Time.get_ticks_msec() < deadline:
		await create_timer(0.05).timeout
	if not panel.editor.canvas.has_node("wf-operation"):
		push_error("The pending tool was not projected after the issue-start receipt")
		quit(1)
		return
	var card = panel.editor.canvas.get_node("wf-operation")
	check(card.get_meta("flow_state") == "awaiting_approval", "Missing waiting state")
	check(not chat.find_child("AIFileApproval", true, false).visible, "Unexpected approval dialog")
	check(not card.get_node("ApprovalActions").visible, "Actions should expand on click")
	card.get_child(-1).pressed.emit()
	var actions = card.get_node("ApprovalActions")
	check(actions.visible, "Actions did not expand")
	actions.get_child(1).pressed.emit()
	await process_frame
	await process_frame
	check(panel.details_panel.is_visible_in_tree() and panel.editor.canvas.is_visible_in_tree(), "Graph and details must coexist")
	check(panel.details_panel.details_document.get_parsed_text().contains("Bound section") and panel.details_panel.details_document.get_v_scroll_bar().value > 0, "Document did not scroll to the bound section")
	check(panel.details_panel._document_anchor(PackedStringArray(["# Other"]), op) == -1, "Unbound prose should not be highlighted")
	check_replaced_button(panel, row, op)
	var marker := repo.path_join("executions")
	check(not FileAccess.file_exists(marker), "Reading details executed the tool")
	check(not chat.confirm_daqian_approval("obsolete-token"), "Wrong token was accepted")
	# The board source changes between opening the details and pressing Confirm.
	var changed := FileAccess.open(repo.path_join("changed"), FileAccess.WRITE)
	changed.close()
	await panel._confirm_operation(op.token)
	check(not FileAccess.file_exists(marker) and not chat.get_daqian_approval().is_empty(), "Stale source was approved")
	DirAccess.remove_absolute(repo.path_join("changed"))
	panel.details_panel.details_confirm.pressed.emit()
	panel.details_panel.details_confirm.pressed.emit()
	deadline = Time.get_ticks_msec() + 12000
	while panel.editor.workflow.get("operation", {}).get("state") != "completed" and Time.get_ticks_msec() < deadline:
		await create_timer(0.05).timeout
	check(FileAccess.get_file_as_string(marker).strip_edges() == "once", "Expected a single command execution")
	check(not chat.confirm_daqian_approval(op.token) and chat.get_daqian_approval().is_empty(), "Consumed token was reused")
	check(not panel.details_panel.visible and panel.editor.workflow.get("operation", {}).get("state") == "completed", "Missing terminal state")
	await panel._start_or_view_direct(panel._direct_binding())
	check(panel.conversation.is_visible_in_tree(), "Unable to revisit the active Issue")
	# A completed tool receipt precedes the assistant's final response.
	# Sending before the response would steer the running turn.
	deadline = Time.get_ticks_msec() + 12000
	var verified := false
	while not verified and Time.get_ticks_msec() < deadline:
		await create_timer(0.05).timeout
		for label in view.find_children("*", "RichTextLabel", true, false):
			if label.get_parsed_text().contains("Verified"):
				verified = true
	check(verified, "Tool continuation did not finish")
	var input = view.find_child("ChatInput", true, false)
	input.text = "Check the receipt again"
	view.find_child("Send", true, false).pressed.emit()
	deadline = Time.get_ticks_msec() + 12000
	var replied := false
	while not replied and Time.get_ticks_msec() < deadline:
		await create_timer(0.05).timeout
		for label in view.find_children("*", "RichTextLabel", true, false):
			if label.get_parsed_text().contains("Receipt rechecked"):
				replied = true
	if not replied:
		for label in view.find_children("*", "RichTextLabel", true, false):
			print(label.get_parsed_text().right(350))
	check(replied and dock.is_visible_in_tree(), "Follow-up did not return in the bound Tianshu conversation")
	panel._leave_conversation()
	check(panel.flow_split.is_visible_in_tree() and chat.find_child("AIWorkspacePages", true, false) != null, "Normal editor views were not restored")
	await check_native_canvas(panel, row)
	if not failed:
		print("DAQIAN_INLINE_APPROVAL_OK")
	await create_timer(0.8).timeout
	quit(1 if failed else 0)

func check_native_canvas(panel, row: Dictionary) -> void:
	var canvas = panel.canvas_panel
	var issue: String = panel.current
	canvas.canvas_message.text = "canvas fixture question"
	canvas.canvas_message.text_submitted.emit(canvas.canvas_message.text)
	var deadline := Time.get_ticks_msec() + 10000
	while canvas.pending_turns.is_empty() and Time.get_ticks_msec() < deadline:
		await create_timer(0.02).timeout
	check(not canvas.pending_turns.is_empty(), "The native canvas did not start its scoped preview: " + panel.notice.text)
	panel._show_board()
	while not canvas.pending_turns.is_empty() and Time.get_ticks_msec() < deadline:
		await create_timer(0.02).timeout
	await process_frame
	check("Canvas fixture answer" not in canvas.canvas_log.text, "The Issue answer appeared on the board")
	await panel._open_issue(row)
	check(canvas.canvas_location == issue and "Canvas fixture answer" in canvas.canvas_log.text, "Returning to the Issue lost its native preview receipt")
	canvas.canvas_message.text = "canvas fixture rejected"
	canvas.canvas_message.text_submitted.emit(canvas.canvas_message.text)
	deadline = Time.get_ticks_msec() + 10000
	while canvas.pending_turns.is_empty() and Time.get_ticks_msec() < deadline:
		await create_timer(0.02).timeout
	panel._draw_board()
	check(canvas.waiting.visible, "Board refresh hid the pending model request")
	while not canvas.pending_turns.is_empty() and Time.get_ticks_msec() < deadline:
		await create_timer(0.02).timeout
	check(canvas.pending_turns.is_empty() and not canvas.waiting.visible and "401" in canvas.canvas_log.text, "Native HTTP failure did not reach the canvas")
	canvas.canvas_message.text = "canvas fixture filtered"
	canvas.canvas_message.text_submitted.emit(canvas.canvas_message.text)
	deadline = Time.get_ticks_msec() + 10000
	while canvas.pending_turns.is_empty() and Time.get_ticks_msec() < deadline:
		await create_timer(0.02).timeout
	while not canvas.pending_turns.is_empty() and Time.get_ticks_msec() < deadline:
		await create_timer(0.02).timeout
	check(not canvas.waiting.visible and "未收到完整答复" in canvas.canvas_log.text and "Unexpected filtered answer" not in canvas.canvas_log.text, "Filtered completion reached canvas routing")
