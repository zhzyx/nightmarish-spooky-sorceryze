extends "res://ai_chat_tab_order.gd"

var chat: Node
var composer: TextEdit

func receipt(name_: String, data: Dictionary) -> void:
	var path := "res://" + name_ + ".json"
	var file := FileAccess.open(path + ".tmp", FileAccess.WRITE)
	file.store_string(JSON.stringify(data))
	file.close()
	DirAccess.rename_absolute(path + ".tmp", path)

func native_handle(window: Window) -> int:
	return DisplayServer.window_get_native_handle(DisplayServer.WINDOW_HANDLE, window.get_window_id())

func check_window(source: Window, field: LineEdit, sample: String) -> Dictionary:
	field.text = sample
	field.grab_focus()
	field.caret_column = 9
	field.select(2, 9)
	var expected := field.get_selected_text()
	var draft := composer.text
	var key := _shortcut_key(KEY_P if source.exclusive else KEY_I, true, source.exclusive, not source.exclusive)
	key.pressed = true
	source.push_input(key)
	key.pressed = false
	source.push_input(key)
	await create_timer(0.25).timeout
	var dialog := source.get_node_or_null("AIWorkbenchWindow") as AcceptDialog
	if not _check(dialog != null and dialog.visible and source.visible and composer.has_focus(), "Window shortcut did not focus composer: " + source.title):
		return {}
	var hwnd := native_handle(dialog)
	if not _check(hwnd != 0 and hwnd != native_handle(source) and dialog.is_ancestor_of(composer), "Expected original composer in a separate HWND"):
		return {}
	var quote := dialog.find_child("InsertWindowReference", true, false) as Button
	if not _check(quote != null and composer.text == draft, "Missing reference or changed draft"): return {}
	quote.pressed.emit()
	var quoted := composer.text
	if not _check(quoted.begins_with(draft) and quoted.ends_with(expected) and not sample in quoted, "Wrong window selection: " + quoted): return {}
	var source_hwnd := native_handle(source)
	dialog.get_ok_button().pressed.emit()
	await create_timer(0.25).timeout
	if not _check(not is_instance_valid(dialog) and field.has_focus() and source.gui_get_focus_owner() == field and field.get_selected_text() == expected and field.caret_column == 9 and field.text == sample, "Source focus, caret or text changed: " + source.title): return {}
	return {"source":source.title, "source_hwnd":source_hwnd, "dialog_hwnd":hwnd, "shortcut":key.as_text(), "source_text":sample, "selection":expected, "composer_after_insert":quoted, "restored_focus":field.get_instance_id(), "field":field.get_instance_id(), "caret":field.caret_column}

