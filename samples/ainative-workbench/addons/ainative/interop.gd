@tool
extends RefCounted
# Independent rest-space adapter. No engine-owned skeleton definitions or assets.
const FAMILIES = ['anatomical','ue4','ue5_manny','ue5_quinn','mixamo']
const REQUIRED = ['hips','head','upper_arm_l','forearm_l','hand_l','upper_arm_r','forearm_r','hand_r','thigh_l','shin_l','foot_l','thigh_r','shin_r','foot_r']

static func encode(t: Transform3D) -> Array:
	return [t.basis.x.x,t.basis.x.y,t.basis.x.z,t.basis.y.x,t.basis.y.y,t.basis.y.z,t.basis.z.x,t.basis.z.y,t.basis.z.z,t.origin.x,t.origin.y,t.origin.z]

static func decode(a: Array) -> Transform3D:
	return Transform3D(Basis(Vector3(a[0],a[1],a[2]),Vector3(a[3],a[4],a[5]),Vector3(a[6],a[7],a[8])),Vector3(a[9],a[10],a[11]))

static func revision(p: Dictionary) -> String:
	var copy = p.duplicate(true)
	copy.erase('revision')
	return JSON.stringify(hash_numbers(copy),'',true,true).sha256_text()

static func hash_numbers(value):
	# Skeleton Transform3D values use engine float32. Canonicalize their exact
	# bits, not a decimal rounding boundary that JSON parsers can cross by 1 ULP.
	if value is int or value is float:
		var number = float(value)
		if number==0: number = 0.0
		return ['number32',PackedFloat32Array([number]).to_byte_array().hex_encode()]
	if value is Array:
		var out = []
		for item in value: out.append(hash_numbers(item))
		return ['array',out]
	if value is Dictionary:
		var out = {}
		for key in value: out[key] = hash_numbers(value[key])
		return ['object',out]
	return ['string',value] if value is String else ['literal',value]

static func load_scene(path: String) -> Dictionary:
	if not FileAccess.file_exists(path): return {'error':'Source file missing'}
	if path.get_extension().to_lower() == 'tscn':
		var packed = ResourceLoader.load(path,'PackedScene',ResourceLoader.CACHE_MODE_IGNORE)
		if packed is PackedScene: return {'scene':packed.instantiate()}
		return {'error':'Invalid packed scene'}
	var doc = FBXDocument.new() if path.get_extension().to_lower() == 'fbx' else GLTFDocument.new()
	var state = FBXState.new() if path.get_extension().to_lower() == 'fbx' else GLTFState.new()
	var err = doc.append_from_file(path,state)
	if err != OK: return {'error':'Asset import failed: '+str(err)}
	var scene = doc.generate_scene(state)
	if scene==null: return {'error':'No imported scene'}
	var error = normalize_imported(scene)
	if error: scene.free(); return {'error':error}
	return {'scene':scene}

static func normalize_imported(scene: Node3D) -> String:
	var sk = skeleton(scene)
	if sk==null: return 'Exactly one imported skeleton required'
	var transform = node_transform(sk)
	if transform.is_equal_approx(Transform3D.IDENTITY): return ''
	var scale = transform.basis.get_scale()
	if absf(scale.x-scale.y)>.00001 or absf(scale.y-scale.z)>.00001 or scale.x<=0: return 'Bake nonuniform or mirrored skeleton ancestor scale before importing'
	var roots = {}
	for i in sk.get_bone_count():
		if sk.get_bone_parent(i)>=0: continue
		roots[str(sk.get_bone_name(i))] = true
		sk.set_bone_rest(i,transform*sk.get_bone_rest(i))
	for player in scene.find_children('*','AnimationPlayer',true,false):
		for name in player.get_animation_list():
			var animation = player.get_animation(name)
			for track in animation.get_track_count():
				var path = animation.track_get_path(track)
				if path.get_subname_count()==0 or not roots.has(str(path.get_subname(0))): continue
				for key in animation.track_get_key_count(track):
					var value = animation.track_get_key_value(track,key)
					match animation.track_get_type(track):
						Animation.TYPE_POSITION_3D: animation.track_set_key_value(track,key,transform*value)
						Animation.TYPE_ROTATION_3D: animation.track_set_key_value(track,key,transform.basis.orthonormalized().get_rotation_quaternion()*value)
						Animation.TYPE_SCALE_3D: animation.track_set_key_value(track,key,scale*value)
	var node = sk
	while node!=null and node is Node3D:
		node.transform = Transform3D.IDENTITY
		if node==scene: break
		node = node.get_parent()
	sk.reset_bone_poses()
	scene.set_meta('interop_import_normalization',encode(transform))
	return ''

