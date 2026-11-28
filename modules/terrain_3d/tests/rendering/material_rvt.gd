extends SceneTree
## Run with the Vulkan Forward+ engine and the demo project. Pass -- --demo for the authored valley, or -- --flyover to exercise both cooked endpoints after a cold start.
## Optional T3D_CAPTURE_DIR saves the actual same-camera direct, cached and source-marker images.

var terrain: Terrain3D
var camera: Camera3D
var failures := 0
var demo := false

func _initialize() -> void:
	run.call_deferred()

func frames(count: int) -> void:
	for i in count:
		await RenderingServer.frame_post_draw

func check(ok: bool, message: String) -> void:
	if not ok:
		failures += 1
		push_error(message)

func make_fixture() -> void:
	camera = Camera3D.new()
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = 42.0
	root.add_child(camera)
	camera.position = Vector3(0, 50, 0)
	camera.look_at(Vector3.ZERO, Vector3.FORWARD)
	camera.make_current()
	var light := DirectionalLight3D.new()
	root.add_child(light)
	light.rotation_degrees = Vector3(-56, -22, 0)
	var world := WorldEnvironment.new()
	world.environment = Environment.new()
	world.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	world.environment.ambient_light_color = Color(0.5,0.5,0.5)
	root.add_child(world)
	terrain = Terrain3D.new()
	terrain.free_editor_textures = false
	root.add_child(terrain)
	terrain.set_camera(camera)
	terrain.set_light_target(light)
	terrain.ocean_enabled = false
	terrain.region_size = Terrain3D.SIZE_64
	terrain.material.world_background = Terrain3DMaterial.NONE
	var albedo := Image.create_empty(64,64,false,Image.FORMAT_RGBA8)
	var normal := Image.create_empty(64,64,false,Image.FORMAT_RGBA8)
	for y in 64:
		for x in 64:
			var u := TAU * x / 64.0
			var v := TAU * y / 64.0
			albedo.set_pixel(x,y,Color(0.50+0.22*cos(u), 0.55+0.20*sin(v),0.32+0.11*cos(u+v),0.50))
			normal.set_pixel(x,y,Color(0.50+0.13*sin(u),0.5+0.18*cos(v),0.9,0.35+0.2*sin(v)))
	albedo.generate_mipmaps()
	normal.generate_mipmaps()
	var asset := Terrain3DTextureAsset.new()
	asset.albedo_texture = ImageTexture.create_from_image(albedo)
	asset.normal_texture = ImageTexture.create_from_image(normal)
	asset.uv_scale = 0.125
	asset.ao_light_affect = 0.8
	terrain.assets.set_texture_asset(0,asset)
	for rz in range(-1,1):
		for rx in range(-1,1):
			var region := terrain.data.add_region_blank(Vector2i(rx,rz), false)
			var heights := Image.create_empty(64,64,false,Image.FORMAT_RF)
			for y in 64:
				for x in 64:
					var gx := x + rx * 64
					var gz := y + rz * 64
					heights.set_pixel(x,y,Color(0.22*gx + 1.2*sin(gz*0.19),0,0))
			region.set_height_map(heights)
			region.calc_height_range()
	terrain.data.update_maps()

func open_demo() -> void:
	change_scene_to_file("res://demo/Demo.tscn")
	await scene_changed
	terrain = current_scene.get_node("Terrain3D")
	current_scene.get_node("UI").hide()
	current_scene.get_node("Terrain3DParticles").hide()
	terrain.assets.get_mesh_asset(0).set_enabled(false)
	terrain.ocean_enabled = false
	await frames(100)
	var player := current_scene.get_node("Player")
	player.hide()
	player.set_physics_process(false)
	var previous := root.get_camera_3d()
	camera = Camera3D.new()
	camera.fov = previous.fov
	camera.near = previous.near
	camera.far = previous.far
	root.add_child(camera)
	# Keep captures comparable across runs. The player camera also processes desktop mouse motion.
	camera.position = Vector3(217.6919,106.7327,-1832.622)
	var pitch := deg_to_rad(25.0)
	camera.look_at(camera.position + Vector3(0.98422*cos(pitch),-sin(pitch),-0.176947*cos(pitch)))
	camera.make_current()
	terrain.set_camera(camera)
	terrain.set_clipmap_target(camera)

func shot() -> Image:
	var img := root.get_texture().get_image()
	img.convert(Image.FORMAT_RGB8)
	return img

