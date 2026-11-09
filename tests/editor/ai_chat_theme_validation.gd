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
		for name in ["ChatInput", "Send", "Stop", "AdvancedToggle", "AddImage"]:
			var control := dock.find_child(name, true, false) as Control
			_check(control != null and control.is_visible_in_tree() and control.size.x > 0 and control.size.y > 0, preset + ": unavailable " + name)
		dock.find_child("AdvancedToggle", true, false).pressed.emit()
		await process_frame
		_check(not dock.is_visible_in_tree(), preset + ": settings navigation failed")
		EditorInterface.set_main_screen_editor("AI Chat")
		await process_frame
		_check(input.text == "主题切换后保留的长草稿 / draft and code: print(42)", preset + ": navigation lost draft")
		samples.append({"preset": preset, "foreground": foreground.to_html(), "background": background.to_html(), "input_contrast": ratio, "editor_base": dock.get_theme_color("base_color", "Editor").to_html()})
	var report := {"scope": "headless theme colors, control geometry, focus signals and settings navigation; no pixel or provider acceptance", "samples": samples, "failures": failures}
	FileAccess.open(OS.get_environment("AI_THEME_REPORT"), FileAccess.WRITE).store_string(JSON.stringify(report, "\t"))
	print("AI_CHAT_THEME_RESULT=" + JSON.stringify(report))
	quit(0 if failures.is_empty() else 1)
