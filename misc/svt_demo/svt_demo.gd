extends Node3D

# Streaming Virtual Texture demo / self test.
# Normal run: slow orbit around a streamed 64 x 64 m terrain layer.
# Self test: godot --path misc/svt_demo -- --svt-test  (bakes page files, compares against a
#            directly sampled texture, prints SVT_TEST lines, exits 0 on PASS)

const AREA := 64.0
const OUT := "res://out/"
const LOG2 := 3
const TILE := 128
const BORDER := 4
const SRC_SIZE := 1024

var test_mode := false
var rvt: RuntimeVirtualTexture
var volume: RuntimeVirtualTextureVolume
var quad: MeshInstance3D
var ref_mat: ShaderMaterial
var svt_mat: ShaderMaterial
var camera: Camera3D
var label: Label

var frame := 0
var stage := 0
var stage_frame := 0
var stable := 0
var failures: PackedStringArray = []
var source_tex: ImageTexture
var shot_ref: Image

var rgba_file := ""
var bc1_file := ""


func _ready() -> void:
	test_mode = "--svt-test" in OS.get_cmdline_user_args()
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(OUT))
	rgba_file = ProjectSettings.globalize_path(OUT + "terrain_rgba8.svt")
	bc1_file = ProjectSettings.globalize_path(OUT + "terrain_bc1.svt")

	var source := _load_or_make_source()
	source_tex = ImageTexture.create_from_image(source)

	_build_environment()
	_build_volume_and_quad()
	_build_camera()
	_register_cvars()
	print("SVT_TEST start test_mode=", test_mode)


func _load_or_make_source() -> Image:
	var png := ProjectSettings.globalize_path(OUT + "source.png")
	if FileAccess.file_exists(png):
		var cached := Image.load_from_file(png)
		if cached != null and cached.get_width() == SRC_SIZE:
			return cached
	var img := Image.create(SRC_SIZE, SRC_SIZE, true, Image.FORMAT_RGBA8)
	var rng := RandomNumberGenerator.new()
	rng.seed = 20261101
	var discs: Array[Vector3] = [] # x, y, radius (uv space)
	for i in 24:
		discs.append(Vector3(rng.randf(), rng.randf(), rng.randf_range(0.01, 0.05)))
	for y in SRC_SIZE:
		for x in SRC_SIZE:
			var u := float(x) / SRC_SIZE
			var v := float(y) / SRC_SIZE
			var c := Color.from_hsv(0.55 + 0.25 * u, 0.45 + 0.2 * v, 0.92)
			# Checker detail keeps bilinear/blocks visible.
			var chk := ((x / 16) + (y / 16)) % 2
			c = c.darkened(0.12 * chk)
			for d in discs:
				var dist := Vector2(u - d.x, v - d.y).length()
				if dist < d.z:
					c = Color.from_hsv(fposmod(d.x * 3.0 + d.y, 1.0), 0.85, 1.0).lerp(c, dist / d.z)
			img.set_pixel(x, y, c)
	img.generate_mipmaps()
	img.save_png(png)
	return img


func _register_cvars() -> void:
	var cv := Engine.get_singleton("CVars")
	if cv == null:
		return
	# Same knobs as the RVT demo, driven by the engine CVar system (--cvar / --cvar-exec / --cvar-file).
	for cvar_name in ["r.VT.RVT.DebugView", "r.VT.RVT.ForceLod", "r.VT.RVT.PickAtScreenCenter",
			"r.VT.RVT.UnlockAll", "r.VT.RVT.Stats", "r.VT.RVT.PageInfo"]:
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
	cv.register_command("r.VT.RVT.UnlockAll", _cmd_unlock_all, "release every locked page")
	cv.register_command("r.VT.RVT.Stats", _cmd_stats, "print paging statistics and the debug view")
	cv.register_command("r.VT.RVT.PageInfo", _cmd_page_info, "level x y")


func _cmd_pick_page(p_args: PackedStringArray) -> String:
	_lock_page_under_center(maxf(float(p_args[0]), 1.0) if not p_args.is_empty() else 5.0)
	return ""


