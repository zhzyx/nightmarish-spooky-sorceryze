extends SceneTree
## Run with the custom Forward+ editor binary, --path <Terrain3D demo project>
## --rendering-method forward_plus --fixed-fps 60 --script <this file>.

var failures: Array[String] = []
var terrain: Terrain3D
var camera: Camera3D
var cv: Object
var tile_rows := PackedFloat32Array()
var command := PackedInt32Array()
var ready := Semaphore.new()

func _initialize() -> void:
	run.call_deferred()

func check(ok: bool, message: String) -> void:
	if not ok:
		push_error(message)
		failures.append(message)

func frames(count: int) -> void:
	for i in count:
		await RenderingServer.frame_post_draw

func read_instances(mm: RID) -> void:
	var rd := RenderingServer.get_rendering_device()
	command = rd.buffer_get_data(RenderingServer.multimesh_get_command_buffer_rd_rid(mm)).to_int32_array()
	tile_rows.clear()
	if command[1] > 0 and command[1] <= RenderingServer.multimesh_get_instance_count(mm):
		tile_rows = rd.buffer_get_data(RenderingServer.multimesh_get_buffer_rd_rid(mm), 0, command[1] * 64).to_float32_array()
	ready.post()

func verify_cut() -> void:
	var mm := terrain.get_quadtree_multimesh_rid()
	check(mm.is_valid(), "Missing quadtree MultiMesh")
	if not mm.is_valid():
		return
	RenderingServer.call_on_render_thread(read_instances.bind(mm))
	ready.wait()
	var res := int(cv.get_value("r.Terrain3D.TileRes"))
	check(command[0] == res * res * 6 and tile_rows.size() > 0, "Invalid indirect draw command %s" % [command])
	var tiles := {}
	var spacing := terrain.vertex_spacing
	var base := res * spacing
	# The demo's procedural background uses the entire region-map grid, centered at zero.
	var side := terrain.region_size * 32
	var origin := Vector2(-side, -side) * (0.5 * spacing)
	for offset in range(0, tile_rows.size(), 16):
		var stride := roundi(tile_rows[offset] / spacing)
		var pos := Vector2(tile_rows[offset + 3], tile_rows[offset + 11])
		var cell := Vector2i(((pos - origin) / base).round())
		var key := Vector3i(cell.x, cell.y, stride)
		check(not tiles.has(key), "Duplicate tile %s" % key)
		tiles[key] = tile_rows.slice(offset + 12, offset + 16)
	for tile: Vector3i in tiles:
		var parent := tile.z * 2
		while parent * res <= side:
			var key := Vector3i(tile.x - posmod(tile.x, parent), tile.y - posmod(tile.y, parent), parent)
			check(not tiles.has(key), "Ancestor overlaps %s" % tile)
			parent *= 2
		var x := tile.x
		var z := tile.y
		var w := tile.z
		var mid := floori(w * 0.5)
		var adjacent := [Vector2i(x-1,z+mid), Vector2i(x+w,z+mid), Vector2i(x+mid,z-1), Vector2i(x+mid,z+w)]
		for edge in 4:
			var neighbor := covering(tiles, adjacent[edge], side / res)
			if neighbor > 0:
				check(is_equal_approx(tiles[tile][edge], maxf(1.0, float(neighbor)/w)), "Wrong seam at %s edge %d" % [tile,edge])
	var missing := 0
	for loc: Vector2i in terrain.data.get_region_locations():
		var corner := Vector2i(((Vector2(loc * terrain.region_size) * spacing - origin) / base).round())
		for z in range(terrain.region_size / res):
			for x in range(terrain.region_size / res):
				var cell := corner + Vector2i(x,z)
				var center := origin + (Vector2(cell) + Vector2(0.5,0.5)) * base
				var point := Vector3(center.x, 0, center.y)
				point.y = terrain.data.get_height(point)
				if is_finite(point.y) and camera.is_position_in_frustum(point) and camera.position.distance_to(point) < float(cv.get_value("r.Terrain3D.MaxDistance")) and covering(tiles, cell, side / res) == 0:
					missing += 1
	check(missing == 0, "%d uncovered authored cells" % missing)
	print("Quadtree GPU cut at ", camera.position, ": ", command[1], " patches, ", missing, " missing")

