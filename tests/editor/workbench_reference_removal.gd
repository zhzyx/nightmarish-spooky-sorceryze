@tool
extends SceneTree

const HISTORY := "res://.godot/editor/ai_chat_history.json"

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
	root.size = Vector2i(1440, 900)
	await create_timer(1.0).timeout
	var settings := EditorInterface.get_editor_settings()
	settings.set_setting("gonggong/issue_number", "1810")
	settings.set_setting("gonggong/request_id", "gonggong-ai-workbench-plan1-u15")
	var dock = root.find_child("AI Chat", true, false)
	var backend = dock.find_child("AIBackend", true, false)
	backend.select(0)
	backend.item_selected.emit(0)
	var config = dock.get_ai_settings_control()
	config.find_child("APIEndpoint", true, false).text = OS.get_environment("U15_ENDPOINT")
	var fixture_key: LineEdit = config.find_child("APIKey", true, false)
	fixture_key.text = "u15-fixture-key"
	fixture_key.text_changed.emit(fixture_key.text)
	dock.find_child("APIModel", true, false).text = "fixture"
	var sidebar = root.find_child("AIWorkbenchSidebar", true, false)
	var snapshots := []
	for folder in ["alpha", "beta"]:
		var path := "res://%s/same.gd" % folder
		EditorInterface.set_main_screen_editor("Script")
		EditorInterface.edit_script(load(path))
		await process_frame
		var code := EditorInterface.get_script_editor().get_current_editor().get_base_editor() as CodeEdit
		code.grab_focus()
		code.select(1, 0, 1, code.get_line(1).length())
		var locator := path + "#L2:1-L2:" + str(code.get_line(1).length() + 1)
		snapshots.append({"kind":"editor","object_id":locator,"revision":code.text.sha256_text()})
		if not await _invoke_workbench(): return
		if folder == "alpha":
			sidebar.close()
			await process_frame
	var rows = sidebar.find_child("WorkbenchReferenceRows", true, false)
	var context: Label = sidebar.find_child("WorkbenchContext", true, false)
	var issue := context.text
	if not _check(rows.is_visible_in_tree() and rows.get_child_count() == 2 and issue == "项目 · U15 project\n工单 · #1810 · gonggong-ai-workbench-plan1-u15", "Visible context and two rows: " + issue): return
	# Wait until the native writer has captured the drafts before configuring the second fixture key.
	var deadline := Time.get_ticks_msec() + 12000
	while Time.get_ticks_msec() < deadline:
		if FileAccess.file_exists(HISTORY) and "u15-next-placeholder" in FileAccess.get_file_as_string(HISTORY): break
		await create_timer(0.1).timeout
	if not _check("u15-next-placeholder" in FileAccess.get_file_as_string(HISTORY), "No pre-rotation draft"): return
	fixture_key.text = "u15-next-placeholder"
	fixture_key.text_changed.emit(fixture_key.text)
	deadline = Time.get_ticks_msec() + 12000
	while Time.get_ticks_msec() < deadline:
		if FileAccess.file_exists(HISTORY + ".bak") and "u15-next-placeholder" not in FileAccess.get_file_as_string(HISTORY) and "u15-next-placeholder" not in FileAccess.get_file_as_string(HISTORY + ".bak"): break
		await create_timer(0.1).timeout
	if not _check(FileAccess.file_exists(HISTORY + ".bak") and "u15-next-placeholder" not in FileAccess.get_file_as_string(HISTORY) and "u15-next-placeholder" not in FileAccess.get_file_as_string(HISTORY + ".bak"), "Retained draft or backup was not scrubbed on rotation"): return
	var before := []
	for i in range(2):
		var row = rows.get_child(i)
		if not _check(row.visible and row.text.count("[REDACTED]") == 2 and snapshots[i].object_id in row.text and snapshots[i].revision in row.text, "Wrong displayed path/revision"): return
		before.append(row.text)
	rows.get_child(0).pressed.emit()
	var after: String = rows.get_child(0).text
	if not _check(rows.get_child_count() == 1 and "alpha" not in after and snapshots[1].object_id in after, "Retained row: " + after): return
	if not _check("u15-fixture-key" not in after and "[REDACTED]" in after, "Unredacted fixture excerpt"): return
	if not _check(context.text == issue, "Issue changed after removal: " + context.text): return
	sidebar.find_child("ChatInput", true, false).text = "retain beta"
	sidebar.find_child("Send", true, false).pressed.emit()
	deadline = Time.get_ticks_msec() + 20000
	while not FileAccess.file_exists("res://received") and Time.get_ticks_msec() < deadline:
		await create_timer(0.05).timeout
	if not _check(FileAccess.file_exists("res://received") and context.text == issue and settings.get_setting("gonggong/issue_number") == "1810" and settings.get_setting("gonggong/request_id") == "gonggong-ai-workbench-plan1-u15" and not rows.is_visible_in_tree(), "Send did not preserve the work order or clear references"): return
	var frozen := []
	deadline = Time.get_ticks_msec() + 10000
	while frozen.is_empty() and Time.get_ticks_msec() < deadline:
		await create_timer(0.1).timeout
		var history = JSON.parse_string(FileAccess.get_file_as_string("res://.godot/editor/ai_chat_history.json"))
		if not history is Dictionary: continue
		for agent in history.agents:
			for msg in agent.transcript:
				if msg.get("content", "").begins_with("retain beta"):
					frozen = msg.get("editor_references", [])
	if not _check(frozen == [snapshots[1]], "Incorrect frozen history"): return
	print("U15_RESULT ", JSON.stringify({"issue_before":issue, "issue_after":context.text,"before":before,"after":after,"selected":snapshots,"history":frozen}))
	quit()
