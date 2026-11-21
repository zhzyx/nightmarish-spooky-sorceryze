@tool
extends SceneTree

# Run in an isolated editor with an authenticated Tianxuan archive fixture.
func _initialize() -> void:
	run.call_deferred()

func button(parent: Node, title: String) -> Button:
	for node in parent.find_children("*", "Button", true, false):
		if node.text == title and node.is_visible_in_tree() and not node.disabled:
			return node
	return null

func run() -> void:
	await create_timer(1.0).timeout
	var dock = root.find_child("Daqian", true, false)
	EditorInterface.set_main_screen_editor("天枢")
	await process_frame
	var panel = dock.find_child("DaqianWorkspace", true, false)
	var entry := button(panel, "历史工单")
	if not entry:
		var path := PackedStringArray()
		var control = panel.historical_issue_button
		while control:
			path.append("%s: %s" % [control.name, control.visible if control is CanvasItem or control is Window else ""])
			control = control.get_parent()
		push_error("Historical issue entry missing: " + " / ".join(path))
		quit(1)
		return
	entry.pressed.emit()
	await process_frame
	var dialog: AcceptDialog = panel.historical_issue_dialog
	var fields := dialog.find_children("*", "LineEdit", true, false)
	var read := button(dialog, "读取历史工单")
	var view: TextEdit = dialog.find_children("*", "TextEdit", true, false)[0]
	var scope := OS.get_environment("HISTORY_TEST_PROJECT")
	var identifier := OS.get_environment("HISTORY_TEST_SOURCE")
	var outputs := []
	for value in [identifier, OS.get_environment("HISTORY_TEST_MISSING_ID")]:
		fields[0].text = scope
		fields[1].text = value
		read.pressed.emit()
		var deadline := Time.get_ticks_msec() + 30000
		while read.disabled and Time.get_ticks_msec() < deadline:
			await create_timer(0.03).timeout
		if read.disabled or not view.visible or view.editable or not value in view.text or not scope in view.text:
			push_error("Archive display did not resolve to the requested read-only view")
			quit(1)
			return
		outputs.append(view.text)
	if not outputs[1].begins_with("无法读取历史工单"):
		push_error("Missing identifier did not show an archive lookup failure")
		quit(1)
		return
	dialog.get_ok_button().pressed.emit()
	await process_frame
	# Seed the external context normally supplied by the issue inspector.
	panel._show_tianxuan_dialog(identifier, {}, {"number": 1642})
	await process_frame
	var context: AcceptDialog
	for child in panel.get_children():
		if child is AcceptDialog and child.visible and child.title.begins_with("天璇 · Issue #"):
			context = child
	if not context or not button(context, "历史工单"):
		push_error("External issue context has no archive entry")
		quit(1)
		return
	button(context, "历史工单").pressed.emit()
	await process_frame
	var nested: AcceptDialog = panel.historical_issue_dialog
	if nested.get_parent() != context or not nested.visible or nested.find_children("*", "LineEdit", true, false)[1].text != identifier:
		push_error("External issue context did not preserve its original identifier")
		quit(1)
		return
	FileAccess.open("res://history-result.json", FileAccess.WRITE).store_string(JSON.stringify(outputs))
	quit(0)
