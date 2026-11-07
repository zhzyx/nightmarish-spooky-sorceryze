@tool
extends RefCounted
const Interop = preload('res://addons/ainative/interop.gd')
const ORDER = ['base_animation','priority_layers','main_socket_weapon','offhand_ik','fingers','final_body_pose','face_reserved','cloth_reserved']

static func capture(sk: Skeleton3D) -> Array:
	var out = []
	for i in sk.get_bone_count(): out.append(sk.get_bone_pose(i))
	return out

static func signature(sk: Skeleton3D) -> String:
	var data = []
	for i in sk.get_bone_count(): data.append([sk.get_bone_name(i),sk.get_bone_parent(i),Interop.encode(sk.get_bone_rest(i))])
	return JSON.stringify(Interop.hash_numbers(data)).sha256_text()

static func validate(sk: Skeleton3D, config: Dictionary) -> String:
	if config.get('skeleton_revision','')!=signature(sk): return '骨架修订不匹配'
	if not config.get('layers',[]) is Array or not config.get('equipment',{}) is Dictionary or not config.get('fingers',{}) is Dictionary: return '配置容器无效'
	var protected = []
	for i in sk.get_bone_count():
		var name = str(sk.get_bone_name(i))
		if sk.get_bone_parent(i)<0 or name.to_lower() in ['pelvis','hips'] or name.to_lower().ends_with('hips'): protected.append(name)
	var ids = {}
	for layer in config.get('layers',[]):
		if not layer is Dictionary: return '图层必须为对象'
		if not layer.has('mask'): return '必须明确指定遮罩'
		if not layer.get('mask',[]) is Array or not layer.get('pose',{}) is Dictionary: return '遮罩或姿势无效'
		if not layer.get('id') is String or layer.id.is_empty(): return '必须提供图层 ID'
		if not (layer.get('priority') is float or layer.get('priority') is int) or not is_finite(layer.priority): return '优先级必须为有限数值'
		if ids.has(layer.get('id','')): return '图层 ID 重复'
		ids[layer.get('id','')] = true
		if not (layer.get('weight',1) is float or layer.get('weight',1) is int): return '权重必须为数值'
		if layer.has('full_body') and not layer.full_body is bool: return 'full_body 必须为布尔值'
		if not is_finite(float(layer.get('weight',1))) or float(layer.get('weight',1))<0 or float(layer.get('weight',1))>1: return '图层权重无效'
		var mask = layer.get('mask',[])
		var unique = {}
		for bone in mask:
			if not bone is String: return '遮罩中的骨骼名称必须为字符串'
			unique[bone] = true
		if unique.size()!=mask.size(): return '遮罩中的骨骼重复'
		for bone in mask:
			if not bone is String or sk.find_bone(bone)<0: return '遮罩中包含未知骨骼'
		if layer.get('full_body',false) and (mask.size()!=sk.get_bone_count() or unique.size()!=sk.get_bone_count()): return '全身图层必须覆盖全部骨骼'
		for bone in layer.get('pose',{}):
			if not bone in mask: return '姿势写入超出遮罩范围'
			var a = layer.pose[bone]
			if not a is Array or a.size()!=12: return '姿势变换无效'
			for x in a:
				if not (x is float or x is int) or not is_finite(x): return '姿势包含非有限数值'
			if absf(Interop.decode(a).basis.determinant())<.00001: return '姿势变换不可逆'
		for bone in protected:
			if bone in mask and not layer.get('full_body',false): return '根骨骼和髋部仅可由基础姿势或全身图层控制'
	var equipment = config.get('equipment',{})
	if not (config.get('finger_priority',15) is float or config.get('finger_priority',15) is int) or not is_finite(config.get('finger_priority',15)): return '手指优先级无效'
	if not equipment.is_empty():
		if not (equipment.get('priority',15) is float or equipment.get('priority',15) is int) or not is_finite(equipment.get('priority',15)): return '装备优先级无效'
		if equipment.get('mode','') not in ['animation','main_to_weapon_to_offhand']: return '装备模式无效'
		if equipment.get('dependencies',[])!=[['main_hand','weapon'],['weapon','off_hand']]: return '约束关系必须为“主手 → 武器 → 副手”；不允许循环'
		for key in ['main_hand','off_hand','off_forearm','off_upper_arm']:
			if not equipment.get(key) is String or sk.find_bone(equipment.get(key,''))<0: return '装备使用了未知骨骼'
		var main = sk.find_bone(equipment.main_hand)
		var ancestor = main
		while ancestor>=0:
			if sk.get_bone_name(ancestor) in [equipment.off_hand,equipment.off_forearm,equipment.off_upper_arm]: return '主手依赖副手 IK 链，形成了无效依赖'
			ancestor = sk.get_bone_parent(ancestor)
		var hand = sk.find_bone(equipment.off_hand)
		var fore = sk.find_bone(equipment.off_forearm)
		var upper = sk.find_bone(equipment.off_upper_arm)
		if sk.get_bone_parent(hand)!=fore or sk.get_bone_parent(fore)!=upper: return 'IK 需要连续的手臂骨骼链'
		for key in ['socket','main_grip','off_grip','off_socket']:
			if not equipment.get(key) is Array or equipment[key].size()!=12: return '握持变换无效'
			for x in equipment[key]:
				if not (x is float or x is int) or not is_finite(x): return '握持变换包含非有限数值'
			if absf(Interop.decode(equipment[key]).basis.determinant())<.00001: return '握持变换不可逆'
	for bone in config.get('fingers',{}):
		if not bone is String or sk.find_bone(bone)<0: return '手指骨骼未知'
		var finger = false
		for prefix in ['thumb','index','middle','ring','pinky']:
			if prefix in bone.to_lower(): finger = true
		if not finger or bone in protected: return '手指覆盖必须指定手指骨骼'
		var hand_ancestor = false
		var parent = sk.get_bone_parent(sk.find_bone(bone))
		while parent>=0:
			for family in ['anatomical','ue4','mixamo']:
				if Interop.semantic(str(sk.get_bone_name(parent)),family) in ['hand_l','hand_r']: hand_ancestor = true
			parent = sk.get_bone_parent(parent)
		if not hand_ancestor: return '手指覆盖必须位于已映射手部的后代骨骼上'
		for name in [equipment.get('main_hand',''),equipment.get('off_hand','')]:
			var ancestor = sk.find_bone(name)
			while ancestor>=0:
				if sk.get_bone_name(ancestor)==bone: return '手指覆盖不能修改手部的祖先骨骼'
				ancestor = sk.get_bone_parent(ancestor)
		var q = config.fingers[bone]
		if not q is Array or q.size()!=4: return '手指四元数无效'
		for x in q:
			if not (x is float or x is int) or not is_finite(x): return '手指四元数包含非有限数值'
		if Quaternion(q[0],q[1],q[2],q[3]).length_squared()<.00001: return '手指四元数为零'
	return ''