static func skeleton(scene: Node) -> Skeleton3D:
	if scene is Skeleton3D: return scene
	var all = scene.find_children('*','Skeleton3D',true,false)
	return all[0] if all.size()==1 else null

static func semantic(name: String, family: String) -> String:
	var n = name.get_slice(':',name.get_slice_count(':')-1).to_lower()
	if family == 'anatomical': return n
	if family == 'mixamo':
		n = n.trim_prefix('mixamorig_').trim_prefix('mixamorig')
		var center = {'hips':'hips','spine':'spine','spine1':'chest','spine2':'upper_chest','neck':'neck','head':'head'}
		if center.has(n): return center[n]
		for side in ['left','right']:
			if not n.begins_with(side): continue
			var suffix = '_l' if side=='left' else '_r'
			var part = n.trim_prefix(side)
			var limbs = {'shoulder':'clavicle','arm':'upper_arm','forearm':'forearm','hand':'hand','upleg':'thigh','leg':'shin','foot':'foot','toebase':'toe'}
			if limbs.has(part): return limbs[part]+suffix
			for finger in ['thumb','index','middle','ring','pinky']:
				if part.begins_with('hand'+finger): return finger+'_'+part.trim_prefix('hand'+finger)+suffix
		return ''
	var aliases = {'pelvis':'hips','spine_01':'spine','spine_02':'chest','spine_03':'upper_chest','neck_01':'neck','head':'head','root':'root'}
	if family in ['ue5_manny','ue5_quinn']:
		aliases['spine_03'] = 'spine_mid'
		aliases['spine_04'] = 'chest'
		aliases['spine_02'] = 'spine_lower'
		aliases['spine_05'] = 'upper_chest'
	if aliases.has(n): return aliases[n]
	for side in ['_l','_r']:
		if not n.ends_with(side): continue
		var part = n.trim_suffix(side)
		var limbs = {'clavicle':'clavicle','upperarm':'upper_arm','lowerarm':'forearm','hand':'hand','thigh':'thigh','calf':'shin','foot':'foot','ball':'toe'}
		if limbs.has(part): return limbs[part]+side
		for finger in ['thumb','index','middle','ring','pinky']:
			if part.begins_with(finger+'_') and part.trim_prefix(finger+'_').is_valid_int(): return finger+'_'+str(int(part.trim_prefix(finger+'_')))+side
	return ''

static func extract(scene: Node, family: String, source: Dictionary, corrections: Dictionary = {}) -> Dictionary:
	if family not in FAMILIES: return {'error':'Unsupported profile family; MetaHuman Body is a separate extension'}
	var sk = skeleton(scene)
	if sk == null: return {'error':'Exactly one Skeleton3D is required'}
	var ancestor = sk
	while ancestor!=null and ancestor is Node3D:
		if not ancestor.transform.is_equal_approx(Transform3D.IDENTITY): return {'error':'Bake skeleton ancestor transforms into the reference asset before extracting a metres profile'}
		if ancestor==scene: break
		ancestor = ancestor.get_parent()
	var p = {'schema_version':1,'family':family,'rules_version':'1','source':source.duplicate(true),'coordinates':{'units':'metres','up':'+Y','forward':'+Z','space':'Godot imported skeleton local'},'bones':[],'mapping':{},'corrections':corrections.duplicate(true),'auxiliary_policy':'preserve_local_rest','binding':'semantic_mapped'}
	p['import_normalization'] = scene.get_meta('interop_import_normalization',encode(Transform3D.IDENTITY))
	for i in sk.get_bone_count():
		var n = str(sk.get_bone_name(i))
		p.bones.append({'name':n,'parent':sk.get_bone_parent(i),'local_rest':encode(sk.get_bone_rest(i)),'global_rest':encode(sk.get_bone_global_rest(i))})
		var meaning = semantic(n,family)
		if meaning:
			if p.mapping.has(meaning): return {'error':'Ambiguous semantic mapping: '+meaning}
			p.mapping[meaning] = i
	for meaning in corrections:
		var i = sk.find_bone(str(corrections[meaning]))
		if i<0: return {'error':'Correction bone missing: '+str(corrections[meaning])}
		p.mapping[meaning] = i
	p.revision = revision(p)
	var error = validate(p)
	return {'error':error} if error else {'profile':p}

