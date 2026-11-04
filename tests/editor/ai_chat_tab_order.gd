extends SceneTree

func _initialize():
	_run.call_deferred()

func _run():
	await create_timer(1.0).timeout
	var dock = root.find_child("AI Chat", true, false)
	assert(dock != null, "AI Chat is missing")
	var tabs = dock.get_parent() as TabContainer
	assert(tabs != null and tabs.get_theme_type_variation() == "MainScreenContainer", "AI Chat left the main screen")
	var labels: Array[String] = []
	for index in tabs.get_tab_count():
		labels.append(tabs.get_tab_title(index))
	assert(tabs.get_tab_control(0) == dock, "AI Chat is not first")
	assert(tabs.get_tab_bar().get_tab_rect(0).position.x < tabs.get_tab_bar().get_tab_rect(1).position.x, "AI Chat is not visually left of 2D")
	assert(labels[1] == "2D", "AI Chat is not immediately before 2D")
	assert(labels.find("3D") > 1 and labels.find("Script") > labels.find("3D"), "Other built-in tabs changed order")
	for index in tabs.get_tab_count():
		tabs.set_current_tab(index)
		await process_frame
		await process_frame
		assert(tabs.get_current_tab_control() == tabs.get_tab_control(index), "Tab switch failed")
		assert(tabs.get_tab_control(index).is_visible_in_tree(), "Selected tab is hidden")
	EditorInterface.set_main_screen_editor("AI Chat")
	await process_frame
	assert(dock.is_visible_in_tree() and dock.find_child("ChatInput", true, false) != null, "AI Chat cannot be used after switching")
	print("AI_CHAT_TAB_ORDER_RESULT=" + JSON.stringify({"labels": labels, "current": tabs.get_current_tab(), "slot": dock.get_default_slot(), "phase": OS.get_environment("AI_CHAT_ORDER_PHASE")}))
	# Use the editor's normal close path so editor_layout.cfg is actually saved.
	root.propagate_notification(Node.NOTIFICATION_WM_CLOSE_REQUEST)
