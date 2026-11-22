@tool
extends "res://base.gd"

var sidebar
var panel

func require(ok: bool, message: String) -> bool:
	if not ok:
		push_error(message)
		quit(1)
	return ok

func open_sidebar() -> void:
	var palette := EditorInterface.get_command_palette()
	palette.popup_centered()
	await process_frame
	var search: LineEdit = palette.find_children("*", "LineEdit", true, false)[0]
	search.text = "editor/open_ai_workbench"
	search.text_changed.emit(search.text)
	palette.find_children("*", "Tree", true, false)[0].item_activated.emit()
	await process_frame

func send_turn(text: String) -> Dictionary:
	var count: int = panel.conversation.get("turns", []).size()
	panel.composer.text = text
	panel.send.pressed.emit()
	var until := Time.get_ticks_msec() + 15000
	while panel.busy and Time.get_ticks_msec() < until:
		await process_frame
	if not require(panel.conversation.get("turns", []).size() == count + 1, "Turn missing: " + panel.feedback.text):
		return {}
	return panel.conversation.turns[-1]

func run() -> void:
	await create_timer(0.8).timeout
	await open_sidebar()
	sidebar = root.find_child("AIWorkbenchSidebar", true, false)
	panel = sidebar.find_child("WorkbenchBusinessModules", true, false)
	var session = sidebar.find_child("WorkbenchBusinessSession", true, false)
	var until := Time.get_ticks_msec() + 15000
	while session.get_identity().is_empty() and Time.get_ticks_msec() < until:
		await process_frame
	if not require(await choose(panel,1), "Could not load modules"):
		return
	var idx := -1
	for i in panel.picker.item_count:
		if panel.picker.get_item_metadata(i) == "default":
			idx = i
	if not require(await choose(panel,idx), "Default module unavailable"):
		return
	var invalid: Dictionary = panel.saved_changes.dependencies("res://broken.tres")
	if not require(invalid.has("res://absent.png") and invalid["res://absent.png"] == null and invalid.has("res://redirect.png") and invalid["res://redirect.png"] == null, "Unavailable dependency recorded as an actual version"):
		return
	if OS.get_environment("SAVE_PHASE") == "reopen":
		EditorInterface.open_scene_from_path("res://level.tscn")
		await create_timer(0.3).timeout
		var actor := EditorInterface.get_edited_scene_root().get_node("Actor") as Sprite2D
		if not require(is_equal_approx(actor.position.x, 37.5), "Reopened scene lost saved node position"):
			return
		if (await send_turn("重开后继续")).is_empty():
			return
		print("SAVE_RESULT=reopen")
		quit()
		return
	sidebar.close()
	EditorInterface.set_main_screen_editor("Script")
	EditorInterface.edit_script(load("res://actor.gd"))
	await process_frame
	var code := EditorInterface.get_script_editor().get_current_editor().get_base_editor() as CodeEdit
	code.grab_focus()
	code.select(2, 0, 2, code.get_line(2).length())
	await open_sidebar()
	var first := await send_turn("核对选中脚本")
	if not require(first.get("context_snapshot",{}).get("references", []).size() == 1, "Missing native script selection"):
		return
	code.deselect()
	code.set_caret_line(1)
	var caret := await send_turn("仅移动光标")
	if not require(caret.get("context_snapshot",{}).get("references", []).is_empty(), "Caret created revision"):
		return
	code.set_line(2, "\treturn 29")
	EditorInterface.get_script_editor().save_all_scripts()
	if (await send_turn("核对已保存脚本")).is_empty():
		return
	var file := FileAccess.open("res://actor.gd", FileAccess.WRITE)
	file.store_string("extends Node\nfunc score():\n\treturn 53\n")
	file.close()
	if (await send_turn("核对磁盘上的更新")).is_empty():
		return
	sidebar.close()
	EditorInterface.open_scene_from_path("res://level.tscn")
	EditorInterface.set_main_screen_editor("2D")
	await create_timer(0.4).timeout
	var node := EditorInterface.get_edited_scene_root().get_node("Actor") as Sprite2D
	EditorInterface.get_selection().clear()
	EditorInterface.get_selection().add_node(node)
	await open_sidebar()
	var selected := await send_turn("核对场景节点")
	if not require(selected.get("context_snapshot", {}).get("references", []).size() == 1, "Missing native node selection"):
		return
	node.position.x = 37.5
	EditorInterface.mark_scene_as_unsaved()
	if not require(EditorInterface.save_scene() == OK, "Native scene save failed"):
		return
	print("SAVE_RESULT=save")
	quit()
