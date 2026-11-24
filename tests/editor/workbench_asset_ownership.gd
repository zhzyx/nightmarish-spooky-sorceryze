extends SceneTree

var panel
var assets
var dialog: ConfirmationDialog
var choices: OptionButton
var fixture: Dictionary
var trace := {}


func _initialize() -> void:
	_run.call_deferred()


func _wait(check: Callable, label: String) -> bool:
	var deadline := Time.get_ticks_msec() + 15000
	while not check.call() and Time.get_ticks_msec() < deadline:
		await process_frame
	if not check.call():
		var detail := str(assets.notice.text) if assets else ""
		push_error(label + " " + detail)
		quit(1)
		return false
	return true


func _check(ok: bool, label: String) -> bool:
	if not ok:
		push_error(label)
		quit(1)
	return ok


func _lookup(path: String) -> bool:
	assets.get_node("OpenStandaloneAsset").pressed.emit()
	assets.source.text = fixture.source_module
	assets.revision.text = fixture.revision
	assets.path.text = path
	assets.lookup.pressed.emit()
	return await _wait(func(): return choices.visible and choices.item_count >= 2, "Asset lookup")


func _confirm() -> bool:
	dialog.get_ok_button().pressed.emit()
	return await _wait(func(): return not panel.busy and not dialog.visible, "Asset confirmation")


func _send() -> bool:
	panel.send.pressed.emit()
	return await _wait(func(): return not panel.busy and panel.composer.text.is_empty(), "Explicit send")