static func validate(p: Dictionary) -> String:
	if p.get('schema_version')!=1 or p.get('family') not in FAMILIES: return 'Unsupported profile schema/family'
	if p.get('coordinates')!={'units':'metres','up':'+Y','forward':'+Z','space':'Godot imported skeleton local'}: return 'Unsupported profile coordinates; import and normalize the reference asset'
	if not p.get('source') is Dictionary or str(p.source.get('sha256','')).length()!=64 or not p.source.get('version','') or not p.source.get('authority',''): return 'Immutable source hash, version and authority required'
	for field in ['sha256','version','authority']:
		if not p.source[field] is String: return 'Source identity fields must be strings'
	if not p.source.sha256.is_valid_hex_number(false): return 'Source SHA256 must be hex'
	var authority = str(p.source.authority)
	if authority.contains('\\') or authority.contains(':/') and not authority.begins_with('https://') and not authority.begins_with('http://'): return 'Source authority must be a portable URI, not a machine path'
	if not p.get('bones') is Array or p.bones.is_empty() or not p.get('mapping') is Dictionary: return 'Bones and mapping required'
	if p.get('revision','')!=revision(p): return 'Profile revision mismatch; regenerate after edits'
	var names = {}
	for b in p.bones:
		if not b is Dictionary or not (b.get('parent') is float or b.get('parent') is int): return 'Invalid bone/parent'
		if b.parent != int(b.parent) or b.parent < -1 or b.parent >= p.bones.size(): return 'Invalid parent index'
	for i in p.bones.size():
		var b = p.bones[i]
		if not b is Dictionary or not b.get('name') is String or names.has(b.name): return 'Invalid/duplicate bone name'
		names[b.name] = true
		if not b.get('parent') is float and not b.get('parent') is int: return 'Invalid parent'
		if b.parent != int(b.parent) or b.parent < -1 or b.parent >= p.bones.size(): return 'Invalid parent index'
		var seen = {}
		var parent = i
		while parent>=0:
			if seen.has(parent): return 'Hierarchy cycle'
			seen[parent] = true
			parent = int(p.bones[parent].parent)
		for field in ['local_rest','global_rest']:
			if not b.get(field) is Array or b[field].size()!=12: return 'Invalid rest transform'
			for v in b[field]:
				if not (v is float or v is int) or not is_finite(float(v)): return 'Nonfinite rest transform'
			if absf(decode(b[field]).basis.determinant())<0.000001: return 'Singular rest transform'
	for meaning in p.mapping:
		var i = p.mapping[meaning]
		if not (i is int or i is float) or i!=int(i) or i<0 or i>=p.bones.size(): return 'Invalid semantic index'
	for b in p.bones:
		var expected = decode(b.local_rest)
		if int(b.parent)>=0: expected = decode(p.bones[int(b.parent)].global_rest)*expected
		if not expected.is_equal_approx(decode(b.global_rest)): return 'Local/global rest disagree'
	var required_indices = {}
	for meaning in REQUIRED:
		if not p.mapping.has(meaning): return 'Missing required semantic: '+meaning
		if required_indices.has(int(p.mapping[meaning])): return 'Required anatomical semantics must use distinct bones'
		required_indices[int(p.mapping[meaning])] = true
	for side in ['_l','_r']:
		for chain in [['thigh','shin','foot'],['upper_arm','forearm','hand']]:
			for j in 2:
				var ancestor = int(p.mapping[chain[j]+side])
				var child = int(p.mapping[chain[j+1]+side])
				while child>=0 and child!=ancestor: child = int(p.bones[child].parent)
				if child<0: return 'Semantic limb mapping must follow an ancestor chain'
	return ''

