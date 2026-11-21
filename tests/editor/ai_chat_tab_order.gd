extends SceneTree

const WORKBENCH_COMMAND := "editor/open_ai_workbench"

func _initialize():
	_run.call_deferred()

func _check(condition: bool, message: String) -> bool:
	if not condition:
		push_error(message)
		quit(1)
	return condition

func _workbench_dock_ids() -> Array[int]:
	var ids: Array[int] = []
	for candidate in root.find_children("*", "EditorDock", true, false):
		if candidate.get_layout_key() == "AIChatMainScreen":
			ids.append(candidate.get_instance_id())
	ids.sort()
	return ids

func _invoke_workbench() -> bool:
	var palette := EditorInterface.get_command_palette()
	var shortcut := InputEventShortcut.new()
	shortcut.shortcut = EditorInterface.get_editor_settings().get_shortcut("editor/command_palette")
	root.push_input(shortcut)
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

func _key(keycode: Key, unicode_value := 0, alt := false):
	var key := InputEventKey.new()
	key.keycode = keycode
	key.unicode = unicode_value
	key.alt_pressed = alt
	key.pressed = true
	root.push_input(key)
	key.pressed = false
	root.push_input(key)

func _visible_rect(control: Control) -> Rect2:
	var visible := control.get_global_rect().intersection(Rect2(Vector2.ZERO, Vector2(root.size)))
	var parent := control.get_parent()
	while parent is Control:
		if parent.clip_contents:
			visible = visible.intersection(parent.get_global_rect())
		parent = parent.get_parent()
	return visible

func _check_sidebar_bounds(viewport: Control, sidebar: Control, composer: Control, rows: Array) -> bool:
	var previous_size := root.size
	for width in [960, 1440]:
		root.size = Vector2i(width, 900)
		for frame in 4:
			await process_frame
		var row := {"width": width, "window": str(root.size)}
		for pair in [["viewport", viewport], ["sidebar", sidebar], ["composer", composer]]:
			var control := pair[1] as Control
			row[pair[0]] = {"rect": str(control.get_global_rect()), "visible": str(_visible_rect(control))}
		rows.append(row)
		var viewport_rect := _visible_rect(viewport)
		var sidebar_rect := _visible_rect(sidebar)
		var composer_rect := _visible_rect(composer)
		if not _check(root.size.x == width and viewport_rect.size.x >= 160 and not viewport_rect.intersects(sidebar_rect) and sidebar_rect.encloses(composer_rect) and composer_rect.size.is_equal_approx(composer.size), "Clipped sidebar input or scene viewport: " + str(row)):
			return false
	root.size = previous_size
	await process_frame
	return true

