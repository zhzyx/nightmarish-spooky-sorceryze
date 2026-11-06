extends SceneTree
const S = preload('res://addons/ainative/character_session.gd')
const Export = preload('res://addons/ainative/character_export.gd')
func _initialize(): run.call_deferred()
func run():
	var args = OS.get_cmdline_user_args()
	var stage = Node3D.new()
	root.add_child(stage)
	var session = S.new()
	session.stage = stage
	root.add_child(session)
	assert(session.reopen(args[0],{}).is_empty())
	var sha = FileAccess.get_sha256(args[0])
	var binding = session.live.get_meta('face_binding')
	var source = S.I.extract(session.live,'anatomical',{'sha256':sha,'version':'target-readback','authority':'local-authorized'},binding.body_mapping)
	assert(not source.has('error'))
	var runner = session.live.get_node('LayeringPlayer')
	var player = runner.get_node(runner.player_path)
	var baked = session.bake_body(player.get_animation(runner.animation_name).length)
	assert(not baked.has('error'))
	baked.animation.set_meta('character_publication_sha256',sha)
	var target = S.read_object(args[1])
	var projected = Export.project(args[0],sha,source.profile,target,baked.animation)
	assert(not projected.has('error'))
	var loaded = S.I.load_scene(args[2])
	assert(not loaded.has('error'))
	var expected = projected.scene
	var actual = loaded.scene
	stage.add_child(expected)
	stage.add_child(actual)
	var sk = S.I.skeleton(actual)
	var reference = S.I.skeleton(expected)
	assert(sk.get_bone_count()==target.bones.size())
	var rest_error = 0.0
	for bone in target.bones:
		var index = sk.find_bone(bone.name)
		assert(index>=0)
		var parent = sk.get_bone_parent(index)
		assert((str(sk.get_bone_name(parent)) if parent>=0 else '')==(target.bones[int(bone.parent)].name if int(bone.parent)>=0 else ''))
		var rest = S.I.decode(bone.global_rest)
		rest_error = maxf(rest_error,rest.origin.distance_to(sk.get_bone_global_rest(index).origin))
		assert(rest.basis.is_equal_approx(sk.get_bone_global_rest(index).basis))
	assert(rest_error<.0001)
	var vertices = 0
	var reconstruction_error = 0.0
	var weight_sum_error = 0.0
	for mesh in actual.find_children('*','MeshInstance3D',true,false):
		if mesh.skin==null: continue
		assert(mesh.get_node(mesh.skeleton)==sk)
		for surface in mesh.mesh.get_surface_count():
			var arrays = mesh.mesh.surface_get_arrays(surface)
			var stride = arrays[Mesh.ARRAY_WEIGHTS].size()/arrays[Mesh.ARRAY_VERTEX].size()
			assert(stride in [4,8])
			for vertex in arrays[Mesh.ARRAY_VERTEX].size():
				var point = arrays[Mesh.ARRAY_VERTEX][vertex]
				var reconstructed = Vector3.ZERO
				var total = 0.0
				for influence in int(stride):
					var offset = vertex*int(stride)+influence
					var weight = arrays[Mesh.ARRAY_WEIGHTS][offset]
					assert(is_finite(weight) and weight>=0)
					if weight==0: continue
					var bind = arrays[Mesh.ARRAY_BONES][offset]
					assert(bind>=0 and bind<mesh.skin.get_bind_count())
					var bone = mesh.skin.get_bind_bone(bind)
					if mesh.skin.get_bind_name(bind)!='': bone = sk.find_bone(mesh.skin.get_bind_name(bind))
					assert(bone>=0 and bone<sk.get_bone_count())
					reconstructed += sk.get_bone_global_rest(bone)*mesh.skin.get_bind_pose(bind)*point*weight
					total += weight
				weight_sum_error = maxf(weight_sum_error,absf(total-1.0))
				reconstruction_error = maxf(reconstruction_error,point.distance_to(reconstructed))
				vertices += 1
	assert(vertices>0 and reconstruction_error<.001 and weight_sum_error<.001)
	var expected_player = expected.find_children('*','AnimationPlayer',true,false)[0]
	var actual_player = actual.find_children('*','AnimationPlayer',true,false)[0]
	assert(actual_player.has_animation('final_body'))
	var duration = expected_player.get_animation('final_body').length
	assert(absf(actual_player.get_animation('final_body').length-duration)<.0001)
	var position_error = 0.0
	var rotation_error = 0.0
	var motion_span = 0.0
	var initial = []
	for sample in 31:
		var time = duration*sample/30.0
		expected_player.play('final_body')
		expected_player.seek(time,true)
		actual_player.play('final_body')
		actual_player.seek(time,true)
		reference.force_update_all_bone_transforms()
		sk.force_update_all_bone_transforms()
		for index in sk.get_bone_count():
			var pose = sk.get_bone_global_pose(index)
			var wanted = reference.get_bone_global_pose(reference.find_bone(sk.get_bone_name(index)))
			assert(pose.origin.is_finite())
			position_error = maxf(position_error,pose.origin.distance_to(wanted.origin))
			rotation_error = maxf(rotation_error,pose.basis.get_rotation_quaternion().angle_to(wanted.basis.get_rotation_quaternion()))
			if sample==0: initial.append(pose.origin)
			else: motion_span = maxf(motion_span,pose.origin.distance_to(initial[index]))
	assert(position_error<.002 and rotation_error<.002 and motion_span>.01)
	var report = {'publication_sha256':sha,'artifact_sha256':FileAccess.get_sha256(args[2]),'target_family':target.family,'bones':sk.get_bone_count(),'vertices_checked':vertices,'max_rest_error_m':rest_error,'max_skin_rest_reconstruction_error_m':reconstruction_error,'max_weight_sum_error':weight_sum_error,'animation_samples':31,'animation_position_error_m':position_error,'animation_rotation_error_rad':rotation_error,'actual_bone_motion_span_m':motion_span,'scope':'Full target hierarchy/rest axes, all exported Skin vertices and 31 animation samples; excludes explicitly unexported runtime geometry'}
	var output = FileAccess.open(args[3],FileAccess.WRITE)
	output.store_string(JSON.stringify(report,'\t'))
	print(JSON.stringify(report))
	stage.free()
	session.free()
	quit()