func _cmd_unlock_all(_p_args: PackedStringArray) -> String:
	rvt.unlock_all_pages()
	return ""


func _cmd_stats(_p_args: PackedStringArray) -> String:
	return "SVT_STATS debug_mode=%d force_lod=%d %s" % [rvt.debug_mode, rvt.debug_force_lod, rvt.get_stats()]


func _cmd_page_info(p_args: PackedStringArray) -> String:
	if p_args.size() < 3:
		return "error: usage: r.VT.RVT.PageInfo <level> <x> <y>"
	return "SVT_PAGE %s" % rvt.get_page_info(int(p_args[0]), int(p_args[1]), int(p_args[2]))


func _lock_page_under_center(p_seconds: float) -> void:
	var vp := get_viewport().get_visible_rect().size
	var from := camera.project_ray_origin(vp * 0.5)
	var dir := camera.project_ray_normal(vp * 0.5)
	var t := -from.y / dir.y if absf(dir.y) > 0.0001 else 0.0
	var page := rvt.pick_page(from + dir * t, 0)
	rvt.lock_page(page.x, page.y, page.z, p_seconds)
	print("SVT_DEBUG pick ", page, " ", rvt.get_page_info(page.x, page.y, page.z))


func _build_environment() -> void:
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.03, 0.04, 0.06)
	var we := WorldEnvironment.new()
	we.environment = env
	add_child(we)


func _bake_files() -> void:
	var src := _load_or_make_source()
	if not FileAccess.file_exists(rgba_file):
		var err := RuntimeVirtualTexture.bake_page_file(rgba_file, src, LOG2, TILE, BORDER, RuntimeVirtualTexture.FORMAT_RGBA8, true)
		print("SVT_TEST bake rgba8 -> ", err)
	if not FileAccess.file_exists(bc1_file):
		var err2 := RuntimeVirtualTexture.bake_page_file(bc1_file, src, LOG2, TILE, BORDER, RuntimeVirtualTexture.FORMAT_BC1, true)
		print("SVT_TEST bake bc1 -> ", err2)


func _build_volume_and_quad() -> void:
	_bake_files()

	rvt = RuntimeVirtualTexture.new()
	rvt.log2_tile_count = LOG2
	rvt.tile_size = TILE
	rvt.tile_border = BORDER
	rvt.pool_size = 6
	rvt.material_type = RuntimeVirtualTexture.MATERIAL_BASE_COLOR
	rvt.max_pages_per_frame = 24
	rvt.page_file = rgba_file

	volume = RuntimeVirtualTextureVolume.new()
	volume.virtual_texture = rvt
	volume.size = Vector3(AREA, 8.0, AREA)
	add_child(volume)

	var plane := PlaneMesh.new()
	plane.size = Vector2(AREA, AREA)
	quad = MeshInstance3D.new()
	quad.mesh = plane  # PlaneMesh already lies in XZ facing +Y.
	quad.position = Vector3(0, 0.05, 0)
	add_child(quad)

	svt_mat = ShaderMaterial.new()
	svt_mat.shader = load("res://svt_receiver.gdshader")
	rvt.apply_to_material(svt_mat, "rvt")

	ref_mat = ShaderMaterial.new()
	ref_mat.shader = load("res://ref_receiver.gdshader")
	ref_mat.set_shader_parameter("src_tex", source_tex)
	ref_mat.set_shader_parameter("area", AREA)

	quad.material_override = svt_mat


func _build_camera() -> void:
	camera = Camera3D.new()
	camera.fov = 60
	camera.far = 500
	add_child(camera)
	camera.position = Vector3(0, 26, 36)
	camera.look_at(Vector3.ZERO)

	if not test_mode:
		var ui := CanvasLayer.new()
		add_child(ui)
		label = Label.new()
		label.position = Vector2(8, 8)
		ui.add_child(label)