func covering(tiles: Dictionary, cell: Vector2i, max_stride: int) -> int:
	var stride := 1
	while stride <= max_stride:
		if tiles.has(Vector3i(cell.x - posmod(cell.x, stride), cell.y - posmod(cell.y, stride), stride)):
			return stride
		stride *= 2
	return 0

func stride_at(point: Vector3) -> int:
	var mm := terrain.get_quadtree_multimesh_rid()
	RenderingServer.call_on_render_thread(read_instances.bind(mm))
	ready.wait()
	var res := int(cv.get_value("r.Terrain3D.TileRes"))
	for offset in range(0, tile_rows.size(), 16):
		var origin := Vector2(tile_rows[offset + 3], tile_rows[offset + 11])
		var side := tile_rows[offset] * res
		if Rect2(origin, Vector2(side, side)).has_point(Vector2(point.x, point.z)):
			return roundi(tile_rows[offset] / terrain.vertex_spacing)
	return 0

func verify_view_selection(vt: bool) -> void:
	var pose := camera.global_transform
	var origin := camera.global_position
	origin.y = terrain.data.get_height(origin)
	check(is_finite(origin.y), "Expected a finite height at the demo camera")
	if not is_finite(origin.y): return
	camera.position = origin + Vector3.UP * 40.0
	camera.look_at(origin, Vector3.FORWARD)
	await frames(12)
	var near_stride := stride_at(origin)
	camera.position.y += 1500.0
	await frames(12)
	var far_stride := stride_at(origin)
	check(near_stride > 0 and far_stride > near_stride, "Nadir LOD did not adapt to altitude: %d -> %d" % [near_stride, far_stride])
	print("Nadir patch stride, 40 m -> 1540 m: ", near_stride, " -> ", far_stride)
	var original_fov := camera.fov
	camera.fov = 35.0
	await frames(8)
	var zoom_stride := stride_at(origin)
	check(zoom_stride > 0 and zoom_stride < far_stride, "Narrow FOV did not refine the elevated view: %d -> %d" % [far_stride, zoom_stride])
	camera.fov = original_fov
	camera.position = origin + Vector3.UP * 45
	camera.look_at(camera.position + Vector3.FORWARD, Vector3.UP)
	await frames(8)
	var front := origin + Vector3.FORWARD * 550
	var back := origin + Vector3.BACK * 550
	check(stride_at(front) > 0 and stride_at(back) == 0, "The color pass retained the backwards patch or dropped the forward patch")
	camera.rotate_y(PI)
	await frames(8)
	check(stride_at(front) == 0 and stride_at(back) > 0, "Rotating without translating did not replace the color cut")
	camera.global_transform = pose
	await frames(8)
	if not vt: return
	var pages := terrain.get_height_vt_rid()
	var first := RenderingServer.runtime_virtual_texture_get_stats(pages)
	var secondary := SubViewport.new()
	secondary.size = Vector2i(160,90)
	secondary.world_3d = camera.get_world_3d()
	secondary.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	root.add_child(secondary)
	var eye := Camera3D.new()
	secondary.add_child(eye)
	eye.global_transform = pose
	eye.rotate_y(0.8)
	await frames(32)
	var both := RenderingServer.runtime_virtual_texture_get_stats(pages)
	check(both.gpu_feedback_batches > first.gpu_feedback_batches and both.gpu_feedback_pages > 0, "Missing live GPU VT feedback")
	check(both.gpu_feedback_views >= 2, "A second viewport replaced primary VT demand")
	secondary.queue_free()
	await frames(40)
	var single := RenderingServer.runtime_virtual_texture_get_stats(pages)
	check(single.gpu_feedback_views < both.gpu_feedback_views, "The removed viewport kept requesting height pages")
	print("VT feedback: ", both.gpu_feedback_views, " views -> ", single.gpu_feedback_views, "; ", single.gpu_feedback_pages, " pages")