func _check_workbench_command(tabs: TabContainer, dock: Node, samples: Array) -> bool:
	var sidebar := root.find_child("AIWorkbenchSidebar", true, false) as EditorDock
	var composer := dock.find_child("ChatInput", true, false) as TextEdit
	var messages := dock.find_child("Messages", true, false)
	var original_tabs := tabs.get_tab_count()
	var original_docks := _workbench_dock_ids()
	if not _check(sidebar != null and not sidebar.is_visible_in_tree() and dock.get_instance_id() in original_docks, "Missing original dock or sidebar"):
		return false
	var draft := composer.text
	EditorInterface.open_scene_from_path("res://sidebar_fixture.tscn")
	await process_frame
	var scene_node := EditorInterface.get_edited_scene_root().get_node("Selection") as Node2D
	var selection := EditorInterface.get_selection()
	selection.clear()
	selection.add_node(scene_node)
	for screen in ["2D", "Script"]:
		EditorInterface.set_main_screen_editor(screen)
		var source: Control
		var code: CodeEdit
		var original_text: String
		if screen == "Script":
			EditorInterface.edit_script(load("res://sidebar_fixture.gd"))
			await process_frame
			code = EditorInterface.get_script_editor().get_current_editor().get_base_editor()
			source = code
			original_text = code.text
			code.set_caret_line(1)
			code.set_caret_column(code.get_line(1).length())
		else:
			source = tabs.get_current_tab_control().find_children("*", "CanvasItemEditorViewport", true, false).front()
		await process_frame
		if not _check(source != null and tabs.get_tab_title(tabs.current_tab) == screen, "Could not select " + screen):
			return false
		source.grab_focus()
		if code:
			_key(KEY_X, 120)
			if not _check(code.text != original_text and code.get_line(1).ends_with("x"), "Script did not receive initial input"):
				return false
		var caret := code.get_caret_column() if code else 0
		for attempt in 2:
			if not await _invoke_workbench():
				return false
			if not _check(sidebar.is_visible_in_tree() and sidebar.get_parent() != tabs and tabs.get_tab_title(tabs.current_tab) == screen and tabs.get_tab_count() == original_tabs, "Sidebar displaced editor screen"):
				return false
			if not _check(sidebar.find_child("ChatInput", true, false) == composer and sidebar.find_child("Messages", true, false) == messages and composer.has_focus(), "Sidebar did not focus the original composer"):
				return false
			if not _check(_workbench_dock_ids() == original_docks and root.find_children("AIWorkbenchSidebar", "EditorDock", true, false).size() == 1 and composer.text == draft, "Sidebar duplicated the session or lost its draft"):
				return false
			if attempt == 0:
				composer.set_caret_line(composer.get_line_count() - 1)
				composer.set_caret_column(composer.get_line(composer.get_caret_line()).length())
				_key(KEY_Z, 122)
				draft += "z"
				if not _check(composer.text == draft, "Shared composer did not receive input"):
					return false
			samples.append({"from": screen, "repeat": attempt > 0, "sidebar": sidebar.get_instance_id(), "composer": composer.get_instance_id(), "dock_ids": original_docks, "tab_count": original_tabs})
		if screen == "2D":
			var bounds := []
			if not await _check_sidebar_bounds(source, sidebar, composer, bounds):
				return false
			samples[-1]["bounds"] = bounds
		if code:
			sidebar.close()
		else:
			sidebar.find_child("CloseWorkbench", true, false).pressed.emit()
		await process_frame
		await process_frame
		if not _check(not sidebar.is_visible_in_tree() and source.has_focus() and dock.find_child("ChatInput", true, false) == composer and composer.text == draft, "Collapse failed to restore the source or draft for " + screen + ": " + str(root.gui_get_focus_owner())):
			return false
		if code:
			if not _check(code.get_caret_column() == caret and code.get_line(1).ends_with("x"), "Script caret or draft changed"):
				return false
			_key(KEY_Y, 121)
			if not _check(code.get_line(1).ends_with("xy"), "Script could not continue at its original caret"):
				return false
			while code.has_undo() and code.text != original_text:
				code.undo()
		else:
			if not _check(selection.get_selected_nodes() == [scene_node] and scene_node.position != Vector2.ZERO, "Lost scene selection"):
				return false
			_key(KEY_W, 0, true) # Native 2D Reset Position.
			if not _check(scene_node.position == Vector2.ZERO, "Viewport could not edit the selected node after collapse"):
				return false
			var history := EditorInterface.get_editor_undo_redo()
			history.get_history_undo_redo(history.get_object_history_id(scene_node)).undo()
		samples[-1]["restored_focus"] = source.get_instance_id()
		samples[-1]["draft_length"] = composer.text.length()
		samples[-1]["continued_edit"] = "inserted y" if code else "reset node position"

	EditorInterface.set_main_screen_editor("2D")
	await process_frame
	if not await _invoke_workbench():
		return false
	EditorInterface.set_main_screen_editor("AI Chat")
	await process_frame
	if not _check(not sidebar.is_visible_in_tree() and dock.is_ancestor_of(composer) and composer.is_visible_in_tree(), "Selecting the full workbench left conversation in the sidebar"):
		return false
	samples.append({"from": "2D", "returned_to_main_tab": dock.is_ancestor_of(composer)})
	composer.grab_focus()
	if not await _invoke_workbench():
		return false
	if not _check(sidebar.is_visible_in_tree() and composer.has_focus() and tabs.get_current_tab_control() == dock, "Window-filling workspace hid the sidebar"):
		return false
	var slot := sidebar.get_parent() as TabContainer
	sidebar.close()
	await process_frame
	if not _check(not slot.is_visible_in_tree() and composer.has_focus() and dock.is_ancestor_of(composer), "Could not restore hidden dock slot and full workspace input"):
		return false

	samples.append({"from": "AI Chat", "restored_focus": composer.get_instance_id(), "restored_hidden_slot": not slot.is_visible_in_tree()})
	EditorInterface.set_main_screen_editor("2D")
	await process_frame
	var inspector := root.find_child("Inspector", true, false) as EditorDock
	inspector.make_visible()
	var inspector_filter := inspector.find_children("*", "LineEdit", true, false).front() as LineEdit
	inspector_filter.grab_focus()
	if not await _invoke_workbench():
		return false
	if not _check(sidebar.get_parent() == inspector.get_parent() and not inspector.is_visible_in_tree(), "Sidebar did not share the Inspector column"):
		return false
	sidebar.close()
	await process_frame
	if not _check(inspector.is_visible_in_tree() and inspector_filter.has_focus(), "Collapse did not restore the Inspector tab and focus"):
		return false
	samples.append({"from": "Inspector", "restored_focus": inspector_filter.get_instance_id()})

	EditorInterface.set_distraction_free_mode(true)
	await process_frame
	if not await _invoke_workbench():
		return false
	if not _check(sidebar.is_visible_in_tree(), "Distraction-free mode hid the requested sidebar"):
		return false
	sidebar.close()
	await process_frame
	if not _check(not slot.is_visible_in_tree() and EditorInterface.is_distraction_free_mode_enabled(), "Collapse changed distraction-free visibility"):
		return false
	samples.append({"from": "2D", "restored_distraction_free_mode": true})
	EditorInterface.set_distraction_free_mode(false)
	await process_frame
	var temporary := LineEdit.new()
	tabs.get_current_tab_control().add_child(temporary)
	temporary.grab_focus()
	if not await _invoke_workbench():
		return false
	temporary.free()
	sidebar.close()
	await process_frame
	if not _check(not sidebar.is_visible_in_tree() and is_instance_valid(composer) and composer.text == draft, "Released focus source prevented collapse"):
		return false
	samples.append({"from": "temporary LineEdit", "released_source": true, "preserved_draft": composer.text == draft})
	return true

