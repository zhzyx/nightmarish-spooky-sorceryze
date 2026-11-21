extends "res://editor_probe.gd"

var picker_panel
var assets
var fixture: Dictionary
var ownership: Array = []
var drafts: Array = []


func _wait(check: Callable, description: String) -> bool:
	var deadline := Time.get_ticks_msec() + 12000
	while not check.call() and Time.get_ticks_msec() < deadline:
		await process_frame
	return _check(check.call(), description)


func _pick_owner(module: String, selected_path: String) -> bool:
	assets.get_node("OpenStandaloneAsset").pressed.emit()
	assets.source.text = fixture.asset.source_module
	assets.revision.text = fixture.asset.revision
	assets.path.text = selected_path
	assets.lookup.pressed.emit()
	var choices: OptionButton = assets.choices
	if not await _wait(func(): return choices.visible and choices.item_count == 4, "Missing both shared asset owners"):
		return false
	var ids := [choices.get_item_metadata(2), choices.get_item_metadata(3)]
	if not _check(ids.has(fixture.modules[0]) and ids.has(fixture.modules[1]) and choices.selected == 0 and assets.dialog.get_ok_button().disabled, "Ambiguous asset was resolved without a choice"):
		return false
	var before: String = picker_panel.module_id
	var index := ids.find(module) + 2
	choices.select(index)
	choices.item_selected.emit(index)
	assets.dialog.get_ok_button().pressed.emit()
	if not await _wait(func(): return not picker_panel.busy and not assets.dialog.visible, "Could not confirm asset owner"):
		return false
	ownership.append({"offered": ids, "before": before, "chosen": picker_panel.module_id, "issue": picker_panel.location.issue_id})
	return _check(picker_panel.module_id == module and picker_panel.location.issue_id == null, "Wrong destination")


func _switch_to_owner(module: String) -> bool:
	var picker: OptionButton = picker_panel.picker
	for index in picker.item_count:
		if picker.get_item_metadata(index) == module:
			picker.select(index)
			picker.item_selected.emit(index)
			return await _wait(func(): return not picker_panel.busy and picker_panel.module_id == module, "Switch " + module)
	return _check(false, "Module missing from visible selector")


func _read_draft(expected: String, turns: int) -> bool:
	var actual := {
		"module": picker_panel.module_id, "draft": picker_panel.composer.text,
		"turns": picker_panel.conversation.get("turns", []).size(),
		"reply_visible": fixture.answer in picker_panel.history.text,
	}
	drafts.append(actual)
	return _check(actual.draft == expected and actual.turns == turns and actual.reply_visible == (turns > 0),
			"Unexpected module draft/history: " + str(actual))


