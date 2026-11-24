extends RefCounted

# Use the editor command against each actual script tab. The business module stays selected.
static func attach(tree: SceneTree, folder: String) -> Dictionary:
	var sidebar := tree.root.find_child("AIWorkbenchSidebar", true, false)
	sidebar.close()
	await tree.process_frame
	var path := "res://%s/same.gd" % folder
	EditorInterface.set_main_screen_editor("Script")
	EditorInterface.edit_script(load(path))
	await tree.process_frame
	var code := EditorInterface.get_script_editor().get_current_editor().get_base_editor() as CodeEdit
	code.grab_focus()
	code.select(1, 0, 1, code.get_line(1).length())
	var ref := {"kind": "editor", "object_id": path + "#L2:1-L2:" + str(code.get_line(1).length() + 1),
		"revision": code.text.sha256_text()}
	var palette := EditorInterface.get_command_palette()
	palette.popup_centered()
	await tree.process_frame
	var search: LineEdit = palette.find_children("*", "LineEdit", true, false).front()
	var results: Tree = palette.find_children("*", "Tree", true, false).front()
	search.text = "editor/open_ai_workbench"
	search.text_changed.emit(search.text)
	results.item_activated.emit()
	await tree.process_frame
	return ref


static func send_turn(tree, input: TextEdit, message: String) -> bool:
	input.text = message
	tree.panel.find_child("ModuleSend", true, false).pressed.emit()
	var until := Time.get_ticks_msec() + 20000
	while tree.picker.disabled and Time.get_ticks_msec() < until:
		await tree.process_frame
	if input.text != "" or tree.picker.disabled:
		tree._fail("Explicit module send failed: " + tree.panel.feedback.text)
		return false
	return true