static func make_skeleton(p: Dictionary) -> Skeleton3D:
	var sk = Skeleton3D.new()
	sk.name = 'Skeleton3D'
	for b in p.bones: sk.add_bone(b.name)
	for i in p.bones.size():
		sk.set_bone_parent(i,int(p.bones[i].parent))
		sk.set_bone_rest(i,decode(p.bones[i].local_rest))
	sk.reset_bone_poses()
	return sk

static func globals(p: Dictionary) -> Array:
	var out = []
	for b in p.bones: out.append(decode(b.global_rest))
	return out

static func pose_global(sk: Skeleton3D, index: int) -> Transform3D:
	var pose = sk.get_bone_pose(index)
	var parent = sk.get_bone_parent(index)
	return pose_global(sk,parent)*pose if parent>=0 else pose

static func pair_map(source: Dictionary, target: Dictionary) -> Dictionary:
	var pairs = {}
	for meaning in source.mapping:
		if target.mapping.has(meaning): pairs[int(source.mapping[meaning])] = int(target.mapping[meaning])
	return pairs

static func proportion(source: Dictionary, target: Dictionary) -> float:
	var s = globals(source)
	var t = globals(target)
	var sh = s[int(source.mapping.hips)].origin.distance_to(s[int(source.mapping.foot_l)].origin)
	var th = t[int(target.mapping.hips)].origin.distance_to(t[int(target.mapping.foot_l)].origin)
	return th/maxf(sh,0.001)

# Geometric frame bridges anatomical identity axes and imported bone axes.
# Translation and segment length adaptation occur before target inverse binds.
static func frames(p: Dictionary) -> Array:
	var rest = globals(p)
	var result = rest.duplicate()
	var next = {'hips':'spine','spine':'chest','chest':'neck','neck':'head'}
	for side in ['_l','_r']:
		next['clavicle'+side] = 'upper_arm'+side
		next['upper_arm'+side] = 'forearm'+side
		next['forearm'+side] = 'hand'+side
		next['thigh'+side] = 'shin'+side
		next['shin'+side] = 'foot'+side
		for finger in ['thumb','index','middle','ring','pinky']:
			for segment in [1,2,3]: next[finger+'_'+str(segment)+side] = finger+'_'+str(segment+1)+side
	for meaning in next:
		if not p.mapping.has(meaning) or not p.mapping.has(next[meaning]): continue
		var i = int(p.mapping[meaning])
		var j = int(p.mapping[next[meaning]])
		var y = rest[j].origin-rest[i].origin
		if y.length()<0.00001: continue
		var z = Vector3.FORWARD
		if absf(y.normalized().dot(z))>.98: z = Vector3.RIGHT
		var x = y.normalized().cross(z).normalized()
		z = x.cross(y.normalized()).normalized()
		result[i] = Transform3D(Basis(x,y,z),rest[i].origin)
	# End effectors inherit geometric orientation and scale from their limb.
	for side in ['_l','_r']:
		for leaf in ['hand','foot']:
			var parent = ('forearm' if leaf=='hand' else 'shin')+side
			if p.mapping.has(leaf+side) and p.mapping.has(parent):
				var i = int(p.mapping[leaf+side])
				result[i] = Transform3D(result[int(p.mapping[parent])].basis,rest[i].origin)
		for finger in ['thumb','index','middle','ring','pinky']:
			for segment in [3,4]:
				var key = finger+'_'+str(segment)+side
				var previous = finger+'_'+str(segment-1)+side
				if p.mapping.has(key) and p.mapping.has(previous) and not p.mapping.has(finger+'_'+str(segment+1)+side):
					var i = int(p.mapping[key])
					result[i] = Transform3D(result[int(p.mapping[previous])].basis,rest[i].origin)
	# A head's native FBX bone axes are not its anatomical up/forward axes.
	# Use the neck's geometric orientation and overall body proportion, so
	# a different bone-frame convention cannot rotate or shear the skull.
	if p.mapping.has('neck') and p.mapping.has('head'):
		var head = int(p.mapping.head)
		var scale = rest[int(p.mapping.hips)].origin.distance_to(rest[int(p.mapping.foot_l)].origin)
		result[head] = Transform3D(result[int(p.mapping.neck)].basis.orthonormalized().scaled(Vector3.ONE*scale),rest[head].origin)
	return result

