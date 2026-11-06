extends SceneTree
# Real workbench replay with supplied private reference assets; no inference.
const Interop = preload('res://addons/ainative/interop.gd')
var failures = []

func check(ok: bool, label: String):
	print(('PASS ' if ok else 'FAIL ') + label)
	if not ok: failures.append(label)

func _initialize(): run.call_deferred()

func run():
	var args = OS.get_cmdline_user_args()
	if args.size() != 1: printerr('Expected private UI configuration JSON'); quit(2); return
	var config = JSON.parse_string(FileAccess.get_file_as_string(args[0]).trim_prefix('\ufeff'))
	if not config is Dictionary: quit(2); return
	for path in [config.screenshot, config.receipt]:
		if FileAccess.file_exists(path): printerr('Choose new evidence destinations'); quit(2); return
	var host = load('res://addons/ainative/workbench.gd').new()
	root.add_child(host)
	host.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	await process_frame
	host.python_edit.text = OS.get_environment('AINATIVE_PYTHON')
	host.host_edit.text = ProjectSettings.globalize_path('res://../../tools/ainative/editor_host.py')
	host.state_dir = ProjectSettings.globalize_path('user://interop-ui-' + str(Time.get_ticks_usec()))
	DirAccess.make_dir_recursive_absolute(host.state_dir)
	var panel
	for node in host.find_children('*','VBoxContainer',true,false):
		if node.get_script() == load('res://addons/ainative/interop_panel.gd'): panel = node
	if panel == null: printerr('Interop panel missing'); quit(1); return
	panel.source_path.text = config.source_path
	panel.reference_path.text = config.reference_path
	panel.source_family.select(Interop.FAMILIES.find(config.source_family))
	panel.target_family.select(Interop.FAMILIES.find(config.target_family))
	panel.authority.text = config.authority
	panel.version.text = config.version
	panel.contacts.text = JSON.stringify(config.get('contacts',{}))
	var before = {config.source_path:FileAccess.get_sha256(config.source_path), config.reference_path:FileAccess.get_sha256(config.reference_path)}
	panel.preview_target()
	check(not panel.profile.is_empty(), 'actual reference extracted through workbench')
	if panel.profile.is_empty(): printerr(panel.message.text); quit(1); return
	var target_revision = panel.profile.revision
	panel.destination.text = host.state_dir.path_join('reference.profile.json')
	panel.save()
	check(FileAccess.file_exists(panel.destination.text),'profile published through panel')
	var saved_profile = JSON.parse_string(FileAccess.get_file_as_string(panel.destination.text))
	check(saved_profile is Dictionary and Interop.validate(saved_profile) == '' and saved_profile.revision == target_revision, 'saved profile retains exact reference revision')
	# Use the actual saved Profile on the next operation, rather than a transient reference.
	panel.reference_path.text = panel.destination.text
	panel.build()
	check(is_instance_valid(panel.built) and panel.built.has_meta('interop'),'actual panel adapts and binds model')
	if not is_instance_valid(panel.built) or not panel.built.has_meta('interop'): printerr(panel.message.text); quit(1); return
	check(host.preview_token.is_empty(),'derived avatar cannot reuse generation approval')
	var sk = Interop.skeleton(panel.built)
	check(sk.get_bone_count() == saved_profile.bones.size(),'full target hierarchy bound')
	var player = panel.built.get_node('AnimationPlayer')
	check(player.has_animation('squat'),'retargeted squat available in workbench')
	for i in panel.motions.item_count:
		if panel.motions.get_item_text(i) == 'squat': panel.motions.select(i)
	panel.play()
	player.seek(0.0,true)
	sk.force_update_all_bone_transforms()
	var initial_pose = []
	for i in sk.get_bone_count(): initial_pose.append(sk.get_bone_global_pose(i))
	player.seek(1.0,true)
	player.pause()
	sk.force_update_all_bone_transforms()
	var pose_motion = 0.0
	for i in sk.get_bone_count(): pose_motion = maxf(pose_motion,sk.get_bone_global_pose(i).origin.distance_to(initial_pose[i].origin))
	check(pose_motion > .01,'actual retargeted animation moves between two sampled times')
	var outputs = {}
	for suffix in ['tscn','glb']:
		panel.destination.text = host.state_dir.path_join('avatar.' + suffix)
		panel.save()
		check(FileAccess.file_exists(panel.destination.text),'workbench publishes ' + suffix)
		if not FileAccess.file_exists(panel.destination.text): printerr(panel.message.text); continue
		var saved_hash = FileAccess.get_sha256(panel.destination.text)
		panel.save()
		check(FileAccess.get_sha256(panel.destination.text) == saved_hash,'repeat publication preserves ' + suffix)
		var loaded = Interop.load_scene(panel.destination.text)
		check(not loaded.has('error'),'published ' + suffix + ' reopens')
		if loaded.has('scene'):
			var reopened = Interop.skeleton(loaded.scene)
			check(reopened != null and reopened.get_bone_count() == sk.get_bone_count(),'reopened ' + suffix + ' retains full hierarchy')
			if reopened:
				for i in reopened.get_bone_count(): check(reopened.get_bone_pose(i).is_equal_approx(reopened.get_bone_rest(i)),suffix + ' reference pose ' + str(i))
			loaded.scene.free()
		outputs[suffix] = {'path':panel.destination.text,'sha256':saved_hash}
	for path in before: check(FileAccess.get_sha256(path) == before[path],'input bytes preserved: ' + path.get_file())
	# Capture the visible preview after a real UI play operation.
	panel.play()
	player.advance(1.0)
	player.pause()
	await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(config.screenshot)
	var result = {'failures':failures,'inputs':before,'target_revision':target_revision,'outputs':outputs,'target_bones':sk.get_bone_count(),'pose_motion_m':pose_motion}
	var file = FileAccess.open(config.receipt,FileAccess.WRITE)
	file.store_string(JSON.stringify(result,'  ',true,true))
	file.close()
	print('AINATIVE_INTEROP_UI failures=' + str(failures.size()))
	quit(0 if failures.is_empty() else 1)
