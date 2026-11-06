extends SceneTree
# Run only in an isolated project hosted by a never-shown native parent window.
# Captures the normal workbench and its current character with a real GPU driver.
const I = preload('res://addons/ainative/interop.gd')

func _initialize(): run.call_deferred()

func percentile(values: Array, fraction: float) -> float:
	var sorted = values.duplicate()
	sorted.sort()
	return float(sorted[clampi(ceili((sorted.size()-1)*fraction),0,sorted.size()-1)])

func stats(values: Array) -> Dictionary:
	if values.is_empty(): return {}
	return {'p50_ms':percentile(values,.5),'p95_ms':percentile(values,.95),'max_ms':percentile(values,1.0)}

func run():
	var args = OS.get_cmdline_user_args()
	if args.size() != 1 or OS.get_environment('AINATIVE_HIDDEN_RENDER_PARENT') == '': printerr('A private config and hidden native host are required'); quit(2); return
	var config = JSON.parse_string(FileAccess.get_file_as_string(args[0]))
	if not config is Dictionary: printerr('Invalid render config'); quit(2); return
	var output = str(config.output)
	if FileAccess.file_exists(output+'.json'): printerr('Choose a new render receipt'); quit(2); return
	var sha = FileAccess.get_sha256(config.scene)
	if sha == '' or sha != config.sha256: printerr('Frozen scene hash mismatch'); quit(2); return
	if RenderingServer.get_current_rendering_driver_name() == 'dummy' or DisplayServer.get_name() == 'headless': printerr('Real GPU rendering required'); quit(2); return
	var host = load('res://addons/ainative/workbench.gd').new()
	root.add_child(host)
	var panel = host.find_child('CharacterWorkbench',true,false)
	var session = panel.session
	var error = session.reopen(config.scene,{})
	if error: printerr(error); host.free(); quit(1); return
	session.playing = false
	var cloth = session.live.get_node_or_null('ClothSolver')
	if cloth == null: printerr('Full character cloth expected'); host.free(); quit(1); return
	if config.mode not in ['realtime','replay']: printerr('Invalid cloth mode'); host.free(); quit(1); return
	if config.mode == 'replay' and cloth.cache.get('key','') != cloth.expected_key: printerr('Matching cache required'); host.free(); quit(1); return
	cloth.mode = config.mode
	cloth.last_time = -1
	var viewport = panel.viewport
	viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	RenderingServer.viewport_set_measure_render_time(viewport.get_viewport_rid(),true)
	var runner = session.live.get_node('LayeringPlayer')
	var player = runner.get_node(runner.player_path)
	var length = player.get_animation(runner.animation_name).length
	var frames = ceili(length*60)
	if config.has('measure_frames'): frames = clampi(int(config.measure_frames),1,frames)
	var wall = []
	var pipeline = []
	var gpu = []
	var render_cpu = []
	var deepest = {'time_seconds':0.0,'knee_angle_rad':PI,'hip_y':0.0}
	var sk = I.skeleton(session.live)
	var hips = int(cloth.profile.mapping.hips)
	var thigh = int(cloth.profile.mapping.thigh_l)
	var knee = int(cloth.profile.mapping.shin_l)
	var ankle = int(cloth.profile.mapping.foot_l)
	for frame in 20:
		session.clock_seconds = frame/60.0
		session.evaluate(1.0/60)
		await process_frame
		await RenderingServer.frame_post_draw
	for frame in frames:
		var start = Time.get_ticks_usec()
		session.clock_seconds = frame/60.0
		session.evaluate(1.0/60)
		if runner.result.has('error') or cloth.result.has('error'): printerr('Full character evaluation failed'); host.free(); quit(1); return
		pipeline.append(session.frame_usec/1000.0)
		var y = sk.get_bone_global_pose(hips).origin.y
		var knee_position = sk.get_bone_global_pose(knee).origin
		var a = sk.get_bone_global_pose(thigh).origin-knee_position
		var b = sk.get_bone_global_pose(ankle).origin-knee_position
		var knee_angle = a.angle_to(b)
		if knee_angle < deepest.knee_angle_rad: deepest = {'time_seconds':frame/60.0,'knee_angle_rad':knee_angle,'hip_y':y}
		await process_frame
		await RenderingServer.frame_post_draw
		wall.append((Time.get_ticks_usec()-start)/1000.0)
		gpu.append(RenderingServer.viewport_get_measured_render_time_gpu(viewport.get_viewport_rid()))
		render_cpu.append(RenderingServer.viewport_get_measured_render_time_cpu(viewport.get_viewport_rid()))
	# Multiview capture uses this same character at a measured deep-squat sample.
	var capture_time = float(config.get('capture_time',deepest.time_seconds))
	session.clock_seconds = capture_time
	session.evaluate(0.0)
	var camera = viewport.find_children('*','Camera3D',true,false)[0]
	var camera_stage = camera.get_parent()
	var fill = OmniLight3D.new()
	fill.light_energy = 1.5
	fill.omni_range = 10
	camera_stage.add_child(fill)
	var views = []
	for view in [['front',Vector3(0,1.3,3.0)],['side',Vector3(3.0,1.3,0)],['back',Vector3(0,1.3,-3.0)]]:
		camera.position = view[1]
		camera.look_at(Vector3(0,.9,0))
		fill.position = camera.position
		await process_frame
		await RenderingServer.frame_post_draw
		var picture = viewport.get_texture().get_image()
		if picture.is_empty() or picture.save_png(output+'-'+view[0]+'.png') != OK: printerr('GPU capture failed'); host.free(); quit(1); return
		views.append(view[0])
	var report = {'schema_version':1,'source_scene_sha256':sha,'display':DisplayServer.get_name(),'driver':RenderingServer.get_current_rendering_driver_name(),'adapter':RenderingServer.get_video_adapter_name(),'renderer':RenderingServer.get_current_rendering_method(),'mode':config.mode,'warmup_frames':20,'frames':frames,'pose_sample_hz':60,'viewport_size':[viewport.size.x,viewport.size.y],'frame_wall':stats(wall),'character_cpu':stats(pipeline),'viewport_gpu':stats(gpu),'viewport_render_cpu':stats(render_cpu),'gpu_timer_available':percentile(gpu,1.0)>0,'deepest_pose':deepest,'views':views,'scope':'Normal workbench UI plus one complete shared character; CPU body/layers/IK/face/cloth/hair and real GPU rendering. Wall time spans evaluate through frame_post_draw, with asynchronous GPU submission, vsync disabled. Image readback occurs after timing. Hidden parent visibility/foreground evidence comes from the native launcher.','limits':'Specific machine, assets, renderer and resolution; no general 60fps guarantee. Zero GPU timer values mean unavailable, not zero GPU cost.'}
	report['capture_time_seconds'] = capture_time
	if FileAccess.get_sha256(config.scene) != sha: printerr('Source changed during render'); host.free(); quit(1); return
	FileAccess.open(output+'.json',FileAccess.WRITE).store_string(JSON.stringify(report,'  ',true,true))
	print(JSON.stringify(report))
	host.free()
	quit()