func height_edit() -> void:
	var size := terrain.region_size
	var loc: Vector2i = terrain.data.get_region_locations()[0]
	var middle := (Vector2(loc) + Vector2(0.5, 0.5)) * size * terrain.vertex_spacing
	camera.environment = Environment.new()
	camera.environment.background_mode = Environment.BG_COLOR
	camera.environment.background_color = Color.BLACK
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = 12.0 * terrain.vertex_spacing
	camera.position = Vector3(middle.x, 1800, middle.y)
	camera.look_at(Vector3(middle.x, 0, middle.y), Vector3.FORWARD)
	var shader := terrain.material.get_shader_rid()
	var source := RenderingServer.shader_get_code(shader)
	var start := source.find("void fragment()")
	check(start >= 0, "Could not locate terrain fragment shader")
	if start < 0:
		return
	# Keep the production vertex shader. Read its interpolated world height as red or green.
	var diagnostic := source.left(start).replace("render_mode ", "render_mode unshaded, ") + "void fragment() { ALBEDO = v_vertex.y > 90.0 ? vec3(0,1,0) : vec3(1,0,0); }"
	RenderingServer.shader_set_code(shader, diagnostic)
	for height: float in [20.0, 960.0]:
		for z in range(-8,9):
			for x in range(-8,9):
				var point := Vector3(middle.x + x * terrain.vertex_spacing, 0, middle.y + z * terrain.vertex_spacing)
				terrain.data.set_height(point, height)
				terrain.data.set_control_hole(point, false)
		terrain.data.update_maps()
		check(terrain.data.get_height_range().y >= height, "Edited height exceeds terrain draw bounds")
		await frames(12)
		var image := root.get_texture().get_image()
		var color := image.get_pixel(image.get_width()/2, image.get_height()/2)
		check((color.g > color.r + 0.4) if height > 90 else (color.r > color.g + 0.4), "Rendered height %s at %s" % [height,color])
	for z in range(-8,9):
		for x in range(-8,9):
			terrain.data.set_control_hole(Vector3(middle.x + x * terrain.vertex_spacing, 0, middle.y + z * terrain.vertex_spacing), true)
	terrain.data.update_maps()
	await frames(12)
	var image := root.get_texture().get_image()
	var hole := image.get_pixel(image.get_width()/2, image.get_height()/2)
	check(hole.g < hole.r + 0.4, "The edited hole still drew terrain")
	RenderingServer.shader_set_code(shader, source)

# The lit demo also exercises Forward+ lighting. Measure the worst framebuffer channel
# separately from the exact displacement check so a lighting change cannot hide a moving mesh.
func verify_stationary() -> void:
	var reference := root.get_texture().get_image()
	var baseline := reference.get_data()
	var max_channel_delta := 0
	for i in 119:
		await RenderingServer.frame_post_draw
		var frame := root.get_texture().get_image()
		if frame.get_data() != baseline:
			max_channel_delta = maxi(max_channel_delta, int(reference.compute_image_metrics(frame, false)["max"]))
	print("Stationary lighting over 120 frames: max channel delta ", max_channel_delta, "/255")
	check(max_channel_delta <= 1, "Stationary lit terrain differs by %d/255" % max_channel_delta)

	var shader := terrain.material.get_shader_rid()
	var code := RenderingServer.shader_get_code(shader)
	var fragment := code.find("void fragment()")
	check(fragment >= 0, "Could not locate the terrain fragment shader")
	if fragment >= 0:
		# Isolate the quadtree draw from the demo sky, instanced props and lights.
		var terrain_layers := terrain.render_layers
		var camera_layers := camera.cull_mask
		var environment := camera.environment
		terrain.render_layers = 1 << 12
		camera.cull_mask = 1 << 12
		camera.environment = Environment.new()
		camera.environment.background_mode = Environment.BG_COLOR
		camera.environment.background_color = Color.BLACK
		var display_height := code.left(fragment).replace("render_mode ", "render_mode unshaded, ")
		display_height += "void fragment() { ALBEDO = fract(v_vertex.y * vec3(0.0931, 0.7311, 2.173)); }"
		RenderingServer.shader_set_code(shader, display_height)
		await frames(120)
		var surface_image := root.get_texture().get_image()
		var center := surface_image.get_size() / 2
		check(surface_image.get_pixelv(center).v > 0.05, "The isolated quadtree did not cover the valley center")
		var surface := surface_image.get_data()
		for i in 119:
			await RenderingServer.frame_post_draw
			if root.get_texture().get_image().get_data() != surface:
				check(false, "Stationary displaced surface changed at frame %d" % (i + 1))
				break
		RenderingServer.shader_set_code(shader, code)
		camera.environment = environment
		camera.cull_mask = camera_layers
		terrain.render_layers = terrain_layers
		await frames(30)

