@tool
extends SceneTree

var failures: Array[String] = []

func check(ok: bool, detail: String) -> void:
	if not ok:
		failures.append(detail)

func _initialize() -> void:
	run.call_deferred()

func run() -> void:
	await create_timer(1.0).timeout
	var base := EditorInterface.get_base_control()
	var settings := EditorInterface.get_editor_settings()
	var consumers: Array[PanelContainer] = []
	for control in base.find_children("*", "PanelContainer", true, false):
		if control.theme_type_variation == &"EditorGlassPanel":
			consumers.append(control)
	check(consumers.size() >= 10, "2D and four 3D viewport information/timing overlays must use glass")
	for consumer in consumers:
		check(consumer.material is ShaderMaterial, "actual editor overlay missing glass material")
	var panel := PanelContainer.new()
	panel.theme_type_variation = "EditorGlassPanel"
	base.add_child(panel)
	await process_frame
	check(panel.material is ShaderMaterial, "glass variation must install its material")
	settings.set_setting("interface/theme/reduce_transparency", true)
	root.propagate_notification(10000)
	await create_timer(0.3).timeout
	for consumer in consumers:
		check(consumer.material == null, "actual editor overlay ignored reduced transparency")
		var backdrop := consumer.get_theme_stylebox("panel") as StyleBoxFlat
		check(backdrop != null and is_equal_approx(backdrop.bg_color.a, 1.0), "reduced transparency overlay must have an opaque background")
	check(panel.material == null, "reduced transparency must restore an opaque unshaded panel")
	settings.set_setting("interface/theme/reduce_transparency", false)
	root.propagate_notification(10000)
	await create_timer(0.3).timeout
	check(panel.material is ShaderMaterial, "glass must return after enabling transparency")
	var own := ShaderMaterial.new()
	panel.material = own
	panel.add_theme_constant_override("background_blur", 0)
	await process_frame
	check(panel.material == own, "custom materials must not be overwritten")
	panel.queue_free()
	await process_frame
	print(JSON.stringify({"failures": failures}))
	quit(0 if failures.is_empty() else 1)