func save(img: Image, suffix: String) -> void:
	var folder := OS.get_environment("T3D_CAPTURE_DIR")
	if not folder.is_empty():
		img.save_png(folder.path_join("material_%s_%s.png" % ["demo" if demo else "fixture",suffix]))

func compare(label: String, channel: int = 0) -> float:
	var mat := terrain.material
	mat.set_shader_param("_t3d_material_rvt_channel",channel)
	mat.set_shader_param("_t3d_material_rvt_debug",false)
	mat.set_shader_param("_t3d_material_rvt_bypass",true)
	await frames(8)
	var direct := shot()
	mat.set_shader_param("_t3d_material_rvt_bypass",false)
	await frames(8)
	var cached := shot()
	await frames(12)
	var settled := shot().get_data()
	mat.set_shader_param("_t3d_material_rvt_debug",true)
	await frames(8)
	var marker := shot()
	# The authored demo's tonemapper maps pure green to yellow-green. Compare against
	# a same-camera all-direct marker so lighting, foliage and sky cannot count as hits.
	mat.set_shader_param("_t3d_material_rvt_bypass",true)
	await frames(4)
	var direct_marker := shot().get_data()
	mat.set_shader_param("_t3d_material_rvt_bypass",false)
	mat.set_shader_param("_t3d_material_rvt_debug",false)
	save(direct,label+"_direct")
	save(cached,label+"_cached")
	save(marker,label+"_sources")
	var a := direct.get_data()
	var b := cached.get_data()
	var m := marker.get_data()
	var hit := 0
	var direct_count := 0
	var mixed_count := 0
	var mixed_error := 0.0
	var error := 0.0
	var squared := 0.0
	var frame_error := 0.0
	var histogram := PackedInt32Array()
	histogram.resize(256)
	for i in range(0,m.size(),3):
		if m[i+1] > m[i]+48 and m[i+1] > m[i+2]+48 and m[i+1] > direct_marker[i+1]+72:
			hit += 1
			for component in 3:
				var d := absi(a[i+component]-b[i+component])
				error += d
				squared += d*d
				frame_error += absi(b[i+component]-settled[i+component])
				histogram[d] += 1
		elif m[i+2] > m[i]+48 and m[i+2] > m[i+1]+48 and m[i+2] > direct_marker[i+2]+72:
			mixed_count += 1
			for component in 3:
				mixed_error += absi(a[i+component]-b[i+component])
		elif m[i] > 160 and m[i] > m[i+1]+110 and m[i] > m[i+2]+110:
			direct_count += 1
	var channels := maxi(hit*3,1)
	var p95 := 0
	var total := 0
	for n in 256:
		total += histogram[n]
		if total >= channels*0.95:
			p95 = n
			break
	var fraction := float(hit)/maxi(hit+mixed_count+direct_count,1)
	var mean := error/channels
	print(label," covered=",fraction," pure_hits=",hit," mixed=",mixed_count," mixed_mae=",mixed_error/maxi(mixed_count*3,1)," direct=",direct_count," mae=",mean," rms=",sqrt(squared/channels)," p95=",p95, " hold_mae=", frame_error/channels)
	check(frame_error/channels <= (1.0 if demo else 0.25),"Stationary warm material flickered between frames")
	check(hit>=1000 and fraction>(0.10 if demo else 0.65),"Too few actual material cache hits")
	check(mean <= (9.0 if demo else 4.0),"Cached material departs from direct material on hit pixels")
	check(p95 <= (30 if demo else 15),"Terrain PBR 95th percentile mismatch")
	return mean

