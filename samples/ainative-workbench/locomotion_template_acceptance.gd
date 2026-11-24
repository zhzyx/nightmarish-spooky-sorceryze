extends SceneTree
const Templates = preload('res://addons/ainative/locomotion_templates.gd')
var failures: Array = []

func _initialize():
	run.call_deferred()

func check(condition: bool, message: String):
	if not condition: failures.append(message)

func run():
	var args = OS.get_cmdline_user_args()
	check(args.size()>=2,'Usage: template.tscn report.json')
	if not failures.is_empty():
		finish('')
		return
	var output_dir = args[0].get_base_dir()
	var standalone_library = load(output_dir.path_join('ainative_locomotion_library.tres')) as AnimationLibrary
	check(standalone_library!=null,'Standalone AnimationLibrary loads')
	if standalone_library!=null:
		for clip in Templates.CLIPS: check(standalone_library.has_animation(clip),'Library contains '+clip)
	for clip in Templates.CLIPS:
		var standalone = load(output_dir.path_join(clip+'.tres')) as Animation
		check(standalone!=null,'Standalone Animation loads: '+clip)
		if standalone!=null: check(is_equal_approx(standalone.length,Templates.duration_for(clip)),'Standalone duration: '+clip)
	var packed = load(args[0]) as PackedScene
	check(packed!=null,'Template scene loads')
	if packed==null:
		finish(args[1])
		return
	var scene = packed.instantiate()
	root.add_child(scene)
	var sk = scene.get_node_or_null('Skeleton3D') as Skeleton3D
	var player = scene.get_node_or_null('AnimationPlayer') as AnimationPlayer
	check(sk!=null and player!=null,'Skeleton3D and AnimationPlayer exist')
	if sk==null or player==null:
		scene.free()
		finish(args[1])
		return
	check(sk.get_bone_count()==18,'17 anatomical bones plus root')
	check(sk.get_bone_name(17)=='root','Independent root bone')
	for i in Templates.NAMES.size():
		check(sk.get_bone_name(i)==Templates.NAMES[i],'Bone name '+str(i))
		check(sk.get_bone_parent(i)==Templates.PARENTS[i],'Bone parent '+str(i))
	var report = {'schema_version':1,'source_scene':args[0],'bone_count':sk.get_bone_count(),'fps':Templates.FPS,'clips':{},'failures':failures}
	for clip in Templates.CLIPS:
		var animation = player.get_animation(clip)
		check(animation!=null,'Clip exists: '+clip)
		if animation==null: continue
		check(is_equal_approx(animation.length,Templates.duration_for(clip)),'Duration: '+clip)
		check(animation.loop_mode==(Animation.LOOP_NONE if clip=='jump' else Animation.LOOP_LINEAR),'Loop mode: '+clip)
		var samples = int(round(animation.length*Templates.FPS))
		var maximum_target_error = 0.0
		var minimum_clearance = 0.0
		var maximum_motion = 0.0
		var maximum_hip_height = -INF
		var first_origins = []
		var first_rotations = []
		var last_origins = []
		var last_rotations = []
		player.play(clip)
		for sample_index in range(samples+1):
			var time = minf(float(sample_index)/Templates.FPS,animation.length)
			var phase = time/animation.length
			if sample_index==samples: phase = 0.0 if clip!='jump' else 1.0
			player.seek(time,true)
			sk.force_update_all_bone_transforms()
			var expected = Templates.sample_pose(sk,clip,phase)
			for side in ['l','r']:
				var foot = sk.find_bone('foot_'+side)
				var actual = sk.get_bone_global_pose(foot).origin
				var target = expected.feet[side] as Vector3
				var rest = sk.get_bone_global_rest(foot).origin
				maximum_target_error = maxf(maximum_target_error,actual.distance_to(target))
				minimum_clearance = minf(minimum_clearance,actual.y-rest.y)
				maximum_motion = maxf(maximum_motion,actual.distance_to(rest))
				check(actual.is_finite(),'Finite foot pose: '+clip)
			var hip_height = sk.get_bone_global_pose(0).origin.y-sk.get_bone_global_rest(0).origin.y
			maximum_hip_height = maxf(maximum_hip_height,hip_height)
			if sample_index==0 or sample_index==samples:
				var origins = []
				var rotations = []
				for bone in sk.get_bone_count():
					var global_pose = sk.get_bone_global_pose(bone)
					origins.append(global_pose.origin)
					rotations.append(global_pose.basis.orthonormalized().get_rotation_quaternion())
				if sample_index==0:
					first_origins = origins
					first_rotations = rotations
				else:
					last_origins = origins
					last_rotations = rotations
		var seam_position = 0.0
		var seam_rotation = 0.0
		for bone in sk.get_bone_count():
			seam_position = maxf(seam_position,(first_origins[bone] as Vector3).distance_to(last_origins[bone]))
			seam_rotation = maxf(seam_rotation,(first_rotations[bone] as Quaternion).angle_to(last_rotations[bone]))
		check(maximum_target_error<.0002,'IK target accuracy: '+clip)
		check(minimum_clearance>-.0002,'No below-ground ankle: '+clip)
		check(maximum_motion>.05,'Nonempty foot motion: '+clip)
		check(seam_position<.0002 and seam_rotation<.001,'Closed endpoint pose: '+clip)
		if clip=='jump': check(maximum_hip_height>.3,'Jump apex')
		report.clips[clip] = {
			'duration_s':animation.length,
			'samples':samples+1,
			'max_ik_target_error_m':maximum_target_error,
			'min_ankle_clearance_m':minimum_clearance,
			'max_ankle_motion_from_rest_m':maximum_motion,
			'max_hip_height_m':maximum_hip_height,
			'endpoint_position_seam_m':seam_position,
			'endpoint_rotation_seam_rad':seam_rotation,
			'loop_mode':'none' if clip=='jump' else 'linear'
		}
	player.stop()
	sk.reset_bone_poses()
	scene.free()
	finish(args[1],report)

func finish(path: String, report: Dictionary = {}):
	report['failures'] = failures
	report['passed'] = failures.is_empty()
	if not path.is_empty():
		var file = FileAccess.open(path,FileAccess.WRITE)
		file.store_string(JSON.stringify(report,'  ',true,true))
		file.close()
	print('AINATIVE_LOCOMOTION_VALIDATION '+JSON.stringify(report))
	quit(0 if failures.is_empty() else 1)
