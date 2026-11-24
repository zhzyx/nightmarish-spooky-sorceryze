@tool
extends RefCounted
# Independent anatomical template + segment-distance skinning. Not an AI autorigger.
const NAMES = ['hips','spine','chest','neck','head','upper_arm_l','forearm_l','hand_l','upper_arm_r','forearm_r','hand_r','thigh_l','shin_l','foot_l','thigh_r','shin_r','foot_r','root']
const PARENTS = [17,0,1,2,3,2,5,6,2,8,9,0,11,12,0,14,15,-1]

static func source_extras(path: String) -> Dictionary:
	if not FileAccess.file_exists(path): return {}
	var file = FileAccess.open(path,FileAccess.READ)
	if file == null or file.get_length()<28: return {}
	if file.get_buffer(4).get_string_from_ascii()!='glTF': return {}
	file.seek(12)
	var length = file.get_32()
	if length<=0 or 20+length>file.get_length(): return {}
	file.seek(20)
	var document = JSON.parse_string(file.get_buffer(length).get_string_from_utf8())
	if not document is Dictionary: return {}
	var asset = document.get('asset',{})
	if not asset is Dictionary: return {}
	var extras = asset.get('extras',{})
	return extras if extras is Dictionary else {}

static func defaults(path: String) -> Dictionary:
	var extras = source_extras(path)
	return {'source_sha256':FileAccess.get_sha256(path),'route':'standard','height_m':1.8,'yaw_degrees':0.0,'auto_orient':true,'crop_below_y':-10000.0,'clean_faces':false,'shoulder_gate_strength':0.0,'reference_pose':'T','confirmed_humanoid':false,'joints':{},'weights':{},'weights_geometry':'','head_landmarks':extras.get('maliang_head_landmarks',{}),'head_review':extras.get('maliang_head_review',{})}

static func head_contract_error(p: Dictionary) -> String:
	var review = p.get('head_review',{})
	if not review is Dictionary or review.get('passed')!=true: return '缺少通过的头脸多视角验收；请检查正面、斜侧面和侧面后再绑骨。'
	if review.get('mode') not in ['automatic','manual'] or review.get('head_geometry_mode') not in ['integrated','merged']: return '头脸验收记录版本无效。'
	var geometry_sha = str(review.get('geometry_sha256',''))
	if geometry_sha.length()!=64 or not geometry_sha.is_valid_hex_number(false): return '头脸验收未绑定源几何。'
	if review.has('source_sha256') and review.source_sha256!=p.get('source_sha256',''): return '头脸验收属于另一份模型。'
	var gate = review.get('head_gate',{})
	if not gate is Dictionary or gate.get('applicable')!=true or gate.get('complete_face')!=true or gate.get('neck_join_pass')!=true:
		return '头脸门禁未通过：嘴、下巴和头颈衔接必须完整。'
	var views = review.get('head_views',{})
	if not views is Dictionary: return '头脸验收缺少多视角记录。'
	for view in ['head_front','head_three_quarter','head_side']:
		if views.get(view)!=true: return '头脸多视角验收缺少或未通过：'+view
	if review.head_geometry_mode=='merged':
		var marks = p.get('head_landmarks',{})
		if not marks is Dictionary or marks.get('confirmed')!=true or marks.get('head_geometry_mode')!='merged': return '换头模型缺少确认的下巴和颈根标记。'
		for key in ['body_neck_y','head_chin_y','head_neck_y']:
			if not (marks.get(key) is float or marks.get(key) is int) or not is_finite(float(marks[key])): return '颈部标记必须为有限数值：'+key
		if not marks.head_neck_y<marks.head_chin_y: return '颈根标记必须低于下巴，不能在脸部裁切。'
	return ''

static func geometry_key(p: Dictionary) -> String:
	return JSON.stringify([p.source_sha256,p.height_m,p.yaw_degrees,p.crop_below_y,p.clean_faces,p.get('shoulder_gate_strength',0.0),'anatomical-segments-v1-arm-chain-gate-v3-source-arm-landmarks-v1']).sha256_text()

