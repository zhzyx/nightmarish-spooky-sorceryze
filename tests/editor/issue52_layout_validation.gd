@tool
extends SceneTree

func _initialize():
	_run.call_deferred()

func settle():
	await create_timer(0.3).timeout

func find_named(node: Node, fragment: String) -> Node:
	for child in node.get_children():
		if fragment in String(child.name):
			return child
		var found = find_named(child, fragment)
		if found != null:
			return found
	return null

func _run():
	root.size = Vector2i(1600, 1000)
	await create_timer(1.0).timeout
	var dock = root.find_child("AI Chat", true, false) as Control
	assert(dock != null, "AI Chat missing")
	var main = dock.get_parent() as TabContainer
	var bottom = find_named(root, "BottomPanel") as TabContainer
	var scene_tabs = find_named(root, "SceneTabs") as Control
	assert(main != null and bottom != null and scene_tabs != null, "Editor controls missing")
	EditorInterface.set_main_screen_editor("3D")
	EditorInterface.set_distraction_free_mode(false)
	await settle()
	var normal_size = main.size
	var before = {}
	for split in root.find_children("Dock*", "SplitContainer", true, false):
		before[String(split.name)] = Array(split.get_split_offsets())
	if OS.get_environment("AI_CHAT_ORDER_PHASE") == "seed":
		print("ISSUE52_LAYOUT_RESULT=" + JSON.stringify({"phase": "seed", "normal_size": [normal_size.x, normal_size.y], "normal_offsets": before}))
		root.propagate_notification(Node.NOTIFICATION_WM_CLOSE_REQUEST)
		return
	EditorInterface.set_main_screen_editor("AI Chat")
	await settle()
	assert(not bottom.visible and not scene_tabs.visible, "AI Chat did not hide bottom panel/scene tabs")
	assert(dock.is_visible_in_tree() and dock.size.x > 0 and dock.size.y > 0, "AI Chat empty")
	var filled_size = main.size
	for screen in ["2D", "3D", "Script"]:
		EditorInterface.set_main_screen_editor(screen)
		await settle()
		assert(bottom.visible and scene_tabs.visible, "Switch away failed to restore controls")
		assert(main.size.x < filled_size.x, "Switch away failed to restore dock width")
		for split in root.find_children("Dock*", "SplitContainer", true, false):
			assert(before[String(split.name)] == Array(split.get_split_offsets()), "Split positions changed: %s" % split.name)
	EditorInterface.set_main_screen_editor("3D")
	EditorInterface.set_distraction_free_mode(true)
	await settle()
	EditorInterface.set_main_screen_editor("AI Chat")
	await settle()
	EditorInterface.set_main_screen_editor("3D")
	await settle()
	assert(EditorInterface.is_distraction_free_mode_enabled(), "Distraction-free state lost")
	EditorInterface.set_distraction_free_mode(false)
	await settle()
	var expand: Button = null
	var event = InputEventKey.new()
	event.keycode = KEY_F12
	event.shift_pressed = true
	for button in bottom.find_children("*", "Button", true, false):
		if button.shortcut != null and button.shortcut.matches_event(event):
			expand = button
	assert(expand != null, "Expand bottom panel button missing")
	bottom.current_tab = 0
	await settle()
	expand.button_pressed = true
	await settle()
	assert(not main.is_visible_in_tree(), "Precondition: expanded panel must hide main screen")
	EditorInterface.set_main_screen_editor("AI Chat")
	await settle()
	assert(not expand.button_pressed, "Expanded panel not reset")
	assert(main.is_visible_in_tree() and dock.is_visible_in_tree() and dock.size.x > 0 and dock.size.y > 0, "Expanded bottom panel left blank AI Chat")
	print("ISSUE52_LAYOUT_RESULT=" + JSON.stringify({"phase": OS.get_environment("AI_CHAT_ORDER_PHASE"), "normal_size": [normal_size.x, normal_size.y], "normal_offsets": before, "filled_size": [filled_size.x, filled_size.y], "distraction_preserved": true, "expanded_panel_nonblank": true, "split_positions_restored": true}))
	root.propagate_notification(Node.NOTIFICATION_WM_CLOSE_REQUEST)