static func bind(source_scene: Node3D, source: Dictionary, target: Dictionary) -> Dictionary:
	for p in [source,target]:
		var error = validate(p)
		if error: return {'error':error}
	var old = skeleton(source_scene)
	if old == null or old.get_bone_count()!=source.bones.size(): return {'error':'Source profile does not match skeleton'}
	for i in old.get_bone_count():
		if old.get_bone_name(i)!=source.bones[i].name or not old.get_bone_rest(i).is_equal_approx(decode(source.bones[i].local_rest)): return {'error':'Source rest changed; create a new profile revision'}
	var pairs = pair_map(source,target)
	var sf = frames(source)
	var sg = globals(source)
	var tf = frames(target)
	var tg = globals(target)
	var scene = Node3D.new()
	scene.name = 'TargetAvatar'
	var sk = make_skeleton(target)
	scene.add_child(sk)
	sk.owner = scene
	var skin = Skin.new()
	for i in target.bones.size(): skin.add_bind(i,tg[i].affine_inverse())
	var report = {'binding':'target_bound','vertices':0,'max_rest_reconstruction_m':0.0,'max_adaptation_m':0.0,'weighted_finger_vertices':0,'missing_source_fingers':[],'auxiliary_policy':'preserve_local_rest; missing weighted semantics collapse to nearest mapped ancestor','unsupported':['MetaHuman Body']}
	for side in ['_l','_r']:
		for finger in ['thumb','index','middle','ring','pinky']:
			if not source.mapping.has(finger+'_1'+side): report.missing_source_fingers.append(finger+side)
	var target_semantic_by_id = {}
	for key in target.mapping: target_semantic_by_id[int(target.mapping[key])] = key
	for mi in source_scene.find_children('*','MeshInstance3D',true,false):
		if mi.skin == null: continue
		var mesh = ArrayMesh.new()
		for si in mi.mesh.get_surface_count():
			var a = mi.mesh.surface_get_arrays(si).duplicate(true)
			var vertices: PackedVector3Array = a[Mesh.ARRAY_VERTEX]
			var bones = a[Mesh.ARRAY_BONES]
			var weights = a[Mesh.ARRAY_WEIGHTS]
			if bones==null or weights==null or weights.size()==0: scene.free(); return {'error':'Weighted mesh required'}
			var influences = weights.size()/vertices.size()
			for vi in vertices.size():
				var out = Vector3.ZERO
				var source_rest_vertex = Vector3.ZERO
				var normal = Vector3.ZERO
				var sum = 0.0
				var finger_weight = 0.0
				for k in int(influences):
					var offset = vi*int(influences)+k
					var w = weights[offset]
					var bind_id = bones[offset]
					if not is_finite(w) or w<0 or bind_id<0 or bind_id>=mi.skin.get_bind_count(): scene.free(); return {'error':'Invalid weight/bind index'}
					var bi = mi.skin.get_bind_bone(bind_id)
					if mi.skin.get_bind_name(bind_id)!='': bi = old.find_bone(mi.skin.get_bind_name(bind_id))
					if w<=0: bones[offset] = 0; continue
					if bi<0 or bi>=old.get_bone_count(): scene.free(); return {'error':'Invalid skin bone'}
					# Missing weighted auxiliaries follow the nearest mapped ancestor explicitly.
					var mapped = bi
					while mapped>=0 and not pairs.has(mapped): mapped = old.get_bone_parent(mapped)
					if mapped<0: scene.free(); return {'error':'Weighted bone has no mapped ancestor: '+str(bi)}
					var ti = pairs[mapped]
					var warp = tf[ti]*sf[mapped].affine_inverse()
					var source_rest = sg[bi]*mi.skin.get_bind_pose(bind_id)
					source_rest_vertex += (source_rest*vertices[vi])*w
					out += (warp*source_rest*vertices[vi])*w
					if a[Mesh.ARRAY_NORMAL]!=null: normal += ((warp*source_rest).basis.inverse().transposed()*a[Mesh.ARRAY_NORMAL][vi])*w
					bones[offset] = ti
					sum += w
					if str(target_semantic_by_id.get(ti,'')).split('_')[0] in ['thumb','index','middle','ring','pinky']: finger_weight += w
				if absf(sum-1)>.001 or not out.is_finite(): scene.free(); return {'error':'Invalid weights or nonfinite deformation'}
				if finger_weight>0.001: report.weighted_finger_vertices += 1
				report.max_adaptation_m = maxf(report.max_adaptation_m,out.distance_to(source_rest_vertex))
				vertices[vi] = out
				if a[Mesh.ARRAY_NORMAL]!=null: a[Mesh.ARRAY_NORMAL][vi] = normal.normalized()
				var reconstructed = Vector3.ZERO
				for k in int(influences):
					var offset = vi*int(influences)+k
					reconstructed += (tg[bones[offset]]*skin.get_bind_pose(bones[offset])*out)*weights[offset]
				report.max_rest_reconstruction_m = maxf(report.max_rest_reconstruction_m,reconstructed.distance_to(out))
				report.vertices += 1
			a[Mesh.ARRAY_VERTEX] = vertices
			a[Mesh.ARRAY_BONES] = bones
			# Recompute tangent basis on export; stale tangents would belong to the original pose.
			a[Mesh.ARRAY_TANGENT] = null
			mesh.add_surface_from_arrays(mi.mesh.surface_get_primitive_type(si),a,[],{},mi.mesh.surface_get_format(si)&Mesh.ARRAY_FLAG_USE_8_BONE_WEIGHTS)
			mesh.surface_set_material(mesh.get_surface_count()-1,mi.mesh.surface_get_material(si))
		var body = MeshInstance3D.new()
		body.name = mi.name
		body.mesh = mesh
		body.skin = skin
		scene.add_child(body)
		body.skeleton = body.get_path_to(sk)
		body.owner = scene
	if report.vertices==0: scene.free(); return {'error':'No skinned geometry'}
	scene.set_meta('interop',{'schema_version':1,'avatar_revision':revision({'source':source.revision,'target':target.revision,'algorithm':'geometric-rest-bind-2'}),'source_skeleton':source,'target_skeleton':target,'binding':'target_bound','diagnostics':report})
	return {'scene':scene,'diagnostics':report}