func run() -> void:
	change_scene_to_file("res://demo/Demo.tscn")
	await scene_changed
	terrain = current_scene.get_node("Terrain3D")
	cv = Engine.get_singleton("CVars")
	cv.set_value("r.Terrain3D.Mode", 1)
	var vt := "--height-vt" in OS.get_cmdline_user_args()
	cv.set_value("r.Terrain3D.VTHeight", int(vt))
	current_scene.get_node("UI").hide()
	current_scene.get_node("Terrain3DParticles").hide()
	var player := current_scene.get_node("Player")
	player.hide()
	player.process_mode = Node.PROCESS_MODE_DISABLED
	terrain.assets.get_mesh_asset(0).set_enabled(false)
	terrain.ocean_enabled = false
	camera = Camera3D.new()
	camera.fov = 75.0
	camera.near = 0.25
	camera.far = 16384.0
	root.add_child(camera)
	# The valley viewpoint is independent of CharacterBody3D settling and captured mouse events.
	camera.position = Vector3(217.6919, 106.7327, -1832.622)
	camera.look_at(camera.position + Vector3(0.892, -0.422618, -0.16037), Vector3.UP)
	camera.make_current()
	terrain.set_camera(camera)
	terrain.set_clipmap_target(camera)
	await frames(100)
	if vt:
		check(terrain.get_height_vt_rid().is_valid(), "Expected height VT on the rendered mesh")
	var pose := camera.global_transform
	await verify_stationary()
	await verify_view_selection(vt)
	await verify_cut()
	var light: DirectionalLight3D = current_scene.get_node("Environment/DirectionalLight3D")
	camera.global_transform = pose
	await frames(100)
	var reference := root.get_texture().get_image()
	light.shadow_enabled = false
	await frames(15)
	var light_delta := float(reference.compute_image_metrics(root.get_texture().get_image(), false)["max"])
	check(light_delta > 8, "Disabling directional shadows did not change the demo")
	light.shadow_enabled = true
	var cast := terrain.cast_shadows
	terrain.cast_shadows = RenderingServer.SHADOW_CASTING_SETTING_OFF
	await frames(15)
	var terrain_delta := float(reference.compute_image_metrics(root.get_texture().get_image(), false)["max"])
	print("Valley shadow toggle, light/terrain max channel change: ", light_delta, " / ", terrain_delta)
	check(terrain_delta > 8, "The terrain did not cast a visible shadow")
	terrain.cast_shadows = cast
	for step in 40:
		camera.global_position = pose.origin + Vector3(step * 8, 0, step * 3)
		await RenderingServer.frame_post_draw
		if step in [1, 16, 32, 39]:
			await verify_cut()
	cv.set_value("r.Terrain3D.Mode", 0)
	await frames(20)
	check(not terrain.get_quadtree_multimesh_rid().is_valid(), "Mode 0 kept the Mode 1 draw")
	cv.set_value("r.Terrain3D.Mode", 1)
	await frames(20)
	await verify_cut()
	terrain.vertex_spacing = 0.5
	await frames(20)
	await verify_cut()
	cv.set_value("r.Terrain3D.MaxDistance", 700)
	cv.set_value("r.Terrain3D.MaxLod", 2)
	cv.set_value("r.Terrain3D.TileRes", 64)
	terrain.vertex_spacing = 0.3
	await frames(20)
	await verify_cut()
	await height_edit()
	terrain.material.world_background = Terrain3DMaterial.NONE
	for region: Vector2i in terrain.data.get_region_locations().duplicate():
		terrain.data.remove_regionl(region, false)
	terrain.data.update_maps()
	await frames(12)
	check(not terrain.get_quadtree_multimesh_rid().is_valid(), "Empty NONE background submitted terrain")
	terrain.data.add_region_blank(Vector2i(-1, -1))
	await frames(12)
	check(terrain.get_quadtree_multimesh_rid().is_valid(), "Adding a region to empty terrain did not restore its draw")
	print("Quadtree regression (VT=", vt, "): ", failures.size(), " failures")
	quit(0 if failures.is_empty() else 1)