func _run():
	await create_timer(1.5).timeout
	if not _check(DisplayServer.get_name() == "Windows" and native_handle(root) != 0 and not root.gui_embed_subwindows, "Native Windows multi-window display required"): return
	receipt("display", {"backend":DisplayServer.get_name(), "editor_pid":OS.get_process_id(), "hwnd":native_handle(root), "renderer":RenderingServer.get_current_rendering_method(), "version":Engine.get_version_info().string})
	chat = root.find_child("AI Chat", true, false)
	var setup := chat.find_child("GongGongRuntimeSetup", true, false)
	if setup: setup.hide()
	EditorInterface.set_main_screen_editor("AI Chat")
	composer = chat.find_child("ChatInput", true, false)
	var keyboard := {}
	if not await _check_workbench_shortcut(chat, keyboard): return
	receipt("keyboard", keyboard)
	composer.text = "Explain the selection."
	var tabs := chat.find_child("AgentTabs", true, false) as TabBar
	var menu := chat.find_child("AgentContextMenu", true, false) as PopupMenu
	tabs.tab_rmb_clicked.emit(tabs.current_tab)
	menu.hide()
	menu.id_pressed.emit(0)
	var rename := chat.find_child("AgentRenameDialog", true, false) as ConfirmationDialog
	if not _check(rename.visible and rename.exclusive, "Session rename modal missing"): return
	var modal := await check_window(rename, rename.find_child("AgentName", true, false), "unsaved-session-name")
	if modal.is_empty(): return
	receipt("modal", modal)
	rename.hide()
	await create_timer(0.25).timeout
	var fs := EditorInterface.get_file_system_dock()
	var slot := fs.get_parent() as TabContainer
	fs.make_visible()
	await process_frame
	slot.get_tab_bar().tab_rmb_clicked.emit(slot.get_tab_idx_from_control(fs))
	await process_frame
	var float_button: Button
	for button: Button in root.find_children("*", "Button", true, false):
		if button.is_visible_in_tree() and button.tooltip_text == "Make this dock floating.":
			float_button = button
			break
	if not _check(float_button != null and not float_button.disabled, "Floating dock action missing"): return
	float_button.pressed.emit()
	await create_timer(0.3).timeout
	var floating := fs.get_window()
	if not _check(floating != root and native_handle(floating) != 0 and not floating.is_embedded(), "Dock did not detach"): return
	var filter: LineEdit
	for line: LineEdit in fs.find_children("*","LineEdit",true,false):
		if line.is_visible_in_tree() and line.editable:
			filter = line
			break
	if not _check(filter != null, "Floating dock filter missing"): return
	var dock_result := await check_window(floating, filter, "q10-filter-selection")
	if dock_result.is_empty(): return
	floating.close_requested.emit()
	await create_timer(0.3).timeout
	if not _check(fs.get_window() == root and fs.get_parent() == slot and filter.text == "q10-filter-selection", "Dock did not return to original slot"): return
	dock_result["original_slot"] = str(slot.get_path())
	dock_result["restored_slot"] = str(fs.get_parent().get_path())
	dock_result["dock"] = fs.get_class()
	receipt("dock", dock_result)

	chat.get_ai_settings_control().find_child("AllowTools", true, false).button_pressed = true
	chat.get_ai_settings_control().find_child("AutoExecuteCommands", true, false).button_pressed = false
	chat.find_child("ConsultationOnly", true, false).button_pressed = false
	EditorInterface.open_scene_from_path("res://part.tscn")
	await create_timer(0.5).timeout
	var scene := EditorInterface.get_edited_scene_root()
	var selection := EditorInterface.get_selection()
	selection.clear()
	selection.add_node(scene)
	if not _check(scene.scene_file_path == "res://part.tscn", "Wrong scene before preview"): return
	for view: Control in root.find_children("*", "Control", true, false):
		if view.has_signal("embedding_completed"):
			view.connect("embedding_completed", func():
				if view.is_visible_in_tree():
					receipt("embedded_view", {"view":str(view.get_path()), "rect":str(view.get_global_rect()), "hwnd":native_handle(view.get_window())})
			, CONNECT_ONE_SHOT)
	receipt("before_preview", {"scene":scene.scene_file_path, "selected":str(scene.name), "scene_id":scene.get_instance_id()})
	var approval := chat.find_child("AIFileApproval", true, false) as ConfirmationDialog
	var deadline := Time.get_ticks_msec() + 35000
	while not approval.visible and Time.get_ticks_msec() < deadline: await process_frame
	if not _check(approval.visible, "No run_scene confirmation"): return
	approval.get_ok_button().pressed.emit()
	deadline = Time.get_ticks_msec() + 45000
	while not FileAccess.file_exists("res://observed-child") and Time.get_ticks_msec() < deadline: await process_frame
	if not _check(EditorInterface.is_playing_scene() and FileAccess.file_exists("res://observed-child"), "Local preview did not start or was not embedded"): return
	EditorInterface.stop_playing_scene()
	await create_timer(0.8).timeout
	if not _check(not EditorInterface.is_playing_scene() and EditorInterface.get_edited_scene_root() == scene and selection.get_selected_nodes() == [scene], "Stopping preview lost the original editor state"): return
	receipt("after_preview", {"scene":scene.scene_file_path, "selected":str(selection.get_selected_nodes()[0].name), "scene_id":scene.get_instance_id(), "playing":EditorInterface.is_playing_scene()})
	quit(0)
