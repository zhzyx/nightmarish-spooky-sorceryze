@tool
extends RefCounted
# Reviewed cage fit; independent generated source is never edited. No cloth solver.
const Interop = preload('res://addons/ainative/interop.gd')
const SHAPE_KEYS = ['chest','waist','hips','depth']

static func embedded_only(value) -> bool:
	if value is Dictionary:
		if value.has('uri') and (not value.uri is String or not value.uri.begins_with('data:')): return false
		for child in value.values():
			if not embedded_only(child): return false
	elif value is Array:
		for child in value:
			if not embedded_only(child): return false
	return true

static func source_bytes(path: String, expected: String) -> Dictionary:
	var bytes = FileAccess.get_file_as_bytes(path)
	if bytes.size()<20 or bytes.decode_u32(0)!=0x46546c67 or bytes.decode_u32(4)!=2 or bytes.decode_u32(8)!=bytes.size(): return {'error':'Invalid independent GLB header'}
	var length = bytes.decode_u32(12)
	if bytes.decode_u32(16)!=0x4e4f534a or length>bytes.size()-20: return {'error':'Invalid independent GLB JSON chunk'}
	var document = JSON.parse_string(bytes.slice(20,20+length).get_string_from_utf8())
	if not document is Dictionary or not embedded_only(document): return {'error':'Garment must be self-contained; external GLB dependencies refused'}
	var digest = HashingContext.new()
	digest.start(HashingContext.HASH_SHA256)
	digest.update(bytes)
	if digest.finish().hex_encode()!=expected: return {'error':'Garment source hash mismatch'}
	return {'bytes':bytes}

static func normal_arrays(a: Array) -> Array:
	var vertices = a[Mesh.ARRAY_VERTEX]
	var indices = a[Mesh.ARRAY_INDEX]
	if indices==null or indices.is_empty(): indices = PackedInt32Array(range(vertices.size()))
	var normals = PackedVector3Array()
	normals.resize(vertices.size())
	for i in range(0,indices.size(),3):
		var ids = [indices[i],indices[i+1],indices[i+2]]
		# Godot front faces use clockwise winding; preserve imported outward orientation.
		var normal = (vertices[ids[2]]-vertices[ids[0]]).cross(vertices[ids[1]]-vertices[ids[0]])
		for id in ids: normals[id] += normal
	for i in normals.size(): normals[i] = normals[i].normalized()
	a[Mesh.ARRAY_NORMAL] = normals
	a[Mesh.ARRAY_TANGENT] = null
	return a

static func shape_error(shape: Dictionary) -> String:
	for key in SHAPE_KEYS:
		var v = shape.get(key,1.0)
		if not (v is float or v is int) or not is_finite(float(v)) or v < .8 or v > 1.2: return 'Body shape outside calibrated 0.8–1.2 envelope: '+key
	for key in shape:
		if not key in SHAPE_KEYS: return 'Unknown body dimension: '+key
	return ''

static func shaped(v: Vector3, shape: Dictionary, hip: float, chest: float) -> Vector3:
	var t = clampf((v.y-hip)/maxf(chest-hip,.001),0,1)
	var width = lerpf(shape.get('hips',1.0),shape.get('waist',1.0),t*2) if t<.5 else lerpf(shape.get('waist',1.0),shape.get('chest',1.0),(t-.5)*2)
	# Fade above shoulders and below hips; stature is unchanged.
	var influence = smoothstep(hip-.25,hip,v.y)*(1.0-smoothstep(chest,chest+.2,v.y))
	return Vector3(v.x*lerpf(1,width,influence),v.y,v.z*lerpf(1,shape.get('depth',1.0),influence))

