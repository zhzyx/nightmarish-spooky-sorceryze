extends Node3D

# Runtime Virtual Texture demo / self test.
# Normal run: orbiting camera over a procedural scene, left half rendered directly, right half sampled from the RVT.
# Self test:  godot --path misc/rvt_demo -- --rvt-test   (writes out/*.png, prints RVT_TEST lines, exits with 0 on success)

const RVT_LAYER := 2
const DIRECT_RIGHT_LAYER := 4
const AREA := 64.0
const OUT_DIR := "res://out/"

var test_mode := false
var shot_mode := false
var height_mode := false
var rvt: RuntimeVirtualTexture
var volume: RuntimeVirtualTextureVolume
var receiver: MeshInstance3D
var camera: Camera3D
var test_tile_material: StandardMaterial3D
var test_disc: MeshInstance3D
var info_label: Label
var ui: CanvasLayer

var frame := 0
var stable := 0
var stage := 0
var stage_frame := 0
var shot_rvt: Image
var shot_direct: Image
var shot_normal: Image
var picked := Vector3i.ZERO
var failures: PackedStringArray = []


func _ready() -> void:
	var args := OS.get_cmdline_user_args()
	test_mode = "--rvt-test" in args
	shot_mode = "--rvt-shot" in args
	height_mode = "--rvt-height" in args
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(OUT_DIR))
	_build_environment()
	_build_source()
	_build_rvt()
	_build_receiver()
	_build_camera()
	_build_ui()
	_set_receiver_mode(true)
	_register_cvars()
	print("RVT_TEST start test_mode=", test_mode)


func _build_environment() -> void:
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.05, 0.06, 0.08)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.5, 0.5, 0.55)
	var we := WorldEnvironment.new()
	we.environment = env
	add_child(we)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-50, 30, 0)
	add_child(sun)


func _make_checker(size: int, cells: int) -> ImageTexture:
	var img := Image.create(size, size, true, Image.FORMAT_RGBA8)
	var step := size / cells
	for y in size:
		for x in size:
			var c := ((x / step) + (y / step)) % 2 == 0
			var v := 1.0 if c else 0.65
			img.set_pixel(x, y, Color(v, v, v, 1.0))
	img.generate_mipmaps()
	return ImageTexture.create_from_image(img)


func _material(color: Color, tex: Texture2D = null) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = color
	m.albedo_texture = tex
	if test_mode:
		m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	return m


func _add_source(mesh: Mesh, mat: Material, pos: Vector3) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.mesh = mesh
	mi.material_override = mat
	mi.position = pos
	# Right half objects live on their own layer so the camera can switch between direct and RVT rendering.
	mi.layers = (DIRECT_RIGHT_LAYER if pos.x > 0.0 else 1) | RVT_LAYER
	add_child(mi)
	return mi


func _build_source() -> void:
	var checker := _make_checker(128, 8)
	for i in 8:
		for j in 8:
			var plane := PlaneMesh.new()
			plane.size = Vector2(8, 8)
			var color := Color.from_hsv(float(i * 8 + j) / 64.0, 0.55, 0.9)
			var mat := _material(color, checker)
			var mi := _add_source(plane, mat, Vector3(-28 + 8 * i, 0, -28 + 8 * j))
			if i == 5 and j == 3:
				test_tile_material = mat
				mi.name = "TestTile"

	# Flat decal-like shapes (no parallax, used by the numeric comparison).
	var rng := RandomNumberGenerator.new()
	rng.seed = 1234
	for k in 14:
		var cyl := CylinderMesh.new()
		cyl.height = 0.04
		cyl.top_radius = rng.randf_range(1.0, 2.5)
		cyl.bottom_radius = cyl.top_radius
		var x := rng.randf_range(4.0, 28.0) * (1.0 if k % 2 == 0 else -1.0)
		var z := rng.randf_range(-28.0, 28.0)
		x = x + signf(x) * cyl.top_radius * 0.0
		if absf(x) < cyl.top_radius + 0.5:
			x = signf(x) * (cyl.top_radius + 0.5)
		_add_source(cyl, _material(Color.from_hsv(rng.randf(), 0.9, 1.0)), Vector3(x, 0.03, z))
	for sx in [-1.0, 1.0]:
		var road := BoxMesh.new()
		road.size = Vector3(30, 0.04, 2.5)
		_add_source(road, _material(Color(0.12, 0.12, 0.14)), Vector3(sx * 15.5, 0.03, 4.0))

	var disc_mesh := CylinderMesh.new()
	disc_mesh.height = 0.04
	disc_mesh.top_radius = 2.0
	disc_mesh.bottom_radius = 2.0
	test_disc = _add_source(disc_mesh, _material(Color(0, 1, 0)), Vector3(20, 0.06, 20))

	if height_mode:
		var tower := BoxMesh.new()
		tower.size = Vector3(4, 2, 4)
		_add_source(tower, _material(Color.WHITE), Vector3(20, 1, 0))

	if not test_mode:
		# Tall content: only sensible with the lit showcase because the RVT is a top-down projection.
		for k in 10:
			var box := BoxMesh.new()
			box.size = Vector3(rng.randf_range(1, 3), rng.randf_range(0.5, 3.0), rng.randf_range(1, 3))
			var pos := Vector3(rng.randf_range(-28, 28), box.size.y * 0.5, rng.randf_range(-28, 28))
			_add_source(box, _material(Color.from_hsv(rng.randf(), 0.7, 0.9)), pos)
		var sphere := SphereMesh.new()
		sphere.radius = 3.0
		sphere.height = 6.0
		_add_source(sphere, _material(Color(0.9, 0.8, 0.2)), Vector3(-10, 3.0, -8))


