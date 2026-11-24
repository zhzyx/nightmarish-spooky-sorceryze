extends SceneTree

var fixture: Dictionary


func _initialize() -> void:
	fixture = JSON.parse_string(OS.get_environment("S10_TASK"))
	run.call_deferred()


func wait_for(check: Callable, label: String) -> bool:
	var deadline := Time.get_ticks_msec() + 16000
	while not check.call() and Time.get_ticks_msec() < deadline:
		await process_frame
	if check.call():
		return true
	printerr("Timeout waiting for ", label)
	quit(1)
	return false


func run() -> void:
	root.gui_embed_subwindows = true
	root.size = Vector2i(1440, 960)
	root.notify_mouse_entered()
	await create_timer(1).timeout
	var entry := root.find_child("OpenAIWorkbenchButton", true, false) as Button
	if entry:
		entry.pressed.emit()
	else:
		var palette := EditorInterface.get_command_palette()
		var shortcut := InputEventShortcut.new()
		shortcut.shortcut = EditorInterface.get_editor_settings().get_shortcut("editor/command_palette")
		root.push_input(shortcut)
		await process_frame
		var search := palette.find_children("*", "LineEdit", true, false).front() as LineEdit
		search.text = "editor/open_ai_workbench"
		search.text_changed.emit(search.text)
		palette.find_children("*", "Tree", true, false).front().item_activated.emit()
	var session := root.find_child("WorkbenchBusinessSession", true, false)
	if not await wait_for(func(): return session and not session.get_identity().is_empty(), "session"):
		return
	var view := session.get_node("WorkbenchIssueDetail")
	await view.open_issue(int(fixture.number))
	var panel := view.get_node("issue_run_control")
	var before: Dictionary = view.get_detail().execution_progress
	if not panel.visible or before.id != fixture.key:
		printerr("Selected task has no matching local worker")
		quit(1)
		return
	var operation: String = fixture.operation
	if operation != "read":
		var button := panel.actions.get_node_or_null(operation) as Button
		if not button or button.disabled or not button.is_visible_in_tree():
			printerr("Missing control ", operation, " in ", panel.summary.text)
			quit(1)
			return
		button.pressed.emit()
		if not await wait_for(func(): return not panel.notice.text.is_empty(), "operation readback"):
			return
		if panel.notice.text != "操作已接收。":
			printerr(panel.notice.text, " ", panel.summary.text)
			quit(1)
			return
	var after: Dictionary = view.get_detail().execution_progress
	print("S10_NATIVE=", JSON.stringify({"before": before, "after": after, "summary": panel.summary.text}))
	quit(0)
