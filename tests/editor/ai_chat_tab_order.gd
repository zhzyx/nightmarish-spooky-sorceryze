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

func _check_workbench_command(tabs: TabContainer, dock: Node, samples: Array) -> bool:
	var palette := EditorInterface.get_command_palette()
	var search := palette.find_children("*", "LineEdit", true, false).front() as LineEdit
	var results := palette.find_children("*", "Tree", true, false).front() as Tree
	var shortcut := InputEventShortcut.new()
	shortcut.shortcut = EditorInterface.get_editor_settings().get_shortcut("editor/command_palette")
	var original_tabs := tabs.get_tab_count()
	var original_docks := _workbench_dock_ids()
	if not _check(dock.get_instance_id() in original_docks, "Original workbench is missing from the editor tree"):
		return false
	for source in ["2D", "Script"]:
		EditorInterface.set_main_screen_editor(source)
		await process_frame
		if not _check(tabs.get_tab_title(tabs.current_tab) == source, "Could not select " + source):
			return false
		for attempt in 2:
			var from_screen := tabs.get_tab_title(tabs.current_tab)
			root.push_input(shortcut)
			await process_frame
			if not _check(palette.visible, "Command palette did not open from " + from_screen):
				return false
			search.text = WORKBENCH_COMMAND
			search.text_changed.emit(search.text)
			var item := results.get_selected()
			if not _check(item != null and item.get_metadata(0) == WORKBENCH_COMMAND, "Workbench command missing"):
				return false
			results.item_activated.emit()
			await process_frame
			var selected := tabs.get_current_tab_control()
			if not _check(selected == dock and dock.is_visible_in_tree() and tabs.get_tab_count() == original_tabs, "Command did not reopen the original dock"):
				return false
			var dock_ids := _workbench_dock_ids()
			if not _check(dock_ids == original_docks, "Command changed the set of workbench instances"):
				return false
			samples.append({"from": from_screen, "repeat": attempt > 0, "instance_id": selected.get_instance_id(), "dock_ids": dock_ids, "tab_count": tabs.get_tab_count()})
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