func _process(_delta: float) -> void:
	frame += 1
	if not test_mode:
		var t := Time.get_ticks_msec() * 0.00025
		camera.position = Vector3(sin(t) * 26.0, 18.0, cos(t) * 26.0)
		camera.look_at(Vector3.ZERO)
		var s := rvt.get_stats()
		label.text = "SVT resident %d/%d levels %s evicted %d computed %d" % [
			s.get("resident_pages", 0), s.get("pool_pages", 0), str(s.get("levels", [])),
			s.get("evicted_total", 0), s.get("rendered_total", 0)]
		return
	_run_test()


func _unhandled_key_input(event: InputEvent) -> void:
	if not (event is InputEventKey) or not event.pressed:
		return
	match event.keycode:
		KEY_T:
			quad.material_override = ref_mat if quad.material_override == svt_mat else svt_mat
		KEY_0, KEY_1, KEY_2, KEY_3, KEY_4, KEY_5:
			rvt.debug_mode = event.keycode - KEY_0
		KEY_L:
			var next_lod := rvt.debug_force_lod + 1
			rvt.debug_force_lod = -1 if next_lod > rvt.log2_tile_count else next_lod
		KEY_P:
			var vp := get_viewport().get_visible_rect().size
			var from := camera.project_ray_origin(vp * 0.5)
			var dir := camera.project_ray_normal(vp * 0.5)
			var t := -from.y / dir.y if absf(dir.y) > 0.0001 else 0.0
			var page := rvt.pick_page(from + dir * t, 0)
			rvt.lock_page(page.x, page.y, page.z, 5.0)
			print("SVT_DEBUG pick ", page, " ", rvt.get_page_info(page.x, page.y, page.z))
		KEY_U:
			rvt.unlock_all_pages()


func _capture() -> Image:
	var img := get_viewport().get_texture().get_image()
	img.convert(Image.FORMAT_RGB8)
	return img


func _fail(msg: String) -> void:
	failures.append(msg)
	print("SVT_TEST FAIL: ", msg)


func _stats() -> Dictionary:
	return rvt.get_stats()


func _wait_stable() -> bool:
	var s := _stats()
	if frame > 3 and s.get("rendered_this_frame", 1) == 0 and s.get("resident_pages", 0) > 0:
		stable += 1
	else:
		stable = 0
	return stable >= 6


# Compares the reference (directly textured) capture with the SVT capture over the quad area.
func _diff(shot_svt: Image, label_name: String, mean_limit: float, outlier_limit: float) -> void:
	var a := shot_ref.get_data()
	var b := shot_svt.get_data()
	var w := shot_ref.get_width()
	var h := shot_ref.get_height()
	var sum := 0.0
	var outliers := 0
	var count := 0
	for y in range(0, h, 2):
		for x in range(0, w, 2):
			var o := (y * w + x) * 3
			# Only compare pixels that actually show the quad (non-background).
			var la := (a[o] + a[o + 1] + a[o + 2]) / 3
			var lb := (b[o] + b[o + 1] + b[o + 2]) / 3
			if la < 20 and lb < 20:
				continue
			var d := (absi(a[o] - b[o]) + absi(a[o + 1] - b[o + 1]) + absi(a[o + 2] - b[o + 2])) / (3.0 * 255.0)
			sum += d
			if d > 0.12:
				outliers += 1
			count += 1
	if count < 1000:
		_fail("%s: too few compared pixels (%d)" % [label_name, count])
		return
	var mean := sum / count
	var frac := float(outliers) / count
	print("SVT_TEST %s mean_abs_diff=%.4f outlier_fraction=%.4f pixels=%d" % [label_name, mean, frac, count])
	if mean > mean_limit:
		_fail("%s mean diff %.4f > %.4f" % [label_name, mean, mean_limit])
	if frac > outlier_limit:
		_fail("%s outlier fraction %.4f > %.4f" % [label_name, frac, outlier_limit])


func _shoot_svt() -> Image:
	quad.material_override = svt_mat
	return _capture()


func _shoot_ref() -> Image:
	quad.material_override = ref_mat
	return _capture()


