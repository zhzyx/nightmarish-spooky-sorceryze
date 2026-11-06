@tool
extends RefCounted
# A deliberately limited compatibility projection of a complete Godot character.
# The editable character package remains the authoritative, full-module artifact.
const Interop = preload('res://addons/ainative/interop.gd')

static func visible_part(part: Node3D, root: Node3D) -> bool:
	var current: Node = part
	while current != null:
		if current is Node3D and not current.visible: return false
		if current == root: return true
		current = current.get_parent()
	return false

static func frozen_mesh(part: MeshInstance3D) -> Dictionary:
	if not part.mesh is ArrayMesh: return {'error':'Compatibility export requires an ArrayMesh: '+str(part.name)}
	var output = ArrayMesh.new()
	for surface in part.mesh.get_surface_count():
		if part.mesh.surface_get_primitive_type(surface) != Mesh.PRIMITIVE_TRIANGLES:
			return {'error':'Only triangle surfaces can be projected'}
		var arrays = part.mesh.surface_get_arrays(surface).duplicate(true)
		var base: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX].duplicate()
		var vertices = base.duplicate()
		var shapes = part.mesh.surface_get_blend_shape_arrays(surface)
		if shapes.size() != part.get_blend_shape_count(): return {'error':'Morph surface count differs'}
		var normal_base = arrays[Mesh.ARRAY_NORMAL]
		var normals = normal_base.duplicate() if normal_base != null else null
		for shape in shapes.size():
			var weight = part.get_blend_shape_value(shape)
			if not is_finite(weight): return {'error':'Nonfinite morph weight'}
			if weight == 0: continue
			var points = shapes[shape][Mesh.ARRAY_VERTEX]
			if points == null or points.size() != base.size(): return {'error':'Morph topology differs'}
			var normal_shape = shapes[shape][Mesh.ARRAY_NORMAL]
			var normalized = part.mesh.blend_shape_mode == Mesh.BLEND_SHAPE_MODE_NORMALIZED
			for vertex in base.size():
				vertices[vertex] += (points[vertex]-base[vertex] if normalized else points[vertex])*weight
				if normals != null and normal_shape != null and normal_shape.size() == normals.size():
					normals[vertex] += (normal_shape[vertex]-normal_base[vertex] if normalized else normal_shape[vertex])*weight
		for point in vertices:
			if not point.is_finite(): return {'error':'Nonfinite projected vertex'}
		if normals != null:
			for vertex in normals.size():
				if not normals[vertex].is_finite(): return {'error':'Nonfinite projected normal'}
				normals[vertex] = normals[vertex].normalized()
		arrays[Mesh.ARRAY_VERTEX] = vertices
		arrays[Mesh.ARRAY_NORMAL] = normals
		arrays[Mesh.ARRAY_TANGENT] = null
		output.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES,arrays,[],{},part.mesh.surface_get_format(surface)&Mesh.ARRAY_FLAG_USE_8_BONE_WEIGHTS)
		output.surface_set_material(surface,part.get_active_material(surface))
	return {'mesh':output}

# The public boundary reloads the frozen publication rather than trusting a
# mutable live scene paired with the hash of an unrelated saved version.
static func project(publication_path: String, expected_sha256: String, source: Dictionary, target: Dictionary, final_animation: Animation) -> Dictionary:
	if expected_sha256.length() != 64 or not expected_sha256.is_valid_hex_number(false): return {'error':'A frozen character publication SHA256 is required'}
	if publication_path.get_extension().to_lower() != 'tscn' or not FileAccess.file_exists(publication_path) or FileAccess.get_sha256(publication_path) != expected_sha256:
		return {'error':'Published character missing or changed; save a new version before export'}
	if final_animation == null or final_animation.get_meta('character_publication_sha256','') != expected_sha256:
		return {'error':'Final body bake must be produced from this exact published character'}
	var loaded = Interop.load_scene(publication_path)
	if loaded.has('error'): return loaded
	var result = _project_loaded(loaded.scene,source,target,final_animation,expected_sha256)
	loaded.scene.free()
	if FileAccess.get_sha256(publication_path) != expected_sha256:
		if result.has('scene'): result.scene.free()
		return {'error':'Published character changed during export'}
	return result

