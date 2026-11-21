extends "res://module_probe.gd"

const CONSULT := "D12 consult once"
const ANSWER := "D12 fixture answer"
var fixture: Array
var rows: VBoxContainer
var observed: Array = []


func attach_file(i: int) -> void:
	var path := "res://module%d.tres" % i
	EditorInterface.inspect_object(load(path))
	await process_frame
	var sidebar := root.find_child("AIWorkbenchSidebar", true, false)
	sidebar.make_visible()
	var menu := sidebar.find_child("WorkbenchResourceSelection", true, false) as MenuButton
	menu.get_popup().id_pressed.emit(0)


func wait_idle() -> bool:
	var deadline := Time.get_ticks_msec() + 15000
	while panel.busy and Time.get_ticks_msec() < deadline:
		await process_frame
	if panel.busy or not panel.feedback.text.is_empty():
		_fail("Business request failed: " + panel.feedback.text)
		return false
	return true


func verify(i: int, expected: String, reference: bool, count: int) -> bool:
	var item: Dictionary = fixture[i]
	var paths := []
	for row in rows.get_children():
		paths.append(row.text)
	var turns: Array = panel.conversation.get("turns", [])
	observed.append({"module": panel.module_id, "issue": panel.location.issue_id,
		"conversation": panel.location.conversation_id, "draft": panel.composer.text,
		"references": paths, "turns": turns.size(), "reply_visible": ANSWER in panel.history.text})
	if panel.module_id != item.module or panel.location.issue_id != item.issue or panel.composer.text != expected or turns.size() != count:
		_fail("Incorrect work order, composer or turn count: " + str(observed.back()))
		return false
	var file := "res://module%d.tres" % i
	if paths.size() != int(reference) or (reference and (file not in paths[0] or FileAccess.get_sha256(file) not in paths[0] or "已失效" in paths[0])):
		_fail("Incorrect file reference: " + str(paths))
		return false
	if count and (panel.history.text.count(CONSULT) != 1 or panel.history.text.count(ANSWER) != 1):
		_fail("Sent message or reply is missing or duplicated")
		return false
	return true


func _run() -> void:
	create_timer(35.0).timeout.connect(func(): _fail("D12 probe timed out during " + OS.get_environment("D12_PHASE")))
	root.size = Vector2i(1440, 900)
	await create_timer(0.7).timeout
	var palette := EditorInterface.get_command_palette()
	palette.popup_centered()
	await process_frame
	var search: LineEdit = palette.find_children("*", "LineEdit", true, false).front()
	var result: Tree = palette.find_children("*", "Tree", true, false).front()
	search.text = "editor/open_ai_workbench"
	search.text_changed.emit(search.text)
	result.item_activated.emit()
	await process_frame
	var sidebar := root.find_child("AIWorkbenchSidebar", true, false)
	panel = sidebar.find_child("WorkbenchBusinessModules", true, false)
	if not panel:
		_fail("Compiled module selector unavailable")
		return
	var session := sidebar.find_child("WorkbenchBusinessSession", true, false)
	var until := Time.get_ticks_msec() + 15000
	while session.get_identity().is_empty() and Time.get_ticks_msec() < until:
		await process_frame
	picker = panel.picker
	rows = sidebar.find_child("WorkbenchReferenceRows", true, false)
	fixture = JSON.parse_string(OS.get_environment("D12_MODULES"))
	var asset: Dictionary = JSON.parse_string(OS.get_environment("D12_ASSET"))
	var locator := "<duobao://%s/%s/%s>" % [asset.source_module, asset.revision, str(asset.path).uri_encode()]
	var asset_draft := "draft B\n" + locator
	var phase := OS.get_environment("D12_PHASE")
	if not await _choose(1):
		return
	if phase == "write" or phase == "other-project":
		if not await _choose(_index("default")):
			return
		if phase == "other-project":
			if panel.composer.text != "" or rows.get_child_count() or not panel.conversation.is_empty():
				_fail("Shared default module leaked a draft across projects")
				return
			print("D12_OBSERVED=" + JSON.stringify({"pid": OS.get_process_id(), "phase": phase, "empty_default": true}))
			root.propagate_notification(Node.NOTIFICATION_WM_CLOSE_REQUEST)
			return
		panel.composer.insert_text_at_caret("private default in first project")
	if not await _choose(_index(fixture[0].module)):
		return
	if phase == "write":
		if not verify(0, "", false, 0):
			return
		await attach_file(0)
		panel.composer.insert_text_at_caret(CONSULT)
		panel.send.pressed.emit()
		if not await wait_idle() or not verify(0, "", false, 1):
			return
		panel.composer.insert_text_at_caret("draft A " + OS.get_environment("TIANXUAN_TOKEN"))
		await attach_file(0)
		var original: int = panel.issues.selected
		panel.issues.select(0)
		panel.issues.item_selected.emit(0)
		if not await wait_idle():
			return
		if panel.composer.text != "" or rows.get_child_count() or not panel.conversation.is_empty():
			_fail("A different issue exposed the previous issue's draft, history or refs")
			return
		panel.issues.select(original)
		panel.issues.item_selected.emit(original)
		if not await wait_idle() or not verify(0, "draft A [REDACTED]", true, 1):
			return
		if not await _choose(_index(fixture[1].module)):
			return
		panel.composer.insert_text_at_caret("draft B")
		panel.stage_asset_reference(asset)
		await attach_file(1)
		if not verify(1, asset_draft, true, 0):
			return
	elif phase == "reopen" or phase == "cleared":
		if not verify(0, "draft A [REDACTED]", true, 1):
			return
		if not await _choose(_index(fixture[1].module)):
			return
		if phase == "reopen":
			if not verify(1, asset_draft, true, 0):
				return
			var assets: Array = panel._asset_references(panel._draft_key(panel.location.issue_id), panel.composer.text)
			if assets != [{"kind": "editor", "object_id": "duobao:" + str(asset.asset_id), "revision": asset.revision}]:
				_fail("Reopened asset locator lost its immutable reference")
				return
			rows.get_child(0).pressed.emit()
			panel.composer.clear()
		if not verify(1, "", false, 0):
			return
		if phase == "cleared":
			if not await _choose(_index(fixture[0].module)):
				return
			session.find_child("SignOut", true, false).pressed.emit()
			panel.composer.undo()
			if not session.get_identity().is_empty() or panel.composer.text != "" or rows.get_child_count() or panel.history.text != "":
				_fail("Signout did not release private data or undo history")
				return
	else:
		if not verify(0, "", false, 0):
			return
	print("D12_OBSERVED=" + JSON.stringify({"pid": OS.get_process_id(), "phase": phase, "controls": observed}))
	root.propagate_notification(Node.NOTIFICATION_WM_CLOSE_REQUEST)
