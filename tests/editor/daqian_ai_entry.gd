@tool
extends SceneTree


func _initialize() -> void:
	run.call_deferred()


func run() -> void:
	root.size = Vector2i(1440,900)
	await create_timer(1.5).timeout
	var chat = root.find_child("AI Chat",true,false)
	if not chat or not chat.get_force_show_icon() or chat.get_icon_name() != &"AIChatWave":
		push_error("Missing wave mark on native AI Chat tab")
		quit(1)
		return
	var tabs: TabContainer = chat.get_parent()
	var tab := tabs.get_tab_idx_from_control(chat)
	var icon := tabs.get_tab_icon(tab)
	var button := root.find_child("OpenAIWorkbench", true, false) as Button
	var daqian := root.find_child("Daqian", true, false)
	if not button or not button.is_visible_in_tree() or not icon or not tabs.is_tab_hidden(tab) or not tabs.is_tab_hidden(tabs.get_tab_idx_from_control(daqian)):
		push_error("Unique workbench entry unavailable")
		quit(1)
		return
	if OS.get_environment("GONGGONG_VALIDATE_TIANSHU") == "1":
		for name: String in ["ui", "board"]:
			var source: Dictionary = daqian.get_meta("tianshu_" + name + "_source", {})
			if source.is_empty():
				push_error("Isolated editor did not load Tianshu " + name)
				quit(1)
				return
			print("TIANSHU_%s_LOADED %s" % [name.to_upper(), source.sha256])
	var accent: Color = chat.get_title_color()
	if accent not in [Color("#7dd3fc"), Color("#0369a1")]:
		push_error("Theme accent missing")
		quit(1)
		return
	EditorInterface.set_main_screen_editor("2D")
	button.pressed.emit()
	await process_frame
	var sidebar := root.find_child("AIWorkbenchSidebar", true, false)
	if not sidebar.is_visible_in_tree() or not sidebar.find_child("ChatInput", true, false):
		push_error("Workbench entry did not open the conversation")
		quit(1)
		return
	sidebar.find_child("ExpandWorkbench", true, false).pressed.emit()
	await process_frame
	var wave: ColorRect = chat.find_child("ChatWave", true, false)
	var wave_icon: SubViewport = chat.find_child("ChatWaveIcon", true, false)
	if not wave or not wave_icon or not wave.material is ShaderMaterial or wave.get_mouse_filter() != Control.MOUSE_FILTER_IGNORE:
		push_error("Missing passive wave header/icon")
		quit(1)
		return
	if wave.material != wave_icon.get_child(0).material or not wave.material.get_shader_parameter("crest") is Texture2D:
		push_error("Header and dock icon must share the themed wave material")
		quit(1)
		return
	for width in [1440, 1100]:
		root.size = Vector2i(width, 900)
		await process_frame
		if wave.size.y <= 0 or wave.get_global_rect().end.x > root.size.x:
			push_error("Wave header outside editor bounds")
			quit(1)
			return
	var screenshot := OS.get_environment("DAQIAN_ENTRY_PREVIEW")
	if not screenshot.is_empty():
		await RenderingServer.frame_post_draw
		var image := root.get_texture().get_image()
		var region := Rect2i(button.get_global_rect().grow(4)).intersection(Rect2i(Vector2i.ZERO, image.get_size()))
		if not region.has_area() or image.get_region(region).save_png(screenshot) != OK:
			push_error("Cannot capture AI Chat entry")
			quit(1)
			return
	print("DAQIAN_AI_ENTRY_OK title=",button.text," color=",accent.to_html()," icon=",icon.get_size())
	root.propagate_notification(Node.NOTIFICATION_WM_CLOSE_REQUEST)