static func set_global(sk: Skeleton3D, i: int, t: Transform3D):
	var parent = sk.get_bone_parent(i)
	var local = sk.get_bone_global_pose(parent).affine_inverse()*t if parent>=0 else t
	sk.set_bone_pose(i,local)
	sk.force_update_all_bone_transforms()

static func solve_arm(sk: Skeleton3D, upper: int, fore: int, hand: int, target: Transform3D) -> Dictionary:
	# CCD rotates joints only. Segment lengths and translations are preserved.
	var before = sk.get_bone_global_pose(hand).origin.distance_to(target.origin)
	for iteration in 32:
		for joint in [fore,upper]:
			var t = sk.get_bone_global_pose(joint)
			var a = sk.get_bone_global_pose(hand).origin-t.origin
			var b = target.origin-t.origin
			if a.length()<.000001 or b.length()<.000001: continue
			t.basis = Basis(Quaternion(a.normalized(),b.normalized()))*t.basis
			set_global(sk,joint,t)
		if sk.get_bone_global_pose(hand).origin.distance_to(target.origin)<.0001: break
	var result = sk.get_bone_global_pose(hand)
	result.basis = target.basis
	set_global(sk,hand,result)
	return {'before_m':before,'after_m':result.origin.distance_to(target.origin),'orientation_radians':result.basis.get_rotation_quaternion().angle_to(target.basis.get_rotation_quaternion())}

