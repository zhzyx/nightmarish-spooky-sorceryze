extends SceneTree

func _initialize():
	_run.call_deferred()

func _check(condition: bool, message: String) -> bool:
	if not condition:
		push_error(message)
		quit(1)
	return condition

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
	print("AI_CHAT_TAB_ORDER_RESULT=" + JSON.stringify({"labels": labels, "current": tabs.get_current_tab(), "initial_selected_key": selected_key, "slot": dock.get_default_slot(), "phase": OS.get_environment("AI_CHAT_ORDER_PHASE")}))
	# Use the editor's normal close path so editor_layout.cfg is actually saved.
	root.propagate_notification(Node.NOTIFICATION_WM_CLOSE_REQUEST)
