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

func _shortcut_key(keycode: Key, command := false, shift := false, alt := false) -> InputEventKey:
	var event := InputEventKey.new()
	event.keycode = keycode
	event.meta_pressed = command and OS.has_feature("macos")
	event.ctrl_pressed = command and not OS.has_feature("macos")
	event.shift_pressed = shift
	event.alt_pressed = alt
	return event

func _send_shortcut(event: InputEventKey):
	event.pressed = true
	root.push_input(event)
	event.pressed = false
	root.push_input(event)

func _check_workbench_shortcut(dock: Node, sample: Dictionary) -> bool:
	var shortcut := EditorInterface.get_editor_settings().get_shortcut(WORKBENCH_COMMAND)
	if not _check(shortcut != null, "Missing dedicated workbench shortcut in Editor Settings"):
		return false
	var sidebar := root.find_child("AIWorkbenchSidebar", true, false) as EditorDock
	var composer := dock.find_child("ChatInput", true, false) as TextEdit
	var source := LineEdit.new()
	root.add_child(source)
	source.text = "source draft"
	source.grab_focus()
	var defaults := shortcut.events
	var default_key := _shortcut_key(KEY_M, true, true)
	if not _check(shortcut.matches_event(default_key), "Default workbench binding changed"):
		return false
	_send_shortcut(default_key)
	await process_frame
	if not _check(sidebar.is_visible_in_tree() and sidebar.is_ancestor_of(composer) and composer.has_focus(), "Default key did not focus the original sidebar composer"):
		return false
	sample["default"] = defaults[0].as_text()
	sample["sidebar"] = sidebar.get_instance_id()
	sample["composer"] = composer.get_instance_id()
	sidebar.close()
	await process_frame
	if not _check(source.has_focus(), "Closing the shortcut-opened sidebar did not restore source focus"):
		return false

	var replacement := _shortcut_key(KEY_P, false, true, true)
	shortcut.events = [replacement]
	_send_shortcut(default_key)
	await process_frame
	if not _check(not sidebar.is_visible_in_tree() and source.has_focus(), "Old binding still invoked workbench after rebinding"):
		return false
	sample["old_binding_inactive"] = true
	_send_shortcut(replacement.duplicate())
	await process_frame
	if not _check(sidebar.is_visible_in_tree() and sidebar.is_ancestor_of(composer) and composer.has_focus(), "Rebound key did not focus the same composer"):
		return false
	sample["rebound"] = replacement.as_text()

	var original_draft := composer.text
	composer.text = "workbench selection"
	var select_all := _shortcut_key(KEY_A, true)
	shortcut.events = [select_all]
	_send_shortcut(select_all.duplicate())
	if not _check(composer.get_selected_text() == composer.text and composer.has_focus(), "Workbench intercepted select-all in the chat composer"):
		return false
	sample["chat_select_all"] = composer.get_selected_text()
	composer.text = original_draft
	sidebar.close()
	await process_frame
	_send_shortcut(select_all.duplicate())
	if not _check(source.get_selected_text() == source.text and not sidebar.is_visible_in_tree(), "Workbench intercepted select-all in the source input"):
		return false
	sample["source_select_all"] = source.get_selected_text()
	shortcut.events = defaults
	source.queue_free()
	await process_frame
	return true

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

func _settle_layout():
	for frame in 4:
		await process_frame

func _press_workbench_button(button: Button):
	button.grab_focus()
	_key(KEY_SPACE, 32)

func _wheel_down(control: Control):
	var wheel := InputEventMouseButton.new()
	wheel.position = _visible_rect(control).get_center()
	wheel.global_position = wheel.position
	wheel.button_index = MOUSE_BUTTON_WHEEL_DOWN
	wheel.pressed = true
	root.push_input(wheel, true)
	wheel.pressed = false
	root.push_input(wheel, true)

func _selection_state(code: TextEdit) -> Dictionary:
	return {
		"text": code.get_selected_text(),
		"origin": [code.get_selection_origin_line(), code.get_selection_origin_column()],
		"caret": [code.get_caret_line(), code.get_caret_column()],
	}