func _run_test() -> void:
	var s := _stats()
	stage_frame += 1
	match stage:
		0: # First frames: only the always-resident coarse levels can be there.
			if frame == 3:
				print("SVT_TEST early stats=", s)
				if s.get("resident_pages", 0) > 40:
					_fail("streaming did not start sparse: %s" % [s])
			if _wait_stable():
				print("SVT_TEST converged frame=", frame, " stats=", s)
				var levels: PackedInt32Array = s.get("levels", PackedInt32Array())
				if levels.size() != LOG2 + 1 or levels[0] < 8:
					_fail("level 0 pages did not stream in: %s" % [str(levels)])
				camera.position = Vector3(6, 9, 14)
				camera.look_at(Vector3(0, 0, -2))
				_next(1)
			elif frame > 1200:
				_fail("never converged: %s" % [s])
				_finish()
		1: # Reference capture at close range (LOD ~ 0).
			if stage_frame == 2:
				quad.material_override = ref_mat
			if stage_frame == 6:
				shot_ref = _capture()
				shot_ref.save_png(ProjectSettings.globalize_path(OUT + "ref_close.png"))
				_next(2)
		2:
			if stage_frame == 2:
				quad.material_override = svt_mat
			if stage_frame == 6:
				var shot := _capture()
				shot.save_png(ProjectSettings.globalize_path(OUT + "svt_close.png"))
				_diff(shot, "close_view", 0.03, 0.06)
				camera.position = Vector3(0, 40, 56)
				camera.look_at(Vector3.ZERO)
				_next(3)
		3: # Far view: new pages stream in, old ones are evicted from the small pool.
			if stage_frame == 2:
				quad.material_override = ref_mat
				stable = 0
			if stage_frame > 10 and _wait_stable():
				print("SVT_TEST far stats=", _stats())
				if _stats().get("evicted_total", 0) < 1:
					_fail("LRU never evicted after moving the camera: %s" % [_stats()])
				shot_ref = _capture()
				_next(4)
			elif stage_frame > 900:
				_fail("far view did not converge")
				_finish()
		4:
			if stage_frame == 2:
				quad.material_override = svt_mat
			if stage_frame == 6:
				var shot := _capture()
				shot.save_png(ProjectSettings.globalize_path(OUT + "svt_far.png"))
				_diff(shot, "far_view", 0.06, 0.15)
				rvt.page_file = bc1_file
				stable = 0
				_next(5)
		5:
			if _wait_stable() and stage_frame > 10:
				print("SVT_TEST bc1 stats=", _stats())
				camera.position = Vector3(6, 9, 14)
				camera.look_at(Vector3(0, 0, -2))
				quad.material_override = ref_mat
				_next(6)
			elif stage_frame > 900:
				_fail("bc1 swap did not converge")
				_finish()
		6:
			if stage_frame == 6:
				shot_ref = _capture()
				quad.material_override = svt_mat
				_next(7)
		7:
			if stage_frame == 6:
				var shot := _capture()
				shot.save_png(ProjectSettings.globalize_path(OUT + "svt_bc1.png"))
				_diff(shot, "bc1_view", 0.05, 0.12)
				# Tiny pool: forces heavy eviction / truncated requests.
				rvt.pool_size = 3
				rvt.page_file = rgba_file
				stable = 0
				_next(8)
		8:
			if _wait_stable() and stage_frame > 10:
				print("SVT_TEST tiny pool stats=", _stats())
				quad.material_override = ref_mat
				_next(9)
			elif stage_frame > 900:
				_fail("tiny pool did not converge")
				_finish()
		9:
			if stage_frame == 6:
				shot_ref = _capture()
				quad.material_override = svt_mat
				_next(10)
		10:
			if stage_frame == 6:
				var shot := _capture()
				_diff(shot, "tiny_pool", 0.12, 0.30)
				_finish()


func _next(s: int) -> void:
	stage = s
	stage_frame = 0


func _finish() -> void:
	var ok := failures.is_empty()
	print("SVT_TEST_RESULT ", "PASS" if ok else "FAIL")
	get_tree().quit(0 if ok else 1)
