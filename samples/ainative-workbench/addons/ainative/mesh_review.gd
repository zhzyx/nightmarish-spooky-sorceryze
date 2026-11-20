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
	# The Python review plan supplies only regions and directions implemented
	# here. Legacy requests retain the original fixed ten-view evidence set.
	var definitions = config.get("render_views", [])
	if definitions.is_empty():
		definitions = [
			{"view": "front", "region": "full_subject", "direction": "front"},
			{"view": "right", "region": "full_subject", "direction": "right"},
			{"view": "back", "region": "full_subject", "direction": "back"},
			{"view": "left", "region": "full_subject", "direction": "left"},
			{"view": "top", "region": "full_subject", "direction": "top"},
			{"view": "detail_upper_front", "region": "upper_body", "direction": "front"},
			{"view": "detail_lower_front", "region": "lower_body", "direction": "front"},
			{"view": "head_front", "region": "head", "direction": "front"},
			{"view": "head_three_quarter", "region": "head", "direction": "three_quarter"},
			{"view": "head_side", "region": "head", "direction": "side"}
		]
	var views = []
	for definition in definitions:
		var target = center
		var scale = 1.0
		match str(definition.get("region", "full_subject")):
			"upper_body":
				target = center + Vector3(0, bounds.size.y * 0.25, 0)
				scale = 0.55
			"lower_body":
				target = center - Vector3(0, bounds.size.y * 0.25, 0)
				scale = 0.55
			"head":
				target = Vector3(center.x, bounds.end.y - bounds.size.y * 0.12, center.z)
				scale = maxf(bounds.size.y * 0.38, 0.001) / distance
			"hand_left":
				target = Vector3(bounds.end.x - bounds.size.x * 0.04, center.y, center.z)
				scale = maxf(bounds.size.y * 0.28, 0.001) / distance
			"hand_right":
				target = Vector3(bounds.position.x + bounds.size.x * 0.04, center.y, center.z)
				scale = maxf(bounds.size.y * 0.28, 0.001) / distance
			"object_detail":
				scale = 0.65
		var offset = Vector3(0, 0.03, 1)
		match str(definition.get("direction", "front")):
			"right":
				offset = Vector3(-1, 0.05, 0)
			"back":
				offset = Vector3(0, 0.03, -1)
			"left":
				offset = Vector3(1, 0.05, 0)
			"top":
				offset = Vector3(0, 1, 0.001)
			"three_quarter":
				offset = Vector3(-1, 0.02, 1)
			"side":
				offset = Vector3(-1, 0.02, 0)
		camera.position = target + offset.normalized() * distance * scale
		var direction = (camera.position - target).normalized()
		var up = Vector3.FORWARD if absf(direction.dot(Vector3.UP)) > 0.999 else Vector3.UP
		camera.look_at(target, up)
		fill.position = camera.position
		fill.look_at(target,up)
		await process_frame
		await RenderingServer.frame_post_draw
		var image = viewport.get_texture().get_image()
		var path = output.path_join(str(definition["view"]) + ".png")
		if image.is_empty() or image.save_png(path) != OK:
			printerr("Rendered view readback failed")
			quit(1)
			return
		views.append({"view": definition["view"], "path": path, "sha256": FileAccess.get_sha256(path)})
	var receipt_plan = config.get("review_plan")
	if receipt_plan is Dictionary and receipt_plan.has("schema_version"):
		receipt_plan = receipt_plan.duplicate(true)
		receipt_plan["schema_version"] = int(receipt_plan["schema_version"])
	var report = {
		"model_sha256": FileAccess.get_sha256(config.model),
		"yaw_degrees": float(yaw),
		"review_plan": receipt_plan,
		"review_plan_sha256": str(config.get("review_plan_sha256", "")),
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
