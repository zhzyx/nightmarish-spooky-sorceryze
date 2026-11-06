extends SceneTree
const I = preload('res://addons/ainative/interop.gd')
const G = preload('res://addons/ainative/garments.gd')
var assembly_spec = {}
func _initialize(): run.call_deferred()
func run():
	var config = JSON.parse_string(FileAccess.get_file_as_string(OS.get_cmdline_user_args()[0]))
	assembly_spec = config
	if FileAccess.file_exists(config.output) or FileAccess.file_exists(config.output+'.face-binding.json'):
		push_error('Output exists'); quit(1); return
	var loaded = I.load_scene(config.body)
	assert(not loaded.has('error'))
	var scene = loaded.scene
	root.add_child(scene)
	var extracted = I.extract(scene,config.get('family','ue4'),{'sha256':FileAccess.get_sha256(config.body),'version':config.get('body_version','ue4-native-147'),'authority':config.get('body_authority','https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/147')},config.get('body_mapping',{}))
	assert(not extracted.has('error'),str(extracted))
	var profile = extracted.profile
	var sk = I.skeleton(scene)
	var head = sk.get_bone_global_rest(profile.mapping.head).origin
	var neck = sk.get_bone_global_rest(profile.mapping.neck).origin
	var hip = sk.get_bone_global_rest(profile.mapping.hips).origin.y
	var chest = sk.get_bone_global_rest(profile.mapping.chest).origin.y
	if config.get('head_mask_sha256','').length()!=64 or FileAccess.get_sha256(config.get('head_mask','')) != config.get('head_mask_sha256'):
		push_error('Approved head mask SHA mismatch'); quit(1); return
	var mask = JSON.parse_string(FileAccess.get_file_as_string(config.get('head_mask','')))
	var mask_error = validate_mask(scene, mask, FileAccess.get_sha256(config.body))
	if not mask_error.is_empty():
		push_error(mask_error); quit(1); return
	var removed = 0
	for mi in scene.find_children('*','MeshInstance3D',true,false):
		var mesh = ArrayMesh.new()
		for key in G.SHAPE_KEYS: mesh.add_blend_shape(key)
		mesh.blend_shape_mode = Mesh.BLEND_SHAPE_MODE_NORMALIZED
		for surface in mi.mesh.get_surface_count():
			var a = mi.mesh.surface_get_arrays(surface).duplicate(true)
			var vertices = a[Mesh.ARRAY_VERTEX]
			var old_indices = a[Mesh.ARRAY_INDEX]
			var hidden = {}
			for entry in mask.surfaces:
				if entry.mesh_path == str(scene.get_path_to(mi)) and int(entry.surface) == surface:
					for id in entry.triangles: hidden[int(id)] = true
			var kept = PackedInt32Array()
			for i in range(0,old_indices.size(),3):
				if hidden.has(i/3): removed += 1
				else: kept.append_array(PackedInt32Array([old_indices[i],old_indices[i+1],old_indices[i+2]]))
			a[Mesh.ARRAY_INDEX] = kept
			var shapes = []
			for key in G.SHAPE_KEYS:
				var shape = []
				shape.resize(Mesh.ARRAY_MAX)
				var points = vertices.duplicate()
				for i in points.size(): points[i] = G.shaped(points[i],{key:2.0},hip,chest)
				shape[Mesh.ARRAY_VERTEX] = points
				shape[Mesh.ARRAY_NORMAL] = a[Mesh.ARRAY_NORMAL]
				shape[Mesh.ARRAY_TANGENT] = a[Mesh.ARRAY_TANGENT]
				shapes.append(shape)
			mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES,a,shapes)
			mesh.surface_set_material(surface,mi.mesh.surface_get_material(surface))
		mi.mesh = mesh
	var face_source = I.load_scene(config.face)
	assert(not face_source.has('error'))
	var face = face_source.scene
	var binding = JSON.parse_string(FileAccess.get_file_as_string(config.binding))
	var face_sk = I.skeleton(face)
	var face_head = face_sk.get_bone_global_rest(face_sk.find_bone(binding.body_mapping.head)).origin
	var scale_factor = config.get('face_scale',.72)
	var offset = head-face_head*scale_factor+Vector3(0,config.get('face_offset_y',0.0),config.get('face_offset_z',0.0))
	var skin = Skin.new()
	for i in sk.get_bone_count(): skin.add_bind(i,sk.get_bone_global_rest(i).affine_inverse())
	var head_parts = []
	for original in face.find_children('*','MeshInstance3D',true,false):
		var name_text = str(original.name)
		if not name_text in config.get('face_parts',['GEO-rain-head','GEO-rain-eyes','GEO-rain-eyebrows','GEO-rain-eyelashes','GEO-rain-gums_lower','GEO-rain-gums_upper','GEO-rain-tongue','GEO-rain-hair_main']): continue
		var mesh = ArrayMesh.new()
		mesh.blend_shape_mode = Mesh.BLEND_SHAPE_MODE_NORMALIZED
		for i in original.mesh.get_blend_shape_count(): mesh.add_blend_shape(original.mesh.get_blend_shape_name(i))
		for surface in original.mesh.get_surface_count():
			var a = original.mesh.surface_get_arrays(surface).duplicate(true)
			var points = a[Mesh.ARRAY_VERTEX]
			var bones = PackedInt32Array()
			var weights = PackedFloat32Array()
			for i in points.size():
				points[i] = points[i]*scale_factor+offset
				points[i] = neck_transition(points[i],neck)
				var head_weight = smoothstep(neck.y,head.y,points[i].y)
				bones.append_array(PackedInt32Array([profile.mapping.head,profile.mapping.neck,0,0]))
				weights.append_array(PackedFloat32Array([head_weight,1-head_weight,0,0]))
			a[Mesh.ARRAY_VERTEX] = points
			a[Mesh.ARRAY_BONES] = bones
			a[Mesh.ARRAY_WEIGHTS] = weights
			var shapes = original.mesh.surface_get_blend_shape_arrays(surface).duplicate(true)
			for i in shapes.size():
				var shaped = shapes[i][Mesh.ARRAY_VERTEX]
				for j in shaped.size(): shaped[j] = neck_transition(shaped[j]*scale_factor+offset,neck)
				if str(original.mesh.get_blend_shape_name(i)) in G.SHAPE_KEYS: shaped = points.duplicate()
				shapes[i][Mesh.ARRAY_VERTEX] = shaped
			mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES,a,shapes)
			mesh.surface_set_material(surface,original.mesh.surface_get_material(surface))
		var mi = MeshInstance3D.new()
		mi.name = original.name
		mi.mesh = mesh
		mi.skin = skin
		scene.add_child(mi)
		mi.skeleton = mi.get_path_to(sk)
		head_parts.append(str(mi.name))
	assert(head_parts.size()>5)
	face.free()
	preload('res://addons/ainative/rigging.gd').owners(scene,scene)
	var packed = PackedScene.new()
	assert(packed.pack(scene)==OK)
	var staged = config.output.get_base_dir().path_join('.assembly-'+str(OS.get_process_id())+'-'+str(Time.get_ticks_usec())+'.tscn')
	if ResourceSaver.save(packed,staged)!=OK:
		push_error('Stage save failed'); quit(1); return
	binding['body_mapping'] = {}
	for semantic in profile.mapping: binding.body_mapping[semantic] = profile.bones[profile.mapping[semantic]].name
	binding['body_source'] = profile.source
	binding['body_profile'] = profile
	binding['face_asset_sha256'] = binding.asset_sha256
	binding['asset_sha256'] = FileAccess.get_sha256(staged)
	binding['mapping_version'] = config.get('mapping_version','ue4-rain-head-v1')
	binding['assembly'] = {'head_parts':head_parts,'head_mask_sha256':FileAccess.get_sha256(config.head_mask),'head_mask':mask,'face_scale':scale_factor,'offset':[offset.x,offset.y,offset.z],'original_head_triangles_hidden':removed,'body_skin':'input body Skin and weights preserved; provenance bound by body_source','head_skin':'explicit head/neck weights only','face_source_rest':I.encode(face_sk.get_bone_global_rest(0)) if is_instance_valid(face_sk) else 'recorded in original FaceBinding'}
	var file = FileAccess.open(staged+'.face-binding.json',FileAccess.WRITE)
	file.store_string(JSON.stringify(binding,'\t'))
	file.close()
	var output = []
	var code = OS.execute(config.get('python','python'),[ProjectSettings.globalize_path('res://../../tools/ainative/customization_publish.py'),staged,config.output],output,true)
	DirAccess.remove_absolute(staged)
	DirAccess.remove_absolute(staged+'.face-binding.json')
	if code != 0:
		push_error('Assembly publication rejected: '+str(output)); quit(1); return
	print(JSON.stringify({'output':config.output,'hidden_triangles':removed,'mask_sha256':binding.assembly.head_mask_sha256}))
	quit()

