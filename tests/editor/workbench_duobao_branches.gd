extends SceneTree

func _initialize() -> void:
	run.call_deferred()

func button(parent: Node, caption: String) -> Button:
	for value in parent.find_children("*","Button",true,false):
		if value.text == caption and value.is_visible_in_tree():
			return value
	return null

func settled(dialog) -> void:
	var until := Time.get_ticks_msec() + 30000
	while dialog.busy and Time.get_ticks_msec() < until:
		await create_timer(0.03).timeout

func run() -> void:
	await create_timer(1.0).timeout
	var chat = root.find_child("AI Chat",true,false)
	var error: String = chat.set_runtime_field("workflow_python", OS.get_environment("G10_PYTHON"))
	if not error.is_empty():
		push_error(error)
		quit(1)
		return
	await create_timer(0.5).timeout
	EditorInterface.set_main_screen_editor("天枢")
	await process_frame
	var panel = root.find_child("DaqianWorkspace",true,false)
	var entry := button(panel,"多宝分支")
	if not entry:
		push_error("Branch entry absent")
		quit(1)
		return
	entry.pressed.emit()
	await process_frame
	var dialog = panel.duobao_dialog
	await settled(dialog)
	var checks := {}
	var start := OS.get_environment("G10_BASE")
	var latest := OS.get_environment("G10_HEAD")
	var first := OS.get_environment("G10_PHASE") == "first"
	checks.entry = dialog.visible and dialog.repository.text == "sample.git"
	checks.start = dialog.snapshot.get("branch") == ("main" if first else "review/g10")
	checks.start_tip = dialog.snapshot.get("head") == (latest if first else start)
	if not checks.start:
		push_error(dialog.status.text)
		quit(1)
		return
	if first:
		dialog.branch_name.text = "review/g10"
		dialog.baseline.text = start
		button(dialog,"创建分支").pressed.emit()
		await settled(dialog)
		checks.created = start in dialog.status.text
		dialog.hide()
		EditorInterface.edit_resource(load("res://sample.gd"))
		await create_timer(0.35).timeout
		var script_editor := EditorInterface.get_script_editor()
		var code: CodeEdit = script_editor.get_current_editor().get_base_editor()
		code.set_caret_line(code.get_line_count()-1)
		code.insert_text_at_caret("# unsaved G10\n")
		await process_frame
		checks.dirty_buffer = not script_editor.get_unsaved_files().is_empty() and not "unsaved G10" in FileAccess.get_file_as_string("res://sample.gd")
		EditorInterface.set_main_screen_editor("天枢")
		await process_frame
		entry.pressed.emit()
		await settled(dialog)
		button(dialog,"切换").pressed.emit()
		await settled(dialog)
		checks.denied = "未保存" in dialog.status.text and dialog.snapshot.head == latest
		dialog.preserve.button_pressed = true
		button(dialog,"切换").pressed.emit()
		await settled(dialog)
		checks.switched = dialog.snapshot.head == start and dialog.snapshot.branch == "review/g10"
	else:
		dialog.branch_name.text = "main"
		button(dialog,"切换").pressed.emit()
		await settled(dialog)
		checks.returned = dialog.snapshot.head == latest and dialog.snapshot.branch == "main"
		checks.recoverable = not str(dialog.snapshot.get("recovery","")).is_empty()
		button(dialog,"恢复本分支修改").pressed.emit()
		await settled(dialog)
		checks.restored = "unsaved G10" in FileAccess.get_file_as_string("res://sample.gd")
	print("G10_CHECKS=",JSON.stringify(checks))
	if checks.values().has(false):
		push_error(dialog.status.text)
		quit(1)
	else:
		quit()
