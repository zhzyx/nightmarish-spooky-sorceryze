@tool
extends "res://order.gd"

var chat: Node
var sidebar: EditorDock
var page: EditorDock
var summary: LineEdit
var private_note: LineEdit
var milestone: LineEdit
var approval: ConfirmationDialog
var send: Button
var input: TextEdit
var reference: Button

func stage(field: LineEdit) -> bool:
	if sidebar.is_visible_in_tree():
		sidebar.close()
		await process_frame
	page.open()
	var tabs := page.get_parent() as TabContainer
	tabs.current_tab = tabs.get_tab_idx_from_control(page)
	await process_frame
	field.grab_focus()
	return await _invoke_workbench()

func send_field(field: LineEdit, name_of_field: String) -> bool:
	if not await stage(field): return false
	if not _check(reference.text.contains(name_of_field) and reference.text.contains(field.text), "Missing field preview: " + reference.text): return false
	input.text = "Read " + name_of_field
	var deadline := Time.get_ticks_msec() + 15000
	while send.disabled and Time.get_ticks_msec() < deadline: await create_timer(0.05).timeout
	send.pressed.emit()
	while (not input.text.is_empty() or not sidebar.find_child("Stop", true, false).disabled) and Time.get_ticks_msec() < deadline: await create_timer(0.05).timeout
	return _check(input.text.is_empty() and not reference.visible, "Field message did not finish")

func _run():
	root.size = Vector2i(1440, 1000)
	await create_timer(1).timeout
	var setup := root.find_child("GongGongRuntimeSetup", true, false) as Window
	if setup: setup.hide()
	chat = root.find_child("AI Chat", true, false)
	sidebar = root.find_child("AIWorkbenchSidebar", true, false)
	for dock in root.find_children("*", "EditorDock", true, false):
		if dock.title == "Project Brief": page = dock
	if not _check(page != null, "Missing registered Project Brief"): return
	summary = page.find_child("Summary", true, false)
	milestone = page.find_child("Milestone", true, false)
	private_note = page.find_child("PrivateNote", true, false)
	private_note.text = "LOCAL_ONLY_1793"
	input = root.find_child("ChatInput", true, false)
	send = root.find_child("Send", true, false)
	reference = root.find_child("WorkbenchReference", true, false)
	approval = root.find_child("AIFileApproval", true, false)
	var settings = chat.get_ai_settings_control()
	var backend = chat.find_child("AIBackend", true, false)
	backend.select(0)
	backend.item_selected.emit(0)
	settings.find_child("APIEndpoint", true, false).text = OS.get_environment("PAGE_TEST_ENDPOINT")
	var key = settings.find_child("APIKey", true, false)
	key.text = "u16-loopback"
	key.text_changed.emit(key.text)
	chat.find_child("APIModel", true, false).text = "fixture"
	if not await send_field(summary, "Brief/Summary"): return
	if OS.get_environment("U16_PACKAGE_PROBE") == "1":
		print("PACKAGE_PROBE_OK")
		quit()
		return
	if not await send_field(milestone, "Brief/Milestone"): return
	if not await stage(private_note): return
	if not _check(not reference.text.contains("LOCAL_ONLY") and reference.text.ends_with("可读范围：页面名、模块标识"), "Private field was staged"): return
	reference.pressed.emit()
	var before := summary.text
	summary.text = "fixture key " + key.text
	if not await stage(summary): return
	if not _check(reference.text.ends_with("可读范围：页面名、模块标识"), "Credential-bearing field was staged"): return
	reference.pressed.emit()
	summary.text = before
	if not await stage(summary): return
	page.title = "Retitled"
	input.text = "stale draft"
	send.pressed.emit()
	if not _check(reference.text.contains("失效") and input.text == "stale draft", "Renamed page draft sent"): return
	reference.pressed.emit()
	input.text = ""
	page.title = "Project Brief"
	var tools := root.find_child("AllowTools", true, false) as CheckBox
	var consultation := root.find_child("ConsultationOnly", true, false) as CheckBox
	var automatic := root.find_child("AutoExecuteCommands", true, false) as CheckBox
	tools.button_pressed = true
	automatic.button_pressed = true
	FileAccess.open("res://.godot/u16-ready", FileAccess.WRITE).store_string("ready")
	var sequence := 0
	while true:
		await create_timer(0.03).timeout
		var filename := "res://.godot/u16-command-%d" % sequence
		if not FileAccess.file_exists(filename): continue
		var action := FileAccess.get_file_as_string(filename)
		if action == "exit":
			quit()
			return
		if action == "development": consultation.button_pressed = false
		if action == "confirm":
			if not _check(approval.visible, "Missing approval dialog"): return
			approval.hide()
			approval.confirmed.emit()
		if action == "reject":
			if not _check(approval.visible, "Missing rejection dialog"): return
			approval.hide()
			approval.canceled.emit()
		if action == "change": summary.text = "User correction"
		if action == "unregister": page.remove_meta("workbench_fields")
		if action == "remove": page.close()
		if action == "restage":
			consultation.button_pressed = true
			if not await send_field(summary, "Brief/Summary"): return
			consultation.button_pressed = false
		var result := {"summary": summary.text, "milestone": milestone.text, "neighbor": private_note.text, "dialog": approval.visible, "saved": EditorInterface.get_editor_settings().get_project_metadata("project_brief", "summary", "First playable")}
		if approval.visible:
			result["preview"] = JSON.parse_string((approval.find_children("*", "TextEdit", true, false)[0] as TextEdit).text)
		FileAccess.open("res://.godot/u16-reply-%d" % sequence, FileAccess.WRITE).store_string(JSON.stringify(result))
		sequence += 1