func count_page_sources(label: String) -> Vector2i:
	var mat := terrain.material
	mat.set_shader_param("_t3d_material_rvt_sources",true)
	await frames(6)
	var source_image := shot()
	save(source_image,label+"_page_sources")
	var color := source_image.get_data()
	mat.set_shader_param("_t3d_material_rvt_bypass",true)
	await frames(4)
	var reference := shot().get_data()
	mat.set_shader_param("_t3d_material_rvt_sources",false)
	mat.set_shader_param("_t3d_material_rvt_bypass",false)
	var counts := Vector2i.ZERO
	var terrain_pixels := 0
	var direct_pixels := 0
	var skyline := Vector2i.ZERO
	var foreground := Vector2i.ZERO
	var skyline_end := source_image.get_width() * (source_image.get_height() / 2) * 3
	var foreground_start := source_image.get_width() * int(source_image.get_height() * 0.7) * 3
	for i in range(0,color.size(),3):
		# The bypass reference marks only terrain red, excluding the sky, water and HUD.
		if reference[i] < 180 or reference[i] < reference[i+1]+110 or reference[i] < reference[i+2]+110:
			continue
		terrain_pixels += 1
		if color[i] > color[i+1]+110 and color[i] > color[i+2]+110:
			direct_pixels += 1
		if color[i+2] > color[i+1]+48 and color[i+2] > color[i]+48 and color[i+2] > reference[i+2]+72:
			counts.y += 1
			if i < skyline_end:
				skyline.y += 1
			elif i >= foreground_start:
				foreground.y += 1
		elif color[i+1] > color[i+2]+48 and color[i+1] > color[i]+48 and color[i+1] > reference[i+1]+72:
			counts.x += 1
			if i < skyline_end:
				skyline.x += 1
			elif i >= foreground_start:
				foreground.x += 1
	print(label," sampled runtime=",counts.x," disk=",counts.y," direct=",direct_pixels," terrain=",terrain_pixels)
	if demo:
		check(terrain_pixels > 1000 and direct_pixels < terrain_pixels * 0.005, "Warm valley terrain unexpectedly used direct shading")
	if label == "valley_horizon":
		print("Horizon RVT/SVT=", skyline, " foreground RVT/SVT=", foreground)
		check(skyline.y > skyline.x and foreground.x > 9 * foreground.y, "Expected streamed hills above runtime foreground at the reported position")
	return counts

# Run in a separate process after baking both authored demo endpoints.
func run_flyover() -> void:
	demo = true
	await open_demo()
	var mat := terrain.material
	var cv := Engine.get_singleton("CVars")
	cv.set_value("r.Terrain3D.Mode",1)
	cv.set_value("r.Terrain3D.VTHeight",1)
	mat.material_rvt_stream_file = "res://demo/data/terrain_near.svt"
	mat.material_rvt_far_stream_file = "res://demo/data/terrain_far.svt"
	mat.material_rvt_enabled = true
	var initial := camera.global_transform
	await frames(180)
	for far_endpoint in [false,true]:
		var stats := RenderingServer.runtime_virtual_texture_get_stats(mat.get_material_rvt_rid(far_endpoint))
		print("Cold material SVT endpoint=",far_endpoint," stats=",stats)
		check(int(stats.stream_first_mip) >= 0 and int(stats.disk_pages)>0, "Cold start rejected the cooked material endpoint")
	if failures:
		quit(1)
		return

	await compare("valley_near")
	await count_page_sources("valley_near")
	# Ground-level view from the reported player position. A straight overhead
	# flyover alone misses both magnified foreground and the dual-scale distance band.
	camera.position = Vector3(311.1, 116.3, -1808.5)
	camera.look_at(camera.position + Vector3(1.0, -0.13, 0.35))
	await frames(150)
	var horizon := await count_page_sources("valley_horizon")
	check(horizon.x > 3000 and horizon.y > 3000, "Ground-level valley must show both runtime detail and streamed terrain")
	await compare("valley_horizon")
	var center := Vector3(420,0,-1400)
	center.y = terrain.data.get_height(center)
	for stop in [[190.0,"transition"],[620.0,"distant"],[300.0,"descent"]]:
		var start := camera.global_transform
		var target := Transform3D(Basis(),center+Vector3(0,stop[0],0)).looking_at(center,Vector3.FORWARD)
		for i in 45:
			camera.global_transform = start.interpolate_with(target,(i+1.0)/45.0)
			await frames(1)
		await frames(85)
		var label := "valley_"+str(stop[1])
		var counts := await count_page_sources(label)
		if stop[1] == "distant":
			check(counts.y>3000,"The distant valley did not display baked material pixels")
		await compare(label)
	camera.global_transform = initial
	await frames(150)
	check((await count_page_sources("valley_return")).x>3000,"Near runtime detail did not return")
	await compare("valley_return")
	check(not terrain.data.get_resident_height_maps_rid().is_valid(),"The valley retained the complete native height array")
	print("Terrain3D valley cold flyover failures=",failures)
	quit(int(failures>0))