func _run() -> void:
	root.size = Vector2i(1440, 900)
	await create_timer(0.8).timeout
	fixture = JSON.parse_string(OS.get_environment("K01_FIXTURE"))
	EditorInterface.set_main_screen_editor("Script")
	EditorInterface.edit_script(load("res://character.gd"))
	await _settle_layout()
	var code := EditorInterface.get_script_editor().get_current_editor().get_base_editor() as CodeEdit
	# The temporary editor copy has no host runtime. Dismiss the first-run setup window.
	var setup := root.find_child("GongGongRuntimeSetup", true, false) as ConfirmationDialog
	if setup:
		setup.hide()
	code.grab_focus()
	var tab_mode := code.tab_input_mode
	var toggle := _shortcut_key(KEY_M)
	toggle.ctrl_pressed = true
	_send_shortcut(toggle)
	if not _check(code.tab_input_mode != tab_mode, "Ctrl+M did not toggle Tab input in CodeEdit"):
		return
	_send_shortcut(toggle)
	code.set_caret_line(1)
	code.set_caret_column(3)
	_send_shortcut(_shortcut_key(KEY_RIGHT, false, true))
	if not _check(code.tab_input_mode == tab_mode and code.get_selected_text() == "m", "Ctrl+M restore or Shift+Right selection failed"):
		return
	code.select(1, 3, 1, code.get_line(1).length())
	var before := _selection_state(code)
	var viewport := code.get_viewport()
	var original_text := code.text
	if not _check(before.text == fixture.asset.path and code.has_focus(), "Missing original editing selection"):
		return
	if fixture.entry == "shortcut":
		_send_shortcut(_shortcut_key(KEY_M, true, true))
	elif not await _invoke_workbench():
		return
	await _settle_layout()
	var sidebar := root.find_child("AIWorkbenchSidebar", true, false) as EditorDock
	var local := sidebar.find_child("ChatInput", true, false) as TextEdit
	if not _check(sidebar.is_visible_in_tree() and local != null and local.has_focus() and code.tab_input_mode == tab_mode,
			"Workbench from CodeEdit: entry=%s sidebar=%s tab_mode_before=%s tab_mode_after=%s" % [fixture.entry, sidebar.is_visible_in_tree(), tab_mode, code.tab_input_mode]):
		return
	picker_panel = sidebar.find_child("WorkbenchBusinessModules", true, false)
	assets = sidebar.find_child("WorkbenchAssetPicker", true, false)
	if not await _wait(func(): return picker_panel._authenticated(), "Verified Tianxuan account"):
		return
	var locator := "<duobao://%s/%s/%s>" % [fixture.asset.source_module, fixture.asset.revision, str(fixture.asset.path).uri_encode()]
	if not await _pick_owner(fixture.modules[0], before.text) or not _read_draft(locator, 0):
		return
	picker_panel.composer.insert_text_at_caret("\nK01 shared model consultation")
	var sent: String = picker_panel.composer.text
	picker_panel.send.pressed.emit()
	if not await _wait(func(): return not picker_panel.busy and picker_panel.composer.text.is_empty(), "Explicit module consultation"):
		return
	var conversation: String = picker_panel.location.conversation_id
	picker_panel.composer.insert_text_at_caret("movement pending")
	if not await _pick_owner(fixture.modules[1], before.text) or not _read_draft(locator, 0):
		return
	picker_panel.composer.insert_text_at_caret("\nanimation pending")
	if not await _switch_to_owner(fixture.modules[0]) or not _read_draft("movement pending", 1):
		return
	if not await _switch_to_owner(fixture.modules[1]) or not _read_draft(locator + "\nanimation pending", 0):
		return
	sidebar.find_child("ExpandWorkbench", true, false).pressed.emit()
	await _settle_layout()
	var restore := root.find_child("RestoreWorkbenchSidebar", true, false) as Button
	if not _check(restore.is_visible_in_tree() and picker_panel.composer.has_focus(), "Module composer did not open in full view"):
		return
	restore.pressed.emit()
	await _settle_layout()
	if not _check(sidebar.is_visible_in_tree() and sidebar.is_ancestor_of(picker_panel.composer) and picker_panel.composer.has_focus(), "Module composer did not return to sidebar"):
		return
	sidebar.find_child("CloseWorkbench", true, false).pressed.emit()
	await _settle_layout()
	var restored := EditorInterface.get_script_editor().get_current_editor().get_base_editor() as CodeEdit
	var after := _selection_state(restored)
	if not _check(not sidebar.is_visible_in_tree() and restored == code and restored.get_viewport() == viewport and restored.has_focus() and after == before and restored.text == original_text, "Script viewport, focus or buffer changed"):
		return
	_key(KEY_X, 120)
	if not _check(restored.get_line(1) == "## x", "Original viewport did not receive the next edit"):
		return
	var next_edit := restored.get_line(1)
	restored.undo()
	if not _check(restored.text == original_text, "Undo did not restore the source text"):
		return
	print("K01_RESULT=" + JSON.stringify({"pid": OS.get_process_id(), "editor_version": Engine.get_version_info().string,
		"script": "res://character.gd", "entry": "editor/open_ai_workbench", "viewport": viewport.get_instance_id(),
		"before_control": code.get_instance_id(), "after_control": restored.get_instance_id(),
		"before_selection": before, "after_selection": after, "next_edit": next_edit,
		"ctrl_m_toggled_and_restored": true, "shift_right_selected": "m", "tab_mode_after_entry": tab_mode,
		"ownership": ownership, "drafts": drafts, "conversation": conversation, "sent": sent}))
	root.propagate_notification(Node.NOTIFICATION_WM_CLOSE_REQUEST)
