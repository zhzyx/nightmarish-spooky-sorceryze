@tool
extends EditorPlugin


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
	var address: LineEdit = dock.find_child("WebPlatformAddress", true, false)
	var connect_button: Button = dock.find_child("ConnectWebPlatform", true, false)
	var status: Label = dock.find_child("WebPlatformStatus", true, false)
	var surface: Control = dock.find_child("WebPlatformSurface", true, false)
	assert(address != null and connect_button != null and status != null and surface != null)
	address.text = "javascript:alert(1)"
	connect_button.pressed.emit()
	await get_tree().process_frame
	assert(status.text.contains("HTTPS"))
	address.text = "http://127.0.0.1:3000"
	connect_button.pressed.emit()
	await get_tree().process_frame
	assert(status.text.contains("后台模式"))
	assert(EditorInterface.get_editor_settings().get_setting("network/web_platform/url") == address.text)
	for size in [Vector2i(1440, 900), Vector2i(1100, 760), Vector2i(900, 680)]:
		root.size = size
		await get_tree().process_frame
		await get_tree().process_frame
		assert(surface.size.x > 0 and surface.size.y > 0)
		assert(surface.get_global_rect().end.x <= root.size.x + 1)
		assert(surface.get_global_rect().end.y <= root.size.y + 1)
	dock.hide()
	await get_tree().process_frame
	dock.show()
	await get_tree().process_frame
	print("WEB_PLATFORM_DOCK_OK")
	get_tree().quit(0)