func _check_workbench_round_trip(tabs: TabContainer, dock: EditorDock, samples: Array) -> bool:
	EditorInterface.set_main_screen_editor("Script")
	EditorInterface.edit_script(load("res://sidebar_fixture.gd"))
	await _settle_layout()
	var code := EditorInterface.get_script_editor().get_current_editor().get_base_editor() as CodeEdit
	var source_screen := tabs.get_current_tab_control()
	code.grab_focus()
	code.select(1, 10, 1, 2)
	var selection := _selection_state(code)
	if not _check(selection.text == "Editable" and selection.caret == [1, 2], "Missing reverse script selection: " + str(selection)):
		return false
	if not await _invoke_workbench():
		return false
	var sidebar := root.find_child("AIWorkbenchSidebar", true, false) as EditorDock
	var composer := sidebar.find_child("ChatInput", true, false) as TextEdit
	var messages := sidebar.find_child("Messages", true, false) as VBoxContainer
	var scroll := sidebar.find_child("ChatScroll", true, false) as ScrollContainer
	var mode := sidebar.find_child("ConsultationOnly", true, false) as CheckBox
	if not _check(mode != null and mode.button_pressed, "Unbound workbench entry should default to consultation"):
		return false
	var expand := sidebar.find_child("ExpandWorkbench", true, false) as Button
	var restore := dock.find_child("RestoreWorkbenchSidebar", true, false) as Button
	if not _check(expand != null and restore != null and expand.is_visible_in_tree(), "Missing workbench view controls"):
		return false
	# Deterministic transcript rows give both native layouts a nontrivial scroll range.
	var rows: Array[Label] = []
	for index in 48:
		var row := Label.new()
		row.text = "Round trip fixture %02d" % index
		messages.add_child(row)
		rows.append(row)
	var draft := "草稿 · round trip\nsecond line"
	composer.text = draft
	await _settle_layout()
	for attempt in 2:
		mode.button_pressed = (attempt == 0)
		var offset := 193 + 127 * attempt
		scroll.scroll_vertical = offset
		if not _check(scroll.scroll_vertical == offset, "Sidebar fixture could not scroll to " + str(offset)):
			return false
		composer.select(1, 6 + attempt, 0, 2 + attempt)
		var sidebar_selection := _selection_state(composer)
		if not _check(not sidebar_selection.text.is_empty() and sidebar_selection.caret == [0, 2 + attempt], "Missing reverse multiline draft selection"):
			return false
		_press_workbench_button(expand)
		await _settle_layout()
		var expanded_selection := _selection_state(composer)
		if not _check(expanded_selection == sidebar_selection, "Expand changed the draft selection: " + str(expanded_selection)):
			return false
		if not _check(tabs.get_current_tab_control() == dock and not sidebar.is_visible_in_tree() and restore.is_visible_in_tree(), "Expand did not select the full native AI workspace"):
			return false
		if not _check(dock.is_ancestor_of(composer) and composer.is_visible_in_tree() and composer.has_focus() and composer.text == draft and dock.is_ancestor_of(messages) and scroll.scroll_vertical == offset, "Full view changed conversation state: " + str(scroll.scroll_vertical)):
			return false
		composer.deselect()
		composer.set_caret_line(1)
		composer.set_caret_column(composer.get_line(1).length())
		_key(KEY_Z, 122)
		draft += "z"
		composer.select(1, 5 + attempt, 0, 1 + attempt)
		var full_selection := _selection_state(composer)
		_wheel_down(scroll)
		await _settle_layout()
		var full_offset := scroll.scroll_vertical
		if not _check(full_offset > offset, "Full conversation did not receive wheel input: " + str(full_offset)):
			return false
		if attempt == 0:
			_press_workbench_button(restore)
		elif not await _invoke_workbench():
			return false
		await _settle_layout()
		if not _check(mode.button_pressed == (attempt == 0), "Changing the workbench view reset the selected conversation mode"):
			return false
		if not _check(tabs.get_current_tab_control() == source_screen and sidebar.is_visible_in_tree() and sidebar.is_ancestor_of(composer) and composer.has_focus(), "Return did not restore Script and its native sidebar"):
			return false
		if not _check(composer.text == draft and _selection_state(composer) == full_selection and sidebar.is_ancestor_of(messages) and scroll.scroll_vertical == full_offset and _selection_state(code) == selection, "Returned conversation or script state changed: " + str([_selection_state(composer), scroll.scroll_vertical, _selection_state(code)])):
			return false
		samples.append({
			"cycle": attempt + 1,
			"entry": "expand button",
			"return": "button" if attempt == 0 else WORKBENCH_COMMAND,
			"source": source_screen.name,
			"composer_id": composer.get_instance_id(),
			"draft": composer.text,
			"expanded_scroll": offset,
			"full_view_user_scroll": full_offset,
			"returned_scroll": scroll.scroll_vertical,
			"sidebar_draft_selection": sidebar_selection,
			"expanded_draft_selection": expanded_selection,
			"full_view_user_selection": full_selection,
			"returned_draft_selection": _selection_state(composer),
			"script_selection": _selection_state(code),
		})
	sidebar.close()
	await _settle_layout()
	if not _check(code.has_focus() and _selection_state(code) == selection, "Closing the restored sidebar lost the script editor focus or selection"):
		return false
	var old_text := code.text
	_key(KEY_X, 120)
	if not _check(code.get_line(1) == "# x draft", "Continued editing did not replace the restored selection"):
		return false
	code.undo()
	if not _check(code.text == old_text, "Could not undo fixture edit"):
		return false
	for row in rows:
		row.free()
	var plugin := EditorPlugin.new()
	var temporary_screen := EditorDock.new()
	temporary_screen.title = "Temporary Workbench Source"
	temporary_screen.default_slot = EditorDock.DOCK_SLOT_MAIN_SCREEN
	temporary_screen.available_layouts = EditorDock.DOCK_LAYOUT_MAIN_SCREEN
	var temporary_input := LineEdit.new()
	temporary_screen.add_child(temporary_input)
	plugin.add_dock(temporary_screen)
	tabs.current_tab = tabs.get_tab_idx_from_control(temporary_screen)
	await _settle_layout()
	temporary_input.grab_focus()
	if not _check(tabs.get_current_tab_control() == temporary_screen and temporary_input.has_focus(), "Temporary screen could not take focus"):
		return false
	if not await _invoke_workbench():
		return false
	_press_workbench_button(expand)
	await _settle_layout()
	var sessions := dock.find_child("AgentTabs", true, false) as TabBar
	var previous_tab := sessions.current_tab
	mode.button_pressed = false
	dock.find_child("AddAgent", true, false).pressed.emit()
	await _settle_layout()
	var new_tab := sessions.current_tab
	if not _check(new_tab != previous_tab and mode.button_pressed, "New workbench session inherited another session's mode"):
		return false
	sessions.current_tab = previous_tab
	sessions.tab_close_pressed.emit(new_tab)
	await _settle_layout()
	plugin.remove_dock(temporary_screen)
	temporary_screen.free()
	plugin.free()
	_press_workbench_button(restore)
	await _settle_layout()
	if not _check(tabs.get_current_tab_control() == dock and sidebar.is_visible_in_tree() and composer.has_focus(), "Released source screen prevented return to the sidebar"):
		return false
	sidebar.close()
	await _settle_layout()
	if not _check(not sidebar.is_visible_in_tree() and dock.is_ancestor_of(composer) and composer.text == draft, "Released source control prevented close"):
		return false
	samples.append({"released_source_screen_while_expanded": true, "script_edit_after_close": "# x draft"})
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
		var shortcut_sample := {}
		if not await _check_workbench_shortcut(dock, shortcut_sample):
			return
		sample["workbench_shortcut"] = shortcut_sample
		var invocations := []
		if not await _check_workbench_command(tabs, dock, invocations):
			return
		var cycles := []
		if not await _check_workbench_round_trip(tabs, dock, cycles):
			return
		sample["round_trips"] = cycles
		sample["workbench"] = {"key": WORKBENCH_COMMAND, "original_instance_id": dock.get_instance_id(), "invocations": invocations}
	print("AI_CHAT_TAB_ORDER_RESULT=" + JSON.stringify(sample))
	# Use the editor's normal close path so editor_layout.cfg is actually saved.
	root.propagate_notification(Node.NOTIFICATION_WM_CLOSE_REQUEST)