static func intersection_diagnostics(body: ArrayMesh, garment: ArrayMesh) -> Dictionary:
	var body_bvh = body.generate_triangle_mesh()
	var garment_bvh = garment.generate_triangle_mesh()
	var body_faces = body.get_faces()
	var crossings = 0
	var tested_edges = 0
	var samples = 0
	var near_surface = 0
	var distances = []
	# Deterministic bounded sampling of actual triangles, not bounding boxes.
	var stride = maxi(1,int(ceil(body_faces.size()/3.0/2048.0)))
	for face in range(0,body_faces.size()/3,stride):
		for edge in 3:
			var start = body_faces[face*3+edge]
			var end = body_faces[face*3+(edge+1)%3]
			if start.distance_to(end)<.000001: continue
			tested_edges += 1
			if not garment_bvh.intersect_segment(start,end).is_empty(): crossings += 1
	var points = garment.surface_get_arrays(0)[Mesh.ARRAY_VERTEX]
	stride = maxi(1,int(ceil(points.size()/512.0)))
	for i in range(0,points.size(),stride):
		var v = points[i]
		var radial = Vector3(v.x,0,v.z).normalized()
		if radial.length_squared()<.5: continue
		var distance = INF
		for direction in [-1,1]:
			var hit = body_bvh.intersect_segment(v,v+radial*direction*.3)
			if not hit.is_empty(): distance = minf(distance,v.distance_to(hit.position))
		samples += 1
		if is_finite(distance):
			distances.append(distance)
			if distance<.003: near_surface += 1
	distances.sort()
	return {'method':'actual triangle BVH edge intersections and bidirectional radial surface-distance samples','body_edges_tested':tested_edges,'crossing_edges':crossings,'garment_samples':samples,'radial_hits':distances.size(),'radial_min_distance_m':distances[0] if not distances.is_empty() else null,'radial_median_distance_m':distances[distances.size()/2] if not distances.is_empty() else null,'samples_under_3mm':near_surface,'status':'intersections_detected' if crossings>0 else 'no_intersections_in_sample','limitations':'Sampled, not exhaustive; radial distance is not shortest clearance; open/nonmanifold body prevents reliable inside/outside certification.'}

