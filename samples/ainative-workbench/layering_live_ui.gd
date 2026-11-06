extends SceneTree
const I = preload('res://addons/ainative/interop.gd')
func _initialize(): run.call_deferred()
func run():
	var args = OS.get_cmdline_user_args()
	var config = JSON.parse_string(FileAccess.get_file_as_string(args[0]))
	root.size = Vector2i(1400,900)
	var host = load('res://addons/ainative/workbench.gd').new()
	root.add_child(host)
	host.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var panel
	for item in host.find_children('*','VBoxContainer',true,false):
		if item.get_script()==load('res://addons/ainative/layering_panel.gd'): panel = item
	if panel==null: printerr('Layering panel missing from normal workbench'); quit(1); return
	host.python_edit.text = OS.get_environment('AINATIVE_PYTHON')
	await process_frame
	host.mesh_container.stretch = false
	host.viewport.size = Vector2i(1024,1024)
	host.viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	host.get_node('WorkbenchScroll').scroll_vertical = int(panel.position.y)
	panel.config_path.text = args[0]
	panel.load_configuration()
	if not is_instance_valid(panel.built): printerr(panel.message.text); quit(1); return
	var report = {'modes':[],'swaps':[]}
	for mode in 4:
		panel.modes.select(mode)
		panel.set_mode(mode)
		var worst = 0.0
		var first_hand = Quaternion.IDENTITY
		var hand_range = 0.0
		for frame in 60:
			panel.runner.playing = false
			panel.runner.sample(frame/30.0)
			if panel.runner.result.has('error'): printerr(panel.runner.result); quit(1); return
			if not panel.runner.result.ik.is_empty(): worst = maxf(worst,panel.runner.result.ik.after_m)
			var sk = I.skeleton(panel.built)
			var q = sk.get_bone_pose_rotation(sk.find_bone('upperarm_r'))
			if frame==0: first_hand = q
			hand_range = maxf(hand_range,first_hand.angle_to(q))
			await process_frame
		report.modes.append({'mode':mode,'frames':60,'worst_grip_error_m':worst,'upper_arm_rotation_range':hand_range,'ik_active':not panel.runner.result.ik.is_empty()})
		if mode==1 and hand_range<.5: printerr('Sword animation failed'); quit(1); return
		if mode==3 and not panel.runner.result.ik.is_empty(): printerr('Full body did not suppress IK'); quit(1); return
		await RenderingServer.frame_post_draw
		host.viewport.get_texture().get_image().save_png(config.output+'-mode'+str(mode)+'.png')
	panel.modes.select(0)
	panel.set_mode(0)
	for garment in [1,2,1]:
		panel.garment.select(garment)
		panel.swap()
		panel.runner.playing = false
		var garment_worst = 0.0
		for frame in 30:
			panel.runner.sample(frame/30.0)
			if not panel.runner.result.has('error'): garment_worst = maxf(garment_worst,panel.runner.result.ik.after_m)
			await process_frame
		if panel.runner.result.has('error'): printerr(panel.runner.result); quit(1); return
		var metadata = panel.built.get_meta('garment')
		var count = I.skeleton(panel.built).get_bone_count()
		if count!=metadata.shared_bones+metadata.skeleton_extension.bones.size(): printerr('Aux bones accumulated'); quit(1); return
		report.swaps.append({'garment':metadata.garment.id,'bones':count,'frames':30,'grip_error_m':panel.runner.result.ik.after_m,'worst_grip_error_m':garment_worst})
		await process_frame
		await RenderingServer.frame_post_draw
		host.viewport.get_texture().get_image().save_png(config.output+'-garment-'+metadata.garment.id+'.png')
	panel.destination.text = config.output+'.tscn'
	panel.save()
	if not FileAccess.file_exists(panel.destination.text): printerr(panel.message.text); quit(1); return
	var saved_sha = FileAccess.get_sha256(panel.destination.text)
	panel.save()
	report.overwrite_rejected = saved_sha==FileAccess.get_sha256(panel.destination.text)
	var reopened = I.load_scene(panel.destination.text)
	root.add_child(reopened.scene)
	var replay = reopened.scene.get_node('LayeringPlayer')
	replay.sample(.5)
	report.reopened_grip_error_m = replay.result.ik.after_m
	reopened.scene.queue_free()
	var previous = panel.built
	panel.config_path.text = 'res://missing.json'
	panel.load_configuration()
	report.invalid_load_preserves_scene = panel.built==previous
	report.source_unchanged = panel.source_sha==FileAccess.get_sha256(config.scene)
	host.get_node('WorkbenchScroll').scroll_vertical = int(host.get_node('WorkbenchScroll').get_v_scroll_bar().max_value)
	await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(config.output+'-negative-ui.png')
	panel.config_path.text = args[0]
	panel.message.text = 'Ready: running + two-hand weapon + generated shirt; saved and reopened successfully.'
	await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(config.output+'-ui.png')
	FileAccess.open(config.output+'-receipt.json',FileAccess.WRITE).store_string(JSON.stringify(report,'\t'))
	print(JSON.stringify(report))
	if config.get('stay_open',false): panel.runner.playing = true; return
	quit()
