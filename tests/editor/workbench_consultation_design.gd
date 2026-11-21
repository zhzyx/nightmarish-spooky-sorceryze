extends SceneTree

var panel: Control


func _initialize() -> void:
	_run.call_deferred()


func _check(condition: bool, message: String) -> bool:
	if not condition:
		push_error(message)
		quit(1)
	return condition


func _idle() -> bool:
	var deadline := Time.get_ticks_msec() + 15000
	while panel.busy and Time.get_ticks_msec() < deadline:
		await process_frame
	return _check(not panel.busy, "Native workbench timed out")


func _run() -> void:
	for frame in 12:
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
	if not _check(results.get_selected() and results.get_selected().get_metadata(0) == search.text, "Workbench missing"):
		return
	results.item_activated.emit()
	await process_frame
	var sidebar := root.find_child("AIWorkbenchSidebar", true, false)
	panel = sidebar.find_child("WorkbenchBusinessModules", true, false)
	var deadline := Time.get_ticks_msec() + 15000
	while (not panel.managed_identity or panel.session.get_identity().is_empty()) and Time.get_ticks_msec() < deadline:
		await process_frame
	var picker := panel.get_node("BusinessModuleSelector") as OptionButton
	picker.item_selected.emit(1)
	if not await _idle():
		return
	var selected := -1
	for i in picker.item_count:
		if picker.get_item_metadata(i) == "default":
			selected = i
	if not _check(selected >= 1, "Module unavailable: " + panel.feedback.text):
		return
	picker.get_popup().hide()
	picker.item_selected.emit(selected)
	if not await _idle():
		return
	var fixture: Dictionary = JSON.parse_string(OS.get_environment("D03_FIXTURE"))
	var action := panel.find_child("ModuleDesignAction", true, false) as Button
	if not _check(action != null and action.is_visible_in_tree() and panel.history.text.contains(fixture.answer), "Consultation unavailable"):
		return
	action.pressed.emit()
	if fixture.has("document"):
		var docs := sidebar.find_child("WorkbenchDocuments", true, false)
		deadline = Time.get_ticks_msec() + 15000
		while docs.reference.is_empty() and Time.get_ticks_msec() < deadline:
			await process_frame
		if not _check(docs.visible and docs.reference.document_id == fixture.document and docs.reference.version == fixture.version and docs.body.text.count(fixture.handwritten) == 1 and docs.body.text.contains(fixture.edited), "Wrong linked document/revision"):
			return
		print("D03_NATIVE=", JSON.stringify({"source":panel.conversation.id, "document":docs.reference, "body":docs.body.text}))
		quit()
		return
	var dialog: AcceptDialog = panel.design
	var body := dialog.find_child("DesignDraftBody", true, false) as TextEdit
	var save := dialog.find_child("SaveDesignDraft", true, false) as Button
	var suggest := dialog.find_child("SuggestDesignDraft", true, false) as Button
	var status := dialog.find_child("DesignDraftStatus", true, false) as Label
	var source := dialog.find_child("DesignSource", true, false) as Label
	var latest := dialog.find_child("LatestDirectionBody", true, false) as TextEdit
	if not _check(dialog.visible and source.text.contains(fixture.id) and body.text == fixture.saved, "Wrong source or saved revision"):
		return
	body.text += "\n\n" + str(fixture.handwritten)
	suggest.pressed.emit()
	if not await _idle():
		return
	if not _check(body.editable and body.text == fixture.generated and panel.conversation.revisions.size() == 1, "Wrong suggestion: " + status.text + " / " + body.text):
		return
	body.text += "\n\n" + str(fixture.edited)
	save.pressed.emit()
	if not await _idle():
		return
	if not _check(latest.visible and latest.text == fixture.concurrent and body.text.ends_with(fixture.edited) and not save.disabled, "Conflict lost local draft or latest revision: " + status.text):
		return
	save.pressed.emit()
	if not await _idle():
		return
	if not _check(save.text == "读取最新修订" and not save.disabled and suggest.disabled and body.text.ends_with(fixture.edited), "Unknown result was not protected: " + status.text):
		return
	save.pressed.emit()
	if not await _idle():
		return
	if not _check(save.disabled and status.text.contains("已读回相同正文") and panel._direction().body == body.text, "Committed revision not recovered: " + status.text):
		return
	var saved := body.text
	dialog.get_ok_button().pressed.emit()
	await process_frame
	if not _check(not dialog.visible, "Close did not dismiss the draft"):
		return
	action.pressed.emit()
	if not _check(dialog.visible and body.text == saved and source.text.contains(fixture.id), "Saved draft did not reopen"):
		return
	print("D03_NATIVE=", JSON.stringify({"source":source.text, "revision":panel._direction().revision, "body":saved}))
	quit()
