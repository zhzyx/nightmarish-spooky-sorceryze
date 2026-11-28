extends SceneTree
## Run the Forward+ build with --path <demo project> --fixed-fps 60 --script <this file>.
## Dispatches the sampler extracted from the compiled terrain material on its actual GPU textures.

var terrain := Terrain3D.new()
var camera := Camera3D.new()
var cv: Object
var pages: RID
var table: RID
var pool: RID
var table_bytes := PackedByteArray()
var page_file := ""
var samples := PackedFloat32Array() # grid x,z, geometry LOD, CPU reference height
var result := PackedFloat32Array()
var compute_source: String
var complete := Semaphore.new()
var failures := 0
var spike_height := 101.23456
const SEAM_SAMPLES := 4 * 2 * 17 * 4
var grid_resolution := 128

func _initialize() -> void:
	run.call_deferred()

func check(ok: bool, message: String) -> void:
	if not ok:
		push_error(message)
		failures += 1

func frames(n: int) -> void:
	for i in n:
		await RenderingServer.frame_post_draw

func height(x: int, z: int) -> float:
	var h := -40.07 + 0.0137*x + 0.09876*z
	if Vector2i(x,z) == Vector2i(-1,-1):
		h += spike_height
	if Vector2i(x,z) == Vector2i(0,0):
		h += 0.5 * spike_height
	return h

func source_linear(p: Vector2) -> float:
	var cell := p.clamp(Vector2(-64,-64),Vector2(63,63))
	var a := Vector2i(cell.floor())
	var b := (a + Vector2i.ONE).min(Vector2i(63,63))
	var f := cell - Vector2(a)
	return lerpf(lerpf(height(a.x,a.y),height(b.x,a.y),f.x),
			lerpf(height(a.x,b.y),height(b.x,b.y),f.x),f.y)

func reference(pos: Vector2, level: int) -> float:
	var dimension := grid_resolution >> level
	var uv := (pos + Vector2(64,64)) / 128.0
	var grid := (uv * dimension).min(Vector2.ONE * (dimension-1))
	var a := Vector2i(grid.floor())
	var b := (a + Vector2i.ONE).min(Vector2i(dimension-1,dimension-1))
	var step := 128.0 / dimension
	var f := grid - Vector2(a)
	var p := Vector2(a) * step - Vector2(64,64)
	var q := Vector2(b) * step - Vector2(64,64)
	return lerpf(lerpf(source_linear(p),source_linear(Vector2(q.x,p.y)),f.x),
			lerpf(source_linear(Vector2(p.x,q.y)),source_linear(q),f.x),f.y)

func query(pos: Vector2, lod: float) -> void:
	var mip := clampf(lod + log(grid_resolution/128.0)/log(2.0), 0, int(cv.get_value("r.Terrain3D.VT.Log2Tiles")))
	var expected := lerpf(reference(pos,floori(mip)),reference(pos,ceili(mip)),fmod(mip,1.0))
	samples.append_array(PackedFloat32Array([pos.x,pos.y,lod,expected]))

func make_samples() -> void:
	samples.clear()
	for z in range(-64,64):
		for x in range(-64,64):
			query(Vector2(x,z),0.0)
	for z in [-64.,-48.,-16.,-1.,0.,16.,32.,63.]:
		for x in [-64.,-48.25,-32.,-16.,-1.,0.,0.25,15.75,16.,31.5,63.]:
			for lod in [0.0,0.375,1.0,1.625,2.0,3.0]:
				query(Vector2(x,z),lod)

