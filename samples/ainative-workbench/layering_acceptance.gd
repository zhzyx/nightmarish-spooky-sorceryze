extends SceneTree
const I = preload('res://addons/ainative/interop.gd')
const M = preload('res://addons/ainative/motion.gd')
const L = preload('res://addons/ainative/layering.gd')
const Player = preload('res://addons/ainative/layering_player.gd')
func _initialize(): run.call_deferred()
func run():
	var args = OS.get_cmdline_user_args()
	var loaded = I.load_scene(args[0])
	root.add_child(loaded.scene)
	var sk = I.skeleton(loaded.scene)
	var p = I.extract(loaded.scene,'ue4',{'sha256':FileAccess.get_sha256(args[0]),'version':'native','authority':'local-native-UE4'})
	if p.has('error'): printerr(p); quit(1); return
	var doc = JSON.parse_string(FileAccess.get_file_as_string(args[1]))
	var motion = M.build(doc,FileAccess.get_sha256(args[1]),true,true)
	var adapted = I.retarget(motion.animation,motion.profile,p.profile,30)
	if adapted.has('error'): printerr(adapted); quit(1); return
	var player = AnimationPlayer.new()
	player.name = 'LayeringSource'
	loaded.scene.add_child(player)
	var lib = AnimationLibrary.new()
	var animation = adapted.animation
	for track in animation.get_track_count(): animation.track_set_path(track,NodePath(str(loaded.scene.get_path_to(sk))+':'+str(animation.track_get_path(track).get_subname(0))))
	lib.add_animation('generated',animation)
	player.add_animation_library('',lib)
	var config = {'skeleton_revision':L.signature(sk),'root_hips':['root','pelvis'],'layers':[],'fingers':{}}
	# Construct an explicit aiming fixture in skeleton space, preserving bone lengths.
	var original_base = L.capture(sk)
	for side in ['r','l']:
		var upper = sk.find_bone('upperarm_'+side)
		var fore = sk.find_bone('lowerarm_'+side)
		var h = sk.find_bone('hand_'+side)
		for pair in [[upper,fore,Vector3(.15 if side=='r' else -.15,-.35,.8)],[fore,h,Vector3(-.25 if side=='r' else .25,.2,.8)]]:
			var t = sk.get_bone_global_pose(pair[0])
			var direction = sk.get_bone_global_pose(pair[1]).origin-t.origin
			t.basis = Basis(Quaternion(direction.normalized(),pair[2].normalized()))*t.basis
			L.set_global(sk,pair[0],t)
	var base = L.capture(sk)
	var pose = {}
	var mask = []
	for meaning in p.profile.mapping:
		if meaning in ['clavicle_l','clavicle_r','upper_arm_l','upper_arm_r','forearm_l','forearm_r','hand_l','hand_r']:
			var idx = int(p.profile.mapping[meaning])
			mask.append(sk.get_bone_name(idx))
			pose[sk.get_bone_name(idx)] = I.encode(base[idx])
	config.layers = [{'id':'aim','priority':10,'weight':1,'mask':mask,'pose':pose}]
	# Author constructed pose/weapon functional fixture. Never claimed AI generated.
	var hand = sk.find_bone('hand_r')
	var off = sk.find_bone('hand_l')
	var main_t = sk.get_bone_global_pose(hand)
	var off_t = sk.get_bone_global_pose(off)
	var main_socket = Transform3D.IDENTITY
	main_socket.origin = main_t.affine_inverse()*sk.get_bone_global_pose(sk.find_bone('middle_01_r')).origin*.7
	var off_socket = Transform3D.IDENTITY
	off_socket.origin = off_t.affine_inverse()*sk.get_bone_global_pose(sk.find_bone('middle_01_l')).origin*.7
	var target = off_t
	target.origin = target.origin.lerp(sk.get_bone_global_pose(sk.find_bone('upperarm_l')).origin,.12)
	config.equipment = {'mode':'main_to_weapon_to_offhand','dependencies':[['main_hand','weapon'],['weapon','off_hand']],'main_hand':'hand_r','off_hand':'hand_l','off_forearm':'lowerarm_l','off_upper_arm':'upperarm_l','socket':I.encode(main_socket),'off_socket':I.encode(off_socket),'main_grip':I.encode(Transform3D.IDENTITY),'off_grip':I.encode((main_t*main_socket).affine_inverse()*target*off_socket)}
	for meaning in p.profile.mapping:
		if meaning.split('_')[0] in ['thumb','index','middle','ring','pinky']:
			var idx = int(p.profile.mapping[meaning])
			var q = base[idx].basis.get_rotation_quaternion()*Quaternion(Vector3.FORWARD,.45)
			config.fingers[sk.get_bone_name(idx)] = [q.x,q.y,q.z,q.w]
	var weapon = Node3D.new()
	weapon.name = 'FunctionalWeaponFixture'
	var mesh = BoxMesh.new()
	mesh.size = Vector3(.04,.04,(main_t*main_socket).origin.distance_to((target*off_socket).origin))
	var grip_delta = (main_t*main_socket).affine_inverse()*(target*off_socket).origin
	var visual = MeshInstance3D.new()
	visual.name = 'GripBar'
	weapon.add_child(visual)
	visual.position = grip_delta*.5
	visual.basis = Basis(Quaternion(Vector3.BACK,grip_delta.normalized()))
	visual.mesh = mesh
	loaded.scene.add_child(weapon)
	var runner = Player.new()
	runner.name = 'LayeringPlayer'
	runner.config = config
	loaded.scene.add_child(runner)
	runner.skeleton_path = runner.get_path_to(sk)
	runner.player_path = runner.get_path_to(player)
	runner.weapon_path = runner.get_path_to(weapon)
	runner.playing = false
	var worst = 0.0
	var before = 0.0
	var main_error = 0.0
	var finger_error = 0.0
	var leg_motion = 0.0
	var leg_first = Quaternion.IDENTITY
	for frame in 120:
		runner.sample(frame/30.0)
		if runner.result.has('error'): printerr(runner.result); quit(1); return
		worst = maxf(worst,runner.result.ik.after_m)
		before = maxf(before,runner.result.ik.before_m)
		main_error = maxf(main_error,(runner.result.weapon_transform*I.decode(config.equipment.main_grip)).origin.distance_to((sk.get_bone_global_pose(hand)*I.decode(config.equipment.socket)).origin))
		for bone in config.fingers:
			var a = config.fingers[bone]
			finger_error = maxf(finger_error,sk.get_bone_pose_rotation(sk.find_bone(bone)).angle_to(Quaternion(a[0],a[1],a[2],a[3])))
		var q = sk.get_bone_pose_rotation(sk.find_bone('thigh_l'))
		if frame==0: leg_first = q
		leg_motion = maxf(leg_motion,leg_first.angle_to(q))
	var checks = {}
	var bad = config.duplicate(true)
	bad.equipment.dependencies.append(['off_hand','main_hand'])
	checks.cycle_rejected = not L.validate(sk,bad).is_empty()
	bad = config.duplicate(true)
	bad.layers[0].mask.append('missing_bone')
	checks.out_of_bounds_rejected = not L.validate(sk,bad).is_empty()
	bad = config.duplicate(true)
	bad.skeleton_revision = 'stale'
	checks.revision_rejected = not L.validate(sk,bad).is_empty()
	bad = config.duplicate(true)
	bad.layers[0].mask.append('pelvis')
	checks.hips_rejected = not L.validate(sk,bad).is_empty()
	var all = []
	for i in sk.get_bone_count(): all.append(sk.get_bone_name(i))
	var full = config.duplicate(true)
	full.equipment = {}
	full.fingers = {}
	full.layers.append({'id':'full','priority':20,'weight':1,'full_body':true,'mask':all,'pose':{}})
	var evaluated = L.evaluate(sk,base,full,0)
	checks.full_body_overrides_upper = evaluated.ownership.hand_r=='full' and sk.get_bone_pose(hand).is_equal_approx(base[hand])
	full.layers[1].priority = 0
	evaluated = L.evaluate(sk,base,full,0)
	checks.upper_overrides_lower_priority_full = evaluated.ownership.hand_r=='aim'
	checks.fingers = config.fingers.size()==30 and finger_error<.002
	checks.main_grip = main_error<.0001
	checks.full_body_suppresses_ik_and_fingers = true
	var protected_full = config.duplicate(true)
	protected_full.layers.append({'id':'full-high','priority':100,'weight':1,'full_body':true,'mask':all,'pose':{}})
	var full_result = L.evaluate(sk,original_base,protected_full,0)
	checks.full_body_suppresses_ik_and_fingers = full_result.ik.is_empty()
	for i in original_base.size(): checks.full_body_suppresses_ik_and_fingers = checks.full_body_suppresses_ik_and_fingers and sk.get_bone_pose(i).is_equal_approx(original_base[i])
	checks.ik = worst<.002 and before>.01
	checks.running_legs_move = leg_motion>.25
	runner.playing = true
	runner.sample(0)
	loaded.scene.set_meta('layering_provenance',{'motion_sha256':FileAccess.get_sha256(args[1]),'avatar_sha256':FileAccess.get_sha256(args[0]),'motion':doc.provenance,'pose_weapon_fingers':'author constructed functional fixtures'})
	M.own(loaded.scene,loaded.scene)
	var output = args[2]
	if FileAccess.file_exists(output): printerr('Destination exists'); quit(2); return
	var packed = PackedScene.new()
	packed.pack(loaded.scene)
	var err = ResourceSaver.save(packed,output)
	checks.saved = err==OK
	var reopened = I.load_scene(output)
	checks.reopened = not reopened.has('error')
	if checks.reopened:
		root.add_child(reopened.scene)
		var replay = reopened.scene.get_node('LayeringPlayer')
		replay.sample(.5)
		checks.reopened_ik = not replay.result.has('error') and replay.result.ik.after_m<.002
	var report = {'checks':checks,'worst_grip_error_m':worst,'before_ik_error_m':before,'leg_rotation_range_radians':leg_motion,'finger_bones':config.fingers.size(),'max_finger_rotation_error_rad':finger_error,'main_grip_error_m':main_error,'frames':120,'source_motion_sha256':FileAccess.get_sha256(args[1]),'asset_sha256':FileAccess.get_sha256(args[0]),'fixture_provenance':'Pose, fingers and box weapon authored functional fixtures; locomotion actual MDM CPU','evaluation_order':L.ORDER}
	FileAccess.open(output+'.json',FileAccess.WRITE).store_string(JSON.stringify(report,'\t'))
	print(JSON.stringify(report))
	for ok in checks.values():
		if not ok: quit(1); return
	motion.scene.free()
	quit()
