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
	var viewport_size = config.get("viewport_size", 1024)
	if not (typeof(viewport_size) in [TYPE_INT, TYPE_FLOAT]) or not is_finite(float(viewport_size)) or int(viewport_size) < 256 or int(viewport_size) > 1024:
		printerr("Invalid render viewport size")
		quit(2)
		return
	var viewport = SubViewport.new()
	viewport.size = Vector2i(int(viewport_size), int(viewport_size))
	viewport.own_world_3d = true
	viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	root.add_child(viewport)
	var stage = Node3D.new()
	viewport.add_child(stage)
	stage.add_child(scene)
	# Optional source-bound triangle ID evidence uses the exact same cameras.
	# Two 12-bit passes avoid subtle 24-bit color quantization entirely.
	var triangle_id_scenes = []
	var triangle_id_model = str(config.get("triangle_id_model", ""))
	var triangle_id_model_high = str(config.get("triangle_id_model_high", ""))
	var triangle_id_models = [triangle_id_model, triangle_id_model_high]
	var id_shader = Shader.new()
	id_shader.code = "shader_type spatial; render_mode unshaded, cull_back; void fragment() { ALBEDO = vec3(UV, UV2.x); }"
	var id_material = ShaderMaterial.new()
	id_material.shader = id_shader
	for id_path in triangle_id_models:
		if id_path.is_empty(): continue
		if not FileAccess.file_exists(id_path):
			printerr("Triangle ID model missing")
			quit(2)
			return
		var id_document = GLTFDocument.new()
		var id_state = GLTFState.new()
		if id_document.append_from_file(id_path, id_state) != OK:
			printerr("Triangle ID GLB decode failed")
			quit(1)
			return
		var id_scene = id_document.generate_scene(id_state)
		if id_scene == null:
			quit(1)
			return
		id_scene.rotation_degrees.y = float(yaw)
		stage.add_child(id_scene)
		for id_mesh in id_scene.find_children("*", "MeshInstance3D", true, false):
			id_mesh.material_override = id_material
		if id_scene is MeshInstance3D:
			id_scene.material_override = id_material
		id_scene.hide()
		triangle_id_scenes.append(id_scene)
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
	var fixed_bounds = config.get("camera_bounds")
	if fixed_bounds is Dictionary:
		var minimum = fixed_bounds.get("min")
		var maximum = fixed_bounds.get("max")
		if not minimum is Array or not maximum is Array or minimum.size() != 3 or maximum.size() != 3:
			printerr("Invalid fixed camera bounds")
			quit(2)
			return
		var minimum_vector = Vector3(float(minimum[0]), float(minimum[1]), float(minimum[2]))
		var maximum_vector = Vector3(float(maximum[0]), float(maximum[1]), float(maximum[2]))
		if not minimum_vector.is_finite() or not maximum_vector.is_finite() or (maximum_vector - minimum_vector).length() <= 0.000001:
			printerr("Invalid fixed camera bounds")
			quit(2)
			return
		bounds = AABB(minimum_vector, maximum_vector - minimum_vector)
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
	var triangle_id_maps = []
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
		if not triangle_id_scenes.is_empty():
			scene.hide()
			var normal_tonemap = environment.tonemap_mode
			environment.tonemap_mode = Environment.TONE_MAPPER_LINEAR
			environment.tonemap_exposure = 1.0
			var pass_receipt = {"view": definition["view"]}
			for pass_index in triangle_id_scenes.size():
				var id_scene = triangle_id_scenes[pass_index]
				id_scene.show()
				await process_frame
				await RenderingServer.frame_post_draw
				var id_image = viewport.get_texture().get_image()
				var pass_name = "low" if pass_index == 0 else "high"
				var id_path = output.path_join(str(definition["view"]) + ".triangles." + pass_name + ".png")
				if id_image.is_empty() or id_image.save_png(id_path) != OK:
					printerr("Triangle ID view readback failed")
					quit(1)
					return
				if pass_index == 0:
					pass_receipt["path"] = id_path
					pass_receipt["sha256"] = FileAccess.get_sha256(id_path)
				else:
					pass_receipt["high_path"] = id_path
					pass_receipt["high_sha256"] = FileAccess.get_sha256(id_path)
				id_scene.hide()
			triangle_id_maps.append(pass_receipt)
			environment.tonemap_mode = normal_tonemap
			scene.show()
			await process_frame
	var component_receipts = []
	var candidates = config.get("components", [])
	if not candidates is Array:
		printerr("Invalid component evidence request")
		quit(2)
		return
	scene.free()
	scene = null
	for candidate_index in candidates.size():
		var candidate = candidates[candidate_index]
		if not candidate is Dictionary or not candidate.get("component_id", "") is String or not FileAccess.file_exists(candidate.get("model", "")):
			printerr("Invalid component evidence entry")
			quit(2)
			return
		var candidate_document = GLTFDocument.new()
		var candidate_state = GLTFState.new()
		if candidate_document.append_from_file(candidate.model, candidate_state) != OK:
			printerr("Component GLB decode failed")
			quit(1)
			return
		var candidate_scene = candidate_document.generate_scene(candidate_state)
		if candidate_scene == null:
			quit(1)
			return
		stage.add_child(candidate_scene)
		await process_frame
		var candidate_bounds = AABB()
		var candidate_found = false
		for mesh in candidate_scene.find_children("*", "MeshInstance3D", true, false):
			var box = mesh.global_transform * mesh.get_aabb()
			candidate_bounds = box if not candidate_found else candidate_bounds.merge(box)
			candidate_found = true
		if candidate_scene is MeshInstance3D:
			candidate_bounds = candidate_scene.global_transform * candidate_scene.get_aabb()
			candidate_found = true
		if not candidate_found or candidate_bounds.size.length() <= 0.000001:
			printerr("No nonempty component geometry")
			quit(1)
			return
		var candidate_center = candidate_bounds.get_center()
		var candidate_radius = maxf(candidate_bounds.size.length() * 0.5, 0.001)
		var candidate_distance = candidate_radius / sin(deg_to_rad(camera.fov * 0.5)) * 1.18
		var candidate_views = []
		for direction in ["front", "back"]:
			var offset = Vector3(0, 0.03, 1) if direction == "front" else Vector3(0, 0.03, -1)
			camera.position = candidate_center + offset.normalized() * candidate_distance
			camera.look_at(candidate_center, Vector3.UP)
			fill.position = camera.position
			fill.look_at(candidate_center, Vector3.UP)
			await process_frame
			await RenderingServer.frame_post_draw
			var image = viewport.get_texture().get_image()
			var path = output.path_join("component-" + str(candidate_index).pad_zeros(3) + "-" + direction + ".png")
			if image.is_empty() or image.save_png(path) != OK:
				printerr("Component rendered view readback failed")
				quit(1)
				return
			candidate_views.append({"view": direction, "path": path, "sha256": FileAccess.get_sha256(path)})
		component_receipts.append({
			"component_id": candidate.component_id,
			"model_sha256": FileAccess.get_sha256(candidate.model),
			"views": candidate_views,
		})
		candidate_scene.free()
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
		"components": component_receipts,
		"triangle_id_maps": triangle_id_maps,
		"triangle_id_model_sha256": FileAccess.get_sha256(triangle_id_model) if not triangle_id_model.is_empty() else "",
		"triangle_id_model_high_sha256": FileAccess.get_sha256(triangle_id_model_high) if not triangle_id_model_high.is_empty() else "",
	}
	var stream = FileAccess.open(output.path_join("views.json"), FileAccess.WRITE)
	if stream == null:
		quit(1)
		return
	stream.store_string(JSON.stringify(report, "\t"))
	stream.close()
	quit()
