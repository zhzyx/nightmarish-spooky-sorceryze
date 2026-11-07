@tool
extends RefCounted
# Independent anatomical template + segment-distance skinning. Not an AI autorigger.
const NAMES = ['hips','spine','chest','neck','head','upper_arm_l','forearm_l','hand_l','upper_arm_r','forearm_r','hand_r','thigh_l','shin_l','foot_l','thigh_r','shin_r','foot_r','root']
const PARENTS = [17,0,1,2,3,2,5,6,2,8,9,0,11,12,0,14,15,-1]

static func defaults(path: String) -> Dictionary:
	return {'source_sha256':FileAccess.get_sha256(path),'route':'standard','height_m':1.8,'yaw_degrees':0.0,'crop_below_y':-10000.0,'clean_faces':false,'reference_pose':'T','confirmed_humanoid':false,'joints':{},'weights':{},'weights_geometry':''}

static func geometry_key(p: Dictionary) -> String:
	return JSON.stringify([p.source_sha256,p.height_m,p.yaw_degrees,p.crop_below_y,p.clean_faces,'anatomical-segments-v1']).sha256_text()

static func build(path: String, p: Dictionary) -> Dictionary:
	if not FileAccess.file_exists(path) or FileAccess.get_sha256(path) != p.get('source_sha256',''): return {'error':'源文件哈希不匹配；请重新打开源文件。'}
	if p.get('route') not in ['standard','free'] or p.get('reference_pose') not in ['T','marked']: return {'error':'请选择标准或自由路线，并使用 Y 轴向上的 T 形参考姿势。'}
	for key in ['height_m','yaw_degrees','crop_below_y']:
		if not (p.get(key) is float or p.get(key) is int) or not is_finite(float(p[key])): return {'error':'参数必须为有限数值：'+key}
	if p.height_m < 0.2 or p.height_m > 4.0: return {'error':'身高必须在 0.2–4 米之间。'}
	if not p.get('joints') is Dictionary or not p.get('weights') is Dictionary: return {'error':'关节和权重修正必须为对象。'}
	if not p.weights.is_empty() and p.get('weights_geometry','')!=geometry_key(p): return {'error':'权重修正属于另一份派生几何；请清除权重并载入新的标记 ID。'}
	var doc = GLTFDocument.new()
	var state = GLTFState.new()
	if doc.append_from_file(path,state) != OK: return {'error':'无法解析 GLB/glTF'}
	var imported = preload('res://addons/ainative/runtime_mesh.gd').generate(doc,state)
	if imported == null: return {'error':'未找到场景'}
	var surfaces = []
	var bounds = AABB()
	var first = true
	var report = {'input_vertices':0,'input_faces':0,'removed_faces':0,'degenerate_faces':0,'duplicate_faces':0,'boundary_edges':0,'nonmanifold_edges':0,'warnings':[]}
	var meshes = imported.find_children('*','MeshInstance3D',true,false)
	if imported is MeshInstance3D: meshes.append(imported)
	for mi in meshes:
		var transform = Transform3D.IDENTITY
		var node = mi
		while node != null and node is Node3D:
			transform = node.transform * transform
			node = node.get_parent()
		transform = Transform3D(Basis(Vector3.UP,deg_to_rad(p.yaw_degrees)),Vector3.ZERO) * transform
		for si in mi.mesh.get_surface_count():
			if mi.mesh.surface_get_primitive_type(si) != Mesh.PRIMITIVE_TRIANGLES: continue
			var a = mi.mesh.surface_get_arrays(si)
			var vertices: PackedVector3Array = a[Mesh.ARRAY_VERTEX]
			for i in vertices.size(): vertices[i] = transform * vertices[i]
			report.input_vertices += vertices.size()
			var normals = a[Mesh.ARRAY_NORMAL]
			if normals != null:
				for i in normals.size(): normals[i] = (transform.basis.inverse().transposed() * normals[i]).normalized()
				a[Mesh.ARRAY_NORMAL] = normals
			var indices = a[Mesh.ARRAY_INDEX]
			if indices == null or indices.is_empty(): indices = PackedInt32Array(range(vertices.size()))
			var kept = PackedInt32Array()
			var seen = {}
			var edges = {}
			for k in range(0,indices.size(),3):
				report.input_faces += 1
				var ids = [indices[k],indices[k+1],indices[k+2]]
				var v = [vertices[ids[0]],vertices[ids[1]],vertices[ids[2]]]
				var degenerate = (v[1]-v[0]).cross(v[2]-v[0]).length_squared() < 1e-16
				var keys = [str(v[0].snapped(Vector3.ONE * 0.000001)),str(v[1].snapped(Vector3.ONE * 0.000001)),str(v[2].snapped(Vector3.ONE * 0.000001))]
				keys.sort()
				var facekey = '|'.join(keys)
				var duplicate = seen.has(facekey)
				seen[facekey] = true
				if degenerate: report.degenerate_faces += 1
				if duplicate: report.duplicate_faces += 1
				if minf(v[0].y,minf(v[1].y,v[2].y)) < p.crop_below_y or (p.clean_faces and (degenerate or duplicate)):
					report.removed_faces += 1
					continue
				kept.append_array(PackedInt32Array(ids))
				for j in 3:
					var edge = [keys[j],keys[(j+1)%3]]
					edge.sort()
					var ek = '|'.join(edge)
					edges[ek] = edges.get(ek,0)+1
			for count in edges.values():
				if count == 1: report.boundary_edges += 1
				if count > 2: report.nonmanifold_edges += 1
			if kept.is_empty(): continue
			# Compact every per-vertex channel together; correction IDs refer to this deterministic order.
			var mapping = {}
			var old_ids = []
			for k in kept.size():
				var old = kept[k]
				if not mapping.has(old):
					mapping[old] = old_ids.size()
					old_ids.append(old)
				kept[k] = mapping[old]
			a[Mesh.ARRAY_VERTEX] = vertices
			for channel in [Mesh.ARRAY_VERTEX,Mesh.ARRAY_NORMAL,Mesh.ARRAY_COLOR,Mesh.ARRAY_TEX_UV,Mesh.ARRAY_TEX_UV2]:
				if a[channel] == null: continue
				var compact = a[channel].duplicate()
				compact.resize(old_ids.size())
				for j in old_ids.size(): compact[j] = a[channel][old_ids[j]]
				a[channel] = compact
			a[Mesh.ARRAY_TANGENT] = null
			a[Mesh.ARRAY_INDEX] = kept
			for v in a[Mesh.ARRAY_VERTEX]:
				bounds = AABB(v,Vector3.ZERO) if first else bounds.expand(v)
				first = false
			surfaces.append({'arrays':a,'material':mi.mesh.surface_get_material(si)})
	imported.free()
	if first or bounds.size.y < 0.0001: return {'error':'清理后没有剩余几何','diagnostics':report}
	if report.boundary_edges or report.nonmanifold_edges: report.warnings.append('检测到开放边或非流形边；请检查预览，当前处理不保证修复为封闭网格。')
	var scale_factor = p.height_m/bounds.size.y
	var offset = Vector3(bounds.get_center().x,bounds.position.y,bounds.get_center().z)
	var h: float = p.height_m
	var positions = [Vector3(0,.51,0),Vector3(0,.61,0),Vector3(0,.73,0),Vector3(0,.83,0),Vector3(0,.91,0),Vector3(.13,.76,0),Vector3(.29,.76,0),Vector3(.44,.76,0),Vector3(-.13,.76,0),Vector3(-.29,.76,0),Vector3(-.44,.76,0),Vector3(.085,.49,0),Vector3(.085,.27,0),Vector3(.085,.055,.04),Vector3(-.085,.49,0),Vector3(-.085,.27,0),Vector3(-.085,.055,.04),Vector3.ZERO]
	for i in positions.size(): positions[i] *= h
	# Median occupied cross-sections fit depth and limb locations to retained geometry.
	var normalized = []
	for surface in surfaces:
		for v in surface.arrays[Mesh.ARRAY_VERTEX]: normalized.append((v-offset)*scale_factor)
	for bi in range(positions.size()-1):
		var candidates = []
		for v in normalized:
			if absf(v.y-positions[bi].y)<h*.035 and absf(v.x-positions[bi].x)<h*.055: candidates.append(v.z)
		if not candidates.is_empty():
			candidates.sort()
			positions[bi].z = candidates[candidates.size()/2]
	for name in p.joints:
		var xyz = p.joints[name]
		if not name in NAMES or not xyz is Array or xyz.size()!=3: return {'error':'关节修正无效：'+str(name)}
		for n in xyz:
			if not (n is float or n is int) or not is_finite(float(n)) or absf(n)>h*2: return {'error':'关节必须包含以米为单位的有限坐标'}
		positions[NAMES.find(name)] = Vector3(xyz[0],xyz[1],xyz[2])
	var root = Node3D.new()
	root.name = 'Character'
	var skeleton = Skeleton3D.new()
	skeleton.name = 'Skeleton3D'
	root.add_child(skeleton)
	var skin = Skin.new()
	for bone_name in NAMES: skeleton.add_bone(bone_name)
	for i in NAMES.size():
		skeleton.set_bone_parent(i,PARENTS[i])
		var relative = positions[i] - positions[PARENTS[i]] if PARENTS[i]>=0 else positions[i]
		skeleton.set_bone_rest(i,Transform3D(Basis.IDENTITY,relative))
		skeleton.set_bone_pose_position(i,relative)
		skin.add_bind(i,Transform3D(Basis.IDENTITY,-positions[i]))
	var mesh = ArrayMesh.new()
	var vertex_id = 0
	for surface in surfaces:
		var a = surface.arrays
		var vertices: PackedVector3Array = a[Mesh.ARRAY_VERTEX]
		var bones = PackedInt32Array()
		var weights = PackedFloat32Array()
		for vi in vertices.size():
			vertices[vi] = (vertices[vi]-offset)*scale_factor
			var scores = []
			for bi in range(positions.size()-1):
				var end = positions[bi]+Vector3(0,.04*h,0)
				for child in positions.size():
					if PARENTS[child] == bi: end = positions[child]; break
				if bi in [13,16]: end = positions[bi]+Vector3(0,0,.10*h)
				if bi in [7,10]: end = positions[bi]+Vector3(signf(positions[bi].x)*.06*h,0,0)
				var delta = end-positions[bi]
				var near = positions[bi]+delta*clampf((vertices[vi]-positions[bi]).dot(delta)/maxf(delta.length_squared(),1e-10),0,1)
				scores.append([1.0/pow(maxf(vertices[vi].distance_to(near),.015*h),4),bi])
			scores.sort_custom(func(x,y): return x[0]>y[0])
			var values = {}
			for k in 4: values[str(scores[k][1])] = scores[k][0]
			# Preserve the support surface under ankle IK: foot/toes are rigid below ankle;
			# transition smoothly over the lower shin. Explicit painted weights take precedence.
			var foot_index = 13 if vertices[vi].x>=0 else 16
			var ankle_height = positions[foot_index].y
			var foot_blend = 1.0-smoothstep(ankle_height+.03*h,ankle_height+.09*h,vertices[vi].y)
			if foot_blend>0:
				var score_total = 0.0
				for value in values.values(): score_total += value
				for key in values: values[key] = values[key]/score_total*(1.0-foot_blend)
				values[str(foot_index)] = values.get(str(foot_index),0)+foot_blend
				if foot_blend>=1.0: values = {str(foot_index):1.0}
				elif values.size()>4:
					var smallest = ''
					for key in values:
						if key!=str(foot_index) and (smallest=='' or values[key]<values[smallest]): smallest = key
					values.erase(smallest)
			if p.weights.has(str(vertex_id)): values = p.weights[str(vertex_id)]
			if not values is Dictionary or values.is_empty() or values.size()>4: root.free(); return {'error':'权重覆盖需要 1–4 个“骨骼索引:权重”条目'}
			var total = 0.0
			for key in values:
				if not str(key).is_valid_int() or int(key)<0 or int(key)>=NAMES.size() or not (values[key] is float or values[key] is int) or not is_finite(float(values[key])) or values[key]<0: root.free(); return {'error':'权重或索引无效'}
				total += values[key]
			if total<=0: root.free(); return {'error':'权重总和为零'}
			for key in values: bones.append(int(key)); weights.append(values[key]/total)
			for k in range(values.size(),4): bones.append(0); weights.append(0)
			vertex_id += 1
		a[Mesh.ARRAY_VERTEX] = vertices
		a[Mesh.ARRAY_BONES] = bones
		a[Mesh.ARRAY_WEIGHTS] = weights
		mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES,a)
		mesh.surface_set_material(mesh.get_surface_count()-1,surface.material)
	for key in p.weights:
		if not str(key).is_valid_int() or int(key)<0 or int(key)>=vertex_id: root.free(); return {'error':'权重修正的顶点 ID 超出派生几何范围'}
	var instance = MeshInstance3D.new()
	instance.name = 'Body'
	instance.mesh = mesh
	instance.skin = skin
	instance.skeleton = NodePath('../Skeleton3D')
	root.add_child(instance)
	var accepted = p.confirmed_humanoid and (p.route=='standard' or p.joints.size()>=NAMES.size()-1)
	if bounds.size.x/bounds.size.y<.65 and p.reference_pose!='marked': accepted = false; report.warnings.append('T 形姿势需要双臂分开，宽高比不小于 0.65。')
	if p.reference_pose=='marked' or p.route=='free':
		for bone in NAMES:
			if bone!='root' and not p.joints.has(bone): accepted = false
	# Standard route is intentionally narrow: separated symmetric limb corridors and upright proportions.
	var corridors = {'arm_l':0,'arm_r':0,'leg_l':0,'leg_r':0,'head':0}
	for v in normalized:
		if v.y>h*.58 and v.y<h*.86 and v.x>h*.24: corridors.arm_l += 1
		if v.y>h*.58 and v.y<h*.86 and v.x< -h*.24: corridors.arm_r += 1
		if v.y<h*.36 and v.x>h*.035: corridors.leg_l += 1
		if v.y<h*.36 and v.x< -h*.035: corridors.leg_r += 1
		if v.y>h*.85 and absf(v.x)<h*.16: corridors.head += 1
	if p.route=='standard':
		for count in corridors.values():
			if count<8: accepted = false
		if minf(corridors.arm_l,corridors.arm_r)/float(maxi(1,maxi(corridors.arm_l,corridors.arm_r)))<.25: accepted = false
	report['anatomy_corridor_vertices'] = corridors
	for side in ['l','r']:
		var hip = positions[NAMES.find('thigh_'+side)]
		var knee = positions[NAMES.find('shin_'+side)]
		var foot = positions[NAMES.find('foot_'+side)]
		if hip.y<=knee.y or knee.y<=foot.y or absf(hip.x-knee.x)>h*.05 or absf(knee.x-foot.x)>h*.05: accepted = false
	if not accepted: report.warnings.append('需要人工检查 T 形姿势；自由网格必须标记全部 17 个关节点。当前预览尚未通过角色绑定验收。')
	root.set_meta('rigging',{'source_sha256':p.source_sha256,'parameters':p,'algorithm':'anatomical-segments-v1','status':'reviewed_template' if accepted else 'needs_landmarks','diagnostics':report,'height_m':h,'vertex_count':vertex_id,'geometry_key':geometry_key(p),'compatibility':'unbound','axes':'Y up, +Z forward; identity rest axes; not SkeletonProfileHumanoid','reference_pose':p.reference_pose})
	var revision = JSON.stringify(p).sha256_text()
	var manifest = {'schema_version':1,'artifacts':[
		{'id':'source','type':'mesh','revision':p.source_sha256,'payload':{'sha256':p.source_sha256}},
		{'id':'skeleton','type':'skeleton_profile','revision':revision,'payload':{'bone_names':NAMES,'parents':PARENTS,'axes':'identity/Y-up/+Z forward','reference_pose':p.reference_pose}},
		{'id':'avatar','type':'avatar_profile','revision':revision,'payload':{'height_m':h},'dependencies':[{'id':'skeleton','revision':revision}]},
		{'id':'character','type':'character','revision':revision,'payload':{'algorithm':'anatomical-segments-v1'},'dependencies':[{'id':'source','revision':p.source_sha256},{'id':'avatar','revision':revision}],'binding':{'level':'semantic_mapped','skeleton':{'id':'skeleton','revision':revision}}}]}
	root.set_meta('ainative_manifest',manifest)
	add_rom(root)
	return {'scene':root,'diagnostics':report,'accepted':accepted}

