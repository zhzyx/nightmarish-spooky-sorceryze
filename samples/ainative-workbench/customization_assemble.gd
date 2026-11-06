extends SceneTree
const I = preload('res://addons/ainative/interop.gd')
const G = preload('res://addons/ainative/garments.gd')
var assembly_spec = {}
func _initialize(): run.call_deferred()
func run():
	var config = JSON.parse_string(FileAccess.get_file_as_string(OS.get_cmdline_user_args()[0]))
	assembly_spec = config
	assert(not FileAccess.file_exists(config.output))
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
	var cutoff = config.get('neck_cut_y',neck.y-.015)
	var removed = 0
	for mi in scene.find_children('*','MeshInstance3D',true,false):
		var mesh = ArrayMesh.new()
		for key in G.SHAPE_KEYS: mesh.add_blend_shape(key)
		mesh.blend_shape_mode = Mesh.BLEND_SHAPE_MODE_NORMALIZED
		for surface in mi.mesh.get_surface_count():
			var a = mi.mesh.surface_get_arrays(surface).duplicate(true)
			var vertices = a[Mesh.ARRAY_VERTEX]
			var old_indices = a[Mesh.ARRAY_INDEX]
			var kept = PackedInt32Array()
			for i in range(0,old_indices.size(),3):
				var center = (vertices[old_indices[i]]+vertices[old_indices[i+1]]+vertices[old_indices[i+2]])/3.0
				if center.y>cutoff and absf(center.x)<config.get('head_hide_half_width',.13): removed += 1
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
	assert(ResourceSaver.save(packed,config.output)==OK)
	binding['body_mapping'] = {}
	for semantic in profile.mapping: binding.body_mapping[semantic] = profile.bones[profile.mapping[semantic]].name
	binding['body_source'] = profile.source
	binding['body_profile'] = profile
	binding['face_asset_sha256'] = binding.asset_sha256
	binding['asset_sha256'] = FileAccess.get_sha256(config.output)
	binding['mapping_version'] = config.get('mapping_version','ue4-rain-head-v1')
	binding['assembly'] = {'head_parts':head_parts,'neck_cut_y':cutoff,'face_scale':scale_factor,'offset':[offset.x,offset.y,offset.z],'original_head_triangles_hidden':removed,'body_skin':'original native UE4 unchanged','head_skin':'explicit head/neck weights only','face_source_rest':I.encode(face_sk.get_bone_global_rest(0)) if is_instance_valid(face_sk) else 'recorded in original FaceBinding'}
	var file = FileAccess.open(config.output+'.face-binding.json',FileAccess.WRITE)
	file.store_string(JSON.stringify(binding,'\t'))
	file.close()
	print(JSON.stringify(binding.assembly))
	quit()

func neck_transition(point: Vector3, neck: Vector3) -> Vector3:
	var weight = 1.0-smoothstep(neck.y+.015,neck.y+.075,point.y)
	return Vector3(point.x*lerpf(1.0,assembly_spec.get('neck_width_scale',2.0),weight),point.y-assembly_spec.get('neck_extend_m',.05)*weight,neck.z+(point.z-neck.z)*lerpf(1.0,assembly_spec.get('neck_depth_scale',1.5),weight))
