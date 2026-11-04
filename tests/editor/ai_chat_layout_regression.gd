@tool
extends SceneTree

# Exercise the real dock in the real editor. Do not reconstruct its containers.
var dock: Control
var failures: Array[String] = []
var samples: Array[Dictionary] = []

func _initialize():
	_run.call_deferred()

func _check(ok: bool, reason: String):
	if not ok:
		failures.append(reason)

func _control(name: String) -> Control:
	return dock.find_child(name, true, false) as Control

func _settle():
	for i in range(12):
		await process_frame

func _visible_rect(control: Control) -> Rect2:
	var rect := control.get_global_rect()
	var parent := control.get_parent()
	while parent is Control:
		if parent.clip_contents:
			rect = rect.intersection(parent.get_global_rect())
		parent = parent.get_parent()
	return rect.intersection(Rect2(Vector2.ZERO, Vector2(root.size)))

func _sample(label: String):
	var item := {"case": label, "window": [root.size.x, root.size.y], "controls": {}}
	item["ancestors"] = []
	var ancestor: Node = dock
	while ancestor != null:
		if ancestor is Control:
			var bounds: Rect2 = ancestor.get_global_rect()
			var min_size: Vector2 = ancestor.get_combined_minimum_size()
			item.ancestors.append({"name": String(ancestor.name), "class": ancestor.get_class(), "rect": [bounds.position.x, bounds.position.y, bounds.size.x, bounds.size.y], "minimum": [min_size.x, min_size.y]})
		ancestor = ancestor.get_parent()
	item["layout_children"] = []
	for child in _control("ChatLayout").get_children():
		if child is Control and child.is_visible_in_tree():
			var min_size: Vector2 = child.get_combined_minimum_size()
			item.layout_children.append({"name": String(child.name), "class": child.get_class(), "minimum": [min_size.x, min_size.y]})
	var sub_agents := _control("SubAgentBar")
	if sub_agents != null:
		var minimum := sub_agents.get_combined_minimum_size()
		item["sub_agent_minimum"] = [minimum.x, minimum.y]
	for name in ["ModelPicker", "ChatInput", "Send", "Stop", "AddImage", "AdvancedToggle", "ChatScroll", "AgentTabs", "SelectorRow", "ActionRow", "ChatComposerPanel"]:
		var control := _control(name)
		_check(control != null, label + ": missing " + name)
		if control == null:
			continue
		var rect := control.get_global_rect()
		var visible := _visible_rect(control)
		var minimum := control.get_combined_minimum_size()
		item.controls[name] = {"rect": [rect.position.x, rect.position.y, rect.size.x, rect.size.y], "visible": [visible.size.x, visible.size.y], "minimum": [minimum.x, minimum.y]}
		_check(control.is_visible_in_tree() and rect.size.x > 0 and rect.size.y > 0, label + ": hidden or empty " + name)
		_check(visible.size.x >= rect.size.x - 2 and visible.size.y >= rect.size.y - 2, label + ": clipped " + name)
	var input := _control("ChatInput")
	_check(input.size.y >= 3 * input.get_line_height(), label + ": input lost three visible lines")
	_check(_control("ChatScroll").get_global_rect().end.y <= input.get_global_rect().position.y + 2, label + ": messages overlap composer")
	samples.append(item)
	if OS.get_environment("AI_LAYOUT_SCREENSHOTS") == "1" and ("collapsed" in label or "attachments" in label or "long draft" in label):
		var output := OS.get_environment("AI_LAYOUT_RESULT").get_basename() + "-" + label.replace(" ", "_")
		var rendered := root.get_texture().get_image()
		_check(rendered != null and not rendered.is_empty(), "Native viewport screenshot unavailable")
		if rendered != null and not rendered.is_empty():
			_check(rendered.save_png(output + ".png") == OK, "Cannot save native screenshot")
		var popup := dock.find_child("ChatSettingsDialog", true, false) as AcceptDialog
		if popup != null and popup.visible:
			var settings_image := popup.get_texture().get_image()
			if settings_image != null and not settings_image.is_empty():
				_check(settings_image.save_png(output + "-settings.png") == OK, "Cannot save settings screenshot")

func _text() -> String:
	var result := ""
	for node in _control("Messages").find_children("*", "RichTextLabel", true, false):
		result += node.get_parsed_text()
	return result

