extends SceneTree
## Compare sparse pages, optional streamed coarse mips and the layered GPU producer in Forward+.

var failures := 0
var sources: Array[Image] = []
var source_map := PackedInt32Array([1, 2, 3, 4])
var terrain_vt: RID
var native_array: RID

func _initialize() -> void:
	run.call_deferred()

func check(value: bool, msg: String) -> void:
	if not value:
		failures += 1
		push_error(msg)

func frames(n: int) -> void:
	for i in n:
		await RenderingServer.frame_post_draw

func read_height(level: int, page: Vector2i, local: Vector2i) -> float:
	var info := RenderingServer.runtime_virtual_texture_get_page_info(terrain_vt, level, page.x, page.y)
	if not info.get("resident", false):
		check(false, "Expected resident page at %s mip %d" % [page, level])
		return NAN
	var texture := RenderingServer.runtime_virtual_texture_get_physical_texture(terrain_vt, 0)
	var pool := RenderingServer.texture_2d_get(texture)
	if pool == null:
		check(false, "Missing RF pool")
		return NAN
	var pos := Vector2i(info.pool_x, info.pool_y) * 20 + Vector2i(2,2) + local
	return pool.get_pixelv(pos).r

func wait_pages() -> Dictionary:
	for i in 300:
		await RenderingServer.frame_post_draw
		var stats := RenderingServer.runtime_virtual_texture_get_stats(terrain_vt)
		if stats.levels.size() == 3 and stats.levels[0] == 16 and stats.rendered_this_frame == 0:
			await frames(8)
			return RenderingServer.runtime_virtual_texture_get_stats(terrain_vt)
	check(false, "Page production did not fill the small fixture")
	return RenderingServer.runtime_virtual_texture_get_stats(terrain_vt)

func create_source(gpu: bool, file: String) -> void:
	terrain_vt = RenderingServer.runtime_virtual_texture_create()
	RenderingServer.runtime_virtual_texture_configure(terrain_vt, RenderingServer.RVT_MATERIAL_WORLD_HEIGHT, 2, 16, 2, 8)
	RenderingServer.runtime_virtual_texture_set_height_source(terrain_vt, native_array if gpu else RID(), source_map, 32, Vector2i(-32,-32),64)
	for i in 4:
		RenderingServer.runtime_virtual_texture_set_height_region(terrain_vt, Vector2i(i % 2 - 1, i / 2 - 1),sources[i])
	RenderingServer.runtime_virtual_texture_set_height_lod(terrain_vt,512,1,2,1000)
	RenderingServer.runtime_virtual_texture_set_max_pages_per_frame(terrain_vt,32)
	RenderingServer.runtime_virtual_texture_set_transform(terrain_vt, Transform3D(Basis.from_scale(Vector3(64,256,64)),Vector3.ZERO))
	RenderingServer.runtime_virtual_texture_set_scenario(terrain_vt,root.world_3d.scenario)
	if not file.is_empty():
		RenderingServer.runtime_virtual_texture_set_height_stream(terrain_vt,file,2)

func run() -> void:
	var camera := Camera3D.new()
	root.add_child(camera)
	camera.position = Vector3(0,20,0)
	camera.make_current()
	var original := Image.create_empty(64,64,false,Image.FORMAT_RF)
	for i in 4:
		sources.append(Image.create_empty(32,32,false,Image.FORMAT_RF))
	for z in 64:
		for x in 64:
			var h := (x-32)*0.375 + (z-32)*0.25 - 12.5
			original.set_pixel(x,z,Color(h,0,0))
			sources[(z/32)*2 + x/32].set_pixel(x%32,z%32,Color(h,0,0))
	var tmp := FileAccess.create_temp(FileAccess.WRITE,"terrain-hybrid-test","svt")
	var file := tmp.get_path_absolute()
	tmp.close()
	check(RuntimeVirtualTexture.bake_height_grid_file(file,original,2,16,2) == OK,"Could not bake the fixture")
	native_array = RenderingServer.texture_2d_layered_create(sources,RenderingServer.TEXTURE_LAYERED_2D_ARRAY)
	create_source(true,"")
	var gpu_stats := await wait_pages()
	check(is_equal_approx(read_height(0,Vector2i(1,1),Vector2i(15,15)),original.get_pixel(31,31).r),"GPU vertex grid produced a wrong signed sample")
	check(gpu_stats.produced_height_pages >= 21 and not gpu_stats.sparse_height_source,"Expected GPU production")
	RenderingServer.free_rid(terrain_vt)
	RenderingServer.free_rid(native_array)
	native_array = RID()
	create_source(false,file)
	var before := await wait_pages()
	check(before.disk_pages == 5 and before.produced_height_pages == 16 and before.sparse_height_source,"Expected 5 SVT and 16 live pages: %s" % before)
	var far := RenderingServer.runtime_virtual_texture_get_page_info(terrain_vt,0,0,0)
	var untouched := RenderingServer.runtime_virtual_texture_get_page_info(terrain_vt,1,0,0)
	# A vertex inside coarse tile (1,1), and within both fine/coarse boundary aprons.
	sources[3].set_pixel(0,0,Color(143.25,0,0))
	RenderingServer.runtime_virtual_texture_set_height_region(terrain_vt,Vector2i.ZERO,sources[3])
	RenderingServer.runtime_virtual_texture_invalidate(terrain_vt,AABB(Vector3(-0.1,-200,-0.1),Vector3(0.2,400,0.2)))
	var target_serial: int = RenderingServer.runtime_virtual_texture_get_page_info(terrain_vt,0,2,2).content_serial
	for i in 240:
		await RenderingServer.frame_post_draw
		if RenderingServer.runtime_virtual_texture_get_page_info(terrain_vt,0,2,2).content_serial != target_serial:
			break
	await frames(8)
	check(is_equal_approx(read_height(0,Vector2i(2,2),Vector2i.ZERO),143.25),"Sparse edited fine vertex")
	check(is_equal_approx(read_height(0,Vector2i(1,1),Vector2i(16,16)),143.25),"Fine neighbor apron is stale")
	check(is_equal_approx(read_height(1,Vector2i(1,1),Vector2i.ZERO),143.25),"Streamed coarse page did not switch to live data")
	check(is_equal_approx(read_height(2,Vector2i.ZERO,Vector2i(8,8)),143.25),"Edited root value")
	check(far.content_serial == RenderingServer.runtime_virtual_texture_get_page_info(terrain_vt,0,0,0).content_serial,"A distant fine page was unnecessarily regenerated")
	check(untouched.content_serial != RenderingServer.runtime_virtual_texture_get_page_info(terrain_vt,1,0,0).content_serial,"A coarse neighbor apron was not refreshed")
	print("Hybrid height before edit ",before," after ", RenderingServer.runtime_virtual_texture_get_stats(terrain_vt))
	RenderingServer.free_rid(terrain_vt)
	print("Height source regression: ", failures, " failures")
	quit(int(failures > 0))
