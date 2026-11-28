extends SceneTree
## Run in Forward+ with --resolution 480x270 --fixed-fps 60. T3D_CAPTURE_DIR saves the masks' source images.

var terrain: Terrain3D
var camera := Camera3D.new()
var cvars: Object
var failures := 0
var capture_dir := OS.get_environment("T3D_CAPTURE_DIR")

const STOPS := [
	["valley", Vector3(217.6919,106.7327,-1832.622), Vector3(0.96,0.0,-0.28)],
	["ridge", Vector3(3550,510,-4750), Vector3(-0.65,-0.12,0.75)],
	["high", Vector3(2200,2950,-4500), Vector3(-0.32,-0.52,0.8)],
	["outside", Vector3(15360,960,-1400), Vector3(0.95,-0.12,0.3)],
]

func _initialize() -> void:
	run.call_deferred()

func check(ok: bool, message: String) -> void:
	if not ok:
		push_error(message)
		failures += 1

func frames(count: int) -> void:
	for _frame in count:
		await RenderingServer.frame_post_draw

func set_pose(stop: Array) -> void:
	camera.position = stop[1]
	camera.look_at(camera.position + stop[2], Vector3.UP)

func silhouette(label: String) -> PackedByteArray:
	var img := root.get_texture().get_image()
	if not capture_dir.is_empty():
		img.save_png(capture_dir.path_join(label + ".png"))
	img.convert(Image.FORMAT_RGBA8)
	var pixels := img.get_data()
	var mask := PackedByteArray()
	mask.resize(img.get_width() * img.get_height())
	for i in mask.size():
		var j := i * 4
		# Ignore transparent clear and the magenta sky. Only Terrain3D is on the camera layer.
		var sky := pixels[j] > 210 and pixels[j+1] < 35 and pixels[j+2] > 210
		mask[i] = int(pixels[j+3] >= 128 and not sky)
	return mask

func metrics(a: PackedByteArray, b: PackedByteArray) -> Dictionary:
	var width := root.size.x
	var height := root.size.y
	var xor_pixels := 0
	var total := 0
	var reference_pixels := 0
	var horizon := PackedInt32Array()
	for x in width:
		var first_a := height
		var first_b := height
		for y in height:
			var i := y * width + x
			if a[i]:
				reference_pixels += 1
				first_a = mini(first_a, y)
			if b[i]:
				first_b = mini(first_b, y)
			xor_pixels += int(a[i] != b[i])
			total += int(a[i] != 0 or b[i] != 0)
		horizon.append(absi(first_a - first_b))
	horizon.sort()
	return {
		"reference": reference_pixels, "xor": xor_pixels,
		"frame_fraction": float(xor_pixels) / a.size(),
		"union_fraction": float(xor_pixels) / maxi(1, total),
		"sky_p95": horizon[int(width * 0.95)], "sky_max": horizon[width - 1],
	}

func fly(mode: int, vt: bool, background: int, name: String) -> Array:
	cvars.set_value("r.Terrain3D.Mode", mode)
	cvars.set_value("r.Terrain3D.VTHeight", int(vt))
	terrain.material.world_background = background
	set_pose(STOPS[0])
	await frames(30)
	var samples := []
	for stop_index in [0,1,2,3,0]:
		var start := camera.global_transform
		set_pose(STOPS[stop_index])
		var finish := camera.global_transform
		var name_at_stop := "%s_%d_%s" % [name, samples.size(), STOPS[stop_index][0]]
		for i in 10:
			camera.global_transform = start.interpolate_with(finish, (i + 1) / 10.0)
			await frames(1)
			if i == 4:
				samples.append(silhouette(name_at_stop + "_moving"))
		await frames(80)
		samples.append(silhouette(name_at_stop + "_warm"))
	var grid: Vector4 = terrain.material.get_shader_param("_t3d_vt_grid")
	check(terrain.get_quadtree_multimesh_rid().is_valid() == (mode == 1), name + " did not select the requested geometry")
	check((grid.w > 0.5) == vt, name + " did not select the requested height source")
	return samples