static func node_transform(node: Node) -> Transform3D:
	var result = Transform3D.IDENTITY
	while node!=null and node is Node3D:
		result = node.transform*result
		node = node.get_parent()
	return result

# Sample source animation in source rest space; solve target locals in hierarchy order.
static func retarget(animation: Animation, source: Dictionary, target: Dictionary, fps: float = 30.0, contacts: Array = []) -> Dictionary:
	for p in [source,target]:
		var error = validate(p)
		if error: return {'error':error}
	if not is_finite(fps) or fps<1 or fps>240: return {'error':'Sample rate must be finite 1..240'}
	for contact in contacts:
		if not contact is Dictionary or contact.get('side') not in ['l','r']: return {'error':'Invalid contact declaration'}
		for key in ['start','end']:
			if not (contact.get(key) is int or contact.get(key) is float) or not is_finite(float(contact[key])): return {'error':'Finite contact interval required'}
		if contact.start<0 or contact.end<contact.start or contact.end>animation.length+.00001: return {'error':'Contact interval outside clip'}
		if contact.has('position_m'):
			if not contact.position_m is Array or contact.position_m.size()!=3: return {'error':'Contact position must have 3 coordinates'}
			for v in contact.position_m:
				if not (v is float or v is int) or not is_finite(float(v)): return {'error':'Finite contact coordinates required'}
	var ss = make_skeleton(source)
	var ts = make_skeleton(target)
	var sr = globals(source)
	var tr = globals(target)
	var pairs = pair_map(source,target)
	var reverse = {}
	for i in pairs: reverse[pairs[i]] = i
	var ratio = proportion(source,target)
	var result = Animation.new()
	result.length = animation.length
	result.loop_mode = animation.loop_mode
	var tracks = {}
	for ti in target.bones.size():
		var indexes = []
		for kind in [Animation.TYPE_POSITION_3D,Animation.TYPE_ROTATION_3D,Animation.TYPE_SCALE_3D]:
			var track = result.add_track(kind)
			result.track_set_path(track,NodePath('Skeleton3D:'+target.bones[ti].name))
			indexes.append(track)
		tracks[ti] = indexes
	var order = []
	var contact_error = 0.0
	while order.size()<target.bones.size():
		for i in target.bones.size():
			if i not in order and (int(target.bones[i].parent)<0 or int(target.bones[i].parent) in order): order.append(i)
	for sample in range(int(ceil(animation.length*fps))+1):
		var time = minf(sample/fps,animation.length)
		ss.reset_bone_poses()
		for track in animation.get_track_count():
			var path = animation.track_get_path(track)
			if path.get_subname_count()==0 or not animation.track_is_enabled(track): continue
			var bi = ss.find_bone(path.get_subname(0))
			if bi<0 or animation.track_get_key_count(track)==0: continue
			match animation.track_get_type(track):
				Animation.TYPE_POSITION_3D: ss.set_bone_pose_position(bi,animation.position_track_interpolate(track,time))
				Animation.TYPE_ROTATION_3D: ss.set_bone_pose_rotation(bi,animation.rotation_track_interpolate(track,time))
				Animation.TYPE_SCALE_3D: ss.set_bone_pose_scale(bi,animation.scale_track_interpolate(track,time))
		ss.force_update_all_bone_transforms()
		var poses = {}
		for ti in order:
			var parent = int(target.bones[ti].parent)
			var parent_pose = poses[parent] if parent>=0 else Transform3D.IDENTITY
			var local = decode(target.bones[ti].local_rest)
			if not source.mapping.has('root') and ti==int(target.mapping.get('root',-2)):
				var hips = int(source.mapping.hips)
				var travel = (pose_global(ss,hips).origin-sr[hips].origin)*ratio
				local.origin += Vector3(travel.x,0,travel.z)
			if reverse.has(ti):
				var si = reverse[ti]
				var sp = pose_global(ss,si)
				var rotation_delta = sp.basis.orthonormalized()*sr[si].basis.orthonormalized().inverse()
				local.basis = parent_pose.basis.inverse()*rotation_delta*tr[ti].basis
				# Keep target segment lengths. Only the locomotion root and pelvis
				# receive source translation; local FK supplies limb positions.
				if si==int(source.mapping.hips) or si==int(source.mapping.get('root',-2)):
					local.origin = parent_pose.affine_inverse()*(tr[ti].origin+(sp.origin-sr[si].origin)*ratio)
			poses[ti] = parent_pose*local
		for contact in contacts:
			if time<float(contact.get('start',0)) or time>float(contact.get('end',animation.length)): continue
			var side = str(contact.get('side','l'))
			if side not in ['l','r']: ss.free(); ts.free(); return {'error':'Contact side must be l/r'}
			var foot = int(target.mapping['foot_'+side])
			var goal = tr[foot].origin
			if contact.has('position_m'):
				var v = contact.position_m
				goal = Vector3(v[0],v[1],v[2])
			contact_error = maxf(contact_error,solve_leg(poses,target,order,side,goal))
		for ti in order:
			var parent = int(target.bones[ti].parent)
			var local = poses[parent].affine_inverse()*poses[ti] if parent>=0 else poses[ti]
			result.position_track_insert_key(tracks[ti][0],time,local.origin)
			result.rotation_track_insert_key(tracks[ti][1],time,local.basis.orthonormalized().get_rotation_quaternion())
			result.scale_track_insert_key(tracks[ti][2],time,local.basis.get_scale())
	ss.free()
	ts.free()
	return {'animation':result,'diagnostics':{'sample_rate':fps,'translation_ratio':ratio,'mapped_bones':pairs.size(),'unmapped_target_bones':target.bones.size()-pairs.size(),'auxiliary_policy':'preserve_local_rest','root_policy':'mapped root; hips fallback when root absent','contact_policy':'explicit planted intervals, analytic two-bone leg IK' if not contacts.is_empty() else 'no planted intervals supplied','max_contact_error_m':contact_error}}

