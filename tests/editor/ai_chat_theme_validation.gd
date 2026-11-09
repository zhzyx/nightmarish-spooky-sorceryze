@tool
extends SceneTree

var failures: Array[String] = []
var samples: Array[Dictionary] = []

func _initialize():
	_run.call_deferred()

func _check(ok: bool, message: String):
	if not ok:
		failures.append(message)

func _luminance(color: Color) -> float:
	var linear := color.srgb_to_linear()
	return 0.2126 * linear.r + 0.7152 * linear.g + 0.0722 * linear.b

func _run():
	await create_timer(0.5).timeout
	var dock := root.find_child("AI Chat", true, false) as Control
	if dock == null:
		push_error("AI Chat dock missing")
		quit(1)
		return
	EditorInterface.set_main_screen_editor("AI Chat")
	var input := dock.find_child("ChatInput", true, false) as TextEdit
	var backend := dock.get_ai_settings_control().find_child("AIBackend", true, false) as OptionButton
	backend.select(0)
	backend.item_selected.emit(0)
	dock.get_ai_settings_control().find_child("APIEndpoint", true, false).text = OS.get_environment("AI_THEME_ENDPOINT")
	dock.get_ai_settings_control().find_child("APIModel", true, false).text = "theme-fixture"
	var key := dock.get_ai_settings_control().find_child("APIKey", true, false) as LineEdit
	key.text = "theme-fixture-key"
	key.text_changed.emit(key.text)
	await create_timer(0.5).timeout
	var deadline := Time.get_ticks_msec() + 10000
	while backend.disabled and Time.get_ticks_msec() < deadline:
		await process_frame
	dock.find_child("ConsultationOnly", true, false).button_pressed = true
	var initial_message_count := dock.find_children("*Message", "HBoxContainer", true, false).size()
	input.text = "firstsecond"
	input.set_caret_column(5)
	var newline := InputEventKey.new()
	newline.keycode = KEY_ENTER
	newline.pressed = true
	newline.shift_pressed = true
	input.gui_input.emit(newline)
	_check(input.text == "first\nsecond", "Shift+Enter did not insert a newline")
	_check(dock.find_children("*Message", "HBoxContainer", true, false).size() == initial_message_count, "Shift+Enter unexpectedly created a message")
	input.text = "Theme contrast seed"
	var send_key := InputEventKey.new()
	send_key.keycode = KEY_ENTER
	send_key.pressed = true
	input.gui_input.emit(send_key)
	_check(input.text.is_empty(), "Enter did not submit and clear the composer")
	var reply_seen := false
	while not reply_seen and Time.get_ticks_msec() < deadline:
		for label in dock.find_children("*", "RichTextLabel", true, false):
			reply_seen = reply_seen or "THEME_REPLY" in label.get_parsed_text()
		await process_frame
	_check(reply_seen, "Loopback theme message did not arrive")
	# Keep populated controls in an inactive Agent while another composer is
	# active; changing theme must update archived cards without rebuilding them.
	dock.find_child("AddAgent", true, false).pressed.emit()
	await process_frame
	var original_message_ids: Array[int] = []
	for row in dock.find_children("*Message", "HBoxContainer", true, false):
		original_message_ids.append(row.get_instance_id())
	_check(dock.find_child("AgentTabs", true, false).tab_count == 2, "Archived Agent precondition failed")
	var settings := EditorInterface.get_editor_settings()
	settings.set_setting("interface/theme/follow_system_theme", false)
	for preset in ["Default", "Light", "Default"]:
		settings.set_setting("interface/theme/color_preset", preset)
		root.propagate_notification(EditorSettings.NOTIFICATION_EDITOR_SETTINGS_CHANGED)
		await create_timer(1.0).timeout
		input.text = "主题切换后保留的长草稿 / draft and code: print(42)"
		input.grab_focus()
		await process_frame
		_check(input.has_focus(), preset + ": composer cannot receive focus")
		var foreground := input.get_theme_color("font_color")
		var style := input.get_theme_stylebox("normal") as StyleBoxFlat
		_check(style != null, preset + ": missing input background")
		if style == null:
			continue
		var background := style.bg_color
		var rendered_foreground := background.blend(foreground)
		var ratio := (maxf(_luminance(rendered_foreground), _luminance(background)) + 0.05) / (minf(_luminance(rendered_foreground), _luminance(background)) + 0.05)
		_check(ratio >= 4.5, preset + ": input text contrast below 4.5:1")
		_check((background.get_luminance() > 0.5) == (preset == "Light"), preset + ": actual theme did not change")
		var message_contrasts: Array[float] = []
		for row in dock.find_children("*Message", "HBoxContainer", true, false):
			for label in row.find_children("*", "RichTextLabel", true, false):
				if label.get_parsed_text().is_empty():
					continue
				var panel: Node = label.get_parent()
				while panel != null and not panel is PanelContainer:
					panel = panel.get_parent()
				if panel is PanelContainer:
					var card := panel.get_theme_stylebox("panel") as StyleBoxFlat
					if card != null:
						var text: Color = card.bg_color.blend(label.get_theme_color("default_color"))
						var contrast := (maxf(_luminance(text), _luminance(card.bg_color)) + 0.05) / (minf(_luminance(text), _luminance(card.bg_color)) + 0.05)
						message_contrasts.append(contrast)
						_check(contrast >= 4.5, preset + ": existing message text contrast below 4.5:1")
		_check(message_contrasts.size() >= 2, preset + ": user/reply message bodies not checked")
		var current_message_ids: Array[int] = []
		for row in dock.find_children("*Message", "HBoxContainer", true, false):
			current_message_ids.append(row.get_instance_id())
		_check(current_message_ids == original_message_ids, preset + ": theme change rebuilt message controls")
		for name in ["ChatInput", "Send", "Stop", "AdvancedToggle", "AddImage"]:
			var control := dock.find_child(name, true, false) as Control
			_check(control != null and control.is_visible_in_tree() and control.size.x > 0 and control.size.y > 0, preset + ": unavailable " + name)
		dock.find_child("AdvancedToggle", true, false).pressed.emit()
		await process_frame
		_check(not dock.is_visible_in_tree(), preset + ": settings navigation failed")
		EditorInterface.set_main_screen_editor("AI Chat")
		await process_frame
		_check(input.text == "主题切换后保留的长草稿 / draft and code: print(42)", preset + ": navigation lost draft")
		samples.append({"preset": preset, "foreground": foreground.to_html(), "background": background.to_html(), "input_contrast": ratio, "editor_base": dock.get_theme_color("base_color", "Editor").to_html(), "message_contrasts": message_contrasts})
	var report := {"scope": "headless theme colors, control geometry, focus signals and settings navigation; no pixel or provider acceptance", "samples": samples, "failures": failures}
	FileAccess.open(OS.get_environment("AI_THEME_REPORT"), FileAccess.WRITE).store_string(JSON.stringify(report, "\t"))
	print("AI_CHAT_THEME_RESULT=" + JSON.stringify(report))
	quit(0 if failures.is_empty() else 1)