# Independent CPU reconstruction from the real resident GPU table, including
# partial parent fades. A missing fine page legitimately loses unsampled detail.
func resident_reference(pos: Vector2, level: int) -> float:
	var uv := (pos + Vector2(64,64)) / 128.0
	var last := int(cv.get_value("r.Terrain3D.VT.Log2Tiles"))
	var total := 0.0
	var weight := 1.0
	while level <= last:
		var side := 1 << (last - level)
		var offset := ((1 << (2*last)) - side*side) * 4 / 3
		var texel := Vector2i((uv * float(side)).floor())
		var i := (offset + texel.y * side + texel.x) * 4
		var resident := int(table_bytes[i+2])
		var alpha := int(table_bytes[i+3])
		if alpha != 0 and resident >= level and resident <= last:
			var blend := 1.0 if resident == last else float(alpha)/255.0
			total += weight * blend * reference(pos,resident)
			if blend == 1.0: return total
			weight *= 1.0 - blend
			level = resident
		level += 1
	return total

func uniform_for(kind: int, binding: int, ids: Array[RID]) -> RDUniform:
	var u := RDUniform.new()
	u.uniform_type = kind
	u.binding = binding
	for id in ids:
		u.add_id(id)
	return u

func dispatch_probe() -> void:
	var rd := RenderingServer.get_rendering_device()
	var shader_source := RDShaderSource.new()
	shader_source.source_compute = compute_source
	var spirv := rd.shader_compile_spirv_from_source(shader_source)
	if not spirv.compile_error_compute.is_empty():
		push_error(spirv.compile_error_compute)
		complete.post()
		return
	var shader := rd.shader_create_from_spirv(spirv)
	var pipeline := rd.compute_pipeline_create(shader)
	var sampler := rd.sampler_create(RDSamplerState.new())
	var count := samples.size()/4
	var input := rd.storage_buffer_create(samples.size()*4,samples.to_byte_array())
	var output := rd.storage_buffer_create((count+SEAM_SAMPLES)*8)
	table_bytes = rd.texture_get_data(RenderingServer.texture_get_rd_texture(table), 0)
	var uniforms: Array[RDUniform] = []
	for tex: RID in [table,pool]:
		uniforms.append(uniform_for(RenderingDevice.UNIFORM_TYPE_SAMPLER_WITH_TEXTURE,uniforms.size(),[sampler,RenderingServer.texture_get_rd_texture(tex)]))
	for buffer: RID in [input,output]:
		uniforms.append(uniform_for(RenderingDevice.UNIFORM_TYPE_STORAGE_BUFFER,uniforms.size(),[buffer]))
	var bindings := rd.uniform_set_create(uniforms,shader,0)
	var list := rd.compute_list_begin()
	rd.compute_list_bind_compute_pipeline(list,pipeline)
	rd.compute_list_bind_uniform_set(list,bindings,0)
	rd.compute_list_dispatch(list,ceili(float(count+SEAM_SAMPLES)/64),1,1)
	rd.compute_list_end()
	result = rd.buffer_get_data(output).to_float32_array()
	for id: RID in [bindings,pipeline,shader,sampler,output,input]:
		rd.free_rid(id)
	complete.post()

