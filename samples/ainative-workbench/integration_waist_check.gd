extends SceneTree
const S = preload('res://addons/ainative/character_session.gd')
func _initialize(): run.call_deferred()
func run():
	var args = OS.get_cmdline_user_args()
	var source = S.I.load_scene(args[0])
	assert(not source.has('error'))
	var live = source.scene
	var recipe = S.read_object(S.recipe_path(FileAccess.get_sha256(args[0])))
	var loaded = S.I.load_scene(recipe.base)
	assert(not loaded.has('error'))
	var base = loaded.scene
	if not base.has_meta('face_binding'): base.set_meta('face_binding',S.read_object(recipe.binding))
	var binding = base.get_meta('face_binding')
	var profile = S.I.extract(base,'anatomical',{'sha256':recipe.source_sha256,'version':'waist-check','authority':binding.source_url},binding.body_mapping)
	assert(not profile.has('error'))
	var fit = S.C.refit(base,profile.profile,live.get_meta('character_dna'),recipe.garment.path,recipe.garment.spec)
	assert(not fit.has('error'))
	var expected = fit.scene.get_node('Garment')
	var actual = live.get_node('Garment')
	var manifest = fit.scene.get_meta('garment')
	var cloth_vertices = {}
	for vertex in manifest.partitions.cloth: cloth_vertices[int(vertex)] = true
	var offset = 0
	var retained_triangles = 0
	var actual_surface = 0
	for surface in expected.mesh.get_surface_count():
		var original = expected.mesh.surface_get_arrays(surface)
		var indices = original[Mesh.ARRAY_INDEX]
		var retained = PackedInt32Array()
		for triangle in range(0,indices.size(),3):
			if not cloth_vertices.has(offset+indices[triangle]) or not cloth_vertices.has(offset+indices[triangle+1]) or not cloth_vertices.has(offset+indices[triangle+2]):
				retained.append_array(PackedInt32Array([indices[triangle],indices[triangle+1],indices[triangle+2]]))
		offset += original[Mesh.ARRAY_VERTEX].size()
		if retained.is_empty(): continue
		assert(actual_surface<actual.mesh.get_surface_count())
		var saved = actual.mesh.surface_get_arrays(actual_surface)
		assert(saved[Mesh.ARRAY_INDEX]==retained,'Retained waist triangle IDs differ')
		for field in [Mesh.ARRAY_VERTEX,Mesh.ARRAY_BONES,Mesh.ARRAY_WEIGHTS]:
			assert(saved[field]==original[field],'Retained waist geometry or skin weights differ')
		retained_triangles += retained.size()/3
		actual_surface += 1
	assert(actual_surface==actual.mesh.get_surface_count())
	assert(actual.skin.get_bind_count()==expected.skin.get_bind_count())
	for index in actual.skin.get_bind_count():
		assert(actual.skin.get_bind_bone(index)==expected.skin.get_bind_bone(index))
		assert(actual.skin.get_bind_name(index)==expected.skin.get_bind_name(index))
		assert(actual.skin.get_bind_pose(index).is_equal_approx(expected.skin.get_bind_pose(index)))
	assert(live.get_node('ClothSolver').binding.cloth_top==recipe.garment.spec.cloth_start_y)
	var report = {'publication_sha256':FileAccess.get_sha256(args[0]),'source_garment_sha256':recipe.garment.spec.source_sha256,'cloth_start_y_m':recipe.garment.spec.cloth_start_y,'retained_triangles':retained_triangles,'exact_triangle_ids':true,'exact_vertex_positions':true,'exact_bone_indices_and_weights':true,'skin_bind_poses_equal':true,'comparison':'Fresh fit from immutable source and saved DNA; original non-cloth triangles retained'}
	var output = FileAccess.open(args[1],FileAccess.WRITE)
	output.store_string(JSON.stringify(report,'\t'))
	print(JSON.stringify(report))
	fit.scene.free()
	base.free()
	live.free()
	quit()
