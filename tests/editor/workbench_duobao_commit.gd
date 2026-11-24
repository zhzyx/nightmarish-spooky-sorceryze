extends SceneTree

func _initialize() -> void:
	run.call_deferred()


func settle(dialog) -> void:
	var deadline := Time.get_ticks_msec() + 45000
	while dialog.busy and Time.get_ticks_msec() < deadline:
		await create_timer(0.03).timeout


func run() -> void:
	await create_timer(1).timeout
	var chat = root.find_child("AI Chat", true, false)
	var error: String = chat.set_runtime_field("workflow_python", OS.get_environment("G11_PYTHON"))
	if not error.is_empty():
		push_error(error)
		quit(1)
		return
	await create_timer(0.5).timeout
	EditorInterface.set_main_screen_editor("天枢")
	await process_frame
	var panel = root.find_child("DaqianWorkspace", true, false)
	var entry: Button = panel.duobao_commit_button
	if not entry or not entry.is_visible_in_tree():
		push_error("G11 entry missing")
		quit(1)
		return
	entry.pressed.emit()
	await process_frame
	var dialog = panel.duobao_commit_dialog
	await settle(dialog)
	var phase := OS.get_environment("G11_NATIVE_PHASE")
	var checks := {"entry": dialog.visible, "initial_diff": dialog.snapshot.get("files", []).size() == 2}
	if not phase.is_empty():
		checks.native_module = dialog.snapshot.get("mode") == "native" and dialog.snapshot.get("branch") == "game" and not dialog.repository.visible
	if not checks.initial_diff:
		push_error(dialog.status.text + str(dialog.snapshot))
		quit(1)
		return
	for item in dialog.files.get_root().get_children():
		if item.get_metadata(0) == "A.txt":
			item.set_checked(0, true)
			item.select(0)
	var deadline := Time.get_ticks_msec() + 30000
	while dialog.preview.text.is_empty() and Time.get_ticks_msec() < deadline:
		await create_timer(0.05).timeout
	checks.preview = "+chosen" in dialog.preview.text and not "working B" in dialog.preview.text
	dialog.message.text = "commit only A"
	dialog.send.pressed.emit()
	dialog.send.pressed.emit()
	await settle(dialog)
	if phase != "restart":
		checks.unknown_response = "503" in dialog.status.text
	if phase.is_empty():
		dialog.send.pressed.emit()
		await settle(dialog)
	if phase != "first":
		checks.received = "多宝已接收" in dialog.status.text
		var rows: Array = dialog.snapshot.get("files", [])
		checks.remaining = rows.size() == 1 and rows[0].status == "M" and rows[0].path == "B.txt"
	print("G11_CHECKS=", JSON.stringify(checks))
	if checks.values().has(false):
		push_error(dialog.status.text)
		quit(1)
	else:
		quit()