func run() -> void:
	if "--flyover" in OS.get_cmdline_user_args():
		await run_flyover()
		return
	demo = "--demo" in OS.get_cmdline_user_args()
	if demo:
		await open_demo()
	else:
		make_fixture()
	var cv := Engine.get_singleton("CVars")
	cv.set_value("r.Terrain3D.Mode",1)
	cv.set_value("r.Terrain3D.VTHeight",1)
	terrain.material.material_rvt_enabled = true
	await frames(220)
	var rid := terrain.material.get_material_rvt_rid()
	check(not terrain.data.get_resident_height_maps_rid().is_valid(),"Height VT material writers retained the complete native height array")
	check(rid.is_valid(),"Missing material RVT")
	if not rid.is_valid():
		quit(1)
		return
	print("Material page stats ",RenderingServer.runtime_virtual_texture_get_stats(rid), " camera=",camera.position, " grid/layout=",terrain.material.get_shader_param("_t3d_material_rvt_grid")," / ",terrain.material.get_shader_param("_t3d_material_rvt_layout"))
	# --bake-near=<path> and --bake-far=<path> author a reusable pair for this exact demo.
	var bake_levels := 3
	var near_levels := 0
	var far_levels := 0
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--bake-levels="):
			bake_levels = int(arg.get_slice("=",1))
		elif arg.begins_with("--bake-near-levels="):
			near_levels = int(arg.get_slice("=",1))
		elif arg.begins_with("--bake-far-levels="):
			far_levels = int(arg.get_slice("=",1))
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--bake-near=") or arg.begins_with("--bake-far="):
			var path := arg.get_slice("=",1)
			var far_endpoint := arg.begins_with("--bake-far=")
			var levels := far_levels if far_endpoint else near_levels
			var result := terrain.material.bake_material_svt(path, levels if levels > 0 else bake_levels, far_endpoint)
			print("Material SVT bake ",path," result=",result)
			check(result == OK,"Authored material SVT bake failed")
			if far_endpoint:
				terrain.material.material_rvt_far_stream_file = path
			else:
				terrain.material.material_rvt_stream_file = path
			await frames(50)
			print("Material SVT attached ", RenderingServer.runtime_virtual_texture_get_stats(terrain.material.get_material_rvt_rid(far_endpoint)))
	await compare("warm")
	var fixture_stream := ""
	if not demo:
		for channel in [1,2,3,4]:
			await compare("pbr_%d"%channel,channel)
		var pages_before_sun := int(RenderingServer.runtime_virtual_texture_get_stats(rid).rendered_total)
		terrain.get_light_target().rotate_x(1.1)
		await frames(16)
		await compare("sun",3)
		check(int(RenderingServer.runtime_virtual_texture_get_stats(rid).rendered_total) == pages_before_sun,"Moving a directional light re-rendered material pages")

		fixture_stream = "user://terrain-material-%d.svt" % OS.get_process_id()
		check(terrain.material.bake_material_svt(fixture_stream, 2) == OK, "Material SVT bake failed")
		check(not terrain.data.get_resident_height_maps_rid().is_valid(), "Offline bake retained the temporary native height array")
		terrain.material.material_rvt_stream_file = fixture_stream
		await frames(100)
		var streamed := RenderingServer.runtime_virtual_texture_get_stats(rid)
		print("Material SVT stats ",streamed)
		check(int(streamed.get("disk_pages",0)) > 0, "Baked physical material pages were not read from disk")
		var last_level := int(terrain.material.get_shader_param("_t3d_material_rvt_layout").y)
		var disk_root := RenderingServer.runtime_virtual_texture_get_page_info(rid,last_level,0,0)
		check(disk_root.from_disk,"The coarsest material page did not originate from the baked file")
		await compare("streamed")
		check((await count_page_sources("close")).x>1000,"Near camera did not sample runtime material pages")
		var original_size := camera.size
		camera.size = 256.0
		camera.position.x += 6.0
		await frames(80)
		check((await count_page_sources("distant")).y>1000,"Distant terrain did not sample the baked material pages")
		await compare("distant")
		camera.size = original_size
		camera.position.x -= 6.0
		await frames(80)
		check((await count_page_sources("returned")).x>1000,"Near material detail did not return after a distant view")

		terrain.material.set_shader_param("_t3d_material_rvt_channel",0)
		await frames(8)
		var before := shot()
		for z in range(-8,8):
			for x in range(-8,8):
				terrain.data.set_color(Vector3(x,0,z),Color(1.0,0.12,0.12))
		terrain.data.update_maps(Terrain3DRegion.TYPE_COLOR)
		await frames(120)
		var after := shot()
		check(before.compute_image_metrics(after,false)["max"]>16,"Editing the source did not reach the visible cached material")
		check(terrain.material.get_material_rvt_rid() == rid, "Local edit replaced material page pool")
		var edited_root := RenderingServer.runtime_virtual_texture_get_page_info(rid,last_level,0,0)
		check(edited_root.resident and not edited_root.from_disk and edited_root.content_serial > disk_root.content_serial,"The coarse SVT kept stale material after a brush edit")
		await compare("edited")
		# Reopening the old file after a brush stroke must reject its source identity.
		var disk_reads := int(RenderingServer.runtime_virtual_texture_get_stats(rid).disk_pages)
		terrain.material.material_rvt_stream_file = ""
		terrain.material.material_rvt_stream_file = fixture_stream
		await frames(80)
		var stale := RenderingServer.runtime_virtual_texture_get_stats(rid)
		check(int(stale.stream_first_mip) == -1 and int(stale.disk_pages) == disk_reads, "Reopening a stale bake silently accepted old material")
		await compare("stale_file")
		# The selected file is still attached under the new signature, but its old header
		# was rejected. Publishing a new bake at that path must reactivate the disk root.
		check(terrain.material.bake_material_svt(fixture_stream, 1) == OK, "Failed to replace the rejected SVT")
		await frames(80)
		var rebaked := RenderingServer.runtime_virtual_texture_get_stats(rid)
		check(int(rebaked.stream_first_mip) == last_level and RenderingServer.runtime_virtual_texture_get_page_info(rid,last_level,0,0).from_disk, "Rebaking the rejected path kept its old index")
		# The source signature and path are identical this time, but the new file has a
		# longer index. Insist that the already active attachment picks it up.
		check(terrain.material.bake_material_svt(fixture_stream, 2) == OK, "Failed to replace an active SVT")
		await frames(80)
		check(int(RenderingServer.runtime_virtual_texture_get_stats(rid).stream_first_mip) == last_level-1, "Rebaking the active path retained its previous mip range")
		await compare("rebaked")
		# Reopen an editor-style bake with only the runtime arrays resident. All
		# inputs here are procedural and have no files to reload for verification.
		var source_asset := terrain.assets.get_texture_asset(0)
		terrain.material.material_rvt_enabled = false
		terrain.assets.clear_textures(false)
		terrain.material.material_rvt_enabled = true
		await frames(80)
		rid = terrain.material.get_material_rvt_rid()
		check(RenderingServer.runtime_virtual_texture_get_page_info(rid,last_level,0,0).from_disk,
				"Releasing the authoring texture list invalidated an unchanged material bake")
		# Preserve the resource name, material settings, and file path but replace
		# the albedo pixels. A runtime-only material must now reject the same file.
		terrain.material.material_rvt_enabled = false
		var changed_image := source_asset.albedo_texture.get_image()
		changed_image.fill(Color(0.9,0.05,0.1,0.5))
		changed_image.generate_mipmaps()
		source_asset.albedo_texture = ImageTexture.create_from_image(changed_image)
		terrain.assets.set_texture_asset(0,source_asset)
		terrain.assets.clear_textures(false)
		terrain.material.material_rvt_enabled = true
		await frames(80)
		rid = terrain.material.get_material_rvt_rid()
		check(int(RenderingServer.runtime_virtual_texture_get_stats(rid).stream_first_mip) == -1,
				"Released textures hid an albedo change from material SVT validation")
		terrain.material.material_rvt_enabled = false
		terrain.assets.clear_textures(true)
		terrain.material.material_rvt_enabled = true
		await frames(60)
		check(terrain.material.bake_material_svt(fixture_stream, 1) == OK,
				"A genuinely empty asset palette must still be able to bake its procedural surface")
		await frames(80)
		rid = terrain.material.get_material_rvt_rid()
		check(RenderingServer.runtime_virtual_texture_get_page_info(rid,last_level,0,0).from_disk,
				"A bake without any texture slots must validate and supply its root page")
	terrain.material.material_rvt_enabled = false
	await frames(8)
	if not fixture_stream.is_empty() and FileAccess.file_exists(fixture_stream):
		DirAccess.remove_absolute(fixture_stream)
	check(not terrain.material.get_material_rvt_rid().is_valid(),"Disabling material RVT retained its physical pages")
	print("Terrain material RVT regression demo=",demo," failures=",failures)
	quit(int(failures>0))