static func fit(path: String, spec: Dictionary, avatar: Node3D, profile: Dictionary, shape: Dictionary) -> Dictionary:
	if avatar.has_meta('garment'): return {'error':'Swap from the immutable base avatar, not a derived assembly; old garments and accessory bones must not accumulate'}
	var error = Interop.validate(profile)
	if error: return {'error':error}
	error = shape_error(shape)
	if error: return {'error':error}
	var captured = source_bytes(path,spec.get('source_sha256',''))
	if captured.has('error'): return captured
	if spec.get('kind') not in ['top','armor','skirt'] or not spec.get('id','') or not spec.get('version',''): return {'error':'Garment identity/version/kind required'}
	if not spec.id is String or not spec.version is String or not spec.id.is_valid_identifier(): return {'error':'Garment ID must be an identifier and version a string'}
	var yaw = spec.get('yaw_degrees',0.0)
	if not (yaw is float or yaw is int) or not is_finite(float(yaw)): return {'error':'Finite garment orientation required'}
	var original_sk = Interop.skeleton(avatar)
	if original_sk==null or original_sk.get_bone_count()!=profile.bones.size(): return {'error':'Avatar skeleton differs from Profile'}
	for i in original_sk.get_bone_count():
		if original_sk.get_bone_parent(i)!=int(profile.bones[i].parent) or not original_sk.get_bone_global_rest(i).is_equal_approx(Interop.decode(profile.bones[i].global_rest)): return {'error':'Avatar hierarchy/global rest does not match immutable Profile'}
		if original_sk.get_bone_name(i)!=profile.bones[i].name or not original_sk.get_bone_rest(i).is_equal_approx(Interop.decode(profile.bones[i].local_rest)): return {'error':'Avatar rest does not match immutable Profile'}
	var doc = GLTFDocument.new()
	var state = GLTFState.new()
	if doc.append_from_buffer(captured.bytes,'',state)!=OK: return {'error':'Garment GLB import failed'}
	var source = doc.generate_scene(state)
	if source==null: return {'error':'Empty garment scene'}
	var surfaces = []
	var bounds = AABB()
	var first = true
	for mi in source.find_children('*','MeshInstance3D',true,false):
		var transform = Transform3D(Basis(Vector3.UP,deg_to_rad(spec.get('yaw_degrees',0.0))),Vector3.ZERO)*Interop.node_transform(mi)
		for si in mi.mesh.get_surface_count():
			var a = mi.mesh.surface_get_arrays(si)
			var vertices = a[Mesh.ARRAY_VERTEX]
			for i in vertices.size():
				vertices[i] = transform*vertices[i]
				bounds = AABB(vertices[i],Vector3.ZERO) if first else bounds.expand(vertices[i])
				first = false
			a[Mesh.ARRAY_VERTEX] = vertices
			surfaces.append({'arrays':a,'material':mi.mesh.surface_get_material(si)})
	source.free()
	if first or minf(bounds.size.x,minf(bounds.size.y,bounds.size.z))<.0001: return {'error':'Degenerate garment cage'}
	var rest = Interop.globals(profile)
	var hips = rest[int(profile.mapping.hips)].origin
	var chest_bone = int(profile.mapping.get('chest',profile.mapping.hips))
	var chest = rest[chest_bone].origin
	var neck = rest[int(profile.mapping.get('neck',profile.mapping.head))].origin
	var shoulder_width = rest[int(profile.mapping.upper_arm_l)].origin.distance_to(rest[int(profile.mapping.upper_arm_r)].origin)
	var target = AABB(Vector3(-shoulder_width*.58,hips.y,-shoulder_width*.30),Vector3(shoulder_width*1.16,neck.y-hips.y,shoulder_width*.60))
	if spec.kind=='skirt':
		var knee_y = (rest[int(profile.mapping.shin_l)].origin.y+rest[int(profile.mapping.shin_r)].origin.y)*.5
		var waist_y = hips.y+(chest.y-hips.y)*.2
		target = AABB(Vector3(-shoulder_width*.7,knee_y,-shoulder_width*.4),Vector3(shoulder_width*1.4,waist_y-knee_y,shoulder_width*.8))
	if spec.has('target_box'):
		var b = spec.target_box
		if not b is Array or b.size()!=6: return {'error':'target_box requires six meter coordinates'}
		for value in b:
			if not (value is float or value is int) or not is_finite(float(value)): return {'error':'Nonfinite target cage'}
		target = AABB(Vector3(b[0],b[1],b[2]),Vector3(b[3],b[4],b[5]))
		if minf(target.size.x,minf(target.size.y,target.size.z))<=0: return {'error':'Invalid target cage dimensions'}
	# The authored cloth boundary is separate from the skeleton's hip joint.
	# Deep poses can intersect a low hip-pinned boundary; refit the partition
	# and cloth binding together instead of weakening prescribed waist pins.
	var cloth_start_y = hips.y
	if spec.has('cloth_start_y'):
		var boundary = spec.cloth_start_y
		if spec.kind != 'skirt' or not (boundary is int or boundary is float) or not is_finite(float(boundary)) or boundary <= target.position.y+.02 or boundary >= target.end.y-.01:
			return {'error':'Skirt cloth_start_y must be finite inside the target cage with a retained waist band'}
		cloth_start_y = float(boundary)
	var scene = avatar.duplicate()
	scene.name = 'GarmentAssembly'
	var sk = Interop.skeleton(scene)
	sk.reset_bone_poses()
	for player in scene.find_children('*','AnimationPlayer',true,false): player.stop()
	# Independent body shape derivation, retaining the same Profile revision.
	var hidden_faces = 0
	var diagnostic_body = ArrayMesh.new()
	for mi in scene.find_children('*','MeshInstance3D',true,false):
		var mesh = ArrayMesh.new()
		for si in mi.mesh.get_surface_count():
			var a = mi.mesh.surface_get_arrays(si)
			var vertices = a[Mesh.ARRAY_VERTEX]
			for i in vertices.size(): vertices[i] = shaped(vertices[i],shape,hips.y,chest.y)
			a[Mesh.ARRAY_VERTEX] = vertices
			diagnostic_body.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES,a)
			# Explicit reviewed torso occlusion region, derived only; full source remains available.
			if spec.get('occlude_torso',false):
				var indices = a[Mesh.ARRAY_INDEX]
				if indices==null or indices.is_empty(): indices = PackedInt32Array(range(vertices.size()))
				var kept = PackedInt32Array()
				for i in range(0,indices.size(),3):
					var center = (vertices[indices[i]]+vertices[indices[i+1]]+vertices[indices[i+2]])/3
					if center.y>hips.y and center.y<chest.y and absf(center.x)<shoulder_width*.4: hidden_faces+=1
					else: kept.append_array(PackedInt32Array([indices[i],indices[i+1],indices[i+2]]))
				a[Mesh.ARRAY_INDEX] = kept
			mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES,normal_arrays(a))
			mesh.surface_set_material(si,mi.mesh.surface_get_material(si))
		mi.mesh = mesh
	var auxiliary = -1
	var extension = []
	if spec.kind=='skirt':
		auxiliary = sk.get_bone_count()
		sk.add_bone('garment_'+str(spec.id)+'_hem')
		sk.set_bone_parent(auxiliary,int(profile.mapping.hips))
		sk.set_bone_rest(auxiliary,Transform3D.IDENTITY)
		sk.reset_bone_pose(auxiliary)
		extension.append({'name':str(sk.get_bone_name(auxiliary)),'parent':sk.get_bone_parent(auxiliary),'local_rest':Interop.encode(sk.get_bone_rest(auxiliary)),'global_rest':Interop.encode(sk.get_bone_global_rest(auxiliary))})
	var skin = Skin.new()
	for i in sk.get_bone_count(): skin.add_bind(i,sk.get_bone_global_rest(i).affine_inverse())
	var mesh = ArrayMesh.new()
	var partitions = {'rigid':[],'skinned':[],'cloth':[],'cloth_pins':[]}
	var vertex_id = 0
	for surface in surfaces:
		var a = surface.arrays
		var vertices = a[Mesh.ARRAY_VERTEX]
		var bones = PackedInt32Array()
		var weights = PackedFloat32Array()
		for i in vertices.size():
			var unit = (vertices[i]-bounds.position)/bounds.size
			vertices[i] = shaped(target.position+unit*target.size,shape,hips.y,chest.y)
			var scores = []
			var zone = 'rigid' if spec.kind=='armor' else ('cloth' if spec.kind=='skirt' and vertices[i].y<cloth_start_y else 'skinned')
			partitions[zone].append(vertex_id)
			if zone=='rigid': scores = [[1.0,chest_bone]]
			elif zone=='cloth':
				var free = clampf((cloth_start_y-vertices[i].y)/maxf(target.size.y*.25,.01),0,1)
				scores = [[free,auxiliary],[1.0-free,int(profile.mapping.hips)]]
				if free<.15: partitions.cloth_pins.append(vertex_id)
			else:
				for semantic in ['hips','spine','chest','upper_arm_l','upper_arm_r']:
					if profile.mapping.has(semantic):
						var b = int(profile.mapping[semantic])
						scores.append([1.0/pow(maxf(vertices[i].distance_to(rest[b].origin),.03),4),b])
				scores.sort_custom(func(x,y): return x[0]>y[0])
				scores = scores.slice(0,4)
			var total = 0.0
			for score in scores: total += score[0]
			for k in 4:
				bones.append(scores[k][1] if k<scores.size() else 0)
				weights.append(scores[k][0]/total if k<scores.size() else 0.0)
			vertex_id += 1
		a[Mesh.ARRAY_VERTEX] = vertices
		a[Mesh.ARRAY_BONES] = bones
		a[Mesh.ARRAY_WEIGHTS] = weights
		a[Mesh.ARRAY_TANGENT] = null
		mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES,normal_arrays(a))
		mesh.surface_set_material(mesh.get_surface_count()-1,surface.material)
		if surface.material==null:
			var material = StandardMaterial3D.new()
			material.albedo_color = {'top':Color(.08,.5,.65),'armor':Color(.75,.5,.12),'skirt':Color(.6,.12,.2)}[spec.kind]
			material.roughness = .8
			mesh.surface_set_material(mesh.get_surface_count()-1,material)
	var garment = MeshInstance3D.new()
	garment.name = 'Garment'
	garment.mesh = mesh
	garment.skin = skin
	scene.add_child(garment)
	garment.skeleton = garment.get_path_to(sk)
	var manifest = {'schema_version':1,'garment':spec.duplicate(true),'avatar_profile_revision':profile.revision,'avatar_source':profile.source.duplicate(true),'body_shape':shape.duplicate(true),'algorithm':'reviewed-axis-cage-v1','partitions':partitions,'cloth_solver':'none; deferred to #152','auxiliary_bone':auxiliary,'shared_bones':profile.bones.size(),'hidden_body_faces':hidden_faces,'vertices':vertex_id,'target_box':[target.position.x,target.position.y,target.position.z,target.size.x,target.size.y,target.size.z]}
	manifest.revision = JSON.stringify(manifest,'',true,true).sha256_text()
	manifest['skeleton_extension'] = {'base_profile_revision':profile.revision,'bones':extension,'combined_revision':Interop.revision({'base_profile_revision':profile.revision,'bones':extension})}
	manifest['clearance'] = intersection_diagnostics(diagnostic_body,mesh)
	manifest.revision = Interop.revision(manifest)
	scene.set_meta('garment',manifest)
	return {'scene':scene,'manifest':manifest}

static func stage(scene: Node3D, path: String) -> String:
	if FileAccess.file_exists(path) or path.get_extension()!='tscn': return 'Choose a new .tscn version; never overwrite a source or derived version'
	var snapshot = scene.duplicate()
	for player in snapshot.find_children('*','AnimationPlayer',true,false): player.stop()
	Interop.skeleton(snapshot).reset_bone_poses()
	preload('res://addons/ainative/rigging.gd').owners(snapshot,snapshot)
	var packed = PackedScene.new()
	var code = packed.pack(snapshot)
	snapshot.free()
	if code!=OK or ResourceSaver.save(packed,path)!=OK: return 'Cannot stage garment assembly'
	return ''