func _run():
	# A headless display can start at 64 px; test the order of visible, unscrolled tabs.
	root.size = Vector2i(1600, 900)
	await create_timer(1.0).timeout
	var dock = root.find_child("AI Chat", true, false)
	if not _check(dock != null, "AI Chat is missing"):
		return
	var tabs = dock.get_parent() as TabContainer
	if not _check(tabs != null and tabs.get_theme_type_variation() == "MainScreenContainer", "AI Chat left the main screen"):
		return
	var labels: Array[String] = []
	for index in tabs.get_tab_count():
		labels.append(tabs.get_tab_title(index))
	if not _check(tabs.get_tab_control(0) == dock, "AI Chat is not first"):
		return
	if not _check(tabs.get_tab_bar().get_tab_rect(0).position.x < tabs.get_tab_bar().get_tab_rect(1).position.x, "AI Chat is not left of Maliang"):
		return
	if not _check(labels.slice(0, 5) == ["AI Chat", "马良", "天枢", "天璇", "2D"], "Unexpected main-screen order: " + str(labels)):
		return
	if not _check(labels.find("3D") > 1 and labels.find("Script") > labels.find("3D"), "Other built-in tabs changed order"):
		return
	var selected_dock = tabs.get_current_tab_control()
	var selected_key = selected_dock.get_layout_key()
	if selected_key.is_empty(): selected_key = tabs.get_tab_title(tabs.current_tab)
	var expected = OS.get_environment("AI_CHAT_ORDER_EXPECT_SELECTED")
	if not _check(expected.is_empty() or selected_key==expected, "Layout migration changed the selected page: " + selected_key):
		return
	for index in tabs.get_tab_count():
		tabs.set_current_tab(index)
		await process_frame
		await process_frame
		if not _check(tabs.get_current_tab_control() == tabs.get_tab_control(index), "Tab switch failed"):
			return
		if not _check(tabs.get_tab_control(index).is_visible_in_tree(), "Selected tab is hidden"):
			return
	EditorInterface.set_main_screen_editor("AI Chat")
	await process_frame
	if not _check(dock.is_visible_in_tree() and dock.find_child("ChatInput", true, false) != null, "AI Chat cannot be used after switching"):
		return
	var sample := {"labels": labels, "current": tabs.get_current_tab(), "initial_selected_key": selected_key, "slot": dock.get_default_slot(), "phase": OS.get_environment("AI_CHAT_ORDER_PHASE")}
	if "--workbench-command" in OS.get_cmdline_user_args():
		var invocations := []
		if not await _check_workbench_command(tabs, dock, invocations):
			return
		sample["workbench"] = {"key": WORKBENCH_COMMAND, "original_instance_id": dock.get_instance_id(), "invocations": invocations}
	print("AI_CHAT_TAB_ORDER_RESULT=" + JSON.stringify(sample))
	# Use the editor's normal close path so editor_layout.cfg is actually saved.
	root.propagate_notification(Node.NOTIFICATION_WM_CLOSE_REQUEST)
