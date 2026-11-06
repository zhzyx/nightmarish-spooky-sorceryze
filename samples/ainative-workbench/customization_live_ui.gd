extends SceneTree
const Customization = preload('res://addons/ainative/customization.gd')
const Interop = preload('res://addons/ainative/interop.gd')
var panel
var viewport: SubViewport
var stage: Node3D
var camera: Camera3D
func _initialize(): run.call_deferred()
func run():
	var args = OS.get_cmdline_user_args()
	if args.size()!=1: printerr('Expected private customization UI config'); quit(2); return
	var config = JSON.parse_string(FileAccess.get_file_as_string(args[0]))
	assert(not FileAccess.file_exists(config.output+'.tscn'),'Choose a new evidence version')
	root.size = Vector2i(1400,1000)
	var host = load('res://addons/ainative/workbench.gd').new()
	root.add_child(host)
	host.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	host.python_edit.text = config.python
	await process_frame
	for node in host.find_children('*','VBoxContainer',true,false):
		if node.get_script()==load('res://addons/ainative/customization_panel.gd'): panel = node
	assert(panel!=null,'Normal workbench customization hook missing')
	viewport = panel.viewport
	stage = panel.stage
	camera = panel.camera
	var scroll = host.get_node('WorkbenchScroll')
	scroll.scroll_vertical = int(panel.position.y)
	panel.source_path.text = config.asset
	panel.binding_path.text = config.binding
	panel.load_source()
	assert(panel.scene!=null,panel.message.text)
	assert(not panel.last_result.has('error'),panel.message.text)
	if not config.get('acceptance',false): return
	var original_sha = FileAccess.get_sha256(config.asset)
	if config.has('wardrobe'):
		panel.wardrobe_path.text = config.wardrobe
		panel.refit_garment()
		assert(panel.fit_revision!='',panel.message.text)
	var fit0 = panel.fit_revision
	var garment0 = panel.scene.get_node('Garment').mesh.surface_get_arrays(0)[Mesh.ARRAY_VERTEX]
	var wardrobe = JSON.parse_string(FileAccess.get_file_as_string(config.wardrobe))
	var garment_sha = FileAccess.get_sha256(wardrobe.garments[0].path)
	await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(config.output+'-time0.png')
	panel.controls.face_width.value = .45
	panel.controls.jaw_width.value = -.35
	panel.controls.chest.value = 1.15
	panel.controls.jawOpen.value = .65
	panel.controls.mouthSmile.value = .65
	panel.controls.lookLeft.value = .65
	if config.has('wardrobe'):
		panel.refit_garment()
		assert(panel.fit_revision!=fit0,panel.message.text)
	var sk = Interop.skeleton(panel.scene)
	var garment1 = panel.scene.get_node('Garment').mesh.surface_get_arrays(0)[Mesh.ARRAY_VERTEX]
	var fit_delta = 0.0
	assert(garment0.size()==garment1.size())
	for i in garment0.size(): fit_delta = maxf(fit_delta,garment0[i].distance_to(garment1[i]))
	assert(fit_delta>.001,'Garment geometry did not refit')
	assert(sk!=null)
	var binding = panel.scene.get_meta('face_binding')
	panel.body_motion_path.text = config.body_motion
	panel.load_body_motion()
	assert(is_instance_valid(panel.body_player),panel.message.text)
	var player = panel.body_player
	var animation = player.get_animation(player.current_animation)
	player.seek(0,true)
	player.pause()
	sk.force_update_all_bone_transforms()
	var body_before = {}
	for semantic in ['chest','neck','head']:
		body_before[semantic] = sk.get_bone_global_pose(sk.find_bone(binding.body_mapping[semantic]))
	player.seek(animation.length*.5,true)
	player.pause()
	sk.force_update_all_bone_transforms()
	var body_delta = {}
	for semantic in body_before:
		var pose = sk.get_bone_global_pose(sk.find_bone(binding.body_mapping[semantic]))
		body_delta[semantic] = body_before[semantic].origin.distance_to(pose.origin)
	assert(body_delta.head>.005,'Generated body motion did not move head')
	var before = []
	for i in sk.get_bone_count(): before.append(Interop.encode(sk.get_bone_pose(i)))
	panel.face_stream_path.text = config.face_stream
	panel.load_expression()
	assert(panel.expression_frames.size()==72,panel.message.text)
	panel.face_frame.value = 0
	panel.apply()
	var mixed = panel.last_result
	panel.frame_character()
	assert(not mixed.has('error'),str(mixed))
	var valid_dna = panel.scene.get_meta('character_dna')
	var invalid_dna = Customization.dna(valid_dna.source_sha256,{'chest':1.21},valid_dna.face,valid_dna.mapping_version)
	assert(Customization.apply_face(panel.scene,invalid_dna,[]).has('error'))
	assert(panel.scene.get_meta('character_dna').revision==valid_dna.revision,'Rejected DNA changed scene')
	for i in sk.get_bone_count(): assert(before[i]==Interop.encode(sk.get_bone_pose(i)),'Face wrote skeleton bone '+str(i))
	panel.destination.text = config.output+'.tscn'
	panel.save_version()
	assert(FileAccess.file_exists(panel.destination.text),panel.message.text)
	var saved_hash = FileAccess.get_sha256(panel.destination.text)
	panel.save_version()
	assert(panel.message.text.contains('overwrite refused'))
	assert(saved_hash==FileAccess.get_sha256(panel.destination.text))
	var reopened = Interop.load_scene(panel.destination.text)
	assert(not reopened.has('error'))
	assert(Customization.validate(reopened.scene.get_meta('character_dna'))=='')
	assert(reopened.scene.get_meta('character_dna').revision==panel.scene.get_meta('character_dna').revision)
	assert(reopened.scene.get_meta('scalp_binding')==panel.scene.get_meta('scalp_binding'))
	for mi in panel.scene.find_children('*','MeshInstance3D',true,false):
		var other = reopened.scene.get_node(panel.scene.get_path_to(mi))
		for i in mi.get_blend_shape_count(): assert(is_equal_approx(mi.get_blend_shape_value(i),other.get_blend_shape_value(i)),'Reopened morph differs')
	assert(reopened.scene.get_node('BodyMotion').has_animation('generated'),'Body animation missing after reopen')
	reopened.scene.free()
	await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(config.output+'-time1.png')
	panel.set_process(false)
	var body_hips = sk.global_transform*sk.get_bone_global_pose(sk.find_bone(binding.body_mapping.hips)).origin
	var comparison_base = panel.immutable_base.duplicate()
	stage.add_child(comparison_base)
	assert(not Customization.apply_face(comparison_base,valid_dna,panel.scene.get_meta('face_layers')).has('error'))
	var comparison_player = player.duplicate()
	comparison_base.add_child(comparison_player)
	comparison_player.play(player.assigned_animation)
	comparison_player.seek(player.current_animation_position,true)
	comparison_player.pause()
	for dressed in [false,true]:
		panel.scene.visible = dressed
		comparison_base.visible = not dressed
		for side in [false,true]:
			camera.global_position = body_hips+(Vector3(3.0,.15,0) if side else Vector3(0,.15,3.0))
			camera.look_at(body_hips)
			await process_frame
			await RenderingServer.frame_post_draw
			viewport.get_texture().get_image().save_png(config.output+('-dressed' if dressed else '-base')+('-side.png' if side else '-front.png'))
	comparison_base.queue_free()
	panel.scene.visible = true
	var head_center = sk.global_transform*sk.get_bone_global_pose(sk.find_bone(binding.body_mapping.head)).origin+Vector3(0,.05,0)
	camera.global_position = head_center+Vector3(.65,.02,0)
	camera.look_at(head_center)
	await process_frame
	await RenderingServer.frame_post_draw
	viewport.get_texture().get_image().save_png(config.output+'-neck-side.png')
	panel.set_process(true)
	assert(original_sha==FileAccess.get_sha256(config.asset))
	assert(garment_sha==FileAccess.get_sha256(wardrobe.garments[0].path))
	var bone_count = sk.get_bone_count()
	var fit_before_reopen = panel.fit_revision
	var saved_layers = panel.scene.get_meta('face_layers').duplicate(true)
	var saved_pose_revision = panel.scene.get_meta('scalp_binding').pose_revision
	# Reopening must restore the saved frame even if the panel currently shows
	# another capture frame, rather than applying stale UI capture state.
	panel.face_frame.value = 71
	panel.source_path.text = panel.destination.text
	panel.load_source()
	assert(panel.scene.get_meta('character_dna').revision==valid_dna.revision,'UI reopen changed DNA')
	assert(Interop.revision({'layers':panel.scene.get_meta('face_layers')})==Interop.revision({'layers':saved_layers}),'UI reopen changed saved expression ownership')
	assert(panel.scene.get_meta('scalp_binding').pose_revision==saved_pose_revision,'Stale capture changed reopened expression')
	panel.refit_garment()
	assert(panel.fit_revision==fit_before_reopen,'Same DNA refit changed cache key')
	assert(is_instance_valid(panel.body_player),'Refit lost reopened body animation')
	assert(panel.scene.find_children('Garment','MeshInstance3D',true,false).size()==1,'Garments accumulated')
	var f = FileAccess.open(config.output+'-receipt.json',FileAccess.WRITE)
	f.store_string(JSON.stringify({'source_sha256':original_sha,'dna':panel.scene.get_meta('character_dna'),'scalp_binding':panel.scene.get_meta('scalp_binding'),'face':mixed,'bones_unchanged':bone_count,'garment_vertex_delta_m':fit_delta,'garment_clearance':panel.scene.get_meta('garment').clearance,'garment_sha256':garment_sha,'ui_reopen_refit_animation_preserved':true,'save_reopen':true,'overwrite_rejected':true,'face_stream_sha256':FileAccess.get_sha256(config.face_stream),'body_animation_combination':body_delta,'body_clip_origin':panel.scene.get_meta('body_motion_source'),'fit_revisions':[fit0,panel.fit_revision],'screenshots':[config.output+'-time0.png',config.output+'-time1.png']},'\t'))
	f.close()
	quit()
