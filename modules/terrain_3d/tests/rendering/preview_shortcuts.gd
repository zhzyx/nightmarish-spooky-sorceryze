extends "res://demo/src/HeightVTPreview.gd"
## Exercise the demo's actual key routing and the state shown in the preview window.

var failures := 0

func _initialize() -> void:
	super._initialize()
	run.call_deferred()

func check(condition: bool, message: String) -> void:
	if not condition:
		failures += 1
		push_error(message)

func press(keycode: Key, repeats := 0) -> void:
	var event := InputEventKey.new()
	event.keycode = keycode
	event.pressed = true
	root.push_input(event, true)
	for i in repeats:
		var repeat := event.duplicate() as InputEventKey
		repeat.echo = true
		root.push_input(repeat, true)
	var release := event.duplicate() as InputEventKey
	release.pressed = false
	root.push_input(release, true)

func capture(name: String) -> void:
	var directory := OS.get_environment("T3D_CAPTURE_DIR")
	if not directory.is_empty():
		check(root.get_texture().get_image().save_png(directory.path_join(name)) == OK, "Could not save " + name)

func run() -> void:
	for frame in 90:
		await RenderingServer.frame_post_draw
	check(hud.is_visible_in_tree() and root.get_visible_rect().encloses(hud.get_global_rect()), "Shortcut panel must be visible inside the viewport")
	var source: Label = hud.get_node("%SourceState")
	var height: Label = hud.get_node("%HeightState")
	var material_state: Label = hud.get_node("%MaterialState")
	check(height.text.begins_with("高度 VT") and source.text == "关闭", "Initial height and source labels")
	capture("terrain-preview.png")
	press(KEY_F8, 2)
	await RenderingServer.frame_post_draw
	check(source.text == "开启" and terrain.material.get_shader_param("_t3d_material_rvt_sources") == true, "Holding F8 must enable source colors once")
	capture("terrain-page-sources.png")
	press(KEY_F8)
	check(source.text == "关闭" and terrain.material.get_shader_param("_t3d_material_rvt_sources") == false, "Second F8 must restore normal shading")
	press(KEY_F7)
	check(material_state.text == "直接着色" and terrain.material.get_shader_param("_t3d_material_rvt_bypass") == true, "F7 must show direct shading")
	press(KEY_F7)
	check(material_state.text.contains("RVT") and terrain.material.get_shader_param("_t3d_material_rvt_bypass") == false, "F7 must restore cached shading")
	press(KEY_F6)
	check(height.text == "原生高度图" and cv.get_value("r.Terrain3D.VTHeight") == 0, "F6 must show native heights")
	press(KEY_F6)
	check(height.text.begins_with("高度 VT") and cv.get_value("r.Terrain3D.VTHeight") != 0, "F6 must restore VT heights")
	print("Terrain3D preview shortcut failures=", failures)
	quit(1 if failures else 0)