func _run():
	await create_timer(0.5).timeout
	dock = root.find_child("AI Chat", true, false) as Control
	if dock == null:
		push_error("AI Chat dock missing")
		quit(1)
		return
	var scale := float(OS.get_environment("AI_LAYOUT_SCALE"))
	_check(is_equal_approx(EditorInterface.get_editor_scale(), scale), "Actual editor scale differs from requested scale")
	EditorInterface.set_main_screen_editor("AI Chat")
	await _settle()
	var backend := _control("AIBackend") as OptionButton
	backend.select(0)
	backend.item_selected.emit(0)
	_control("APIEndpoint").text = OS.get_environment("AI_LAYOUT_ENDPOINT")
	_control("APIKey").text = "layout-fixture"
	_control("APIModel").text = "layout-model"
	_control("ConsultationOnly").button_pressed = true
	var picker := _control("ModelPicker") as OptionButton
	picker.clear()
	picker.add_item("Long model name ".repeat(25))
	picker.select(0)
	var input := _control("ChatInput") as TextEdit
	var tabs := _control("AgentTabs") as TabBar
	var toggle := _control("AdvancedToggle") as Button
	var image := Image.create(64, 64, false, Image.FORMAT_RGB8)
	image.fill(Color.CORNFLOWER_BLUE)
	var paths := PackedStringArray()
	for i in range(4):
		var path := ProjectSettings.globalize_path("res://layout_%d.png" % i)
		_check(image.save_png(path) == OK, "Failed to create attachment fixture")
		paths.append(path)
	# The normal editor minimum is 1024*EDSCALE. Explicitly relax it for this
	# narrow-viewport stress test and verify the requested width was achieved.
	root.min_size = Vector2i.ZERO
	for width in [int(OS.get_environment("AI_LAYOUT_WIDTH"))]:
		root.size = Vector2i(width, 900)
		await _settle()
		_check(root.size == Vector2i(width, 900), "Requested physical viewport was not achieved")
		picker.clear()
		picker.add_item("Long model name ".repeat(25))
		picker.select(0)
		toggle.button_pressed = false
		await _settle()
		_sample("%d collapsed" % width)
		toggle.button_pressed = true
		await _settle()
		_sample("%d settings" % width)
		var settings := _control("AdvancedSettingsScroll") as ScrollContainer
		_check(settings != null and settings.is_visible_in_tree(), "Settings scroll missing/hidden")
		if settings != null:
			_check(settings.get_v_scroll_bar().max_value > settings.size.y, "Settings do not have an independent scroll range")
			settings.scroll_vertical = int(settings.get_v_scroll_bar().max_value)
			await _settle()
			_sample("%d settings scrolled" % width)
		var popup := dock.find_child("ChatSettingsDialog", true, false) as AcceptDialog
		if popup != null:
			var before := input.get_global_rect()
			_check(popup.visible and not popup.exclusive, "Settings popup must be visible and nonexclusive")
			popup.hide()
			popup.canceled.emit()
			await _settle()
			_check(not toggle.button_pressed and not popup.visible, "Cancel left settings toggle latched")
			_check(input.get_global_rect() == before, "Settings popup changed composer rectangle")
			toggle.button_pressed = true
			await _settle()
			popup.hide()
			popup.confirmed.emit()
			await _settle()
			_check(not toggle.button_pressed, "Done left settings toggle latched")
			toggle.button_pressed = true
			await _settle()
		input.text = ("Long draft wraps within the composer. ".repeat(12) + "\n").repeat(25)
		input.text_changed.emit()
		await _settle()
		_sample("%d long draft" % width)
		dock.find_child("AIImagePicker", true, false).files_selected.emit(paths)
		await _settle()
		_check(_control("ImageAttachments").find_children("ImageThumbnail", "Button", true, false).size() == 4, "Four attachment thumbnails not rendered")
		_sample("%d settings + attachments" % width)
		input.text = "DRAFT_%d" % width
		input.text_changed.emit()
		var first := tabs.current_tab
		_control("AddAgent").pressed.emit()
		await _settle()
		_check(input.text.is_empty(), "New session inherited draft")
		tabs.current_tab = first
		await _settle()
		_check(input.text == "DRAFT_%d" % width, "Session switch lost draft")
		_check(_control("ImageAttachments").find_children("ImageThumbnail", "Button", true, false).size() == 4, "Session switch lost attachments")
		_sample("%d switched session" % width)
		for i in range(4):
			var buttons := _control("ImageAttachments").find_children("RemoveImage", "Button", true, false)
			if not buttons.is_empty():
				buttons[0].pressed.emit()
		await _settle()
		toggle.button_pressed = false
		input.text = "layout-response"
		_control("Send").pressed.emit()
		var deadline := Time.get_ticks_msec() + 10000
		while not _control("Stop").disabled and Time.get_ticks_msec() < deadline:
			await process_frame
		if "LAYOUT_REPLY" not in _text():
			print("LAYOUT_SEND_DIAGNOSTIC ", _text())
		_check(_control("Stop").disabled and "LAYOUT_REPLY" in _text(), "Send did not complete via loopback fixture")
		await _settle()
		_sample("%d long response" % width)
		input.text = "layout-stop"
		_control("Send").pressed.emit()
		await create_timer(0.1).timeout
		_check(not _control("Stop").disabled, "Stop never became available")
		_sample("%d sending" % width)
		_control("Stop").pressed.emit()
		await _settle()
		_check(_control("Stop").disabled and not _control("Send").disabled, "Stop did not restore composer controls")
		for screen in ["3D", "Script"]:
			EditorInterface.set_main_screen_editor(screen)
			await _settle()
			_check(not dock.is_visible_in_tree(), "AI Chat stayed visible on " + screen)
			var normal_menu := false
			for menu in root.find_children("*", "MenuBar", true, false):
				if menu.theme_type_variation == "MainMenuBar" and menu.is_visible_in_tree():
					normal_menu = true
			_check(normal_menu, "Full editor menu was not restored on " + screen)
			EditorInterface.set_main_screen_editor("AI Chat")
			await _settle()
			_sample("%d return from %s" % [width, screen])
	var report := {"scale": EditorInterface.get_editor_scale(), "samples": samples, "failures": failures}
	FileAccess.open(OS.get_environment("AI_LAYOUT_RESULT"), FileAccess.WRITE).store_string(JSON.stringify(report, "\t"))
	print("AI_LAYOUT_RESULT ", JSON.stringify({"scale": scale, "samples": samples.size(), "failures": failures}))
	quit(0 if failures.is_empty() else 1)
