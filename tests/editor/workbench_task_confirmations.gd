extends SceneTree

var fixture: Dictionary
var action: Node


func _initialize() -> void:
	fixture = JSON.parse_string(OS.get_environment("A02_TASK"))
	run.call_deferred()


func wait_for(check: Callable, label: String) -> bool:
	var deadline := Time.get_ticks_msec() + 20000
	while not check.call() and Time.get_ticks_msec() < deadline:
		await process_frame
	if check.call():
		return true
	printerr("A02 timeout ", label, " ", action.status.text if action else "")
	quit(1)
	return false


func click(control: Button) -> void:
	var pos := root.get_screen_transform().affine_inverse() * control.get_screen_transform() * (control.size / 2)
	var motion := InputEventMouseMotion.new()
	motion.position = pos
	motion.global_position = pos
	root.push_input(motion, true)
	for pressed in [true, false]:
		var event := InputEventMouseButton.new()
		event.position = pos
		event.global_position = pos
		event.button_index = MOUSE_BUTTON_LEFT
		event.button_mask = MOUSE_BUTTON_MASK_LEFT if pressed else 0
		event.pressed = pressed
		root.push_input(event, true)


func labels() -> Array:
	var result := []
	for row: Node in action.rows.get_children():
		result.append({"issue": row.get_node("SelectTask").text, "label": row.get_node("Target").text,
			"selected": row.get_node("SelectTask").button_pressed})
	return result


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
	action = view.get_node("issue_task_confirmation")
	action.open.pressed.emit()
	if not await wait_for(func(): return action.dialog.visible and action.status.text.begins_with("勾选"), "list"):
		return
	await process_frame
	await process_frame
	if action.rows.get_child_count() != int(fixture.get("task_count", 2)):
		printerr("Unexpected number of independently selectable tasks: ", action.rows.get_child_count())
		quit(1)
		return
	var before := labels()
	var selected := []
	var rects := []
	var viewport: Rect2 = action.rows.get_parent().get_global_rect()
	var target_row: Node = action.rows.get_child(0)
	for row: Node in action.rows.get_children():
		var toggle := row.get_node("SelectTask") as Button
		if fixture.get("focus_only", false):
			if not toggle.text.begins_with("#%d " % int(fixture.number)):
				continue
			target_row = row
			action.rows.get_parent().ensure_control_visible(row)
			await process_frame
		var act := row.get_node("ConfirmTask") as Button
		var select_rect := toggle.get_global_rect()
		var act_rect := act.get_global_rect()
		rects.append([str(select_rect), str(act_rect)])
		if not viewport.encloses(select_rect) or not viewport.encloses(act_rect):
			printerr("Outside simultaneous visible area ", viewport, " ", rects)
			quit(1)
			return
		if fixture.action != "read":
			click(toggle)
			if not toggle.button_pressed:
				printerr("Native selection failed ", select_rect)
				quit(1)
				return
			selected.append(toggle.text)
	if fixture.action != "read":
		var button: Button = target_row.get_node("ConfirmTask")
		var expected := "确认启动本项" if fixture.action == "confirm" else "撤销本项确认"
		if button.text != expected or button.disabled:
			printerr("Action unavailable: ", button.text)
			quit(1)
			return
		click(button)
		if not await wait_for(func(): return action.status.text.begins_with("已从天璇"), "write and readback"):
			return
	print("A02_NATIVE=", JSON.stringify({"before": before, "after": labels(), "selected": selected,
		"rects": rects, "viewport": str(viewport), "feedback": action.status.text}))
	quit(0)
