extends SceneTree

var panel
var widget
var fixture: Dictionary
var trace := []


func _initialize() -> void:
	fixture = JSON.parse_string(OS.get_environment("D13_FIXTURE"))
	run.call_deferred()


func expect(value: bool, message: String) -> bool:
	if not value:
		push_error(message)
		quit(1)
	return value


func wait_for(test: Callable, message: String) -> bool:
	var deadline := Time.get_ticks_msec() + 12000
	while not test.call() and Time.get_ticks_msec() < deadline:
		await process_frame
	return expect(test.call(), message)


func select(control: OptionButton, index: int) -> void:
	control.select(index)
	control.item_selected.emit(index)


func capture() -> void:
	trace.append({"summary": widget.summary.text, "revision": widget.revisions.get_item_text(widget.revisions.selected) if widget.revisions.selected >= 0 else null,
		"body": widget.body.text, "event": widget.event.text, "notice": widget.notice.text, "confirm_enabled": not widget.confirm.disabled})


func decision(button: Button) -> bool:
	if not expect(button.is_visible_in_tree() and not button.disabled, "Expected active decision: " + button.text):
		return false
	button.pressed.emit()
	button.pressed.emit()
	return await wait_for(func(): return not widget.busy, "Decision timed out")


func run() -> void:
	for frame in 12:
		await process_frame
	var palette := EditorInterface.get_command_palette()
	var shortcut := InputEventShortcut.new()
	shortcut.shortcut = EditorInterface.get_editor_settings().get_shortcut("editor/command_palette")
	root.push_input(shortcut)
	await process_frame
	var search := palette.find_children("*", "LineEdit", true, false)[0] as LineEdit
	search.text = "editor/open_ai_workbench"
	search.text_changed.emit(search.text)
	palette.find_children("*", "Tree", true, false)[0].item_activated.emit()
	await process_frame
	var sidebar := root.find_child("AIWorkbenchSidebar", true, false)
	panel = sidebar.find_child("WorkbenchBusinessModules", true, false)
	widget = sidebar.find_child("WorkbenchDesignProgress", true, false)
	if not await wait_for(func(): return panel.managed_identity and not panel.session.get_identity().is_empty(), "Account unavailable"):
		return
	if fixture.mode == "document":
		await read_document()
	else:
		await read_chat()


func read_chat() -> void:
	var picker: OptionButton = panel.picker
	picker.item_selected.emit(1)
	if not await wait_for(func(): return not panel.busy, "Module list failed"):
		return
	for index in picker.item_count:
		if picker.get_item_metadata(index) == "default":
			picker.get_popup().hide()
			select(picker, index)
			break
	if not await wait_for(func(): return panel.progress_action.is_visible_in_tree() and not panel.busy, "Conversation entry unavailable"):
		return
	panel.progress_action.pressed.emit()
	if not await wait_for(func(): return widget.dialog.visible and not widget.busy, "Stage view failed"):
		return
	if not expect(widget.summary.text.contains(fixture.id) and widget.body.text == fixture.body, "Wrong source or stage revision: " + widget.summary.text):
		return
	capture()
	if fixture.mode == "stale":
		if not await decision(widget.confirm):
			return
		if not expect(widget.body.text == "Replacement direction" and widget.notice.text.contains("409"), "Concurrent edit approved or missing"):
			return
		capture()
		widget.reason.text = "Include the lever location."
		widget.reason.text_changed.emit(widget.reason.text)
		if not await decision(widget.send_back):
			return
		if not expect(widget.confirm.disabled and widget.event.text.contains("Include the lever location.") and widget.event.text.contains(fixture.actor), "Return receipt missing"):
			return
	else:
		if fixture.mode == "direction":
			select(widget.revisions, 1)
			if not expect(widget.body.text == "Replacement direction" and widget.event.text.contains("Include the lever location.") and widget.confirm.disabled, "Wrong historical return"):
				return
			capture()
			select(widget.revisions, 2)
		if not await decision(widget.confirm):
			return
		if not expect(widget.confirm.disabled and widget.event.text.contains(fixture.actor) and widget.summary.text.contains(fixture.pending + "：未开始"), "Approval crossed stage boundary"):
			return
	capture()
	print("D13_NATIVE=", JSON.stringify(trace))
	quit()


func read_document() -> void:
	var session = panel.session
	var docs = session.get_node("WorkbenchDocuments")
	session.find_child("OpenWorkbenchDocuments", true, false).pressed.emit()
	if not await wait_for(func(): return docs.documents.item_count == 1, "Document list unavailable"):
		return
	docs.documents.select(0)
	docs.documents.item_selected.emit(0)
	if not await wait_for(func(): return docs.reference.get("version") == 2, "Current document revision missing"):
		return
	docs.progress.pressed.emit()
	if not await wait_for(func(): return widget.dialog.visible and not widget.busy, "Document stage view failed"):
		return
	if not expect(widget.summary.text.contains("v2 尚未签认") and widget.notice.text.contains("没有") and widget.confirm.disabled and widget.body.text.is_empty(), "v2 inherited v1 approvals"):
		return
	capture()
	widget.dialog.hide()
	docs.history.pressed.emit()
	var history = session.get_node("WorkbenchDocumentHistory")
	if not await wait_for(func(): return not history.read.disabled, "Version history unavailable"):
		return
	select(history.source, history.source.get_item_index(1))
	history.read.pressed.emit()
	if not await wait_for(func(): return docs.reference.get("version") == 1, "Historical version unavailable"):
		return
	docs.progress.pressed.emit()
	if not await wait_for(func(): return widget.dialog.visible and not widget.busy, "Historical design view failed"):
		return
	if not expect(widget.summary.text.contains(fixture.id) and widget.summary.text.contains("v1 签认") and widget.summary.text.contains("One pull.") and widget.confirm.disabled, "Document approval missing: " + widget.summary.text):
		return
	for index in 3:
		select(widget.stage, index)
		if not expect(widget.body.text.contains(fixture.bodies[index]) and widget.event.text.contains(fixture.actor) and widget.confirm.disabled, "Wrong approved stage revision"):
			return
		capture()
	print("D13_NATIVE=", JSON.stringify(trace))
	quit()
