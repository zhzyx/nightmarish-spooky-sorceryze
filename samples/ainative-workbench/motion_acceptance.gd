extends SceneTree
const Motion = preload('res://addons/ainative/motion.gd')
const Interop = preload('res://addons/ainative/interop.gd')

func _initialize():
	call_deferred('run')

func run():
	var args = OS.get_cmdline_user_args()
	if args.size()<2: push_error('motion JSON and destination required'); quit(2); return
	var doc = JSON.parse_string(FileAccess.get_file_as_string(args[0]))
	var result = Motion.build(doc,FileAccess.get_sha256(args[0]))
	if result.has('error'): push_error(result.error); quit(1); return
	root.add_child(result.scene)
	var player = result.scene.get_node('AnimationPlayer')
	player.play('generated')
	player.seek(result.animation.length*.5,true)
	var sk = Interop.skeleton(result.scene)
	var sample = sk.get_bone_pose_rotation(16)
	assert(sample.is_finite())
	var output = {'profile_revision':result.profile.revision,'frames':doc.streams.body.frames.size(),'duration':result.animation.length,'tracks':result.animation.get_track_count(),'processing':result.scene.get_meta('motion_processing')}
	if args.size()>2:
		var target_scene = Interop.load_scene(args[2])
		if target_scene.has('error'): push_error(target_scene.error); quit(1); return
		root.add_child(target_scene.scene)
		var extracted = Interop.extract(target_scene.scene,args[3],{'sha256':FileAccess.get_sha256(args[2]),'version':FileAccess.get_sha256(args[2]),'authority':'artifact:validated-147-avatar'})
		if extracted.has('error'): push_error(extracted.error); quit(1); return
		var target = extracted.profile
		var adapted = Interop.retarget(result.animation,result.profile,target,30)
		if adapted.has('error'): push_error(adapted.error); quit(1); return
		output['retarget_tracks'] = adapted.animation.get_track_count()
		output['target_revision'] = target.revision
		var target_player = AnimationPlayer.new()
		target_player.name = 'MotionPlayer'
		target_scene.scene.add_child(target_player)
		var library = AnimationLibrary.new()
		var skeleton_path = str(target_scene.scene.get_path_to(Interop.skeleton(target_scene.scene)))
		for track in adapted.animation.get_track_count():
			var path = adapted.animation.track_get_path(track)
			adapted.animation.track_set_path(track,NodePath(skeleton_path+':'+str(path.get_subname(0))))
		library.add_animation('generated',adapted.animation)
		target_player.add_animation_library('',library)
		target_player.play('generated')
		target_player.seek(adapted.animation.length*.5,true)
		var target_error = Motion.stage(target_scene.scene,args[1].get_basename()+'-target.tscn')
		if target_error: push_error(target_error); quit(1); return
		target_scene.scene.queue_free()
	var error = Motion.stage(result.scene,args[1])
	if error: push_error(error); quit(1); return
	print(JSON.stringify(output))
	result.scene.queue_free()
	quit()