# final_animation is sampled from the final body pose, including layers/IK and
# fingers. The caller's bake receipt still needs actual sample/readback evidence;
# a matching hash annotation alone is not proof of final-pose equivalence.
static func _project_loaded(character: Node3D, source: Dictionary, target: Dictionary, final_animation: Animation, published_sha256: String) -> Dictionary:
	if target.get('family') not in ['ue4','ue5_manny','mixamo']:
		return {'error':'First-version compatibility targets are UE4, Manny and Mixamo; Quinn is unvalidated'}
	if published_sha256.length() != 64 or not published_sha256.is_valid_hex_number(false):
		return {'error':'A frozen character publication SHA256 is required'}
	for profile in [source,target]:
		var invalid = Interop.validate(profile)
		if invalid: return {'error':invalid}
	var body = Interop.skeleton(character)
	if body == null or body.get_bone_count() != source.bones.size(): return {'error':'Source profile must include the actual body skeleton and equipment extensions'}
	if not Interop.node_transform(body).is_equal_approx(Transform3D.IDENTITY): return {'error':'Normalize body skeleton transforms before export'}
	for bone in body.get_bone_count():
		if str(body.get_bone_name(bone)) != source.bones[bone].name or body.get_bone_parent(bone) != int(source.bones[bone].parent) or not body.get_bone_rest(bone).is_equal_approx(Interop.decode(source.bones[bone].local_rest)):
			return {'error':'Current skeleton differs from source profile'}
	if final_animation == null or not is_finite(final_animation.length) or final_animation.length <= 0:
		return {'error':'A finite final body animation is required'}
	var captured = {}
	for track in final_animation.get_track_count():
		var path = final_animation.track_get_path(track)
		var kind = final_animation.track_get_type(track)
		if path.get_subname_count() != 1 or body.find_bone(str(path.get_subname(0))) < 0 or kind not in [Animation.TYPE_POSITION_3D,Animation.TYPE_ROTATION_3D,Animation.TYPE_SCALE_3D] or not final_animation.track_is_enabled(track) or final_animation.track_get_key_count(track) < 2:
			return {'error':'Final body bake must contain sampled bone TRS tracks only'}
		var key = str(path.get_subname(0))+':'+str(kind)
		if captured.has(key): return {'error':'Duplicate final body track'}
		captured[key] = true
		var previous_time = -1.0
		for index in final_animation.track_get_key_count(track):
			var time = final_animation.track_get_key_time(track,index)
			var value = final_animation.track_get_key_value(track,index)
			if not is_finite(time) or time < 0 or time <= previous_time or time > final_animation.length+.00001:
				return {'error':'Invalid sampled body key times'}
			previous_time = time
			if kind == Animation.TYPE_ROTATION_3D:
				if not value is Quaternion or not value.is_finite() or not is_equal_approx(value.length(),1.0): return {'error':'Invalid sampled body rotation'}
			elif not value is Vector3 or not value.is_finite(): return {'error':'Invalid sampled body vector'}
	if captured.size() != body.get_bone_count()*3: return {'error':'Final bake must cover every current body bone'}
	var projection = Node3D.new()
	projection.name = 'CompatibilitySource'
	var projected_skeleton = Interop.make_skeleton(source)
	projection.add_child(projected_skeleton)
	var report = {
		'schema_version':1,'scope':'body_skin_and_final_body_animation',
		'published_character_sha256':published_sha256,'source_profile_revision':source.revision,
		'target_profile_revision':target.revision,'target_family':target.family,
		'included':[],'excluded':[],
		'static_morph_policy':'Current body/face morph values baked into rest geometry; editable morph channels and facial animation excluded',
		'excluded_runtime':['character_editing','face_animation','weapon_attachment','cloth_simulation_and_cache','hair_guides_and_dynamics'],
		'compatibility':'target_bound; external roundtrip evidence required'
	}
	# Portable character packages reconstruct these meshes at runtime. They may
	# not exist yet on this non-running frozen instance, so name the geometry
	# omission explicitly rather than reporting only lost simulation settings.
	if character.has_node('ClothSolver'):
		report.excluded.append({'part':'ClothSolver/SimulatedClothRender','reason':'Runtime-generated cloth surface geometry and cache are excluded; any retained main-Skin waist is listed separately'})
	if character.has_node('IndependentHair'):
		report.excluded.append({'part':'IndependentHair','reason':'Independent hair geometry, scalp cap and guide dynamics are excluded from this body compatibility projection'})
	for part in character.find_children('*','MeshInstance3D',true,false):
		var label = str(character.get_path_to(part))
		if not visible_part(part,character):
			report.excluded.append({'part':label,'reason':'hidden geometry'})
			continue
		if part.skin == null:
			report.excluded.append({'part':label,'reason':'no body Skin; rigid props and runtime surfaces are not projected'})
			continue
		var actual_skeleton = part.get_node_or_null(part.skeleton)
		if actual_skeleton == null:
			projection.free()
			return {'error':'Unresolved Skin skeleton: '+label}
		if actual_skeleton != body:
			report.excluded.append({'part':label,'reason':'independent auxiliary skeleton; never interpret its indices as body bones'})
			continue
		if not Interop.node_transform(part).is_equal_approx(Transform3D.IDENTITY):
			projection.free()
			return {'error':'Normalize skinned mesh transforms before projection: '+label}
		var frozen = frozen_mesh(part)
		if frozen.has('error'):
			projection.free()
			return frozen
		var copy = MeshInstance3D.new()
		copy.name = part.name
		copy.mesh = frozen.mesh
		copy.skin = part.skin.duplicate()
		projection.add_child(copy)
		copy.skeleton = copy.get_path_to(projected_skeleton)
		report.included.append({'part':label,'morph_channels_frozen':part.get_blend_shape_count(),'surfaces':copy.mesh.get_surface_count()})
	var bound = Interop.bind(projection,source,target)
	projection.free()
	if bound.has('error'): return bound
	var converted = Interop.retarget(final_animation,source,target)
	if converted.has('error'):
		bound.scene.free()
		return converted
	var player = AnimationPlayer.new()
	player.name = 'AnimationPlayer'
	var library = AnimationLibrary.new()
	library.add_animation('final_body',converted.animation)
	player.add_animation_library('',library)
	bound.scene.add_child(player)
	player.owner = bound.scene
	report['binding'] = bound.diagnostics
	report['animation_tracks'] = converted.animation.get_track_count()
	report['animation_duration'] = converted.animation.length
	bound.scene.set_meta('character_compatibility_export',report.duplicate(true))
	return {'scene':bound.scene,'report':report}