func _build_rvt() -> void:
	rvt = RuntimeVirtualTexture.new()
	rvt.material_type = RuntimeVirtualTexture.MATERIAL_BASE_COLOR if test_mode else RuntimeVirtualTexture.MATERIAL_BASE_COLOR_NORMAL_ROUGHNESS
	if height_mode:
		rvt.material_type = RuntimeVirtualTexture.MATERIAL_WORLD_HEIGHT
	rvt.log2_tile_count = 5
	rvt.tile_size = 128
	rvt.tile_border = 4
	rvt.pool_size = 24
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--pool="):
			rvt.pool_size = int(a.get_slice("=", 1))
	rvt.cull_mask = RVT_LAYER
	rvt.max_pages_per_frame = 16
	volume = RuntimeVirtualTextureVolume.new()
	volume.virtual_texture = rvt
	volume.position = Vector3(0, 0, 0)
	volume.size = Vector3(AREA, 8.0, AREA)
	add_child(volume)


func _build_receiver() -> void:
	var plane := PlaneMesh.new()
	plane.size = Vector2(AREA * 0.5, AREA)
	receiver = MeshInstance3D.new()
	receiver.mesh = plane
	receiver.position = Vector3(AREA * 0.25, 0.0, 0.0)
	receiver.layers = 1
	var mat := ShaderMaterial.new()
	var path := "res://rvt_receiver_unshaded.gdshader" if test_mode else "res://rvt_receiver_lit.gdshader"
	if height_mode:
		path = "res://rvt_receiver_height.gdshader"
	mat.shader = load(path)
	rvt.apply_to_material(mat, "rvt")
	receiver.material_override = mat
	add_child(receiver)


func _build_camera() -> void:
	camera = Camera3D.new()
	camera.fov = 60
	camera.far = 500
	camera.cull_mask = 1 | DIRECT_RIGHT_LAYER
	add_child(camera)
	camera.position = Vector3(0, 40, 50)
	camera.look_at(Vector3.ZERO)


func _build_ui() -> void:
	ui = CanvasLayer.new()
	add_child(ui)
	info_label = Label.new()
	info_label.position = Vector2(8, 8)
	ui.add_child(info_label)
	var pt := TextureRect.new()
	pt.texture = rvt.get_page_table_texture()
	pt.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	pt.custom_minimum_size = Vector2(128, 128)
	pt.size = Vector2(128, 128)
	pt.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	pt.position = Vector2(8, 560)
	ui.add_child(pt)
	var ph := TextureRect.new()
	ph.texture = rvt.get_physical_texture(0)
	ph.size = Vector2(256, 256)
	ph.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	ph.position = Vector2(144, 456)
	ui.add_child(ph)
	ui.visible = not test_mode


