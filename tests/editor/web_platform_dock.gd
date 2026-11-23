@tool
extends EditorPlugin
## Compatibility entry for the historical main-screen dock smoke test.
## Tianxuan now hosts native views under the retained layout identity.


func _enter_tree() -> void:
	run.call_deferred()


func run() -> void:
	var root: Window = get_tree().root
	assert(DisplayServer.get_name() == "headless")
	root.size = Vector2i(1440, 900)
	await get_tree().create_timer(1).timeout
	var dock = root.find_child("WebPlatform", true, false)
	assert(dock != null)
	assert(dock.get_title() == "天璇")
	assert(dock.get_layout_key() == "WebPlatformMainScreen")
	var tabs: TabContainer = dock.get_parent()
	tabs.current_tab = tabs.get_tab_idx_from_control(dock)
	await get_tree().process_frame
	var main := dock.find_child("TianxuanWorkspaceView", true, false)
	var sidebar := root.find_child("TianxuanSidebarView", true, false)
	assert(main != null and sidebar != null)
	assert(main.get_meta("controller") == sidebar.get_meta("controller"))
	assert(root.find_children("*", "WebPlatformDock", true, false).is_empty())
	assert(main.find_child("AuthenticateTianxuan", true, false) != null)
	for size in [Vector2i(1440, 900), Vector2i(1100, 760), Vector2i(900, 680)]:
		root.size = size
		await get_tree().process_frame
		await get_tree().process_frame
		assert(main.size.x > 0 and main.size.y > 0)
		assert(main.get_global_rect().end.x <= root.size.x + 1)
		assert(main.get_global_rect().end.y <= root.size.y + 1)
	dock.hide()
	await get_tree().process_frame
	dock.show()
	await get_tree().process_frame
	print("TIANXUAN_NATIVE_DOCK_OK")
	get_tree().quit(0)
