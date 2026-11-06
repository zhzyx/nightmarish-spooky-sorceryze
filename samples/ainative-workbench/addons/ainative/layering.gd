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
	if config.get('skeleton_revision','')!=signature(sk): return 'Skeleton revision mismatch'
	if not config.get('layers',[]) is Array or not config.get('equipment',{}) is Dictionary or not config.get('fingers',{}) is Dictionary: return 'Invalid configuration containers'
	var protected = []
	for i in sk.get_bone_count():
		var name = str(sk.get_bone_name(i))
		if sk.get_bone_parent(i)<0 or name.to_lower() in ['pelvis','hips'] or name.to_lower().ends_with('hips'): protected.append(name)
	var ids = {}
	for layer in config.get('layers',[]):
		if not layer is Dictionary: return 'Layer must be object'
		if not layer.has('mask'): return 'Explicit mask required'
		if not layer.get('mask',[]) is Array or not layer.get('pose',{}) is Dictionary: return 'Invalid mask or pose'
		if not layer.get('id') is String or layer.id.is_empty(): return 'Layer id required'
		if not (layer.get('priority') is float or layer.get('priority') is int) or not is_finite(layer.priority): return 'Finite priority required'
		if ids.has(layer.get('id','')): return 'Duplicate layer id'
		ids[layer.get('id','')] = true
		if not (layer.get('weight',1) is float or layer.get('weight',1) is int): return 'Numeric weight required'
		if layer.has('full_body') and not layer.full_body is bool: return 'Boolean full_body required'
		if not is_finite(float(layer.get('weight',1))) or float(layer.get('weight',1))<0 or float(layer.get('weight',1))>1: return 'Invalid layer weight'
		var mask = layer.get('mask',[])
		var unique = {}
		for bone in mask:
			if not bone is String: return 'Mask bone must be string'
			unique[bone] = true
		if unique.size()!=mask.size(): return 'Duplicate mask bone'
		for bone in mask:
			if not bone is String or sk.find_bone(bone)<0: return 'Unknown mask bone'
		if layer.get('full_body',false) and (mask.size()!=sk.get_bone_count() or unique.size()!=sk.get_bone_count()): return 'Full body must cover every bone'
		for bone in layer.get('pose',{}):
			if not bone in mask: return 'Pose writes outside mask'
			var a = layer.pose[bone]
			if not a is Array or a.size()!=12: return 'Invalid pose transform'
			for x in a:
				if not (x is float or x is int) or not is_finite(x): return 'Nonfinite pose'
			if absf(Interop.decode(a).basis.determinant())<.00001: return 'Singular pose'
		for bone in protected:
			if bone in mask and not layer.get('full_body',false): return 'Root and hips belong to base/full-body only'
	var equipment = config.get('equipment',{})
	if not (config.get('finger_priority',15) is float or config.get('finger_priority',15) is int) or not is_finite(config.get('finger_priority',15)): return 'Invalid finger priority'
	if not equipment.is_empty():
		if not (equipment.get('priority',15) is float or equipment.get('priority',15) is int) or not is_finite(equipment.get('priority',15)): return 'Invalid equipment priority'
		if equipment.get('mode','') not in ['animation','main_to_weapon_to_offhand']: return 'Invalid equipment mode'
		if equipment.get('dependencies',[])!=[['main_hand','weapon'],['weapon','off_hand']]: return 'Constraint graph must be main_hand -> weapon -> off_hand; cycle rejected'
		for key in ['main_hand','off_hand','off_forearm','off_upper_arm']:
			if not equipment.get(key) is String or sk.find_bone(equipment.get(key,''))<0: return 'Unknown equipment bone'
		var main = sk.find_bone(equipment.main_hand)
		var ancestor = main
		while ancestor>=0:
			if sk.get_bone_name(ancestor) in [equipment.off_hand,equipment.off_forearm,equipment.off_upper_arm]: return 'Main hand depends on offhand IK chain'
			ancestor = sk.get_bone_parent(ancestor)
		var hand = sk.find_bone(equipment.off_hand)
		var fore = sk.find_bone(equipment.off_forearm)
		var upper = sk.find_bone(equipment.off_upper_arm)
		if sk.get_bone_parent(hand)!=fore or sk.get_bone_parent(fore)!=upper: return 'IK requires contiguous arm chain'
		for key in ['socket','main_grip','off_grip','off_socket']:
			if not equipment.get(key) is Array or equipment[key].size()!=12: return 'Invalid grip transform'
			for x in equipment[key]:
				if not (x is float or x is int) or not is_finite(x): return 'Nonfinite grip'
			if absf(Interop.decode(equipment[key]).basis.determinant())<.00001: return 'Singular grip'
	for bone in config.get('fingers',{}):
		if not bone is String or sk.find_bone(bone)<0: return 'Unknown finger bone'
		var finger = false
		for prefix in ['thumb','index','middle','ring','pinky']:
			if prefix in bone.to_lower(): finger = true
		if not finger or bone in protected: return 'Finger override requires a finger bone'
		var hand_ancestor = false
		var parent = sk.get_bone_parent(sk.find_bone(bone))
		while parent>=0:
			for family in ['anatomical','ue4','mixamo']:
				if Interop.semantic(str(sk.get_bone_name(parent)),family) in ['hand_l','hand_r']: hand_ancestor = true
			parent = sk.get_bone_parent(parent)
		if not hand_ancestor: return 'Finger override must descend from a mapped hand'
		for name in [equipment.get('main_hand',''),equipment.get('off_hand','')]:
			var ancestor = sk.find_bone(name)
			while ancestor>=0:
				if sk.get_bone_name(ancestor)==bone: return 'Finger override cannot change a hand ancestor'
				ancestor = sk.get_bone_parent(ancestor)
		var q = config.fingers[bone]
		if not q is Array or q.size()!=4: return 'Invalid finger quaternion'
		for x in q:
			if not (x is float or x is int) or not is_finite(x): return 'Nonfinite finger quaternion'
		if Quaternion(q[0],q[1],q[2],q[3]).length_squared()<.00001: return 'Zero finger quaternion'
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
	if not is_finite(timestamp): return {'error':'Finite timestamp required'}
	var error = validate(sk,config)
	if error: return {'error':error}
	if base.size()!=sk.get_bone_count(): return {'error':'Base pose bone count mismatch'}
	for t in base:
		if not t is Transform3D or not t.is_finite() or absf(t.basis.determinant())<.00001: return {'error':'Invalid base pose'}
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