func _process(delta: float) -> void:
	frame += 1
	var stats := rvt.get_stats()
	if height_mode:
		_run_height_test(stats)
		return
	if shot_mode:
		camera.position = Vector3(18, 16, 30)
		camera.look_at(Vector3(0, 0, -4))
		if frame == 150 or frame == 300:
			var tag := "lit_rvt" if receiver.visible else "lit_direct"
			get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path(OUT_DIR + tag + ".png"))
			print("RVT_SHOT ", tag, " stats=", stats)
			if frame == 150:
				_set_receiver_mode(false)
			else:
				get_tree().quit()
		return
	if not test_mode:
		var t := Time.get_ticks_msec() * 0.0003
		camera.position = Vector3(sin(t) * 40.0, 20.0 + 15.0 * sin(t * 0.7), cos(t) * 40.0)
		camera.look_at(Vector3.ZERO)
		info_label.text = "RVT resident %d/%d requested %d rendered(frame) %d total %d evicted %d  debug=%s lod=%d\n[0-5] debug view  [L] force lod  [P] pick+lock page  [U] unlock  [T] toggle receiver" % [
			stats.get("resident_pages", 0), stats.get("pool_pages", 0), stats.get("requested_pages", 0),
			stats.get("rendered_this_frame", 0), stats.get("rendered_total", 0), stats.get("evicted_total", 0),
			["off", "page table", "page table mip", "physical pool", "lod", "borders"][rvt.debug_mode], rvt.debug_force_lod]
		return
	_run_test(stats)


func _unhandled_key_input(event: InputEvent) -> void:
	if not (event is InputEventKey) or not event.pressed:
		return
	match event.keycode:
		KEY_T:
			_set_receiver_mode(not receiver.visible)
		KEY_0, KEY_1, KEY_2, KEY_3, KEY_4, KEY_5:
			rvt.debug_mode = event.keycode - KEY_0
		KEY_L:
			var next_lod := rvt.debug_force_lod + 1
			rvt.debug_force_lod = -1 if next_lod > rvt.log2_tile_count else next_lod
		KEY_P:
			_lock_page_under_center()
		KEY_U:
			rvt.unlock_all_pages()


func _register_cvars() -> void:
	var cv := Engine.get_singleton("CVars")
	if cv == null:
		return
	# Names mirror UE's RVT debug console variables. The engine resolves --cvar / --cvar-exec /
	# --cvar-file long before this scene exists, so anything that was set up front is replayed here:
	# variables come back through get_value(), commands through register_command().
	for cvar_name in ["r.VT.RVT.DebugView", "r.VT.RVT.ForceLod", "r.VT.RVT.PickAtScreenCenter",
			"r.VT.RVT.LockPage", "r.VT.RVT.UnlockAll", "r.VT.RVT.Stats", "r.VT.RVT.PageInfo"]:
		if cv.has_variable(cvar_name) or cv.has_command(cvar_name):
			cv.unregister(cvar_name)

	var set_debug_view := func(value: Variant) -> void:
		rvt.debug_mode = clampi(int(value), 0, 5)
	cv.register_variable("r.VT.RVT.DebugView", 0, "0 off, 1 page table, 2 residency, 3 physical pool, 4 lod, 5 borders")
	cv.set_changed_callback("r.VT.RVT.DebugView",
			func(_name: String, value: Variant) -> void: set_debug_view.call(value))
	set_debug_view.call(cv.get_value("r.VT.RVT.DebugView"))

	var set_force_lod := func(value: Variant) -> void:
		rvt.debug_force_lod = clampi(int(value), -1, rvt.log2_tile_count)
	cv.register_variable("r.VT.RVT.ForceLod", -1, "-1 auto, otherwise pin the sampled level")
	cv.set_changed_callback("r.VT.RVT.ForceLod",
			func(_name: String, value: Variant) -> void: set_force_lod.call(value))
	set_force_lod.call(cv.get_value("r.VT.RVT.ForceLod"))

	cv.register_command("r.VT.RVT.PickAtScreenCenter", _cmd_pick_page,
			"seconds to lock the page under the screen center")
	cv.register_command("r.VT.RVT.LockPage", _cmd_lock_page, "level x y [seconds] (default 10 s)")
	cv.register_command("r.VT.RVT.UnlockAll", _cmd_unlock_all, "release every locked page")
	cv.register_command("r.VT.RVT.Stats", _cmd_stats, "print paging statistics and the debug view")
	cv.register_command("r.VT.RVT.PageInfo", _cmd_page_info, "level x y")


func _cmd_pick_page(p_args: PackedStringArray) -> String:
	_lock_page_under_center(maxf(float(p_args[0]), 1.0) if not p_args.is_empty() else 5.0)
	return ""


func _cmd_lock_page(p_args: PackedStringArray) -> String:
	if p_args.size() < 3:
		return "error: usage: r.VT.RVT.LockPage <level> <x> <y> [seconds]"
	var level := int(p_args[0])
	var x := int(p_args[1])
	var y := int(p_args[2])
	var seconds := float(p_args[3]) if p_args.size() > 3 else 10.0
	rvt.lock_page(level, x, y, seconds)
	return "RVT_PAGE %s" % rvt.get_page_info(level, x, y)