func neck_transition(point: Vector3, neck: Vector3) -> Vector3:
	var weight = 1.0-smoothstep(neck.y+.015,neck.y+.075,point.y)
	return Vector3(point.x*lerpf(1.0,assembly_spec.get('neck_width_scale',2.0),weight),point.y-assembly_spec.get('neck_extend_m',.05)*weight,neck.z+(point.z-neck.z)*lerpf(1.0,assembly_spec.get('neck_depth_scale',1.5),weight))

static func validate_mask(scene: Node, mask: Variant, source_sha: String) -> String:
	if not mask is Dictionary or mask.get('schema_version') != 1 or mask.get('source_sha256') != source_sha:
		return 'Head mask source SHA/schema mismatch'
	if not mask.get('surfaces') is Array or mask.surfaces.is_empty(): return 'Head mask surfaces required'
	var seen = {}
	for entry in mask.surfaces:
		if not entry is Dictionary or not entry.get('mesh_path') is String or not entry.get('triangles') is Array: return 'Malformed head mask'
		var mesh = scene.get_node_or_null(entry.mesh_path)
		var surface = entry.get('surface',-1)
		if not mesh is MeshInstance3D or not (surface is float or surface is int) or surface != int(surface) or surface < 0 or surface >= mesh.mesh.get_surface_count(): return 'Head mask surface mismatch'
		var key = entry.mesh_path + ':' + str(int(surface))
		if seen.has(key): return 'Duplicate head mask surface'
		seen[key] = true
		var arrays = mesh.mesh.surface_get_arrays(int(surface))
		var count = arrays[Mesh.ARRAY_INDEX].size()/3
		if entry.get('vertex_count') != arrays[Mesh.ARRAY_VERTEX].size() or entry.get('triangle_count') != count: return 'Head mask topology mismatch'
		var ids = {}
		for id in entry.triangles:
			if not (id is float or id is int) or id != int(id) or id < 0 or id >= count or ids.has(int(id)): return 'Invalid/duplicate head triangle ID'
			ids[int(id)] = true
	return ''