static func evaluate(sk: Skeleton3D, base: Array, config: Dictionary, timestamp: float) -> Dictionary:
	if not is_finite(timestamp): return {'error':'时间戳必须为有限数值'}
	var error = validate(sk,config)
	if error: return {'error':error}
	if base.size()!=sk.get_bone_count(): return {'error':'基础姿势的骨骼数量不匹配'}
	for t in base:
		if not t is Transform3D or not t.is_finite() or absf(t.basis.determinant())<.00001: return {'error':'基础姿势无效'}
	for i in base.size(): sk.set_bone_pose(i,base[i])
	var layers = config.get('layers',[]).duplicate(true)
	layers.sort_custom(func(a,b): return a.priority<b.priority if a.priority!=b.priority else str(a.id)<str(b.id))
	var ownership = {}
	var priorities = {}
	var full_priority = -INF
	for layer in layers:
		if layer.get('full_body',false) and float(layer.get('weight',1))==1: full_priority = maxf(full_priority,layer.priority)
		for bone in layer.mask:
			var i = sk.find_bone(bone)
			# A full-body layer replaces unspecified bones with its base pose.
			var pose = Interop.decode(layer.pose[bone]) if layer.get('pose',{}).has(bone) else base[i]
			sk.set_bone_pose(i,sk.get_bone_pose(i).interpolate_with(pose,float(layer.get('weight',1))))
			ownership[bone] = layer.id
			if float(layer.get('weight',1))>0: priorities[bone] = layer.priority
	sk.force_update_all_bone_transforms()
	var equipment = config.get('equipment',{})
	var weapon = Transform3D.IDENTITY
	var ik = {}
	if not equipment.is_empty():
		weapon = sk.get_bone_global_pose(sk.find_bone(equipment.main_hand))*Interop.decode(equipment.socket)*Interop.decode(equipment.main_grip).affine_inverse()
		var chain_priority = maxf(priorities.get(equipment.off_upper_arm,-INF),maxf(priorities.get(equipment.off_forearm,-INF),priorities.get(equipment.off_hand,-INF)))
		if equipment.mode=='main_to_weapon_to_offhand' and chain_priority<float(equipment.get('priority',15)):
			ik = solve_arm(sk,sk.find_bone(equipment.off_upper_arm),sk.find_bone(equipment.off_forearm),sk.find_bone(equipment.off_hand),weapon*Interop.decode(equipment.off_grip)*Interop.decode(equipment.off_socket).affine_inverse())
	for bone in config.get('fingers',{}):
		if priorities.get(bone,-INF)>=float(config.get('finger_priority',15)): continue
		var a = config.fingers[bone]
		sk.set_bone_pose_rotation(sk.find_bone(bone),Quaternion(a[0],a[1],a[2],a[3]).normalized())
	sk.force_update_all_bone_transforms()
	var globals = []
	for i in sk.get_bone_count(): globals.append(Interop.encode(sk.get_bone_global_pose(i)))
	return {'schema':'ainative.final_body_pose.v1','skeleton_revision':config.skeleton_revision,'timestamp_seconds':timestamp,'space':'skeleton_local_metres','evaluation_order':ORDER,'global_bone_poses':globals,'local_bone_poses':capture(sk),'ownership':ownership,'weapon_transform':weapon,'ik':ik,'face_contract':'post-body head/neck owner must be declared; face blendshapes do not mutate body','cloth_contract':'read final_body_pose, never feed back into body or grips'}