func _cmd_unlock_all(_p_args: PackedStringArray) -> String:
	rvt.unlock_all_pages()
	return ""


func _cmd_stats(_p_args: PackedStringArray) -> String:
	return "RVT_STATS debug_mode=%d force_lod=%d %s" % [rvt.debug_mode, rvt.debug_force_lod, rvt.get_stats()]


func _cmd_page_info(p_args: PackedStringArray) -> String:
	if p_args.size() < 3:
		return "error: usage: r.VT.RVT.PageInfo <level> <x> <y>"
	return "RVT_PAGE %s" % rvt.get_page_info(int(p_args[0]), int(p_args[1]), int(p_args[2]))


func _pick_world_center() -> Vector3:
	var vp := get_viewport().get_visible_rect().size
	var from := camera.project_ray_origin(vp * 0.5)
	var dir := camera.project_ray_normal(vp * 0.5)
	var t := -from.y / dir.y if absf(dir.y) > 0.0001 else 0.0
	return from + dir * t


func _lock_page_under_center(p_seconds: float = 5.0) -> Dictionary:
	var page := rvt.pick_page(_pick_world_center(), 0)
	rvt.lock_page(page.x, page.y, page.z, p_seconds)
	var info := rvt.get_page_info(page.x, page.y, page.z)
	print("RVT_DEBUG pick page %s info=%s" % [page, info])
	return info


func _wait_stable(stats: Dictionary) -> bool:
	if frame > 5 and stats.get("gpu_ready", false) and stats.get("rendered_this_frame", 1) == 0 and stats.get("resident_pages", 0) > 0:
		stable += 1
	else:
		stable = 0
	return stable >= 8


func _capture() -> Image:
	var img := get_viewport().get_texture().get_image()
	img.convert(Image.FORMAT_RGB8)
	return img


func _fail(msg: String) -> void:
	failures.append(msg)
	print("RVT_TEST FAIL: ", msg)


func _diff(a: Image, b: Image, x_from: int, label: String, mean_limit: float, outlier_limit: float) -> void:
	var da := a.get_data()
	var db := b.get_data()
	var w := a.get_width()
	var h := a.get_height()
	var sum := 0.0
	var outliers := 0
	var count := 0
	for y in range(0, h, 2):
		for x in range(x_from, w, 2):
			var o := (y * w + x) * 3
			var d := (absi(da[o] - db[o]) + absi(da[o + 1] - db[o + 1]) + absi(da[o + 2] - db[o + 2])) / (3.0 * 255.0)
			sum += d
			if d > 0.1:
				outliers += 1
			count += 1
	var mean := sum / count
	var frac := float(outliers) / count
	print("RVT_TEST %s mean_abs_diff=%.4f outlier_fraction=%.4f" % [label, mean, frac])
	if mean > mean_limit:
		_fail("%s mean diff %.4f > %.4f" % [label, mean, mean_limit])
	if frac > outlier_limit:
		_fail("%s outlier fraction %.4f > %.4f" % [label, frac, outlier_limit])


func _set_receiver_mode(on: bool) -> void:
	receiver.visible = on
	camera.cull_mask = 1 if on else (1 | DIRECT_RIGHT_LAYER)


