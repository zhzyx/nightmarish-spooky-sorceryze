@tool
extends "res://order.gd"

const PRIVATE_DRAFT := "UNSENT_EXTENSION_DRAFT_1809"

func _run():
	root.size = Vector2i(960, 900)
	await create_timer(1).timeout
	var chat := root.find_child("AI Chat", true, false)
	var sidebar := root.find_child("AIWorkbenchSidebar", true, false) as EditorDock
	var tabs := chat.get_parent() as TabContainer
	var input := chat.find_child("ChatInput", true, false) as TextEdit
	var send := chat.find_child("Send", true, false) as Button
	var label := chat.find_child("WorkbenchReference", true, false) as Button
	var config: Control = chat.get_ai_settings_control()
	var backend := chat.find_child("AIBackend", true, false) as OptionButton
	backend.select(0)
	backend.item_selected.emit(0)
	config.find_child("APIEndpoint", true, false).text = OS.get_environment("PAGE_TEST_ENDPOINT")
	var key := config.find_child("APIKey", true, false) as LineEdit
	key.text = "page-fixture"
	key.text_changed.emit(key.text)
	chat.find_child("APIModel", true, false).text = "fixture"
	var pages: Array = []
	for title: String in ["马良", "R4 Notes"]:
		var page: EditorDock
		for index in tabs.get_tab_count():
			if tabs.get_tab_title(index) == title:
				page = tabs.get_tab_control(index)
		if not _check(page != null, "Missing registered page " + title): return
		tabs.current_tab = tabs.get_tab_idx_from_control(page)
		await process_frame
		var note := page.find_child("PrivateNote", true, false) as TextEdit
		if note:
			note.grab_focus()
			note.text = PRIVATE_DRAFT
		if not await _invoke_workbench(): return
		await _settle_layout()
		var module: String = "AINativeMainScreen" if title == "马良" else "res://addons/notes/plugin.gd"
		var expected := "页面：" + title + "\n模块：" + module + "\n可读范围：页面名、模块标识"
		if not _check(label.is_visible_in_tree() and label.text == expected and page.is_visible_in_tree() and sidebar.is_ancestor_of(input), "Incorrect preview: " + label.text): return
		if not _check(_visible_rect(label).size.is_equal_approx(label.size) and label.size.y >= label.get_theme_font_size("font_size") * 3, "Page preview is clipped: rect=%s visible=%s sidebar=%s window=%s font=%d" % [label.get_global_rect(), _visible_rect(label), sidebar.get_global_rect(), root.size, label.get_theme_font_size("font_size")]): return
		var bounds := []
		for width in [960, 1200, 1440]:
			root.size = Vector2i(width, 900)
			await _settle_layout()
			if not _check(_visible_rect(label).size.is_equal_approx(label.size) and _visible_rect(input).size.is_equal_approx(input.size), "Clipped at %d px: reference %s visible %s; input %s visible %s" % [width, label.get_global_rect(), _visible_rect(label), input.get_global_rect(), _visible_rect(input)]): return
			bounds.append({"window_width":width, "reference":str(label.get_global_rect()), "composer":str(input.get_global_rect())})
		pages.append({"name":title, "module":module, "preview":label.text, "bounds":bounds, "composer":input.get_instance_id()})
		input.text = "inspect " + title
		var deadline := Time.get_ticks_msec() + 12000
		while send.disabled and Time.get_ticks_msec() < deadline: await create_timer(0.1).timeout
		if not _check(not send.disabled, "Loopback connection unavailable"): return
		send.pressed.emit()
		deadline = Time.get_ticks_msec() + 18000
		while not sidebar.find_child("Stop", true, false).disabled and Time.get_ticks_msec() < deadline:
			await create_timer(0.1).timeout
		if not _check(input.text.is_empty() and not label.visible, "Page reference not consumed: " + label.text): return
		sidebar.close()
		await _settle_layout()
		if note:
			if not _check(note.text == PRIVATE_DRAFT, "Plugin draft changed"): return
			note.grab_focus()
			if not await _invoke_workbench(): return
			page.title = "Renamed Notes"
			input.text = "only the typed question"
			send.pressed.emit()
			if not _check(label.text.contains("失效") and input.text == "only the typed question", "Changed page was sent"): return
			label.pressed.emit()
			if not _check(not label.visible, "Removal failed"): return
			send.pressed.emit()
			deadline = Time.get_ticks_msec() + 18000
			while not sidebar.find_child("Stop", true, false).disabled and Time.get_ticks_msec() < deadline:
				await create_timer(0.1).timeout
			if not _check(input.text.is_empty() and not label.visible and note.text == PRIVATE_DRAFT, "Removed reference reappeared"): return
	print("PAGE_RESULT=" + JSON.stringify(pages))
	quit()
