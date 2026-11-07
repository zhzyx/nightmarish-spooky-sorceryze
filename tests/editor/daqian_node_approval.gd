@tool
extends SceneTree

var failed := false

func _initialize() -> void:
	run.call_deferred()

func check(value: bool, message: String) -> void:
	if not value:
		push_error(message)
		failed = true

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
	panel.workspace_path.text = repo
	panel.python_path.text = OS.get_environment("DAQIAN_TEST_PYTHON")
	await panel._save_connection()
	var row: Dictionary = panel.board.issues[0]
	await panel._open_issue(row)
	# Reset the editor's remembered default. From this point every user action is inside Tianshu.
	var backend = chat.find_child("AIBackend", true, false)
	backend.select(0)
	backend.item_selected.emit(0)
	chat.find_child("APIModel", true, false).text = ""
	await panel._start_or_view_direct(row)
	if not panel.conversation.is_visible_in_tree() or not dock.is_visible_in_tree():
		push_error("Missing model did not open a configuration surface inside Tianshu: " + panel.notice.text)
		quit(1)
		return
	var view = panel.conversation
	var advanced = view.find_child("AdvancedToggle", true, false)
	advanced.button_pressed = true
	var endpoint = view.find_child("APIEndpoint", true, false)
	check(endpoint.is_visible_in_tree() and not chat.find_child("ChatSettingsDialog", true, false).visible, "Connection settings must open inline")
	endpoint.text = OS.get_environment("DAQIAN_TEST_ENDPOINT")
	view.find_child("AutoExecuteCommands", true, false).button_pressed = false
	view.find_child("AllowTools", true, false).button_pressed = true
	view.find_child("RefreshModels", true, false).pressed.emit()
	var picker = view.find_child("ModelPicker", true, false)
	var limit := Time.get_ticks_msec() + 10000
	while not chat.get_daqian_models().options.any(func(option): return option.id == "fixture") and Time.get_ticks_msec() < limit:
		await create_timer(0.05).timeout
	for i in picker.item_count:
		if picker.get_item_metadata(i) == "fixture":
			picker.select(i)
			picker.item_selected.emit(i)
	check(chat.get_daqian_models().current == "fixture", "Refreshed model missing")
	await panel._apply_issue_model()
	check(panel.saved.get("execution_models", {}).get(row.url, {}).get("id") == "fixture", "Issue model was not saved")
	check(panel.publish_button.text == "开始推进", "Bound model was not used for the requirement decision")
	await panel._start_or_view_direct(row)
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
	check(panel.details_document.get_parsed_text().contains("Bound section") and panel.details_document.get_v_scroll_bar().value > 0, "Document did not scroll to the bound section")
	check(panel._document_anchor(PackedStringArray(["# Other"]), op) == -1, "Unbound prose should not be highlighted")
	var marker := repo.path_join("executions")
	check(not FileAccess.file_exists(marker), "Reading details executed the tool")
	check(not chat.confirm_daqian_approval("obsolete-token"), "Wrong token was accepted")
	# The board source changes between opening the details and pressing Confirm.
	var changed := FileAccess.open(repo.path_join("changed"), FileAccess.WRITE)
	changed.close()
	await panel._confirm_operation(op.token)
	check(not FileAccess.file_exists(marker) and not chat.get_daqian_approval().is_empty(), "Stale source was approved")
	DirAccess.remove_absolute(repo.path_join("changed"))
	panel.details_confirm.pressed.emit()
	panel.details_confirm.pressed.emit()
	deadline = Time.get_ticks_msec() + 12000
	while panel.editor.workflow.get("operation", {}).get("state") != "completed" and Time.get_ticks_msec() < deadline:
		await create_timer(0.05).timeout
	check(FileAccess.get_file_as_string(marker).strip_edges() == "once", "Expected a single command execution")
	check(not chat.confirm_daqian_approval(op.token) and chat.get_daqian_approval().is_empty(), "Consumed token was reused")
	check(not panel.details_panel.visible and panel.editor.workflow.get("operation", {}).get("state") == "completed", "Missing terminal state")
	await panel._start_or_view_direct(panel._direct_binding())
	check(panel.conversation.is_visible_in_tree(), "Unable to revisit the active Issue")
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
	check(replied and dock.is_visible_in_tree(), "Follow-up did not return in the bound Tianshu conversation")
	panel._leave_conversation()
	check(panel.flow_split.is_visible_in_tree() and chat.find_child("AIWorkspacePages", true, false) != null, "Normal editor views were not restored")
	if not failed:
		print("DAQIAN_INLINE_APPROVAL_OK")
	await create_timer(0.8).timeout
	quit(1 if failed else 0)
