extends SceneTree
func _initialize(): run.call_deferred()
func run():
	var args = OS.get_cmdline_user_args()
	var config = JSON.parse_string(FileAccess.get_file_as_string(args[0]))
	root.size = Vector2i(1400,900)
	var host = load('res://addons/ainative/workbench.gd').new(); root.add_child(host)
	if OS.has_environment('AINATIVE_PYTHON'): host.python_edit.text = OS.get_environment('AINATIVE_PYTHON')
	host.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	await process_frame
	var panel = host.find_child('ClothPanel',true,false)
	if panel==null: printerr('Missing normal workbench cloth hook'); quit(1); return
	host.mesh_container.stretch = false; host.viewport.size = Vector2i(1024,1024); host.viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	panel.configuration.text = args[0]; panel.build()
	if not is_instance_valid(panel.built): printerr(panel.message.text); quit(1); return
	panel.runner.playing = false
	host.get_node('WorkbenchScroll').scroll_vertical = int(panel.position.y)
	var player = panel.runner.get_node(panel.runner.player_path)
	var cycle_frames = ceili(player.get_animation(panel.runner.animation_name).length*60)
	for frame in config.get('frames',cycle_frames*2):
		panel.runner.sample(frame/60.0)
		if panel.cloth.result.has('error'): printerr(panel.cloth.result); quit(1); return
		await process_frame
		if frame in [0,59,119,179]:
			await RenderingServer.frame_post_draw
			host.viewport.get_texture().get_image().save_png(config.output+'-frame'+str(frame)+'.png')
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(config.output+'-ui.png')
	var metrics = {}
	for key in ['solver_us','render_upload_us','total_us']:
		var values = []
		for sample in panel.cloth.samples: values.append(sample[key])
		values.sort(); metrics[key] = {'p50':values[values.size()/2],'p95':values[mini(values.size()-1,int(values.size()*.95))]}
	var report = {'metrics':metrics,'frames':panel.cloth.samples.size(),'last':panel.cloth.result,'cpu':OS.get_processor_name(),'gpu':RenderingServer.get_video_adapter_name(),'engine':Engine.get_version_info(),'normal_workbench_panel_found':true}
	if config.get('full_ui_checks',false):
		var previous = panel.built
		panel.settings_edit.text = '{"mass":-1,"compliance":0,"pin_weight":1,"lod":0}'
		panel.apply_settings(); report.invalid_settings_rejected = panel.cloth.settings.mass>0 and panel.built==previous
		panel.settings_edit.text = JSON.stringify(panel.cloth.settings)
		await panel.change_mode(1); panel.runner.playing = false
		report.baked_frames = panel.cloth.cache.frames.size()
		panel.runner.sample(.5)
		var expected_render = panel.cloth.rendered.duplicate()
		panel.destination.text = config.output+'-ui-saved.tscn'; panel.save()
		if not FileAccess.file_exists(panel.destination.text): printerr(panel.message.text); quit(1); return
		var digest = FileAccess.get_sha256(panel.destination.text); panel.save()
		report.overwrite_rejected = FileAccess.get_sha256(panel.destination.text)==digest and panel.message.text.begins_with('Choose new .tscn')
		var reopen_config = config.duplicate(true); reopen_config.scene = panel.destination.text
		var reopen_path = config.output+'-reopen.json'
		FileAccess.open(reopen_path,FileAccess.WRITE).store_string(JSON.stringify(reopen_config))
		panel.configuration.text = reopen_path; panel.build(); panel.runner.playing = false; panel.runner.sample(.5)
		report.reopened_cache = not panel.cloth.result.has('error') and panel.cloth.cache.frames.size()==cycle_frames
		var reopen_error = 0.0
		for i in expected_render.size(): reopen_error = maxf(reopen_error,expected_render[i].distance_to(panel.cloth.rendered[i]))
		report.reopened_render_max_error_m = reopen_error
		report.reopened_cache = report.reopened_cache and reopen_error<.00001
		previous = panel.built; panel.configuration.text = 'res://missing-cloth-config.json'; panel.build()
		report.failure_preserves_previous = panel.built==previous
		panel.configuration.text = reopen_path
		panel.message.text = 'Cloth baked, saved and reopened. Invalid input and overwrite rejected.'
		await process_frame; await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png(config.output+'-verified-ui.png')
		for key in ['invalid_settings_rejected','overwrite_rejected','reopened_cache','failure_preserves_previous']:
			if not report[key]: printerr('FAIL '+key); quit(1); return
	FileAccess.open(config.output+'-metrics.json',FileAccess.WRITE).store_string(JSON.stringify(report,'\t'))
	print(JSON.stringify(metrics))
	quit()
