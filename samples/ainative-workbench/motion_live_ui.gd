extends SceneTree
const Interop = preload('res://addons/ainative/interop.gd')

func _initialize(): run.call_deferred()

func run():
	var args = OS.get_cmdline_user_args()
	var config = JSON.parse_string(FileAccess.get_file_as_string(args[0]))
	var host = load('res://addons/ainative/workbench.gd').new()
	root.add_child(host)
	host.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	await process_frame
	host.python_edit.text = config.python
	host.host_edit.text = ProjectSettings.globalize_path('res://../../tools/ainative/editor_host.py')
	host.state_dir = config.runtime.path_join('ui-'+str(Time.get_ticks_usec()))
	DirAccess.make_dir_recursive_absolute(host.state_dir)
	var panel
	for node in host.find_children('*','VBoxContainer',true,false):
		if node.get_script()==load('res://addons/ainative/motion_panel.gd'): panel = node
	assert(panel!=null)
	panel.result_path.text = config.motion
	panel.runtime.text = config.runtime
	panel.prompt.text = config.get('prompt','A person walks forward and raises both arms.')
	panel.context.text = config.get('context','')
	panel.video.text = config.get('video','')
	panel.in_place.button_pressed = config.get('in_place',false)
	panel.looping.button_pressed = config.get('loop',false)
	panel.smoothing.value = config.get('smoothing',0)
	panel.edits.text = JSON.stringify(config.get('edits',[]))
	host.preview_token = 'stale-must-clear'
	if config.get('generate',false):
		panel.generate(config.get('mode','text')=='video')
		while panel.thread!=null: await create_timer(.1).timeout
		assert(panel.response.get('code')==0,str(panel.response))
	panel.preview()
	assert(panel.built.has('scene'),panel.message.text)
	assert(host.preview_token=='')
	panel.target_avatar.text = config.avatar
	panel.target_family.select(Interop.FAMILIES.find(config.family))
	panel.fps.value = config.get('fps',30)
	panel.contacts.text = JSON.stringify(config.get('contacts',[]))
	panel.retarget()
	assert(panel.built.scene.has_meta('motion_target_profile'),panel.message.text)
	var player = panel.built.scene.get_node('AnimationPlayer')
	var sk = Interop.skeleton(panel.built.scene)
	player.seek(0,true)
	player.pause()
	panel.frame_pose()
	await process_frame
	await RenderingServer.frame_post_draw
	host.viewport.get_texture().get_image().save_png(config.screenshot.get_basename()+'-time0.png')
	sk.force_update_all_bone_transforms()
	var first = []
	for i in sk.get_bone_count(): first.append(sk.get_bone_global_pose(i).origin)
	player.seek(player.get_animation('generated').length*.5,true)
	player.pause()
	sk.force_update_all_bone_transforms()
	var change = 0.0
	for i in sk.get_bone_count(): change = maxf(change,first[i].distance_to(sk.get_bone_global_pose(i).origin))
	assert(change>.01,'No actual target pose change')
	panel.destination.text = config.output
	panel.save()
	assert(panel.last_publish_code==0,panel.message.text)
	assert(FileAccess.file_exists(config.output),panel.message.text)
	var hash_before = FileAccess.get_sha256(config.output)
	panel.save()
	assert(panel.last_publish_code>0,'Duplicate publication did not explicitly fail')
	var duplicate_code = panel.last_publish_code
	assert(FileAccess.get_sha256(config.output)==hash_before,'Overwrite changed immutable version')
	var saved = Interop.load_scene(config.output)
	assert(saved.has('scene'))
	assert(saved.scene.has_meta('motion_streams'))
	root.add_child(saved.scene)
	var reopened_players = saved.scene.find_children('*','AnimationPlayer',true,false)
	assert(reopened_players.size()==1,'Published AnimationPlayer missing or ambiguous')
	var reopened_player = reopened_players[0]
	assert(reopened_player.has_animation('generated'),'Published generated animation missing')
	var reopened_animation = reopened_player.get_animation('generated')
	assert(reopened_animation.get_track_count()==player.get_animation('generated').get_track_count())
	var reopened_sk = Interop.skeleton(saved.scene)
	for i in reopened_sk.get_bone_count(): assert(reopened_sk.get_bone_pose(i).is_equal_approx(reopened_sk.get_bone_rest(i)),'Published reference pose not rest')
	for track in reopened_animation.get_track_count():
		var path = reopened_animation.track_get_path(track)
		assert(reopened_player.get_node(reopened_player.root_node).get_node_or_null(NodePath(str(path.get_concatenated_names())))==reopened_sk,'Saved track path does not resolve to skeleton')
		assert(reopened_sk.find_bone(str(path.get_subname(0)))>=0,'Saved track bone missing')
	var reopen_error = 0.0
	for time in [0.0,reopened_animation.length*.5]:
		for animation_player in [player,reopened_player]:
			animation_player.play('generated')
			animation_player.seek(time,true)
			animation_player.pause()
		for skeleton in [sk,reopened_sk]: skeleton.force_update_all_bone_transforms()
		for i in sk.get_bone_count():
			var original_pose = sk.get_bone_global_pose(i)
			var saved_pose = reopened_sk.get_bone_global_pose(i)
			reopen_error = maxf(reopen_error,original_pose.origin.distance_to(saved_pose.origin))
			assert(original_pose.is_equal_approx(saved_pose),'Reopened animated transform differs from live pose')
	saved.scene.free()
	await process_frame
	host.get_node('WorkbenchScroll').scroll_vertical = int(panel.position.y)
	panel.frame_pose()
	await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(config.screenshot)
	host.viewport.get_texture().get_image().save_png(config.screenshot.get_basename()+'-preview.png')
	var receipt = {'source_sha256':FileAccess.get_sha256(config.motion),'animation_sha256':hash_before,'target_pose_change_m':change,'target_bones':sk.get_bone_count(),'processing':panel.built.scene.get_meta('motion_processing'),'source_profile':panel.built.profile.revision,'target_profile':panel.built.scene.get_meta('motion_target_profile').revision,'saved':config.output,'screenshot':config.screenshot}
	receipt['retarget'] = panel.built.scene.get_meta('motion_retarget')
	receipt['reopened_tracks'] = reopened_animation.get_track_count()
	receipt['reopened_pose_max_error_m'] = reopen_error
	receipt['duplicate_publication_exit_code'] = duplicate_code
	receipt['generation_button'] = panel.response if config.get('generate',false) else {'triggered':false}
	var file = FileAccess.open(config.receipt,FileAccess.WRITE)
	file.store_string(JSON.stringify(receipt,'  ',true,true))
	file.close()
	print(JSON.stringify(receipt))
	quit()
