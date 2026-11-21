@tool
extends SceneTree

const WORKBENCH_COMMAND := "editor/open_ai_workbench"

func _initialize() -> void:
	run.call_deferred()

func _check(ok: bool, message: String) -> bool:
	if not ok:
		push_error(message)
		quit(1)
	return ok

func _invoke_workbench() -> bool:
	var palette := EditorInterface.get_command_palette()
	palette.popup_centered()
	await process_frame
	if not _check(palette.visible, "Command palette did not open"):
		return false
	var search := palette.find_children("*", "LineEdit", true, false).front() as LineEdit
	var results := palette.find_children("*", "Tree", true, false).front() as Tree
	search.text = WORKBENCH_COMMAND
	search.text_changed.emit(search.text)
	var item := results.get_selected()
	if not _check(item != null and item.get_metadata(0) == WORKBENCH_COMMAND, "Workbench command missing"):
		return false
	results.item_activated.emit()
	await process_frame
	return true

func run() -> void:
	await create_timer(1.0).timeout
	var dock = root.find_child("AI Chat", true, false)
	var backend = dock.find_child("AIBackend", true, false)
	backend.select(0)
	backend.item_selected.emit(0)
	dock.get_ai_settings_control().find_child("APIEndpoint", true, false).text = OS.get_environment("GONGGONG_TEST_ENDPOINT")
	dock.find_child("APIModel", true, false).text = "fixture"
	var observations := []
	for folder in ["alpha", "beta", "alpha"]:
		var path := "res://%s/same.gd" % folder
		EditorInterface.set_main_screen_editor("Script")
		EditorInterface.edit_script(load(path))
		await process_frame
		var code := EditorInterface.get_script_editor().get_current_editor().get_base_editor() as CodeEdit
		code.grab_focus()
		code.select(1, 0, 1, code.get_line(1).length())
		var revision := code.text.sha256_text()
		if not await _invoke_workbench():
			return
		var sidebar = root.find_child("AIWorkbenchSidebar", true, false)
		var chip: Button = sidebar.find_child("WorkbenchReference", true, false)
		if not _check(chip.visible and path in chip.text, "Wrong draft reference: " + chip.text):
			return
		var removed := observations.size() == 2
		if removed:
			chip.pressed.emit()
			if not _check(not chip.visible, "Reference still visible after removal"):
				return
		var other := "beta" if folder == "alpha" else "alpha"
		EditorInterface.edit_script(load("res://%s/same.gd" % other))
		await process_frame
		var marker := "selection-test-%d" % observations.size()
		sidebar.find_child("ChatInput", true, false).text = marker
		sidebar.find_child("Send", true, false).pressed.emit()
		var deadline := Time.get_ticks_msec() + 18000
		while not FileAccess.file_exists("res://received-" + marker) and Time.get_ticks_msec() < deadline:
			await create_timer(0.05).timeout
		if not _check(FileAccess.file_exists("res://received-" + marker), "Loopback did not receive " + marker):
			return
		observations.append({"path":path, "revision":revision, "removed":removed, "marker":marker})
		await create_timer(0.25).timeout
		sidebar.close()
		await process_frame
	FileAccess.open("res://observations.json", FileAccess.WRITE).store_string(JSON.stringify(observations))
	quit()
