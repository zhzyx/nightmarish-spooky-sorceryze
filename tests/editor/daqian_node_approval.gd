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
	settings.set_setting("gonggong/workspace", repo)
	settings.set_setting("gonggong/python", OS.get_environment("DAQIAN_TEST_PYTHON"))
	var dock = root.find_child("Daqian", true, false)
	var panel = dock.find_child("DaqianWorkspace", true, false)
	var chat = root.find_child("AI Chat", true, false)
	dock.make_visible()
	await panel.refresh()
	var row: Dictionary = panel.board.issues[0]
	await panel._open_issue(row)
	var backend = chat.find_child("AIBackend", true, false)
	backend.select(0)
	backend.item_selected.emit(0)
	chat.find_child("APIEndpoint", true, false).text = OS.get_environment("DAQIAN_TEST_ENDPOINT")
	chat.find_child("AutoExecuteCommands", true, false).button_pressed = false
	chat.find_child("AllowTools", true, false).button_pressed = true
	var error: String = chat.open_daqian_chat(row.url, row.number, row.request, "Inspect this bound requirement", false, {"backend":0, "id":"fixture"})
	check(error.is_empty(), error)
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
	if not failed:
		print("DAQIAN_INLINE_APPROVAL_OK")
	await create_timer(0.8).timeout
	quit(1 if failed else 0)