func _run_test(stats: Dictionary) -> void:
	stage_frame += 1
	match stage:
		0: # Converge the first view.
			if _wait_stable(stats):
				print("RVT_TEST converged frame=%d stats=%s" % [frame, stats])
				if stats.get("resident_pages", 0) < 10:
					_fail("too few resident pages")
				_set_receiver_mode(true)
				_next(1)
			elif frame > 900:
				_fail("never converged: %s" % [stats])
				_finish()
		1:
			if stage_frame == 4:
				shot_rvt = _capture()
				shot_rvt.save_png(ProjectSettings.globalize_path(OUT_DIR + "rvt.png"))
				_set_receiver_mode(false)
				_next(2)
		2:
			if stage_frame == 4:
				shot_direct = _capture()
				shot_direct.save_png(ProjectSettings.globalize_path(OUT_DIR + "direct.png"))
				_diff(shot_rvt, shot_direct, shot_rvt.get_width() / 2 + 6, "static_view", 0.03, 0.06)
				_set_receiver_mode(true)
				# Fly closer: new, finer pages must stream in and old ones may be evicted.
				camera.position = Vector3(10, 6, 14)
				camera.look_at(Vector3(10, 0, -4))
				_next(3)
		3:
			if _wait_stable(stats) and stage_frame > 10:
				print("RVT_TEST close_view stats=%s" % [stats])
				_set_receiver_mode(true)
				_next(4)
		4:
			if stage_frame == 4:
				shot_rvt = _capture()
				shot_rvt.save_png(ProjectSettings.globalize_path(OUT_DIR + "rvt_close.png"))
				_set_receiver_mode(false)
				_next(5)
		5:
			if stage_frame == 4:
				shot_direct = _capture()
				shot_direct.save_png(ProjectSettings.globalize_path(OUT_DIR + "direct_close.png"))
				_diff(shot_rvt, shot_direct, shot_rvt.get_width() / 2 + 6, "close_view", 0.04, 0.10)
				_set_receiver_mode(true)
				camera.position = Vector3(0, 40, 50)
				camera.look_at(Vector3.ZERO)
				stable = 0
				# Material parameter changes are not tracked by the scene, the RVT must be invalidated explicitly.
				test_tile_material.albedo_color = Color(1, 0, 1)
				rvt.invalidate(AABB(Vector3(8, -1, -8), Vector3(8, 2, 8)))
				_next(6)
		6:
			if _wait_stable(stats) and stage_frame > 20:
				shot_rvt = _capture()
				shot_rvt.save_png(ProjectSettings.globalize_path(OUT_DIR + "rvt_recolor.png"))
				# Tile (5,3): center x = 12, z = -4.
				var p := camera.unproject_position(Vector3(12, 0, -4))
				var c := shot_rvt.get_pixel(int(p.x), int(p.y))
				print("RVT_TEST recolored tile pixel at %s = %s" % [p, c])
				if c.r < 0.6 or c.b < 0.6 or c.g > 0.5:
					_fail("tile recolor was not picked up after invalidate, pixel=%s" % [c])
				# Moving an object is tracked automatically.
				var before := camera.unproject_position(Vector3(20, 0, 20))
				var green_before := shot_rvt.get_pixel(int(before.x), int(before.y))
				print("RVT_TEST disc before move pixel=%s" % [green_before])
				if green_before.g < 0.8 or green_before.r > 0.3:
					_fail("disc not visible in RVT before moving, pixel=%s" % [green_before])
				test_disc.position = Vector3(20, 0.06, -20)
				_next(7)
		7:
			if stage_frame > 3 and _wait_stable(stats) and stage_frame > 20:
				shot_rvt = _capture()
				shot_rvt.save_png(ProjectSettings.globalize_path(OUT_DIR + "rvt_moved.png"))
				var old_p := camera.unproject_position(Vector3(20, 0, 20))
				var new_p := camera.unproject_position(Vector3(20, 0, -20))
				var c_old := shot_rvt.get_pixel(int(old_p.x), int(old_p.y))
				var c_new := shot_rvt.get_pixel(int(new_p.x), int(new_p.y))
				print("RVT_TEST disc after move: old=%s new=%s" % [c_old, c_new])
				if c_new.g < 0.8 or c_new.r > 0.3:
					_fail("moved disc is not at its new position, pixel=%s" % [c_new])
				if c_old.g > 0.8 and c_old.r < 0.3:
					_fail("moved disc still visible at the old position, pixel=%s" % [c_old])
				# Reconfigure at runtime: new pool, new tile size.
				rvt.pool_size = 40
				rvt.tile_size = 64
				rvt.tile_border = 2
				stable = 0
				_next(8)
			elif stage_frame > 600:
				_fail("update did not converge")
				_finish()
		8:
			if stage_frame > 5 and _wait_stable(stats):
				print("RVT_TEST reconfigured stats=%s" % [stats])
				shot_rvt = _capture()
				_set_receiver_mode(false)
				_next(9)
			elif stage_frame > 600:
				_fail("reconfigure did not converge")
				_finish()
		9:
			if stage_frame == 4:
				shot_direct = _capture()
				_diff(shot_rvt, shot_direct, shot_rvt.get_width() / 2 + 6, "reconfigured_view", 0.03, 0.06)
				shot_normal = shot_rvt
				_set_receiver_mode(true)
				rvt.debug_mode = RuntimeVirtualTexture.DEBUG_PAGE_TABLE
				_next(10)
		10: # Debug views must visibly replace the sampled color.
			if stage_frame == 4:
				var debug_shot := _capture()
				debug_shot.save_png(ProjectSettings.globalize_path(OUT_DIR + "debug_page_table.png"))
				_diff_expect_change(shot_normal, debug_shot, shot_normal.get_width() / 2 + 6, "debug_page_table", 0.05)
				rvt.debug_mode = RuntimeVirtualTexture.DEBUG_PHYSICAL_POOL
			if stage_frame == 8:
				_capture().save_png(ProjectSettings.globalize_path(OUT_DIR + "debug_pool.png"))
				rvt.debug_mode = RuntimeVirtualTexture.DEBUG_BORDERS
			if stage_frame == 12:
				_capture().save_png(ProjectSettings.globalize_path(OUT_DIR + "debug_borders.png"))
				rvt.debug_mode = RuntimeVirtualTexture.DEBUG_OFF
				rvt.debug_force_lod = rvt.log2_tile_count
				_next(11)
		11: # Forced coarse LOD must change the receiver image.
			if stage_frame == 4:
				var lod_shot := _capture()
				_diff_expect_change(shot_normal, lod_shot, shot_normal.get_width() / 2 + 6, "debug_force_lod", 0.02)
				rvt.debug_force_lod = -1
				_next(12)
		12: # Picking + locking a page: resident, reported, and unlockable.
			if stage_frame == 2:
				picked = rvt.pick_page(_pick_world_center(), 0)
				rvt.lock_page(picked.x, picked.y, picked.z, 30.0)
			if stage_frame == 12:
				var info := rvt.get_page_info(picked.x, picked.y, picked.z)
				print("RVT_TEST picked page %s info=%s" % [picked, info])
				if not info.get("locked", false):
					_fail("page was not locked: %s" % [info])
				if not info.get("resident", false):
					_fail("locked page was not produced: %s" % [info])
				rvt.unlock_all_pages()
				if rvt.get_page_info(picked.x, picked.y, picked.z).get("locked", true):
					_fail("unlock_all_pages did not release the page")
				_finish()


