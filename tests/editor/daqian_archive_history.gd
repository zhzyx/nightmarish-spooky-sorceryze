@tool
extends SceneTree


func _initialize() -> void:
	run.call_deferred()


func run() -> void:
	await create_timer(1.0).timeout
	EditorInterface.set_main_screen_editor("天枢")
	await process_frame
	var panel = root.find_child("DaqianWorkspace", true, false)
	if panel == null or not panel.archive_history_button.is_visible_in_tree():
		push_error("Archive history entry unavailable")
		quit(1)
		return
	panel.archive_history_button.pressed.emit()
	await process_frame
	var dialog = panel.archive_history_dialog
	dialog.project.text = OS.get_environment("HISTORY_TEST_PROJECT")
	dialog.file_path.text = OS.get_environment("HISTORY_TEST_PATH")
	dialog.search.pressed.emit()
	var deadline := Time.get_ticks_msec() + 40000
	while dialog.commits.item_count == 0 and Time.get_ticks_msec() < deadline and dialog.details.text == "":
		await create_timer(0.04).timeout
	if dialog.commits.item_count != 3:
		push_error("Expected two contents and one deletion: " + str(dialog.details.text))
		quit(1)
		return
	var reads := []
	for row in range(3):
		dialog.commits.select(row)
		dialog.commits.item_selected.emit(row)
		deadline = Time.get_ticks_msec() + 40000
		while not dialog.source.visible and Time.get_ticks_msec() < deadline:
			await create_timer(0.04).timeout
		if not dialog.source.visible or dialog.details.editable:
			push_error("Failed to read selected file: " + str(dialog.details.text))
			quit(1)
			return
		var file: String = dialog.details.text
		dialog.source.pressed.emit()
		reads.append({"oid": dialog.commits.get_item_metadata(row), "file": file, "source": dialog.details.text})
	FileAccess.open("res://history-result.json", FileAccess.WRITE).store_string(JSON.stringify(reads))
	quit()
