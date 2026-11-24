extends SceneTree

var widget
var fixture: Dictionary
var trace := []


func _initialize() -> void:
	fixture = JSON.parse_string(OS.get_environment("D09_FIXTURE"))
	run.call_deferred()


func wait_for(test: Callable, description: String) -> bool:
	var deadline := Time.get_ticks_msec() + 12000
	while not test.call() and Time.get_ticks_msec() < deadline:
		await process_frame
	if not test.call():
		if is_instance_valid(widget):
			print("D09_DIAGNOSTIC=", widget.dialog.visible, " ", widget.status.text, " ", widget.dialog.get_ok_button().disabled)
		push_error(description)
		quit(1)
		return false
	return true


func click(button: Button, double_click: bool = false) -> void:
	var pos := root.get_screen_transform().affine_inverse() * button.get_screen_transform() * (button.size / 2)
	var hover := InputEventMouseMotion.new()
	hover.position = pos
	hover.global_position = pos
	root.push_input(hover, true)
	for pressed: bool in [true, false]:
		var event := InputEventMouseButton.new()
		event.position = pos
		event.global_position = pos
		event.button_mask = MOUSE_BUTTON_MASK_LEFT if pressed else 0
		event.button_index = MOUSE_BUTTON_LEFT
		event.pressed = pressed
		event.double_click = pressed and double_click
		root.push_input(event, true)


func open_signoff(view, version: int, signed: bool) -> bool:
	await process_frame
	click(view.signoff)
	if not await wait_for(func(): return widget.dialog.visible and (widget.criteria.editable or widget.status.text.contains("已签认")), "Signoff not loaded: " + widget.status.text):
		return false
	var ok: Button = widget.dialog.get_ok_button()
	var valid: bool = widget.version == version and widget.document_id == fixture.id and widget.dialog.title.contains("v%d" % version) and ok.disabled
	if signed:
		valid = valid and not widget.criteria.editable and widget.criteria.text == fixture.first and widget.status.text.contains(fixture.actor)
	else:
		valid = valid and widget.criteria.editable and widget.criteria.text.is_empty()
	if not valid:
		push_error("Unexpected signoff: " + widget.status.text)
		quit(1)
	return valid


func confirm(version: int, acceptance: String, lose_response: bool) -> bool:
	var ok: Button = widget.dialog.get_ok_button()
	widget.criteria.text = acceptance
	widget.criteria.text_changed.emit()
	await process_frame
	click(ok)
	click(ok, true)
	if lose_response:
		if not await wait_for(func(): return widget.status.text.contains("重试"), "No retry after lost response: " + widget.status.text):
			return false
		if widget.criteria.editable or ok.disabled:
			push_error("Retry changed its inputs")
			quit(1)
			return false
		click(ok)
	if not await wait_for(func(): return widget.status.text.contains("已签认"), "Missing signed receipt: " + widget.status.text):
		return false
	if not widget.status.text.contains(fixture.actor) or widget.criteria.text != acceptance or not ok.disabled:
		push_error("Receipt did not match signer or criteria")
		quit(1)
		return false
	trace.append({"version": version, "status": widget.status.text, "acceptance": widget.criteria.text})
	return true


func run() -> void:
	root.gui_embed_subwindows = true
	root.size = Vector2i(1440, 960)
	root.notify_mouse_entered()
	await create_timer(0.8).timeout
	var sidebar = root.find_child("AIWorkbenchSidebar", true, false)
	var entry = root.find_child("OpenAIWorkbenchButton", true, false)
	if entry:
		entry.pressed.emit()
	else:
		var palette = EditorInterface.get_command_palette()
		var shortcut := InputEventShortcut.new()
		shortcut.shortcut = EditorInterface.get_editor_settings().get_shortcut("editor/command_palette")
		root.push_input(shortcut)
		await process_frame
		var search = palette.find_children("*", "LineEdit", true, false)[0]
		search.text = "editor/open_ai_workbench"
		search.text_changed.emit(search.text)
		palette.find_children("*", "Tree", true, false)[0].item_activated.emit()
	var session = sidebar.find_child("WorkbenchBusinessSession", true, false)
	if not await wait_for(func(): return not session.get_identity().is_empty(), "Account unavailable"):
		return
	var view = session.get_node("WorkbenchDocuments")
	widget = session.get_node("WorkbenchDesignSignoff")
	session.find_child("OpenWorkbenchDocuments", true, false).pressed.emit()
	if not await wait_for(func(): return view.documents.item_count == 1, "No design in browser"):
		return
	view.documents.select(0)
	view.documents.item_selected.emit(0)
	var version := int(fixture.version)
	if not await wait_for(func(): return int(view.reference.get("version", 0)) == version, "Selected revision did not load"):
		return
	if not await open_signoff(view, version, false):
		return
	trace.append({"unsigned": version, "body": view.body.text})
	if not await confirm(version, fixture.first if version == 1 else fixture.second, version == 1):
		return
	if version == 2:
		click(widget.dialog.get_cancel_button())
		view.history.pressed.emit()
		var history = session.get_node("WorkbenchDocumentHistory")
		if not await wait_for(func(): return not history.read.disabled, "Version history missing"):
			return
		var index: int = history.source.get_item_index(1)
		history.source.select(index)
		history.source.item_selected.emit(index)
		history.read.pressed.emit()
		if not await wait_for(func(): return view.reference.get("version") == 1, "Historical revision missing"):
			return
		if not await open_signoff(view, 1, true):
			return
		trace.append({"reopened": 1, "status": widget.status.text, "acceptance": widget.criteria.text, "body": view.body.text})
	print("D09_NATIVE=", JSON.stringify(trace))
	quit(0)