static func arm_chain_weight_falloff(point: Vector3, shoulder: Vector3, height: float, strength: float = 0.0) -> float:
	# Keep the inner chest out of every arm-chain bone; bounded retries can
	# tighten this gate without changing bone placement or repeating a fit.
	var gate = clampf(strength,0.0,1.0)
	var lateral = smoothstep(absf(shoulder.x)-height*(.01-.012*gate),absf(shoulder.x)+height*.04,absf(point.x))
	var below_shoulder = smoothstep(shoulder.y-height*(.12-.04*gate),shoulder.y-height*(.025-.01*gate),point.y)
	return lateral*below_shoulder

static func fit_t_pose_yaw(source_bounds: AABB, p: Dictionary) -> float:
	var yaw = float(p.get('yaw_degrees',0.0))
	if not p.get('auto_orient',false) or not is_zero_approx(yaw): return yaw
	if p.get('route')!='standard' or p.get('reference_pose')!='T': return yaw
	# A T pose may be authored with its arms along Z. Align that dominant
	# horizontal span to the template's X axis instead of placing arms in space.
	if source_bounds.size.z>source_bounds.size.x*1.5 and source_bounds.size.z>source_bounds.size.y*.65:
		return -90.0
	return yaw

static func source_arm_joints(extras: Dictionary, yaw_degrees: float, offset: Vector3, scale_factor: float) -> Dictionary:
	var result = {'joints':{},'validation_state':''}
	var record = extras.get('maliang_humanoid_landmarks',{})
	if not record is Dictionary: return {'error':'素体关节记录格式无效。'}
	if record.is_empty(): return result
	if record.get('reference_pose')!='T' or record.get('coordinate_space')!='Y_up_meters_left_positive_X':
		return {'error':'素体关节记录的参考姿势或坐标系无效。'}
	var landmarks = record.get('landmarks',{})
	if not landmarks is Dictionary: return {'error':'素体关节记录缺少坐标。'}
	var names = {'upper_arm_l':'shoulder_l','forearm_l':'elbow_l','hand_l':'wrist_l','upper_arm_r':'shoulder_r','forearm_r':'elbow_r','hand_r':'wrist_r'}
	var rotation = Basis(Vector3.UP,deg_to_rad(yaw_degrees))
	for bone_name in names:
		var xyz = landmarks.get(names[bone_name])
		if not xyz is Array or xyz.size()!=3: return {'error':'素体关节记录缺少完整手臂关键点：'+names[bone_name]}
		for value in xyz:
			if not (value is float or value is int) or not is_finite(float(value)): return {'error':'素体关节记录包含非有限坐标：'+names[bone_name]}
		var source_point = Vector3(xyz[0],xyz[1],xyz[2])
		result.joints[bone_name] = (rotation*source_point-offset)*scale_factor
	result.validation_state = str(record.get('validation_state','unknown'))
	return result

