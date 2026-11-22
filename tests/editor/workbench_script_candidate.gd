extends "res://changes.gd"

func verify_reopened_script(expected: String) -> void:
	EditorInterface.set_main_screen_editor("Script")
	var script := load("res://actor.gd") as GDScript
	EditorInterface.edit_script(script)
	await process_frame
	var code := EditorInterface.get_script_editor().get_current_editor().get_base_editor() as CodeEdit
	var saved := FileAccess.get_sha256("res://actor.gd")
	if not require(saved == expected and code.text == FileAccess.get_file_as_string("res://actor.gd"), "Reopened script differs from saved revision"):
		return
	print("SCRIPT_REOPEN=", JSON.stringify({"saved":saved, "play":script.call("play"), "line":code.get_line(5)}))
	quit()

func run() -> void:
	await create_timer(0.8).timeout
	var expected := OS.get_environment("WORKBENCH_SCRIPT_REOPEN")
	if not expected.is_empty():
		await verify_reopened_script(expected)
		return
	await open_sidebar()
	sidebar = root.find_child("AIWorkbenchSidebar",true,false)
	panel = sidebar.find_child("WorkbenchBusinessModules",true,false)
	var session = sidebar.find_child("WorkbenchBusinessSession",true,false)
	var until := Time.get_ticks_msec() + 15000
	while session.get_identity().is_empty() and Time.get_ticks_msec() < until:
		await process_frame
	if not require(await choose(panel,1), "Modules unavailable"):
		return
	var index := -1
	for i in panel.picker.item_count:
		if panel.picker.get_item_metadata(i) == "default":
			index = i
	if not require(await choose(panel,index), "Default module unavailable"):
		return
	panel.continue_work.button_pressed = true
	sidebar.close()
	EditorInterface.set_main_screen_editor("Script")
	var editor := EditorInterface.get_script_editor()
	EditorInterface.edit_script(load("res://actor.gd"))
	await process_frame
	var code := editor.get_current_editor().get_base_editor() as CodeEdit
	code.grab_focus()
	code.select(5,1,5,code.get_line(5).length())
	await open_sidebar()
	if (await send_turn("固定当前调用点，然后继续。")).is_empty():
		return
	code.deselect()
	code.set_line(2,"static func score(points: int, bonus: int = 3) -> int:")
	editor.save_current_script()
	var manual := FileAccess.get_sha256("res://actor.gd")
	var manual_source := code.text
	if (await send_turn("更新调用点，显式传入 bonus=7。保留人工签名。")).is_empty():
		return
	var review = panel.find_child("ReviewScriptCandidate",true,false)
	if not require(review.is_visible_in_tree(), "Bound suggestion unavailable: " + str(panel.conversation.turns[-1])):
		return
	review.pressed.emit()
	if not require(review.dialog.visible and not review.dialog.get_ok_button().disabled, "Diff unavailable: " + review.status.text):
		return
	var diff: String = review.diff.text
	code.set_line(5,"\treturn score(99)")
	review.dialog.confirmed.emit()
	if not require(review.dialog.get_ok_button().disabled and code.get_line(5) == "\treturn score(99)" and FileAccess.get_sha256("res://actor.gd") == manual, "Concurrent edit was overwritten"):
		return
	review.dialog.hide()
	var selected_line := "\treturn score(2, 7)"
	if OS.get_environment("WORKBENCH_SCRIPT_CASE") == "same_line":
		selected_line = "\treturn score(99)"
		editor.save_current_script()
		review.pressed.emit()
		if not require(review.dialog.visible and review.dialog.get_ok_button().disabled, "Stale diff offered for the saved conflicting line"):
			return
		review.dialog.hide()
	else:
		code.set_line(5,"\treturn score(2)")
		review.pressed.emit()
		if not require(not review.dialog.get_ok_button().disabled, "Reopened preview missing"):
			return
		review.dialog.confirmed.emit()
	await process_frame
	var saved := FileAccess.get_file_as_string("res://actor.gd")
	if not require(not review.dialog.visible and saved == manual_source.replace("\treturn score(2)", selected_line) and saved == code.text, "Native save lost edits: " + saved):
		return
	print("SCRIPT_CANDIDATE=", JSON.stringify({"manual":manual,"candidate":FileAccess.get_sha256("res://actor.gd"),"diff":diff,"signature":code.get_line(2),"conflict_rejected":true,"display_driver":DisplayServer.get_name()}))
	quit()
