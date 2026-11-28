extends "res://demo/src/HeightVTPreview.gd"
## godot --path <valley-demo> --rendering-method forward_plus --resolution 640x360 --fixed-fps 60 --script <this-file>
## Set T3D_CAPTURE_DIR to save the direct, cached and source frames.
## For a high-resolution subset, pass -- --reported-only, -- --reported-and-motion or -- --ground-perspective.
## Exercises F6/F7/F8 through the preview's normal input handling.

const REPORTED := Vector3(3029.1, 133.0, -2590.8)
const VIEW_SIZE := 22.0
const WARM_FRAMES := 100

var eye := Camera3D.new()
var errors := 0
var folder := OS.get_environment("T3D_CAPTURE_DIR")

func _initialize() -> void:
	super._initialize()
	run_detail.call_deferred()

func frames(n: int) -> void:
	for i in n:
		await RenderingServer.frame_post_draw

func check(ok: bool, message: String) -> void:
	if not ok:
		push_error(message)
		errors += 1

func press(code: Key) -> void:
	var event := InputEventKey.new()
	event.keycode = code
	event.pressed = true
	root.push_input(event, true)
	var released := event.duplicate() as InputEventKey
	released.pressed = false
	root.push_input(released, true)

func set_cached(value: bool) -> void:
	if material_cached != value:
		press(KEY_F7)
	check(material_cached == value and (terrain.material.get_shader_param("_t3d_material_rvt_bypass") == true) == (not value), "F7 did not select the requested surface")

func set_sources(value: bool) -> void:
	if show_page_sources != value:
		press(KEY_F8)
	check(show_page_sources == value and (terrain.material.get_shader_param("_t3d_material_rvt_sources") == true) == value, "F8 did not select the requested source view")

func capture(name_: String) -> Image:
	var image := root.get_texture().get_image()
	image.convert(Image.FORMAT_RGB8)
	if not folder.is_empty() and not name_.is_empty():
		check(image.save_png(folder.path_join(name_ + ".png")) == OK, "Could not save " + name_)
	return image

func luma(pixels: PackedByteArray, i: int) -> float:
	return (54.0 * pixels[i] + 183.0 * pixels[i+1] + 19.0 * pixels[i+2]) / 256.0

func source_kind(data: PackedByteArray, i: int) -> int:
	var r := int(data[i])
	var g := int(data[i+1])
	var b := int(data[i+2])
	if g > r + 48 and g > b + 48:
		return 1 # Live RVT.
	if b > r + 48 and b > g + 48:
		return 2 # Baked SVT.
	if r > g + 110 and r > b + 110:
		return 3 # Direct terrain.
	return 0

func score(direct: Image, cached: Image, sources: Image, direct_mask: Image, roi := Rect2i()) -> Dictionary:
	var a := direct.get_data()
	var b := cached.get_data()
	var marker := sources.get_data()
	var reference := direct_mask.get_data()
	var width := direct.get_width()
	if not roi.has_area():
		roi = Rect2i(Vector2i.ZERO, direct.get_size())
	var live := 0
	var disk := 0
	var hits := 0
	var count := 0
	var a_gradient := 0.0
	var b_gradient := 0.0
	var error := 0.0
	for y in range(roi.position.y + 2, roi.end.y - 2):
		for x in range(roi.position.x + 2, roi.end.x - 2):
			var i := (y*width + x)*3
			# The all-direct F8 frame identifies terrain independently of the tested reader.
			if source_kind(reference,i) != 3 or source_kind(reference,i+3) != 3 or source_kind(reference,i+3*width) != 3:
				continue
			count += 1
			var kind := source_kind(marker, i)
			live += int(kind == 1)
			disk += int(kind == 2)
			if kind != 1 and kind != 2:
				continue
			hits += 1
			var ya := luma(a,i)
			var yb := luma(b,i)
			a_gradient += absf(luma(a,i+3)-ya) + absf(luma(a,i+3*width)-ya)
			b_gradient += absf(luma(b,i+3)-yb) + absf(luma(b,i+3*width)-yb)
			for c in 3:
				error += absi(int(a[i+c])-int(b[i+c]))
	return {
		"terrain": count, "live": float(live)/maxi(1,count), "disk": float(disk)/maxi(1,count),
		"mae": error/(3*maxi(1,hits)), "direct_gradient": a_gradient/(2*maxi(1,hits)),
		"cache_gradient": b_gradient/(2*maxi(1,hits)), "gradient_ratio": b_gradient/maxf(1e-9,a_gradient)
	}

func compare(label: String, roi := Rect2i()) -> void:
	set_sources(false)
	set_cached(true)
	await frames(WARM_FRAMES)
	var cached := capture(label+"_cached")
	var hold_max := 0.0
	for i in 4:
		await frames(8)
		hold_max = maxf(hold_max,cached.compute_image_metrics(capture(""),false).max)
	set_cached(false)
	await frames(6)
	var direct := capture(label+"_direct")
	set_sources(true)
	await frames(5)
	var direct_mask := capture("")
	set_cached(true)
	await frames(6)
	var sources := capture(label+"_sources")
	set_sources(false)
	if not roi.has_area():
		roi = Rect2i(Vector2i.ZERO,cached.get_size())
	var m := score(direct,cached,sources,direct_mask,roi)
	print("DETAIL ",label," position=",eye.position," roi=",roi," hold_max=",hold_max," ",m)
	check(m.terrain > roi.get_area()*0.8,label+" incomplete terrain coverage")
	check(m.live > 0.90,label+" uses coarse disk pages or direct shading for the close-up")
	check(m.direct_gradient > 0.3,label+" lacks usable reference texture")
	check(m.gradient_ratio >= 0.80 and m.gradient_ratio <= 1.20,label+" loses or invents fine texture contrast")
	check(m.mae <= 5.0,label+" cached material differs visibly from F7 direct shading")
	check(hold_max <= 2.0,label+" flickers while the camera is stationary")