static func build(path: String, p: Dictionary) -> Dictionary:
	if not FileAccess.file_exists(path) or FileAccess.get_sha256(path) != p.get('source_sha256',''): return {'error':'源文件哈希不匹配；请重新打开源文件。'}
	if p.get('route') not in ['standard','free'] or p.get('reference_pose') not in ['T','marked']: return {'error':'请选择标准或自由路线，并使用 Y 轴向上的 T 形参考姿势。'}
	for key in ['height_m','yaw_degrees','crop_below_y','shoulder_gate_strength']:
		if not (p.get(key) is float or p.get(key) is int) or not is_finite(float(p[key])): return {'error':'参数必须为有限数值：'+key}
	if p.height_m < 0.2 or p.height_m > 4.0: return {'error':'身高必须在 0.2–4 米之间。'}
	if p.shoulder_gate_strength < 0.0 or p.shoulder_gate_strength > 1.0: return {'error':'肩胸权重边界强度必须在 0–1 之间。'}
	if not p.get('joints') is Dictionary or not p.get('weights') is Dictionary: return {'error':'关节和权重修正必须为对象。'}
	var head_problem = head_contract_error(p)
	if not head_problem.is_empty(): return {'error':head_problem}
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
	var source_bounds = AABB()
	var source_bounds_found = false
	for mi in meshes:
		var source_transform = Transform3D.IDENTITY
		var source_node = mi
		while source_node != null and source_node is Node3D:
			source_transform = source_node.transform * source_transform
			source_node = source_node.get_parent()
		var source_box = source_transform * mi.mesh.get_aabb()
		source_bounds = source_bounds.merge(source_box) if source_bounds_found else source_box
		source_bounds_found = true
	var requested_yaw = float(p.yaw_degrees)
	p.yaw_degrees = fit_t_pose_yaw(source_bounds,p)
	report['applied_yaw_degrees'] = p.yaw_degrees
	report['auto_orient_applied'] = not is_equal_approx(requested_yaw,p.yaw_degrees)
	if not p.weights.is_empty() and p.get('weights_geometry','')!=geometry_key(p):
		imported.free()
		return {'error':'权重修正属于另一份派生几何；请清除权重并载入新的标记 ID。'}
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
	report['source_arm_landmarks_applied'] = false
	if p.route=='standard' and p.reference_pose=='T':
		var landmark_fit = source_arm_joints(source_extras(path),p.yaw_degrees,offset,scale_factor)
		if landmark_fit.has('error'): return {'error':landmark_fit.error,'diagnostics':report}
		for bone_name in landmark_fit.joints:
			positions[NAMES.find(bone_name)] = landmark_fit.joints[bone_name]
		report.source_arm_landmarks_applied = not landmark_fit.joints.is_empty()
		report.source_arm_landmarks_validation_state = landmark_fit.validation_state
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
				var score = 1.0/pow(maxf(vertices[vi].distance_to(near),.015*h),4)
				if bi in [5,6,7,8,9,10]:
					var shoulder_index = 5 if bi in [5,6,7] else 8
					score *= arm_chain_weight_falloff(vertices[vi],positions[shoulder_index],h,float(p.get('shoulder_gate_strength',0.0)))
				scores.append([score,bi])
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
	# One-click mode replaces the separate confirmation checkbox with these
	# automatic anatomy checks; saving still requires an explicit user action.
	var accepted = (p.confirmed_humanoid or p.get('one_click',false)) and (p.route=='standard' or p.joints.size()>=NAMES.size()-1)
	var humanoid_errors: Array = []
	if bounds.size.x/bounds.size.y<.65 and p.reference_pose!='marked':
		accepted = false
		humanoid_errors.append('正视角未检测到展开且分离的双臂，T 形人物宽高比应不小于 0.65。')
		report.warnings.append('T 形姿势需要双臂分开，宽高比不小于 0.65。')
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
		for region in corridors:
			if corridors[region]<8:
				accepted = false
				humanoid_errors.append('正视角人形区域不完整或点数不足：'+region)
		if minf(corridors.arm_l,corridors.arm_r)/float(maxi(1,maxi(corridors.arm_l,corridors.arm_r)))<.25:
			accepted = false
			humanoid_errors.append('正视角左右臂区域明显不对称。')
	report['anatomy_corridor_vertices'] = corridors
	for side in ['l','r']:
		var hip = positions[NAMES.find('thigh_'+side)]
		var knee = positions[NAMES.find('shin_'+side)]
		var foot = positions[NAMES.find('foot_'+side)]
		if hip.y<=knee.y or knee.y<=foot.y or absf(hip.x-knee.x)>h*.05 or absf(knee.x-foot.x)>h*.05:
			accepted = false
			if p.route=='standard': humanoid_errors.append('正视角腿部关键点顺序或对齐不合理：'+side)
	report['humanoid_front_passed'] = humanoid_errors.is_empty()
	report['humanoid_errors'] = humanoid_errors
	if not accepted: report.warnings.append('需要人工检查 T 形姿势；自由网格必须标记全部 17 个关节点。当前预览尚未通过角色绑定验收。')
	root.set_meta('rigging',{'source_sha256':p.source_sha256,'parameters':p,'algorithm':'anatomical-segments-v1','skinning_algorithm':'segment-distance-arm-chain-gate-v3','status':'reviewed_template' if accepted else 'needs_landmarks','diagnostics':report,'height_m':h,'vertex_count':vertex_id,'geometry_key':geometry_key(p),'compatibility':'unbound','axes':'Y up, +Z forward; identity rest axes; not SkeletonProfileHumanoid','reference_pose':p.reference_pose})
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
		var rotations = {'upper_arm_l':Vector3(0,0,1.0),'upper_arm_r':Vector3(0,0,-1.0),'forearm_l':Vector3(0,0,.18),'forearm_r':Vector3(0,0,-.18),'hand_l':Vector3(0,0,-.12),'hand_r':Vector3(0,0,.12)} if motion=='raise_arms' else ({'thigh_l':Vector3(-.8,0,0),'thigh_r':Vector3(-.8,0,0),'shin_l':Vector3(1.4,0,0),'shin_r':Vector3(1.4,0,0),'spine':Vector3(.25,0,0)} if motion=='squat' else {'hips':Vector3(0,.8,0)})
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

