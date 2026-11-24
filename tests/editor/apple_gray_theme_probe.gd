@tool
extends SceneTree

var failures: Array[String] = []
var samples: Array[Dictionary] = []

func _initialize() -> void:
	run.call_deferred()

func luminance(c: Color) -> float:
	var linear := c.srgb_to_linear()
	return linear.r * 0.2126 + linear.g * 0.7152 + linear.b * 0.0722

func run() -> void:
	await create_timer(1.0).timeout
	var settings := EditorInterface.get_editor_settings()
	var base := EditorInterface.get_base_control()
	for preset in ["Apple Gray", "Apple Gray Dark", "Default", "Light"]:
		settings.set_setting("interface/theme/color_preset", preset)
		settings.settings_changed.emit()
		root.propagate_notification(10000)
		await create_timer(0.5).timeout
		var bg := base.get_theme_color("base_color", "Editor")
		var fg := base.get_theme_color("font_color", "Editor")
		if preset == "Apple Gray Dark" and bg.r > 0.3:
			failures.append("dark preset did not reach the actual controls")
		var composited := bg.blend(fg)
		var ratio := (maxf(luminance(bg), luminance(composited)) + 0.05) / (minf(luminance(bg), luminance(composited)) + 0.05)
		if ratio < 4.5:
			failures.append(preset + ": body contrast below 4.5")
		var normal := base.get_theme_stylebox("normal", "Button") as StyleBoxFlat
		var hover := base.get_theme_stylebox("hover", "Button") as StyleBoxFlat
		if normal.bg_color == hover.bg_color:
			failures.append(preset + ": hover is indistinguishable")
		if int(settings.get_setting("interface/theme/corner_radius")) != 6:
			failures.append(preset + ": preset overwrote radius")
		samples.append({"preset": preset, "contrast": ratio, "button_radius": normal.corner_radius_top_left})
	print(JSON.stringify({"failures": failures, "samples": samples}))
	quit(0 if failures.is_empty() else 1)
