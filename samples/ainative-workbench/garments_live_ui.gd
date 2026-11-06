extends SceneTree
# Actual workbench controls and rendered source/assembly views; inference is external.
const Interop = preload('res://addons/ainative/interop.gd')
const Acceptance = preload('res://garments_acceptance.gd')
func _initialize(): run.call_deferred()
func run():
	var args = OS.get_cmdline_user_args()
	if args.size()!=1: printerr('Expected private UI JSON'); quit(2); return
	var config = JSON.parse_string(FileAccess.get_file_as_string(args[0]).trim_prefix('\ufeff'))
	if not config is Dictionary or FileAccess.file_exists(config.receipt): quit(2); return
	if config.has('workbench_screenshot'): root.size = Vector2i(1280,800)
	var host = load('res://addons/ainative/workbench.gd').new()
	root.add_child(host)
	host.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	await process_frame
	host.mesh_container.stretch = false
	host.viewport.size = Vector2i(1024,1024)
	var panel
	for item in host.find_children('*','VBoxContainer',true,false):
		if item.get_script()==load('res://addons/ainative/garments_panel.gd'): panel = item
	if panel==null: printerr('Garment UI missing'); quit(1); return
	panel.config_path.text = config.wardrobe
	panel.load_wardrobe()
	var config_before = panel.config.duplicate(true)
	var target_count_before = panel.targets.item_count
	var garment_count_before = panel.garments.item_count
	if config.get('regression_checks',false):
		var invalid_path = config.receipt+'.invalid.json'
		if FileAccess.file_exists(invalid_path): quit(2); return
		var invalid_file = FileAccess.open(invalid_path,FileAccess.WRITE)
		invalid_file.store_string('{"targets":[{}],"garments":[]}')
		invalid_file.close()
		panel.config_path.text = invalid_path
		panel.load_wardrobe()
		if panel.config!=config_before or panel.targets.item_count!=target_count_before or panel.garments.item_count!=garment_count_before: printerr('Invalid wardrobe replaced valid UI state'); quit(1); return
		panel.config_path.text = config.wardrobe
	if not config.get('source_only',false): panel.targets.select(config.get('target_index',0))
	panel.garments.select(config.get('garment_index',0))
	panel.shape.text = JSON.stringify(config.get('shape',{}))
	var source = panel.config.garments[panel.garments.selected]
	var before = FileAccess.get_sha256(source.path)
	if config.get('source_only',false):
		var doc = GLTFDocument.new()
		var state = GLTFState.new()
		if doc.append_from_file(source.path,state)!=OK: quit(1); return
		var imported = doc.generate_scene(state)
		if config.get('double_sided_diagnostic',false):
			for mi in imported.find_children('*','MeshInstance3D',true,false):
				var material = StandardMaterial3D.new()
				material.cull_mode = BaseMaterial3D.CULL_DISABLED
				mi.material_override = material
		host.preview_root.add_child(imported)
		host.preview_scene = imported
		host.mesh_container.show()
		host.frame_mesh()
	else:
		panel.build()
		if not is_instance_valid(panel.built): printerr(panel.message.text); quit(1); return
	var swap = {}
	if config.has('swap_to') and not config.get('source_only',false):
		var old_id = panel.built.get_meta('garment').garment.id
		panel.garments.select(config.swap_to)
		panel.build()
		await process_frame
		if not is_instance_valid(panel.built): printerr(panel.message.text); quit(1); return
		swap = {'before':old_id,'after':panel.built.get_meta('garment').garment.id,'independent_instances':panel.built.find_children('Garment','MeshInstance3D',true,false).size()}
		var metadata = panel.built.get_meta('garment')
		swap['bone_count'] = Interop.skeleton(panel.built).get_bone_count()
		swap['expected_bone_count'] = metadata.shared_bones+metadata.skeleton_extension.bones.size()
		if swap.bone_count!=swap.expected_bone_count: printerr('Swap accumulated accessory bones'); quit(1); return
		if swap.before==swap.after or swap.independent_instances!=1: printerr('Swap did not replace independent garment'); quit(1); return
	var scene = host.preview_scene
	var publication = {}
	if config.has('save_path'):
		if FileAccess.file_exists(config.save_path): quit(2); return
		host.python_edit.text = OS.get_environment('AINATIVE_PYTHON')
		host.host_edit.text = ProjectSettings.globalize_path('res://../../tools/ainative/editor_host.py')
		host.state_dir = config.receipt.get_base_dir()
		panel.destination.text = config.save_path
		panel.save()
		if not FileAccess.file_exists(config.save_path): printerr(panel.message.text); quit(1); return
		var published_sha = FileAccess.get_sha256(config.save_path)
		var reopened = Interop.load_scene(config.save_path)
		if reopened.has('error'): printerr(reopened.error); quit(1); return
		root.add_child(reopened.scene)
		var bindings_match = Acceptance.binding_matches(scene.get_node('Garment'),reopened.scene.get_node('Garment'))
		var persisted_manifest = reopened.scene.get_meta('garment',{})
		var metadata_match = scene.get_meta('garment').revision==persisted_manifest.get('revision') and Interop.revision(persisted_manifest)==persisted_manifest.get('revision')
		panel.save()
		var no_clobber = FileAccess.get_sha256(config.save_path)==published_sha and not panel.message.text.begins_with('Published')
		publication = {'path':config.save_path,'sha256':published_sha,'skin_weights_retained':bindings_match,'manifest_retained':metadata_match,'no_clobber':no_clobber}
		reopened.scene.free()
		if not bindings_match or not metadata_match or not no_clobber: printerr('UI save/reopen/no-clobber failed'); quit(1); return
	var screenshots = []
	for index in 3:
		var path = config.screenshot_prefix+'-'+str(index)+'.png'
		if FileAccess.file_exists(path): printerr('Evidence exists: '+path); quit(2); return
		scene.rotation.y = [0.0,PI/2,PI][index]
		await process_frame
		await RenderingServer.frame_post_draw
		host.viewport.get_texture().get_image().save_png(path)
		screenshots.append({'path':path,'sha256':FileAccess.get_sha256(path),'angle_degrees':index*90})
	scene.rotation.y = 0
	if not config.get('source_only',false):
		panel.play()
		for player in scene.find_children('*','AnimationPlayer',true,false): player.advance(config.get('animation_time',1.0)); player.pause()
		var path = config.screenshot_prefix+'-animation.png'
		if FileAccess.file_exists(path): quit(2); return
		await process_frame
		await RenderingServer.frame_post_draw
		host.viewport.get_texture().get_image().save_png(path)
		screenshots.append({'path':path,'sha256':FileAccess.get_sha256(path),'animation_time':config.get('animation_time',1.0)})
	var result = {'source_sha256':before,'source_preserved':FileAccess.get_sha256(source.path)==before,'source_only':config.get('source_only',false),'swap':swap,'screenshots':screenshots,'manifest':scene.get_meta('garment',{}),'visual_acceptance':'requires human review of rendered images; screenshots alone are not acceptance'}
	result['publication'] = publication
	if config.has('workbench_screenshot'):
		if FileAccess.file_exists(config.workbench_screenshot): quit(2); return
		await process_frame
		host.get_node('WorkbenchScroll').scroll_vertical = int(panel.position.y)
		await process_frame
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png(config.workbench_screenshot)
		result['workbench_screenshot'] = {'path':config.workbench_screenshot,'sha256':FileAccess.get_sha256(config.workbench_screenshot)}
	result['invalid_wardrobe_state_preserved'] = config.get('regression_checks',false)
	var file = FileAccess.open(config.receipt,FileAccess.WRITE)
	file.store_string(JSON.stringify(result,'  ',true,true))
	file.close()
	quit(0 if result.source_preserved else 1)