func _run() -> void:
	fixture = JSON.parse_string(OS.get_environment("C07_FIXTURE"))
	for i in 12:
		await process_frame
	var palette := EditorInterface.get_command_palette()
	var shortcut := InputEventShortcut.new()
	shortcut.shortcut = EditorInterface.get_editor_settings().get_shortcut("editor/command_palette")
	root.push_input(shortcut)
	await process_frame
	var search := palette.find_children("*", "LineEdit", true, false)[0] as LineEdit
	var results := palette.find_children("*", "Tree", true, false)[0] as Tree
	search.text = "editor/open_ai_workbench"
	search.text_changed.emit(search.text)
	if not _check(results.get_selected() and results.get_selected().get_metadata(0) == search.text, "Workbench command"):
		return
	results.item_activated.emit()
	await process_frame
	var side := root.find_child("AIWorkbenchSidebar", true, false)
	panel = side.find_child("WorkbenchBusinessModules", true, false)
	assets = side.find_child("WorkbenchAssetPicker", true, false)
	if not _check(panel and assets and assets.is_visible_in_tree(), "Mounted native asset picker"):
		return
	if not await _wait(func(): return panel._authenticated(), "Verified host identity"):
		return
	dialog = assets.dialog
	choices = assets.choices
	var local := side.find_child("ChatInput", true, false) as TextEdit
	local.text = "Original draft"
	assets.get_node("OpenStandaloneAsset").pressed.emit()
	assets.source.text = fixture.source_module
	assets.revision.text = fixture.revision
	assets.path.text = "delayed.glb"
	assets.lookup.pressed.emit()
	var sync := OS.get_environment("C07_SYNC")
	if not await _wait(func(): return FileAccess.file_exists(sync.path_join("read-started")), "Expected HTTP read in flight"):
		return
	dialog.get_cancel_button().pressed.emit()
	var release := FileAccess.open(sync.path_join("release-read"), FileAccess.WRITE)
	release.close()
	var read_finished := func() -> bool:
		if dialog.visible or not FileAccess.file_exists(sync.path_join("read-released")):
			return false
		if panel.session:
			return panel.session.find_children("*", "HTTPRequest", false, false).is_empty()
		return panel.http.get_http_client_status() == HTTPClient.STATUS_DISCONNECTED
	if not await _wait(read_finished, "Dismissed pending lookup"):
		return
	for frame in 8:
		await process_frame
	if not _check(assets.selected_asset.is_empty() and local.text == "Original draft", "Canceled lookup repopulated draft"):
		return
	trace.canceled_in_flight = true
	if not await _lookup(fixture.free):
		return
	if not _check(choices.item_count == 2 and choices.selected == 1 and panel.module_id == "", "Unowned reference-only"):
		return
	if not await _confirm():
		return
	var local_draft := local.text
	if not _check(local_draft.begins_with("Original draft\n<duobao://") and local_draft.contains(str(fixture.free).uri_encode()) and panel.module_id == "", "Unowned reference reached local draft"):
		return
	trace.unowned = local_draft

	if not await _lookup(fixture.path):
		return
	if not _check(choices.item_count == 4 and choices.selected == 0 and dialog.get_ok_button().disabled, "Multiple owners require a choice"):
		return
	trace.owners = [choices.get_item_metadata(2), choices.get_item_metadata(3)]
	if not _check(trace.owners.has(fixture.modules[0]) and trace.owners.has(fixture.modules[1]) and choices.get_item_text(2) != choices.get_item_text(3), "Distinct same-name owners"):
		return
	dialog.get_cancel_button().pressed.emit()
	if not await _wait(func(): return not dialog.visible, "Cancel dismissed dialog"):
		return
	if not _check(not dialog.visible and local.text == local_draft and panel.module_id == "", "Cancel altered the conversation"):
		return
	trace.cancel_preserved_draft = true
	await assets.open_standalone_asset(fixture)
	if not _check(dialog.visible and choices.item_count == 4 and choices.selected == 0 and assets.path.text == fixture.path, "Opened native object entry"):
		return
	choices.select(1)
	choices.item_selected.emit(1)
	if not await _confirm():
		return
	if not _check(panel.module_id == "" and local.text.begins_with(local_draft) and local.text.contains(str(fixture.path).uri_encode()), "Shared reference changed ownership"):
		return
	trace.shared_reference_only = true
	local_draft = local.text
	if not await _lookup(fixture.path):
		return
	var index := 2 if choices.get_item_metadata(2) == fixture.modules[1] else 3
	choices.select(index)
	choices.item_selected.emit(index)
	if not await _confirm():
		return
	var module_draft: String = panel.composer.text
	if not _check(panel.module_id == fixture.modules[1] and panel.location.issue_id == null and module_draft.contains(str(fixture.path).uri_encode()) and local.text == local_draft, "Explicit module did not receive draft"):
		return
	if not await _send():
		return
	trace.selected_module = panel.module_id
	trace.module_conversation = panel.location.conversation_id

	var issues := panel.issues as OptionButton
	var idx := -1
	for i in issues.item_count:
		if issues.get_item_metadata(i) == fixture.issue:
			idx = i
	if not _check(idx > 0, "Expected existing issue"):
		return
	issues.select(idx)
	issues.item_selected.emit(idx)
	if not await _wait(func(): return not panel.busy and panel.location.get("issue_id") == fixture.issue, "Issue selection"):
		return
	if not _check(assets.issue_button.is_visible_in_tree(), "No issue entry"):
		return
	assets.issue_button.pressed.emit()
	if not await _wait(func(): return assets.issue_assets.item_count == 2, "Issue assets"):
		return
	assets.issue_assets.select(1)
	assets.issue_assets.item_selected.emit(1)
	if not await _wait(func(): return not dialog.get_ok_button().disabled, "Inherit issue owner"):
		return
	if not _check(not choices.visible and panel.location.issue_id == fixture.issue, "Issue wrongly prompted for owner"):
		return
	if not await _confirm():
		return
	if not _check(panel.module_id == fixture.modules[1] and panel.location.issue_id == fixture.issue and panel.composer.text == module_draft, "Issue draft changed provenance"):
		return
	if not await _send():
		return
	trace.inherited_issue = panel.location.issue_id
	trace.conversation = panel.location.conversation_id
	print("C07_NATIVE=" + JSON.stringify(trace))
	quit()
