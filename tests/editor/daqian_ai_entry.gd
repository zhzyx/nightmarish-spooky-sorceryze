@tool
extends SceneTree


func _initialize() -> void:
	run.call_deferred()


func run() -> void:
	root.size = Vector2i(1440,900)
	await create_timer(1.5).timeout
	var chat = root.find_child("AI Chat",true,false)
	if not chat or not chat.get_force_show_icon() or chat.get_icon_name() != &"AIChatPig":
		push_error("Missing pig mark on native AI Chat tab")
		quit(1)
		return
	var tabs: TabContainer = chat.get_parent()
	var tab := tabs.get_tab_idx_from_control(chat)
	var icon := tabs.get_tab_icon(tab)
	if tab != 0 or not icon or tabs.get_tab_title(tab).is_empty():
		push_error("AI Chat title, icon or position missing")
		quit(1)
		return
	var accent: Color = chat.get_title_color()
	if accent not in [Color("#9ee9ee"), Color("#763a80")]:
		push_error("Theme accent missing")
		quit(1)
		return
	tabs.current_tab = 1
	await process_frame
	tabs.current_tab = tab
	await process_frame
	if not chat.is_visible_in_tree() or not chat.find_child("ChatInput",true,false):
		push_error("AI Chat entry did not open chat")
		quit(1)
		return
	var screenshot := OS.get_environment("DAQIAN_ENTRY_PREVIEW")
	if not screenshot.is_empty():
		await RenderingServer.frame_post_draw
		var image := root.get_texture().get_image()
		var bar := tabs.get_tab_bar()
		var entry := bar.get_tab_rect(tab)
		var top := bar.get_global_rect().position + entry.position
		var region := Rect2i(Vector2i(top - Vector2(8,4)), Vector2i(minf(640.0,bar.size.x), entry.size.y+8)).intersection(Rect2i(Vector2i.ZERO,image.get_size()))
		if not region.has_area() or image.get_region(region).save_png(screenshot) != OK:
			push_error("Cannot capture AI Chat entry")
			quit(1)
			return
	print("DAQIAN_AI_ENTRY_OK title=",tabs.get_tab_title(tab)," color=",accent.to_html()," icon=",icon.get_size())
	root.propagate_notification(Node.NOTIFICATION_WM_CLOSE_REQUEST)