static func exercise(tree, fixture: Array) -> void:
	tree.root.size = Vector2i(1440, 900)
	var panel: Control = tree.panel
	var input := panel.find_child("ModuleChatInput", true, false) as TextEdit
	var context := panel.find_child("WorkbenchContext", true, false) as Label
	var rows := panel.find_child("WorkbenchReferenceRows", true, false) as VBoxContainer
	var issue := panel.find_child("ModuleIssue", true, false) as OptionButton
	var issue_id: String = issue.get_item_metadata(issue.selected)
	var original := context.text
	if issue_id != fixture[0].issue_id or fixture[0].module_id not in original or issue.get_item_text(issue.selected) not in original:
		tree._fail("Incorrect business context above module input")
		return
	var config = tree.root.find_child("AI Chat", true, false).get_ai_settings_control()
	var key := config.find_child("APIKey", true, false) as LineEdit
	key.text = "u15-business-fixture"
	key.text_changed.emit(key.text)
	var chat = tree.root.find_child("AI Chat", true, false)
	EditorInterface.open_scene_from_path("res://retained.tscn")
	await tree.process_frame
	var manual_node := EditorInterface.get_edited_scene_root()
	var manual := {"kind": "editor", "object_id": "res://retained.tscn#.",
		"revision": FileAccess.get_sha256("res://retained.tscn")}
	if chat.stage_workbench_reference(panel, manual_node) != "" or rows.get_child_count() != 1:
		tree._fail("Explicit retained reference was not staged in its business scope")
		return
	var retained_text: String = rows.get_child(0).text
	input.text = "keep beta"
	var current := panel.find_child("WorkbenchCurrentContext", true, false) as Label
	var selected := [await attach(tree, "alpha"), await attach(tree, "beta")]
	if not current.is_visible_in_tree() or not rows.is_visible_in_tree() or rows.get_child_count() != 1 or not input.is_visible_in_tree():
		tree._fail("Current selection and retained reference were not shown separately")
		return
	var row_bounds := rows.get_global_rect()
	var input_bounds := input.get_global_rect()
	if row_bounds.position.y >= input_bounds.position.y or current.get_global_rect().position.y >= input_bounds.position.y:
		tree._fail("References are not above the module composer")
		return
	var current_beta := current.tooltip_text
	if selected[1].object_id not in current_beta or "alpha" in current_beta or current_beta.count("[REDACTED]") != 2:
		tree._fail("Current script locator or redaction is wrong: " + JSON.stringify({
			"current_locator_present": selected[1].object_id in current_beta,
			"old_locator_present": "alpha" in current_beta,
			"redaction_count": current_beta.count("[REDACTED]")}))
		return
	if rows.get_child(0).text != retained_text or manual.object_id not in retained_text or manual.revision not in retained_text or input.text != "keep beta":
		tree._fail("Updating current selection changed the retained reference or draft")
		return
	rows.get_child(0).pressed.emit()
	var remaining := current.tooltip_text
	if rows.get_child_count() != 0 or remaining != current_beta or context.text != original or input.text != "keep beta" or issue.get_item_metadata(issue.selected) != issue_id:
		tree._fail("Removing a retained reference changed current selection, draft or work order")
		return
	if not await send_turn(tree, input, "keep beta"):
		return
	if rows.is_visible_in_tree() or context.text != original or issue.get_item_metadata(issue.selected) != issue_id:
		tree._fail("Sending changed the issue or left retained references in the composer")
		return
	await attach(tree, "alpha")
	if chat.stage_workbench_reference(panel, manual_node) != "" or rows.get_child_count() != 1:
		tree._fail("Missing pre-switch retained reference")
		return
	var prev := issue.selected
	if not await tree._choose_work_order(issue, 0):
		return
	if rows.get_child_count() != 0:
		tree._fail("Issue switch retained another issue's manual selection")
		return
	if not await tree._choose_work_order(issue, prev):
		return
	if rows.get_child_count() != 1 or manual.object_id not in rows.get_child(0).text or manual.revision not in rows.get_child(0).text:
		tree._fail("Returning to the original issue did not restore its retained reference")
		return
	if not await tree._choose(tree._index(fixture[1].module_id)):
		return
	if rows.get_child_count() != 0 or not input.text.is_empty() or issue.get_item_metadata(issue.selected) != fixture[1].issue_id:
		tree._fail("New module retained the old draft or manual reference")
		return
	await attach(tree, "alpha")
	if selected[0].object_id not in current.tooltip_text:
		tree._fail("The new module did not capture the actual current selection")
		return
	if not await send_turn(tree, input, "module B uses current alpha"):
		return
	await attach(tree, "beta")
	var session: Node = tree.root.find_child("WorkbenchBusinessSession", true, false)
	session.find_child("SignOut", true, false).pressed.emit()
	if rows.get_child_count() != 0 or fixture[1].module_id in context.text or panel.content.visible or not panel.module_id.is_empty():
		tree._fail("Signing out retained business context")
		return
	session.find_child("ChooseAccount", true, false).pressed.emit()
	session.find_child("AccountEmail", true, false).text = "reviewer@example.invalid"
	session.find_child("AccountSecret", true, false).text = OS.get_environment("C06_SECOND_PASSWORD")
	session.find_child("BusinessProject", true, false).text = "c06/other"
	session.find_child("Authenticate", true, false).pressed.emit()
	var until := Time.get_ticks_msec() + 15000
	while session.get_identity().get("id", "") != OS.get_environment("C06_SECOND_ID") and Time.get_ticks_msec() < until:
		await tree.process_frame
	if panel.project != "c06/other" or session.get_identity().get("id", "") != OS.get_environment("C06_SECOND_ID"):
		tree._fail("The second test account or project did not activate")
		return
	if not await tree._choose(1) or not await tree._choose(tree._index("default")):
		return
	if rows.get_child_count() != 0 or not panel.history.text.is_empty() or not input.text.is_empty() or issue.get_item_metadata(issue.selected) != null:
		tree._fail("Another account/project inherited the original work order, history, draft or selections")
		return
	print("U15_BUSINESS=" + JSON.stringify({"selected": selected, "retained": manual, "before": retained_text, "after": remaining,
		"module": fixture[0].module_id, "issue_id": issue_id, "context_before_and_after": original,
		"rows_rect": str(row_bounds), "input_rect": str(input_bounds), "second_account_project": panel.project,
		"issue_switch_cleared": true, "module_switch_cleared": true, "logout_cleared": true,
		"automatic_latest_only": true, "manual_preserved_until_explicit_removal": true}))
	tree.quit()
