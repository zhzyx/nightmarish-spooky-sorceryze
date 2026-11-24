extends SceneTree

var fixture: Dictionary
var action: Node
var view: Node


func _initialize() -> void:
	fixture = JSON.parse_string(OS.get_environment("A01_TASK"))
	run.call_deferred()


func wait_for(check: Callable, label: String) -> bool:
	var deadline := Time.get_ticks_msec() + 15000
	while not check.call() and Time.get_ticks_msec() < deadline:
		await process_frame
	if check.call():
		return true
	printerr("A01 timeout: ", label, "; ", action.status.text if action else "")
	quit(1)
	return false


func run() -> void:
	root.gui_embed_subwindows = true
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
	if not await wait_for(func(): return session and not session.get_identity().is_empty(), "business session"):
		return
	view = session.get_node("WorkbenchIssueDetail")
	await view.open_issue(int(fixture.number))
	action = view.get_node("issue_task_target")
	if not action.open.is_visible_in_tree():
		quit(1)
		return
	var observations := []
	for proposal: Dictionary in fixture.proposals:
		action.open.pressed.emit()
		if not action.dialog.visible or action.dialog.get_ok_button().disabled:
			quit(1)
			return
		action.stage.text = proposal.stage
		action.criteria.text = proposal.criteria
		action.dialog.get_ok_button().pressed.emit()
		if not await wait_for(func(): return action.dialog.visible and view.get_detail().get("task_target") is Dictionary and int(view.get_detail().task_target.revision) == int(proposal.revision), "durable target"):
			return
		observations.append({"target": view.get_detail().task_target, "feedback": action.status.text,
			"stage": action.stage.text, "criteria": action.criteria.text})
		action.dialog.hide()
	print("A01_NATIVE=", JSON.stringify(observations))
	quit(0)