static func solve_leg(poses: Dictionary, p: Dictionary, order: Array, side: String, goal: Vector3) -> float:
	var a = int(p.mapping['thigh_'+side])
	var b = int(p.mapping['shin_'+side])
	var c = int(p.mapping['foot_'+side])
	var start = poses[a].origin
	var knee = poses[b].origin
	var end = poses[c].origin
	var l1 = start.distance_to(knee)
	var l2 = knee.distance_to(end)
	var distance = start.distance_to(goal)
	if minf(l1,l2)<.00001 or distance<.00001: return distance
	var axis = (goal-start).normalized()
	var bend = knee-start-axis*(knee-start).dot(axis)
	if bend.length()<.00001:
		bend = Vector3.FORWARD-axis*Vector3.FORWARD.dot(axis)
	if bend.length()<.00001: bend = Vector3.RIGHT-axis*Vector3.RIGHT.dot(axis)
	bend = bend.normalized()
	var reach = clampf(distance,absf(l1-l2)+.000001,l1+l2-.000001)
	var along = (l1*l1-l2*l2+reach*reach)/(2*reach)
	var new_knee = start+axis*along+bend*sqrt(maxf(0,l1*l1-along*along))
	var new_end = start+axis*reach
	var before = poses.duplicate()
	poses[a] = Transform3D(Basis(Quaternion((knee-start).normalized(),(new_knee-start).normalized()))*before[a].basis,start)
	poses[b] = Transform3D(Basis(Quaternion((end-knee).normalized(),(new_end-new_knee).normalized()))*before[b].basis,new_knee)
	poses[c] = Transform3D(before[c].basis,new_end)
	for i in order:
		if i in [a,b,c]: continue
		var parent = int(p.bones[i].parent)
		if parent>=0: poses[i] = poses[parent]*before[parent].affine_inverse()*before[i]
	return new_end.distance_to(goal)