func _diff_expect_change(a: Image, b: Image, x_from: int, label: String, min_mean: float) -> void:
	var da := a.get_data()
	var db := b.get_data()
	var w := a.get_width()
	var h := a.get_height()
	var sum := 0.0
	var count := 0
	for y in range(0, h, 2):
		for x in range(x_from, w, 2):
			var o := (y * w + x) * 3
			var la := (da[o] + da[o + 1] + da[o + 2]) / 3
			var lb := (db[o] + db[o + 1] + db[o + 2]) / 3
			if la < 20 and lb < 20:
				continue
			sum += (absi(da[o] - db[o]) + absi(da[o + 1] - db[o + 1]) + absi(da[o + 2] - db[o + 2])) / (3.0 * 255.0)
			count += 1
	if count < 1000:
		_fail("%s: too few compared pixels (%d)" % [label, count])
		return
	var mean := sum / count
	print("RVT_TEST %s mean_abs_diff=%.4f pixels=%d" % [label, mean, count])
	if mean < min_mean:
		_fail("%s debug view did not change the image (mean %.4f < %.4f)" % [label, mean, min_mean])


func _next(s: int) -> void:
	stage = s
	stage_frame = 0


func _finish() -> void:
	var ok := failures.is_empty()
	print("RVT_TEST_RESULT ", "PASS" if ok else "FAIL")
	get_tree().quit(0 if ok else 1)


func _run_height_test(stats: Dictionary) -> void:
	camera.position = Vector3(0, 80, 0.01)
	camera.look_at(Vector3.ZERO, Vector3(0, 0, -1))
	camera.cull_mask = 1
	receiver.visible = true
	if not _wait_stable(stats):
		if frame > 900:
			_fail("height never converged")
			_finish()
		return
	if stage_frame < 5:
		stage_frame += 1
		return
	var img := _capture()
	img.save_png(ProjectSettings.globalize_path(OUT_DIR + "height.png"))
	var top := img.get_pixelv(camera.unproject_position(Vector3(20, 2, 0))).srgb_to_linear().r
	var ground := img.get_pixelv(camera.unproject_position(Vector3(20, 0, 12))).srgb_to_linear().r
	print("RVT_TEST height tower_top=%.3f (expect 0.75) ground=%.3f (expect 0.5)" % [top, ground])
	if absf(top - 0.75) > 0.04:
		_fail("tower height %.3f" % top)
	if absf(ground - 0.5) > 0.04:
		_fail("ground height %.3f" % ground)
	_finish()