func probe(label: String, require_fine: bool, require_degraded: bool = false) -> void:
	pages = terrain.get_height_vt_rid()
	check(pages.is_valid(),label+" missing VT RID")
	if not pages.is_valid():
		return
	table = RenderingServer.runtime_virtual_texture_get_page_table_texture(pages)
	pool = RenderingServer.runtime_virtual_texture_get_physical_texture(pages,0)
	var gdshader := RenderingServer.shader_get_code(terrain.material.get_shader_rid())
	var start := gdshader.find("float t3d_physical_height(")
	var end := gdshader.find("float t3d_view_distance(",start)
	var pos := gdshader.find("{",end) + 1
	var depth := 1
	while pos < gdshader.length() and depth > 0:
		if gdshader[pos] == "{": depth += 1
		if gdshader[pos] == "}": depth -= 1
		pos += 1
	check(start >= 0 and end > start,"Missing production VT sampler")
	if start < 0 or end < 0: return
	var material_grid: Vector4 = terrain.material.get_shader_param("_t3d_vt_grid")
	var layout_v: Vector4 = terrain.material.get_shader_param("_t3d_vt_layout")
	check(material_grid == Vector4(-64,-64,128,1),"Unexpected active height domain %s" % material_grid)
	compute_source = """#version 450
layout(local_size_x=64) in;
layout(set=0,binding=0) uniform sampler2D _t3d_vt_page_table;
layout(set=0,binding=1) uniform sampler2D _t3d_vt_physical0;
layout(set=0,binding=2,std430) readonly buffer Queries {vec4 data[];} queries;
layout(set=0,binding=3,std430) writeonly buffer Results {vec2 data[];} results;
const vec4 _t3d_vt_grid=vec4%s;
const vec4 _t3d_vt_layout=vec4%s;
float t3d_native_height(vec2 p) { return -99999.0; }
""" % [str(material_grid),str(layout_v)]
	compute_source += gdshader.substr(start,pos-start)
	# Run the actual mesh morph and VT displacement for both triangles sharing a tile edge.
	var vertex := gdshader.find("vec2 local = VERTEX.xz;")
	var control := gdshader.find("ivec3 v_region",vertex)
	var h_start := gdshader.find("float h;",control)
	var h_end := gdshader.find("}",gdshader.find("h = mix(t3d_native_height",h_start))+1
	check(vertex>=0 and control>vertex and h_start>control and h_end>h_start,"Missing mesh vertex path")
	compute_source += """
vec3 vertex_at(vec2 origin, vec2 local_pos, float scale_in, vec4 INSTANCE_CUSTOM, vec2 camera) {
	mat4 MODEL_MATRIX=mat4(1.0);
	MODEL_MATRIX[0][0]=scale_in; MODEL_MATRIX[3].xz=origin;
	vec3 VERTEX=vec3(local_pos.x,0,local_pos.y), v_vertex=vec3(0), v_camera_pos=vec3(camera.x,0,camera.y);
	vec3 _target_pos=v_camera_pos;
	const float _t3d_tile_res=16.0, _vertex_density=1.0, _vertex_spacing=1.0, _region_texel_size=1.0/64.0;
	const float _t3d_lod0_distance=64.0;
	const vec4 _t3d_draw_bounds=vec4(-64,-64,64,64);
	const int _t3d_last_lod=3;
	vec2 UV, UV2; float v_vertex_xz_dist;
""" + gdshader.substr(vertex,control-vertex) + gdshader.substr(h_start,h_end-h_start) + """
	return vec3(v_vertex.xz,h);
}
void main() {
	uint id=gl_GlobalInvocationID.x;
	if (id<%du) { results.data[id]=t3d_vt_sample(queries.data[id].xy,queries.data[id].z); return; }
	uint k=id-%du;
	if(k>=%du) return;
	int edge=int(k%%4u), half_tile=int((k/4u)%%2u), i=int((k/8u)%%17u), band=int(k/136u);
	vec2 fine_origin, fine_local, coarse_local;
	vec4 ratios=vec4(1);
	float along=float(half_tile*16), n=float(i), edge_coord=float(half_tile*8+i/2);
	if(edge==0) {fine_origin=vec2(-16,along);fine_local=vec2(16,n);coarse_local=vec2(0,edge_coord);ratios.y=2;}
	if(edge==1) {fine_origin=vec2(32,along);fine_local=vec2(0,n);coarse_local=vec2(16,edge_coord);ratios.x=2;}
	if(edge==2) {fine_origin=vec2(along,-16);fine_local=vec2(n,16);coarse_local=vec2(edge_coord,0);ratios.w=2;}
	if(edge==3) {fine_origin=vec2(along,32);fine_local=vec2(n,0);coarse_local=vec2(edge_coord,16);ratios.z=2;}
	vec2 camera=coarse_local*2.0+vec2(float(band)*31.3+2.0,10);
	vec3 a=vertex_at(fine_origin,fine_local,1.0,ratios,camera);
	vec3 b=vertex_at(vec2(0),coarse_local,2.0,vec4(1),camera);
	results.data[id]=vec2(length(a.xy-b.xy),abs(a.z-b.z));
}""" % [samples.size()/4,samples.size()/4,SEAM_SAMPLES]
	result.clear()
	RenderingServer.call_on_render_thread(dispatch_probe)
	complete.wait()
	check(result.size()==samples.size()/2+SEAM_SAMPLES*2,"Missing GPU samples")
	if result.is_empty(): return
	var sources := [0,0,0]
	var worst := 0.0
	var max_fine_deviation := 0.0
	var last := int(cv.get_value("r.Terrain3D.VT.Log2Tiles"))
	for i in samples.size()/4:
		var expected := samples[4*i+3]
		max_fine_deviation = maxf(max_fine_deviation, absf(expected-result[2*i]))
		if not require_fine:
			var p := Vector2(samples[4*i],samples[4*i+1])
			var mip := clampf(samples[4*i+2] + log(grid_resolution/128.0)/log(2.0),0,last)
			expected = lerpf(resident_reference(p,floori(mip)),resident_reference(p,ceili(mip)),fmod(mip,1.0))
		worst = maxf(worst,absf(expected-result[2*i]))
		var path := roundi(result[2*i+1])
		if path >= 0 and path < 3: sources[path] += 1
	check(sources[1]+sources[2]==samples.size()/4, label+" sampled outside the VT or found a missing root")
	var seam_error := 0.0
	for i in range(samples.size()/2,result.size()):
		seam_error = maxf(seam_error,result[i])
	check(seam_error<=0.001,label+" shared edge position or height differs")
	check(worst<=0.001,label+" height error exceeds 1 mm")
	if require_fine: check(sources[1]==samples.size()/4,label+" samples did not use requested pages")
	if require_degraded:
		check(sources[2] > 0, label + " did not sample a resident ancestor")
		check(sources[0] == 0, label + " sampled native heights with a missing fine page")
	print(label," GPU samples=",samples.size()/4," requested=",sources[1]," ancestor=",sources[2]," native=",sources[0]," max_error_m=",worst," seam_error_m=",seam_error," max_fine_deviation_m=",max_fine_deviation)

