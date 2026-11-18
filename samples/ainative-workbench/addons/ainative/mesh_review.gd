extends SceneTree
# Render one generated GLB into evidence views for the independent vision reviewer.

func _initialize():
	run.call_deferred()


func run():
	var args = OS.get_cmdline_user_args()
	if args.size() != 1:
		printerr("Expected one private render request")
		quit(2)
		return
	var config = JSON.parse_string(FileAccess.get_file_as_string(args[0]))
	if not config is Dictionary or not FileAccess.file_exists(config.get("model", "")):
		printerr("Invalid render request")
		quit(2)
		return
	var output = str(config.output)
	if DirAccess.make_dir_recursive_absolute(output) != OK:
		quit(1)
		return
	var document = GLTFDocument.new()
	var state = GLTFState.new()
	if document.append_from_file(config.model, state) != OK:
		printerr("GLB decode failed")
		quit(1)
		return
	var scene = document.generate_scene(state)
	if scene == null:
		quit(1)
		return
	var yaw = config.get("yaw_degrees", 0.0)
	if not (typeof(yaw) in [TYPE_INT, TYPE_FLOAT]) or not is_finite(float(yaw)) or absf(float(yaw)) > 180.0:
		printerr("Invalid confirmed review orientation")
		quit(2)
		return
	# A source-bound frame corrects review evidence only; it never rewrites GLB
	# geometry. Missing metadata retains the original zero-yaw render behavior.
	scene.rotation_degrees.y = float(yaw)
	var viewport = SubViewport.new()
	viewport.size = Vector2i(1024, 1024)
	viewport.own_world_3d = true
	viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	root.add_child(viewport)
	var stage = Node3D.new()
	viewport.add_child(stage)
	stage.add_child(scene)
	var environment = Environment.new()
	environment.background_mode = Environment.BG_COLOR
	environment.background_color = Color(0.035, 0.045, 0.065)
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.ambient_light_color = Color.WHITE
	environment.ambient_light_energy = 0.65
	var world_environment = WorldEnvironment.new()
	world_environment.environment = environment
	stage.add_child(world_environment)
	var camera = Camera3D.new()
	camera.fov = 42
	camera.near = 0.001
	camera.far = 10000
	stage.add_child(camera)
	camera.current = true
	var fill = DirectionalLight3D.new()
	fill.light_energy = 0.8
	stage.add_child(fill)
	var rim = DirectionalLight3D.new()
	rim.rotation_degrees = Vector3(-35, 145, 0)
	rim.light_energy = 1.1
	stage.add_child(rim)
	await process_frame
	var bounds = AABB()
	var found = false
	for mesh in scene.find_children("*", "MeshInstance3D", true, false):
		var box = mesh.global_transform * mesh.get_aabb()
		bounds = box if not found else bounds.merge(box)
		found = true
	if scene is MeshInstance3D:
		bounds = scene.global_transform * scene.get_aabb()
		found = true
	if not found or bounds.size.length() <= 0.000001:
		printerr("No nonempty rendered geometry")
		quit(1)
		return
	var center = bounds.get_center()
	var radius = maxf(bounds.size.length() * 0.5, 0.001)
	var distance = radius / sin(deg_to_rad(camera.fov * 0.5)) * 1.18
	# Frame the complete head and neck, not merely the upper torso. Three
	# independent directions make horizontal face cuts and neck gaps visible.
	var head_center = Vector3(center.x, bounds.end.y - bounds.size.y * 0.12, center.z)
	var head_scale = maxf(bounds.size.y * 0.38, 0.001) / distance
	# Anatomical sides, not screen-left/screen-right: with a +Z-facing
	# character, its right side is observed from -X.
	var definitions = [
		["front", Vector3(0, 0.05, 1), center, 1.0],
		["right", Vector3(-1, 0.05, 0), center, 1.0],
		["back", Vector3(0, 0.05, -1), center, 1.0],
		["left", Vector3(1, 0.05, 0), center, 1.0],
		["top", Vector3(0, 1, 0.001), center, 1.0],
		["detail_upper_front", Vector3(0, 0.03, 1), center + Vector3(0, bounds.size.y * 0.25, 0), 0.55],
		["detail_lower_front", Vector3(0, 0.03, 1), center - Vector3(0, bounds.size.y * 0.25, 0), 0.55],
		["head_front", Vector3(0, 0.02, 1), head_center, head_scale],
		["head_three_quarter", Vector3(-1, 0.02, 1), head_center, head_scale],
		["head_side", Vector3(-1, 0.02, 0), head_center, head_scale]
	]
	var views = []
	for definition in definitions:
		var target = definition[2] as Vector3
		camera.position = target + (definition[1] as Vector3).normalized() * distance * float(definition[3])
		var direction = (camera.position - target).normalized()
		var up = Vector3.FORWARD if absf(direction.dot(Vector3.UP)) > 0.999 else Vector3.UP
		camera.look_at(target, up)
		fill.position = camera.position
		fill.look_at(target,up)
		await process_frame
		await RenderingServer.frame_post_draw
		var image = viewport.get_texture().get_image()
		var path = output.path_join(str(definition[0]) + ".png")
		if image.is_empty() or image.save_png(path) != OK:
			printerr("Rendered view readback failed")
			quit(1)
			return
		views.append({"view": definition[0], "path": path, "sha256": FileAccess.get_sha256(path)})
	var report = {
		"model_sha256": FileAccess.get_sha256(config.model),
		"yaw_degrees": float(yaw),
		"script_sha256": str(config.get("script_sha256", "")),
		"camera_convention": "anatomical_front_plus_z_right_minus_x_y_up",
		"views": views,
	}
	var stream = FileAccess.open(output.path_join("views.json"), FileAccess.WRITE)
	if stream == null:
		quit(1)
		return
	stream.store_string(JSON.stringify(report, "\t"))
	stream.close()
	scene.free()
	quit()