func compare_paths(label: String, background: int) -> void:
	var clip := await fly(0, false, background, label + "_clip")
	var native := await fly(1, false, background, label + "_native")
	var virtual := await fly(1, true, background, label + "_vt")
	var max_xor := 0.0
	var max_sky := 0
	var max_native_xor := 0
	for i in clip.size():
		var name_at_pose := "%s %s %s" % [label, STOPS[[0,1,2,3,0][i/2]][0], "warm" if i % 2 else "moving"]
		var source := metrics(native[i], virtual[i])
		var footprint := metrics(clip[i], virtual[i])
		max_native_xor = maxi(max_native_xor, source.xor)
		check(source.frame_fraction <= 0.0025 and source.sky_p95 <= 2, name_at_pose + " diverged between height sources %s" % source)
		# NONE can contain only a few authored silhouette pixels. Use the full frame as
		# denominator there. FLAT/NOISE cover the horizon, so require overlap of both masks.
		if background == Terrain3DMaterial.NONE:
			check(footprint.frame_fraction <= 0.003 and footprint.sky_p95 <= 2, name_at_pose + " authored bounds changed %s" % footprint)
		else:
			check(footprint.reference > root.size.x * root.size.y * 0.1, name_at_pose + " empty reference silhouette")
			check(footprint.union_fraction <= 0.006 and footprint.sky_p95 <= 3, name_at_pose + " lost procedural coverage %s" % footprint)
		if i % 2:
			print(name_at_pose, " native/VT xor=", source.xor, ", clip/VT ", footprint)
		max_xor = maxf(max_xor, footprint.frame_fraction)
		max_sky = maxi(max_sky, footprint.sky_p95)
	var returning := metrics(virtual[1], virtual[-1])
	check(returning.frame_fraction < 0.001 and returning.sky_p95 <= 1, label + " did not recover its returning silhouette")
	print(label, " max clip/VT frame difference=", max_xor, ", max horizon p95=", max_sky, ", max native/VT XOR=", max_native_xor)

func run() -> void:
	change_scene_to_file("res://demo/Demo.tscn")
	await scene_changed
	terrain = current_scene.get_node("Terrain3D")
	current_scene.get_node("UI").hide()
	current_scene.get_node("Terrain3DParticles").hide()
	var player := current_scene.get_node("Player")
	player.hide()
	player.process_mode = Node.PROCESS_MODE_DISABLED
	terrain.ocean_enabled = false
	terrain.assets.get_mesh_asset(0).set_enabled(false)
	terrain.material.material_rvt_enabled = false
	const TERRAIN_LAYER := 1 << 8
	terrain.render_layers = TERRAIN_LAYER
	camera.cull_mask = TERRAIN_LAYER
	camera.near = 0.5
	camera.far = 24576
	camera.fov = 70
	var environment := Environment.new()
	environment.background_mode = Environment.BG_COLOR
	environment.background_color = Color(1,0,1)
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.ambient_light_color = Color.WHITE
	environment.tonemap_mode = Environment.TONE_MAPPER_LINEAR
	camera.environment = environment
	root.transparent_bg = true
	root.add_child(camera)
	set_pose(STOPS[0])
	camera.make_current()
	terrain.set_camera(camera)
	terrain.set_clipmap_target(camera)
	cvars = Engine.get_singleton("CVars")
	await frames(30)
	print("MaxDistance=", cvars.get_value("r.Terrain3D.MaxDistance"), ", mesh_size=", terrain.mesh_size, ", mesh_lods=", terrain.mesh_lods, ", viewport=", root.size)
	await compare_paths("NOISE", Terrain3DMaterial.NOISE)
	await compare_paths("FLAT", Terrain3DMaterial.FLAT)
	await compare_paths("NONE", Terrain3DMaterial.NONE)
	terrain.material.world_background = Terrain3DMaterial.FLAT
	set_pose(STOPS[2])
	await frames(16)
	var full := silhouette("full_distance")
	cvars.set_value("r.Terrain3D.MaxDistance", 700.0)
	await frames(16)
	var limited := metrics(full, silhouette("limited_distance"))
	check(limited.union_fraction > 0.5, "An explicit positive draw distance stopped limiting coverage")
	print("Height horizon regression: ", failures, " failures")
	quit(int(failures > 0))
