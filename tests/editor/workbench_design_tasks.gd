extends SceneTree

var fixture: Dictionary
var widget


func _initialize() -> void:
	fixture = JSON.parse_string(OS.get_environment("D10_FIXTURE"))
	run.call_deferred()


func wait_for(check: Callable, message: String) -> bool:
	var deadline := Time.get_ticks_msec() + 15000
	while not check.call() and Time.get_ticks_msec() < deadline:
		await process_frame
	if not check.call():
		if is_instance_valid(widget):
			print("D10 status: ", widget.status.text)
		push_error(message)
		quit(1)
		return false
	return true


func click(button: Button) -> void:
	var pos := root.get_screen_transform().affine_inverse() * button.get_screen_transform() * (button.size / 2)
	var motion := InputEventMouseMotion.new()
	motion.position = pos
	motion.global_position = pos
	root.push_input(motion, true)
	for pressed: bool in [true, false]:
		var event := InputEventMouseButton.new()
		event.position = pos
		event.global_position = pos
		event.button_index = MOUSE_BUTTON_LEFT
		event.button_mask = MOUSE_BUTTON_MASK_LEFT if pressed else 0
		event.pressed = pressed
		root.push_input(event, true)


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
	if not await wait_for(func(): return not session.get_identity().is_empty(), "Session unavailable"):
		return
	var view = session.get_node("WorkbenchDocuments")
	var signoff = session.get_node("WorkbenchDesignSignoff")
	widget = session.get_node("WorkbenchDesignTasks")
	session.find_child("OpenWorkbenchDocuments", true, false).pressed.emit()
	if not await wait_for(func(): return view.documents.item_count == 1, "No design"):
		return
	view.documents.select(0)
	view.documents.item_selected.emit(0)
	if not await wait_for(func(): return not view.signoff.disabled, "No revision"):
		return
	view.signoff.pressed.emit()
	if not await wait_for(func(): return signoff.split.is_visible_in_tree(), "No split action on signed design"):
		return
	click(signoff.split)
	if not await wait_for(func(): return widget.dialog.visible and not widget.add_item.disabled, "Cannot map tasks"):
		return
	for item: Dictionary in fixture.items:
		widget.paragraph.select(int(item.paragraph) - 1)
		var index := -1
		for i in widget.module.item_count:
			if widget.module.get_item_metadata(i) == item.module_id:
				index = i
		if index == -1:
			push_error("Target module absent")
			quit(1)
			return
		widget.module.select(index)
		widget.task_title.text = item.title
		widget.acceptance.text = item.acceptance
		click(widget.add_item)
	if widget.items.size() != fixture.items.size():
		push_error("Missing staged item")
		quit(1)
		return
	click(widget.dialog.get_ok_button())
	click(widget.dialog.get_ok_button())
	if not await wait_for(func(): return widget.status.text.contains("重试"), "Lost receipt not handled"):
		return
	if widget.form.visible:
		push_error("Retry inputs can change")
		quit(1)
		return
	click(widget.dialog.get_ok_button())
	if not await wait_for(func(): return widget.status.text.contains("已生成"), "Split did not finish"):
		return
	var trace := {"status": widget.status.text, "revision": signoff.version, "items": widget.items.duplicate(true), "opened": []}
	var tasks: Dictionary = await session.api_request(HTTPClient.METHOD_GET, widget.route)
	var doc_id: String = signoff.document_id
	widget.dialog.hide()
	signoff.dialog.hide()
	view.hide()
	var changed: Dictionary = await session.api_request(HTTPClient.METHOD_PATCH, "/api/v1/docs/" + doc_id, {
		"expected_version": 1, "body_md": "A different design."})
	if changed.status != 200 or int(changed.data.get("version", 0)) != 2:
		push_error("Follow-up revision failed")
		quit(1)
		return
	var detail = session.get_node("WorkbenchIssueDetail")
	detail.find_child("OpenIssueDetail", true, false).pressed.emit()
	var read = detail.find_child("ReadIssueDetail", true, false)
	var field = detail.find_child("IssueDetailNumber", true, false)
	var source = detail.find_child("OpenIssueDesignSource", true, false)
	for task: Dictionary in tasks.data.tasks:
		field.text = str(int(task.number))
		field.text_changed.emit(field.text)
		read.pressed.emit()
		if not await wait_for(func(): return source.visible, "No original design in issue details"):
			return
		source.pressed.emit()
		if not await wait_for(func(): return view.reference.get("version") == 1 and view.reference.get("paragraph") == int(task.paragraph), "Wrong source"):
			return
		trace.opened.append({"number": int(task.number), "reference": view.reference.duplicate(), "body": view.raw_body})
		view.hide()
	print("D10_NATIVE=", JSON.stringify(trace))
	quit(0)