func settled(full: bool = false) -> void:
	var locked := RID()
	for i in 240:
		await RenderingServer.frame_post_draw
		var rid := terrain.get_height_vt_rid()
		if rid.is_valid():
			var stats := RenderingServer.runtime_virtual_texture_get_stats(rid)
			if full and stats.gpu_ready and rid != locked:
				var last := int(cv.get_value("r.Terrain3D.VT.Log2Tiles"))
				for level in last+1:
					for y in 1 << (last-level):
						for x in 1 << (last-level):
							RenderingServer.runtime_virtual_texture_lock_page(rid,level,x,y,90)
				locked = rid
			if stats.gpu_ready and stats.resident_pages > 0 and (not full or stats.levels[0] == (1 << int(cv.get_value("r.Terrain3D.VT.Log2Tiles")))**2):
				await frames(14)
				return
	check(false,"Height pages did not settle")

func run() -> void:
	root.add_child(camera)
	camera.position = Vector3(0,100,0)
	camera.look_at(Vector3.ZERO,Vector3.FORWARD)
	terrain.free_editor_textures = false
	terrain.tessellation_level = 0
	terrain.ocean_enabled = false
	root.add_child(terrain)
	terrain.region_size = Terrain3D.SIZE_64
	terrain.material.material_rvt_enabled = false
	terrain.material.world_background = Terrain3DMaterial.NONE
	terrain.set_camera(camera)
	for rz in range(-1,1):
		for rx in range(-1,1):
			var region := terrain.data.add_region_blank(Vector2i(rx,rz),false)
			var img := Image.create_empty(64,64,false,Image.FORMAT_RF)
			for z in 64:
				for x in 64: img.set_pixel(x,z,Color(height(rx*64+x,rz*64+z),0,0))
			region.set_height_map(img)
			region.calc_height_range()
	terrain.data.update_maps()
	cv = Engine.get_singleton("CVars")
	cv.set_value("r.Terrain3D.Mode",1)
	cv.set_value("r.Terrain3D.VT.TileSize",16)
	cv.set_value("r.Terrain3D.VT.Log2Tiles",3)
	cv.set_value("r.Terrain3D.VT.PoolSize",16)
	var offline := Image.create_empty(128,128,false,Image.FORMAT_RF)
	for z in 128:
		for x in 128:
			offline.set_pixel(x,z,Color(height(x-64,z-64),0,0))
	page_file = OS.get_temp_dir().path_join("terrain-height-regression-%d.svt" % OS.get_process_id())
	var err := RuntimeVirtualTexture.bake_height_grid_file(page_file,offline,3,16,int(cv.get_value("r.Terrain3D.VT.Border")))
	check(err == OK,"Could not bake hybrid coarse mip fixture")
	terrain.height_vt_stream_file = page_file
	terrain.height_vt_stream_levels = 1
	cv.set_value("r.Terrain3D.VTHeight",1)
	make_samples()
	await settled(true)
	check(not terrain.data.get_resident_height_maps_rid().is_valid(), "Pure VT retained the native GPU height array")
	await probe("Warm ramp, negative heights, spike and seams",true)
	var original := terrain.get_height_vt_rid()
	var initial := RenderingServer.runtime_virtual_texture_get_stats(original)
	check(initial.height_grid and initial.produced_height_pages > 0 and initial.disk_pages > 0, "Hybrid root and live height pages were not both consumed")
	var far_before := RenderingServer.runtime_virtual_texture_get_page_info(original,0,0,0)
	spike_height = 1000.12345
	terrain.data.set_height(Vector3(-1,0,-1),height(-1,-1))
	terrain.data.set_height(Vector3(0,0,0),height(0,0))
	terrain.data.update_maps(0)
	make_samples()
	await frames(32)
	await probe("Incremental edit across four page borders",true)
	var after := RenderingServer.runtime_virtual_texture_get_stats(original)
	var far_after := RenderingServer.runtime_virtual_texture_get_page_info(original,0,0,0)
	check(terrain.get_height_vt_rid() == original, "Incremental edit recreated the height VT")
	check(far_before.resident and far_after.resident and far_before.pool_x == far_after.pool_x and far_before.pool_y == far_after.pool_y and far_before.content_serial == far_after.content_serial, "Incremental edit displaced an unrelated resident page")
	check(after.rendered_total > initial.rendered_total and after.rendered_total - initial.rendered_total < initial.resident_pages, "Incremental edit rebaked the full pool")
	check(after.disk_pages == initial.disk_pages, "Edited coarse mip reloaded stale disk heights")
	print("Incremental pages=",after.rendered_total-initial.rendered_total," of ",initial.resident_pages," hybrid disk reads=",after.disk_pages)
	terrain.height_vt_stream_levels = 0
	terrain.height_vt_stream_file = ""
	RenderingServer.runtime_virtual_texture_unlock_all_pages(original)
	cv.set_value("r.Terrain3D.TileRes",4)
	cv.set_value("r.Terrain3D.Lod0Distance",16)
	cv.set_value("r.Terrain3D.MaxDistance",34)
	camera.position = Vector3(-48,-28,-48)
	cv.set_value("r.Terrain3D.VT.PoolSize",4)
	await frames(24)
	await settled()
	await probe("Small pool",false,true)
	camera.position = Vector3(48,-28,48)
	await frames(40)
	await probe("Moved camera with small pool",false,true)
	var evicted := int(RenderingServer.runtime_virtual_texture_get_stats(terrain.get_height_vt_rid()).evicted_total)
	check(evicted>0,"No page was evicted after the camera moved")
	print("Evicted pages after crossing the fixture: ",evicted)
	cv.set_value("r.Terrain3D.Lod0Distance",256)
	cv.set_value("r.Terrain3D.MaxDistance",6000)
	cv.set_value("r.Terrain3D.VT.PoolSize",16)
	cv.set_value("r.Terrain3D.VT.Log2Tiles",2)
	grid_resolution=64
	await frames(24)
	await settled(true)
	make_samples()
	await probe("Half resolution VT",true)
	cv.set_value("r.Terrain3D.VT.TileSize",20)
	grid_resolution = 80
	await frames(24)
	await settled(true)
	make_samples()
	await probe("Non-dyadic page size",true)
	terrain.material.material_rvt_enabled = true
	await frames(20)
	var writer := terrain.material.get_material_rvt_rid()
	check(writer.is_valid(), "Material RVT writer missing in the combined path")
	check(not terrain.data.get_resident_height_maps_rid().is_valid(), "Combined height VT and material RVT allocated a native GPU height array")
	var dependency := RenderingServer.runtime_virtual_texture_get_stats(writer)
	check(dependency.material_height_source == terrain.get_height_vt_rid(), "Material writer is not reading the active height VT")
	spike_height += 50.0
	terrain.data.set_height(Vector3(-1,0,-1),height(-1,-1))
	terrain.data.set_height(Vector3(0,0,0),height(0,0))
	terrain.data.update_maps(0,false)
	make_samples()
	await frames(40)
	var refreshed := RenderingServer.runtime_virtual_texture_get_stats(writer)
	check(refreshed.height_dependency_invalidations > dependency.height_dependency_invalidations, "Height edits did not refresh dependent material pages")
	check(not terrain.data.get_resident_height_maps_rid().is_valid(), "Local height editing restored the full native GPU array")
	print("Combined height/material VT: native GPU array resident=",terrain.data.get_resident_height_maps_rid().is_valid(),", material dependency invalidations after local edit=",refreshed.height_dependency_invalidations-dependency.height_dependency_invalidations)
	cv.set_value("r.Terrain3D.VTHeight",0)
	await frames(8)
	check(not terrain.get_height_vt_rid().is_valid(),"Disabling VT kept the old surface source")
	check(terrain.data.get_resident_height_maps_rid().is_valid(), "Material writer and native rendering did not restore the authored GPU height array")
	check(terrain.material.get_material_rvt_rid() == writer, "Disabling height VT destroyed the independent material RVT writer")
	var detached := RenderingServer.runtime_virtual_texture_get_stats(writer)
	var detached_source: RID = detached.material_height_source
	check(not detached_source.is_valid(), "Material writer retained a freed height VT dependency")
	cv.set_value("r.Terrain3D.VTHeight",1)
	await settled(true)
	await probe("Re-enabled height VT",true)
	check(not terrain.data.get_resident_height_maps_rid().is_valid(), "Returning to VT kept a redundant native GPU array")
	check(RenderingServer.runtime_virtual_texture_get_stats(writer).material_height_source == terrain.get_height_vt_rid(), "Material writer did not bind the replacement height VT")
	terrain.material.material_rvt_enabled = false
	await frames(8)
	check(not terrain.material.get_material_rvt_rid().is_valid() and not terrain.data.get_resident_height_maps_rid().is_valid(), "Height-only rendering retained the material writer or native array")
	terrain.material.material_rvt_enabled = true
	await frames(8)
	var transient := terrain.data.set_height_maps_consumer(camera,true)
	check(transient.is_valid(), "An active native-height consumer was not restored")
	terrain.data.set_height_maps_consumer(camera,false)
	await frames(6)
	check(not terrain.data.get_resident_height_maps_rid().is_valid(), "A released consumer retained its native GPU array")
	var external := terrain.data.get_height_maps_rid()
	await frames(12)
	check(external.is_valid() and external == terrain.data.get_resident_height_maps_rid(), "External native-height RID demand was lost")
	if FileAccess.file_exists(page_file): DirAccess.remove_absolute(page_file)
	terrain.queue_free()
	await frames(4)
	camera.queue_free()
	await frames(4)
	print("Height VT regression: ",failures," failures")
	quit(0 if failures==0 else 1)