# Traverse boundary+2 for both floor- and nearest-snapped 128-cell origins. Replay
# identical poses for each preview mode so gradients and masks refer to the same ground.
func moving_frames(prefix: String, cached: bool, source: bool, suffix: String) -> Array[Image]:
	set_cached(cached)
	set_sources(source)
	eye.position = Vector3(2978.0, 500.0, REPORTED.z)
	await frames(80)
	var images: Array[Image] = []
	for step in range(1, 49):
		eye.position.x = 2978.0 + step * 4.0
		await frames(1)
		if step in [8,24,40]:
			images.append(capture(prefix + "_cross_" + str(int(eye.position.x)) + "_" + suffix if not suffix.is_empty() else ""))
	return images

func compare_motion(prefix: String) -> void:
	var direct := await moving_frames(prefix,false,false,"direct")
	var cached := await moving_frames(prefix,true,false,"cached")
	var sources := await moving_frames(prefix,true,true,"sources")
	var masks := await moving_frames(prefix,false,true,"")
	set_cached(true)
	set_sources(false)
	for i in direct.size():
		var m := score(direct[i],cached[i],sources[i],masks[i])
		var label := "%s moving x=%d" % [prefix,3010+i*64]
		print("DETAIL ",label," ",m)
		check(m.terrain > root.size.x*root.size.y*0.8, label + " missing foreground")
		check(m.live > 0.80, label + " lost runtime coverage at a window crossing")
		check(m.gradient_ratio >= 0.75 and m.gradient_ratio <= 1.25 and m.mae <= 6.0, label + " blurred or shifted cached detail during translation")

func compare_ground(prefix: String) -> void:
	var pose := eye.global_transform
	var projection := eye.projection
	eye.projection = Camera3D.PROJECTION_PERSPECTIVE
	eye.position = Vector3(3029.1,125.0,-2590.8)
	eye.look_at(eye.position + Vector3(0.55,-0.48,-0.70))
	var roi := Rect2i(root.size.x/4,root.size.y/2,root.size.x/2,root.size.y/2-10)
	await compare(prefix+"_ground_perspective",roi)
	eye.projection = projection
	eye.global_transform = pose

func move_eye(destination: Vector3, steps: int) -> void:
	var initial := eye.position
	for i in steps:
		eye.position = initial.lerp(destination,(i+1.0)/steps)
		await frames(1)

func run_detail() -> void:
	if not folder.is_empty():
		check(DirAccess.make_dir_recursive_absolute(folder) == OK, "Could not create capture directory " + folder)
	await frames(20)
	check(is_instance_valid(terrain) and terrain.material.material_rvt_enabled,"Valley preview did not enable RVT")
	if not is_instance_valid(terrain):
		quit(1)
		return
	var locations := terrain.data.get_region_locations()
	var expected := PackedInt32Array()
	expected.resize(Terrain3DData.REGION_MAP_SIZE * Terrain3DData.REGION_MAP_SIZE)
	expected.fill(0)
	for i in locations.size():
		expected[Terrain3DData.get_region_map_index(locations[i])] = i + 1
	check(locations.size() > 0 and terrain.data.get_region_map() == expected,
			"Loaded valley region map contains a spurious terrain layer")
	check(RenderingServer.material_get_param(terrain.material.get_material_rid(), "_region_map") == expected,
			"Terrain material must receive the same valid region map as CPU height queries")
	current_scene.get_node("UI").hide()
	var player := current_scene.get_node("Player")
	player.hide()
	player.process_mode = Node.PROCESS_MODE_DISABLED
	terrain.ocean_enabled = false
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	root.add_child(eye)
	eye.projection = Camera3D.PROJECTION_ORTHOGONAL
	eye.size = VIEW_SIZE
	eye.near = 0.1
	eye.far = 16384.0
	eye.position = REPORTED
	eye.look_at(eye.position + Vector3.DOWN,Vector3.FORWARD)
	eye.make_current()
	terrain.set_camera(eye)
	terrain.set_clipmap_target(eye)
	var authored := Vector3(425.0, 0, -1400.0)
	authored.y = terrain.data.get_height(authored) + 28.0
	var boundary := Vector3(420.0,0,-2047.0)
	boundary.y = terrain.data.get_height(boundary) + 45.0
	for use_vt in [true,false]:
		if (cv.get_value("r.Terrain3D.VTHeight") != 0) != use_vt:
			press(KEY_F6)
		var prefix := "vt" if use_vt else "native"
		var ground_only := "--ground-perspective" in OS.get_cmdline_user_args()
		if ground_only:
			await compare_ground(prefix)
		else:
			await move_eye(REPORTED,12)
			await compare(prefix+"_reported")
		var grid: Vector4 = terrain.material.get_shader_param("_t3d_vt_grid")
		check((grid.w > 0.5) == use_vt,prefix+" did not use the requested height source")
		if ground_only or "--reported-only" in OS.get_cmdline_user_args():
			continue
		await compare_motion(prefix)
		if "--reported-and-motion" in OS.get_cmdline_user_args():
			continue
		# Move beyond an entire 512-cell detail window, including its overlap.
		await move_eye(Vector3(3679.1,850.0,-2610.8),48)
		await compare(prefix+"_outside_initial_window")
		await move_eye(authored,24)
		await compare(prefix+"_inside")
		await move_eye(boundary,30)
		await compare(prefix+"_region_edge")
		await move_eye(REPORTED,24)
		await compare(prefix+"_return")
		await compare_ground(prefix)
	print("Terrain close-up material regression: ", errors, " failures")
	quit(int(errors > 0))