static func attach_animations(scene: Node3D, source_scene: Node, source: Dictionary, target: Dictionary, contacts: Dictionary = {}) -> Dictionary:
	for name in contacts:
		if not contacts[name] is Array: return {'error':'Contact declarations must be arrays by animation name'}
	var players = source_scene.find_children('*','AnimationPlayer',true,false)
	var previous = scene.get_node_or_null('AnimationPlayer')
	if previous!=null:
		scene.remove_child(previous)
		previous.free()
	var player = AnimationPlayer.new()
	player.name = 'AnimationPlayer'
	scene.add_child(player)
	player.owner = scene
	var library = AnimationLibrary.new()
	player.add_animation_library('',library)
	var reports = {}
	for original in players:
		for name in original.get_animation_list():
			if name=='RESET': continue
			var converted = retarget(original.get_animation(name),source,target,30.0,contacts.get(name,[]))
			if converted.has('error'): return converted
			library.add_animation(name.replace('/','_'),converted.animation)
			reports[name] = converted.diagnostics
	if scene.has_meta('interop'):
		var metadata = scene.get_meta('interop')
		metadata['contacts'] = contacts.duplicate(true)
		metadata['animation_source_revision'] = source.revision
		metadata['animation_algorithm'] = 'rest-delta-fk-root-contact-1'
		metadata['avatar_revision'] = revision({'source':source.revision,'target':target.revision,'contacts':contacts,'bind':'geometric-rest-bind-2','retarget':'rest-delta-fk-root-contact-1'})
	return {'animations':reports}

static func stage_scene(scene: Node3D, path: String) -> String:
	var packed = PackedScene.new()
	if packed.pack(scene)!=OK: return 'Cannot pack avatar'
	return '' if ResourceSaver.save(packed,path)==OK else 'Cannot stage scene'

static func stage_glb(scene: Node3D, path: String) -> String:
	var doc = GLTFDocument.new()
	var state = GLTFState.new()
	if doc.append_from_scene(scene,state)!=OK: return 'Cannot encode GLB'
	return '' if doc.write_to_filesystem(state,path)==OK else 'Cannot stage GLB'