static func validate_scene(scene: Node3D) -> Dictionary:
	var report = {'passed':false,'scene_valid':false,'issues':[],'unsupported':[],'movement_m':{},'rest_error_m':0.0,'squat_ankle_drift_m':0.0,'squat_sole_drift_m':0.0,'raise_chest_outward_m':0.0,'bone_count':0,'anatomical_bone_count':NAMES.size()-1}
	if scene == null:
		report.issues.append('角色场景为空。')
		return report
	var sk = scene.get_node_or_null('Skeleton3D') as Skeleton3D
	var body = scene.get_node_or_null('Body') as MeshInstance3D
	var player = scene.get_node_or_null('AnimationPlayer') as AnimationPlayer
	if sk == null or body == null or body.mesh == null or body.skin == null:
		report.issues.append('角色缺少 Skeleton3D、Body Mesh 或 Skin，无法执行骨骼验收。')
		return report
	report.bone_count = sk.get_bone_count()
	if sk.get_bone_count()!=NAMES.size(): report.issues.append('骨骼数量应为 17 根解剖骨加独立 root。')
	var skeleton_complete = sk.get_bone_count()==NAMES.size()
	var positions: Array[Vector3] = []
	for i in NAMES.size():
		var index = sk.find_bone(NAMES[i])
		if index<0 or index!=i or sk.get_bone_parent(index)!=PARENTS[i]:
			report.issues.append('骨骼名称、顺序或父子关系不符合标准模板：'+NAMES[i])
			skeleton_complete = false
			positions.append(Vector3.ZERO)
			continue
		var rest = sk.get_bone_global_rest(index)
		if not rest.origin.is_finite() or not rest.basis.x.is_finite() or not rest.basis.y.is_finite() or not rest.basis.z.is_finite():
			report.issues.append('骨骼静止变换包含非有限数值：'+NAMES[i])
			skeleton_complete = false
		positions.append(rest.origin)
	var height = float(scene.get_meta('rigging',{}).get('height_m',1.8))
	if skeleton_complete:
		for i in range(1,5):
			if positions[i].y<=positions[PARENTS[i]].y: report.issues.append('躯干骨骼高度顺序不合理：'+NAMES[i])
		for side in ['l','r']:
			var upper = positions[NAMES.find('upper_arm_'+side)]
			var forearm = positions[NAMES.find('forearm_'+side)]
			var hand = positions[NAMES.find('hand_'+side)]
			var direction = 1.0 if side=='l' else -1.0
			if (forearm.x-upper.x)*direction<=height*.03 or (hand.x-forearm.x)*direction<=height*.03: report.issues.append('手臂骨骼方向或长度不合理：'+side)
			var hip = positions[NAMES.find('thigh_'+side)]
			var knee = positions[NAMES.find('shin_'+side)]
			var foot = positions[NAMES.find('foot_'+side)]
			if hip.y<=knee.y or knee.y<=foot.y: report.issues.append('腿部骨骼高度顺序不合理：'+side)
			if absf(hip.x-knee.x)>height*.05 or absf(knee.x-foot.x)>height*.05: report.issues.append('腿部骨骼左右对齐异常：'+side)
			if absf(knee.z-hip.z)>height*.12 or absf(foot.z-hip.z)>height*.16: report.issues.append('腿部骨骼不在合理的矢状面附近：'+side)
		for pair in [['upper_arm_l','upper_arm_r'],['forearm_l','forearm_r'],['hand_l','hand_r'],['thigh_l','thigh_r'],['shin_l','shin_r'],['foot_l','foot_r']]:
			var left = positions[NAMES.find(pair[0])]
			var right = positions[NAMES.find(pair[1])]
			if absf(left.y-right.y)>height*.08 or absf(left.z-right.z)>height*.12 or absf(left.x+right.x)>height*.08: report.issues.append('左右骨骼明显不对称：'+pair[0]+' / '+pair[1])
	var weights_valid = body.skin.get_bind_count()==sk.get_bone_count()
	var rest_valid = true
	var surfaces: Array = []
	var rest_deform: Array[Transform3D] = []
	for bi in sk.get_bone_count(): rest_deform.append(sk.get_bone_global_rest(bi)*body.skin.get_bind_pose(bi) if bi<body.skin.get_bind_count() else Transform3D.IDENTITY)
	for si in body.mesh.get_surface_count():
		var arrays = body.mesh.surface_get_arrays(si)
		var vertices = arrays[Mesh.ARRAY_VERTEX]
		var bones = arrays[Mesh.ARRAY_BONES]
		var weights = arrays[Mesh.ARRAY_WEIGHTS]
		if vertices == null or bones == null or weights == null or bones.size()!=vertices.size()*4 or weights.size()!=vertices.size()*4:
			report.issues.append('蒙皮通道缺失或长度不匹配。')
			weights_valid = false
			continue
		surfaces.append(arrays)
		for vi in vertices.size():
			var v: Vector3 = vertices[vi]
			var deformed = Vector3.ZERO
			var total = 0.0
			for j in 4:
				var bi = bones[vi*4+j]
				var weight = weights[vi*4+j]
				if bi<0 or bi>=sk.get_bone_count() or bi>=body.skin.get_bind_count() or not is_finite(weight) or weight<0:
					weights_valid = false
					continue
				total += weight
				deformed += (rest_deform[bi]*v)*weight
			if absf(total-1.0)>.0001: weights_valid = false
			if not deformed.is_finite(): rest_valid = false
			else: report.rest_error_m = maxf(report.rest_error_m,deformed.distance_to(v))
	if not weights_valid: report.issues.append('逐顶点骨索引、绑定或权重无效。')
	if not rest_valid or report.rest_error_m>.0002: report.issues.append('静止姿势蒙皮无法还原原几何。')
	report.scene_valid = skeleton_complete and weights_valid and rest_valid and report.rest_error_m<=.0002
	if player == null:
		report.unsupported.append('当前角色没有 AnimationPlayer，无法自动执行 ROM 检查。')
	else:
		for motion in ['raise_arms','squat','turn']:
			if not player.has_animation(motion):
				report.unsupported.append('当前引擎结果缺少检查动画：'+motion)
				continue
			if not report.scene_valid: continue
			player.play(motion)
			player.advance(1.0)
			sk.force_update_all_bone_transforms()
			var pose_deform: Array[Transform3D] = []
			for bi in sk.get_bone_count(): pose_deform.append(sk.get_bone_global_pose(bi)*body.skin.get_bind_pose(bi))
			var shoulder_rest_l = sk.get_bone_global_rest(sk.find_bone('upper_arm_l')).origin
			var shoulder_rest_r = sk.get_bone_global_rest(sk.find_bone('upper_arm_r')).origin
			var chest_x_limit = minf(absf(shoulder_rest_l.x),absf(shoulder_rest_r.x))-height*.01
			var chest_y_low = minf(shoulder_rest_l.y,shoulder_rest_r.y)-height*.14
			var chest_y_high = maxf(shoulder_rest_l.y,shoulder_rest_r.y)+height*.02
			var maximum = 0.0
			for arrays in surfaces:
				var vertices = arrays[Mesh.ARRAY_VERTEX]
				var bones = arrays[Mesh.ARRAY_BONES]
				var weights = arrays[Mesh.ARRAY_WEIGHTS]
				for vi in vertices.size():
					var v: Vector3 = vertices[vi]
					var deformed = Vector3.ZERO
					for j in 4:
						var bi = bones[vi*4+j]
						deformed += (pose_deform[bi]*v)*weights[vi*4+j]
					if not deformed.is_finite(): report.issues.append('变形后出现非有限顶点：'+motion)
					else:
						maximum = maxf(maximum,deformed.distance_to(v))
						if motion=='raise_arms' and v.y>=chest_y_low and v.y<=chest_y_high and absf(v.x)<chest_x_limit:
							report.raise_chest_outward_m = maxf(report.raise_chest_outward_m,absf(deformed.x)-absf(v.x))
			report.movement_m[motion] = maximum
			if maximum<=.02: report.issues.append('实际蒙皮变形不足：'+motion)
			if motion=='raise_arms':
				for side in ['l','r']:
					var shoulder = sk.get_bone_global_pose(sk.find_bone('upper_arm_'+side)).origin
					var elbow = sk.get_bone_global_pose(sk.find_bone('forearm_'+side)).origin
					var wrist = sk.get_bone_global_pose(sk.find_bone('hand_'+side)).origin
					if elbow.y<=shoulder.y+height*.01 or wrist.y<=elbow.y+height*.01: report.issues.append('抬臂时肩、肘、腕的高度关系不合理：'+side)
					var upper_direction = (elbow-shoulder).normalized()
					var forearm_direction = (wrist-elbow).normalized()
					if upper_direction.dot(forearm_direction)<.85: report.issues.append('抬臂时肘部出现明显折返：'+side)
				if report.raise_chest_outward_m>height*.025: report.issues.append('抬臂时肩带内侧胸口出现明显外鼓。')
			if motion=='squat':
				var foot_indices = [sk.find_bone('foot_l'),sk.find_bone('foot_r')]
				for sample in 41:
					player.seek(sample*.05,true)
					sk.force_update_all_bone_transforms()
					var squat_deform: Array[Transform3D] = []
					for bi in sk.get_bone_count(): squat_deform.append(sk.get_bone_global_pose(bi)*body.skin.get_bind_pose(bi))
					for index in foot_indices: report.squat_ankle_drift_m = maxf(report.squat_ankle_drift_m,sk.get_bone_global_pose(index).origin.distance_to(sk.get_bone_global_rest(index).origin))
					for arrays in surfaces:
						var vertices = arrays[Mesh.ARRAY_VERTEX]
						var bones = arrays[Mesh.ARRAY_BONES]
						var weights = arrays[Mesh.ARRAY_WEIGHTS]
						for vi in vertices.size():
							var v: Vector3 = vertices[vi]
							if v.y>height*.025: continue
							var deformed = Vector3.ZERO
							for j in 4:
								var bi = bones[vi*4+j]
								deformed += (squat_deform[bi]*v)*weights[vi*4+j]
							report.squat_sole_drift_m = maxf(report.squat_sole_drift_m,deformed.distance_to(v))
				if report.squat_ankle_drift_m>=.003 or report.squat_sole_drift_m>=.003: report.issues.append('下蹲时脚踝或足底接触不稳定。')
	if player != null: player.stop()
	sk.reset_bone_poses()
	report.passed = report.scene_valid and report.issues.is_empty() and report.unsupported.is_empty()
	return report

static func owners(node: Node, root: Node):
	for child in node.get_children(): child.owner = root; owners(child,root)

static func stage(scene: Node3D, target: String, allow_limited: bool = false) -> String:
	if FileAccess.file_exists(target) or target.get_extension()!='tscn': return '请选择新的 .tscn 版本；现有文件不可覆盖。'
	var metadata = scene.get_meta('rigging',{})
	var allowed_status = ['reviewed_template','capability_limited'] if allow_limited else ['reviewed_template']
	if metadata.get('status') not in allowed_status: return '发布前请检查 T 形姿势，或补全自由网格的关节标记。'

	var snapshot = scene.duplicate()
	snapshot.get_node('AnimationPlayer').stop()
	snapshot.get_node('Skeleton3D').reset_bone_poses()
	owners(snapshot,snapshot)
	var packed = PackedScene.new()
	var error = packed.pack(snapshot)
	snapshot.free()
	if error!=OK or ResourceSaver.save(packed,target)!=OK: return '无法保存场景'
	return ''