static func add_rom(root: Node3D):
	var player = AnimationPlayer.new()
	player.name = 'AnimationPlayer'
	root.add_child(player)
	var library = AnimationLibrary.new()
	for motion in ['raise_arms','squat','turn']:
		var animation = Animation.new()
		animation.length = 2.0
		animation.loop_mode = Animation.LOOP_LINEAR
		var rotations = {'upper_arm_l':Vector3(0,0,.75),'upper_arm_r':Vector3(0,0,-.75)} if motion=='raise_arms' else ({'thigh_l':Vector3(-.8,0,0),'thigh_r':Vector3(-.8,0,0),'shin_l':Vector3(1.4,0,0),'shin_r':Vector3(1.4,0,0),'spine':Vector3(.25,0,0)} if motion=='squat' else {'hips':Vector3(0,.8,0)})
		var sk = root.get_node('Skeleton3D')
		var tracks = {}
		for bone in NAMES:
			var track = animation.add_track(Animation.TYPE_ROTATION_3D)
			animation.track_set_path(track,NodePath('Skeleton3D:'+bone))
			tracks[bone] = track
		var hip_track = animation.add_track(Animation.TYPE_POSITION_3D)
		animation.track_set_path(hip_track,NodePath('Skeleton3D:hips'))
		var hip_rest = sk.get_bone_rest(0).origin
		for step in 41:
			var time = step*.05
			var amount = sin(time*PI/2.0)
			var hip_shift = Vector3(0,-root.get_meta('rigging').height_m*.13*amount,0) if motion=='squat' else Vector3.ZERO
			var angles = {}
			for bone in rotations: angles[bone] = rotations[bone]*amount
			if motion=='squat':
				for side in ['l','r']:
					var upper = sk.get_bone_rest(sk.find_bone('shin_'+side)).origin
					var lower = sk.get_bone_rest(sk.find_bone('foot_'+side)).origin
					var target = upper+lower-hip_shift
					var l1 = Vector2(upper.y,upper.z).length()
					var l2 = Vector2(lower.y,lower.z).length()
					var d = Vector2(target.y,target.z).length()
					var alpha = atan2(-target.z,-target.y)
					var rest1 = atan2(-upper.z,-upper.y)
					var rest2 = atan2(-lower.z,-lower.y)
					var theta = acos(clampf((l1*l1+d*d-l2*l2)/maxf(2*l1*d,1e-9),-1,1))
					var bend = acos(clampf((d*d-l1*l1-l2*l2)/maxf(2*l1*l2,1e-9),-1,1))
					angles['thigh_'+side] = Vector3(alpha-theta-rest1,0,0)
					angles['shin_'+side] = Vector3(bend+rest1-rest2,0,0)
					angles['foot_'+side] = -angles['thigh_'+side]-angles['shin_'+side]
			for bone in NAMES: animation.rotation_track_insert_key(tracks[bone],time,Quaternion.from_euler(angles.get(bone,Vector3.ZERO)))
			animation.position_track_insert_key(hip_track,time,hip_rest+hip_shift)
		library.add_animation(motion,animation)
	player.add_animation_library('',library)

static func owners(node: Node, root: Node):
	for child in node.get_children(): child.owner = root; owners(child,root)

static func stage(scene: Node3D, target: String) -> String:
	if FileAccess.file_exists(target) or target.get_extension()!='tscn': return '请选择新的 .tscn 版本；现有文件不可覆盖。'
	var metadata = scene.get_meta('rigging',{})
	if metadata.get('status')!='reviewed_template': return '发布前请检查 T 形姿势，或补全自由网格的关节标记。'

	var snapshot = scene.duplicate()
	snapshot.get_node('AnimationPlayer').stop()
	snapshot.get_node('Skeleton3D').reset_bone_poses()
	owners(snapshot,snapshot)
	var packed = PackedScene.new()
	var error = packed.pack(snapshot)
	snapshot.free()
	if error!=OK or ResourceSaver.save(packed,target)!=OK: return '无法保存场景'
	return ''
