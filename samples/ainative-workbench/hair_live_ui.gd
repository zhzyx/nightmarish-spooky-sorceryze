extends SceneTree
var panel
func _initialize(): run.call_deferred()
func run():
	var config = JSON.parse_string(FileAccess.get_file_as_string(OS.get_cmdline_user_args()[0]))
	root.size = Vector2i(1400,1000)
	var host = load('res://addons/ainative/workbench.gd').new()
	root.add_child(host)
	host.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	host.python_edit.text = config.python
	await process_frame
	for node in host.find_children('*','VBoxContainer',true,false):
		if node.get_script()==load('res://addons/ainative/hair_panel.gd'): panel = node
	assert(panel!=null)
	panel.source_path.text = config.asset
	panel.binding_path.text = config.binding
	panel.base_source_path.text = config.get('base',config.asset)
	panel.load_source()
	assert(panel.scene!=null,panel.message.text)
	await process_frame
	await RenderingServer.frame_post_draw
	panel.viewport.get_texture().get_image().save_png(config.output+'-baseline-no-hair.png')
	panel.hair_source.text = config.hair
	panel.bind_hair()
	assert(not panel.last_result.has('error'),panel.message.text)
	await process_frame
	var hair = panel.scene.get_node('IndependentHair')
	var sk = hair.body
	var head = sk.find_bone(panel.scene.get_meta('face_binding').body_mapping.head)
	var center = sk.global_transform*sk.get_bone_global_pose(head).origin+Vector3(0,.07,0)
	var output = {'views':[],'roots':hair.config.roots,'head_rest':str(sk.get_bone_global_rest(head))}
	var interop = preload('res://addons/ainative/interop.gd')
	assert(interop.skeleton(panel.scene)==sk,'Auxiliary skeleton confused body discovery')
	var extra = Skeleton3D.new()
	panel.scene.add_child(extra)
	assert(interop.skeleton(panel.scene)==null,'Two body skeletons must be rejected')
	extra.free()
	assert(interop.skeleton(panel.scene)==sk)
	for view in [['front',Vector3(0,.05,.85)],['side',Vector3(.85,.05,0)],['back',Vector3(0,.05,-.85)]]:
		panel.camera.global_position = center+view[1]
		panel.camera.look_at(center)
		await process_frame
		await RenderingServer.frame_post_draw
		var path = config.output+'-'+view[0]+'.png'
		panel.viewport.get_texture().get_image().save_png(path)
		output.views.append(path)
	if config.get('acceptance',false):
		var initial_revision = hair.config.scalp_revision
		var initial_roots = hair.config.roots.duplicate(true)
		panel.controls.face_width.value = .45
		panel.controls.jaw_width.value = -.35
		hair = panel.scene.get_node('IndependentHair')
		assert(hair.config.scalp_revision!=initial_revision)
		assert(hair.config.roots!=initial_roots,'Scalp roots did not change')
		output.rebound = {'old':initial_revision,'new':hair.config.scalp_revision}
		var pose_hair = hair
		hair.offsets[0] = Vector3(.001,.002,.003)
		panel.controls.mouthSmile.value = .4
		assert(panel.scene.get_node('IndependentHair')==pose_hair,'Expression-only update rebuilt hair')
		assert(hair.offsets[0]==Vector3(.001,.002,.003),'Expression-only update reset dynamics')
		output.expression_preserves_dynamics = true
		output.combinations = []
		for lod in 3:
			for cards in [false,true]:
				var full_count = 0
				for hat in [false,true]:
					panel.hair_lod.select(lod)
					panel.hair_cards.set_pressed_no_signal(cards)
					panel.hair_hat.set_pressed_no_signal(hat)
					panel.update_representation()
					var count = hair.get_meta('triangle_count')
					assert(count>0)
					if not hat: full_count = count
					else: assert(count<full_count,'Hat did not selectively mask crown')
					await process_frame
					await RenderingServer.frame_post_draw
					var path = config.output+'-lod'+str(lod)+'-cards'+str(cards)+'-hat'+str(hat)+'.png'
					panel.viewport.get_texture().get_image().save_png(path)
					output.combinations.append({'lod':lod,'cards':cards,'hat':hat,'triangles':count,'view':path})
					if lod==0 and not cards:
						panel.camera.global_position = center+Vector3(.65,.03,0)
						panel.camera.look_at(center)
						await process_frame
						await RenderingServer.frame_post_draw
						panel.viewport.get_texture().get_image().save_png(config.output+'-root-side-hat'+str(hat)+'.png')
						panel.camera.global_position = center+Vector3(0,.05,-.85)
						panel.camera.look_at(center)
		panel.body_motion_path.text = config.motion
		panel.load_body_motion()
		assert(is_instance_valid(panel.body_player),panel.message.text)
		var player = panel.body_player
		player.pause()
		var timings = []
		var max_offset = 0.0
		var original_count = sk.get_bone_count()
		for frame in 120:
			player.seek(float(frame)/60.0,true)
			var before = [sk.get_bone_pose(head),sk.get_bone_pose(sk.find_bone(panel.scene.get_meta('face_binding').body_mapping.neck))]
			hair._process(1.0/60)
			assert(sk.get_bone_pose(head)==before[0])
			assert(sk.get_bone_pose(sk.find_bone(panel.scene.get_meta('face_binding').body_mapping.neck))==before[1])
			assert(sk.get_bone_count()==original_count)
			for offset in hair.offsets: max_offset = maxf(max_offset,offset.length())
			timings.append(hair.last_step_us)
			if frame in [0,60,119]:
				panel.frame_character()
				await process_frame
				await RenderingServer.frame_post_draw
				panel.viewport.get_texture().get_image().save_png(config.output+'-motion'+str(frame)+'.png')
		var resets = hair.reset_count
		panel.scene.position.x += 2
		hair._process(1.0/60)
		assert(hair.reset_count>resets)
		panel.scene.position.x -= 2
		hair._process(.5)
		output.motion = {'steps':120,'max_offset_m':max_offset,'solver_us':timings,'collisions':hair.collision_count,'reset_count':hair.reset_count,'body_bones_unchanged':original_count,'head_neck_writes':0}
		# Controlled shoulder contact pose in the real skeleton, separately
		# identified from the captured animation above. Restore immediately.
		var arm = sk.find_bone(panel.scene.get_meta('face_binding').body_mapping.upper_arm_l)
		var arm_pose = sk.get_bone_pose(arm)
		var parent_pose = sk.get_bone_global_pose(sk.get_bone_parent(arm))
		var target = sk.global_transform.affine_inverse()*(hair.global_transform*hair.point(0,hair.config.rows-1))
		sk.set_bone_pose_position(arm,parent_pose.affine_inverse()*target)
		sk.force_update_all_bone_transforms()
		var contacts_before = hair.collision_count
		hair._process(1.0/60)
		assert(hair.collision_count>contacts_before,'Controlled shoulder contact did not activate')
		var sphere_center = hair.to_local(sk.global_transform*sk.get_bone_global_pose(arm).origin)
		var tip = hair.point(0,hair.config.rows-1)+hair.offsets[0]
		assert(tip.distance_to(sphere_center)>=.0749,'Shoulder projection still penetrates')
		output.controlled_contact = {'semantic':'upper_arm_l','radius_m':.075,'separation_m':tip.distance_to(sphere_center),'contacts':hair.collision_count-contacts_before,'pose_is_test_fixture':true}
		sk.set_bone_pose_position(arm,arm_pose.origin)
		sk.set_bone_pose_rotation(arm,arm_pose.basis.get_rotation_quaternion())
		hair._process(.5)
		var spec = hair.config.spec.duplicate(true)
		var previous = hair
		spec.sha256 = '0'.repeat(64)
		assert(preload('res://addons/ainative/hair.gd').bind(panel.scene,spec).has('error'))
		assert(panel.scene.get_node('IndependentHair')==previous)
		var original_dna = panel.scene.get_meta('character_dna').duplicate(true)
		var changed_face = original_dna.face.duplicate(true)
		changed_face.face_width = -.2
		var customization = preload('res://addons/ainative/customization.gd')
		var changed_dna = customization.dna(original_dna.source_sha256,original_dna.body,changed_face,original_dna.mapping_version)
		assert(not customization.apply_face(panel.scene,changed_dna,panel.scene.get_meta('face_layers')).has('error'))
		hair._process(1.0/60)
		assert(not hair.is_processing() and hair.has_meta('hair_error'),'Out-of-panel scalp revision did not stop stale solver')
		customization.apply_face(panel.scene,original_dna,panel.scene.get_meta('face_layers'))
		var rebound = preload('res://addons/ainative/hair.gd').bind(panel.scene,hair.config.spec)
		assert(not rebound.has('error'))
		hair = rebound.hair
		previous = hair
		panel.update_representation()
		output.external_scalp_change_stops_solver = true
		var selected = JSON.parse_string(FileAccess.get_file_as_string(hair.config.spec.path))
		selected.samples[0].barycentric = [2,-1,0]
		var corrupt_path = config.output+'-bad-mapping.json'
		var corrupt_file = FileAccess.open(corrupt_path,FileAccess.WRITE)
		corrupt_file.store_string(JSON.stringify(selected))
		corrupt_file.close()
		var corrupt_spec = hair.config.spec.duplicate(true)
		corrupt_spec.path = corrupt_path
		corrupt_spec.sha256 = FileAccess.get_sha256(corrupt_path)
		assert(preload('res://addons/ainative/hair.gd').bind(panel.scene,corrupt_spec).has('error'),'Changed barycentric mapping accepted with new selection SHA')
		assert(panel.scene.get_node('IndependentHair')==previous)
		selected = JSON.parse_string(FileAccess.get_file_as_string(hair.config.spec.path))
		selected.samples[0].source_triangle = 0
		corrupt_path = config.output+'-bad-triangle.json'
		corrupt_file = FileAccess.open(corrupt_path,FileAccess.WRITE)
		corrupt_file.store_string(JSON.stringify(selected))
		corrupt_file.close()
		corrupt_spec.path = corrupt_path
		corrupt_spec.sha256 = FileAccess.get_sha256(corrupt_path)
		assert(preload('res://addons/ainative/hair.gd').bind(panel.scene,corrupt_spec).has('error'),'Wrong triangle accepted with valid barycentric weights')
		assert(panel.scene.get_node('IndependentHair')==previous)
		spec = hair.config.spec.duplicate(true)
		spec.binding_revision = initial_revision
		assert(preload('res://addons/ainative/hair.gd').bind(panel.scene,spec).has('error'))
		assert(panel.scene.get_node('IndependentHair')==previous)
		panel.destination.text = config.output+'.tscn'
		panel.save_version()
		assert(FileAccess.file_exists(panel.destination.text),panel.message.text)
		var saved_sha = FileAccess.get_sha256(panel.destination.text)
		var saved_text = FileAccess.get_file_as_string(panel.destination.text)
		assert(not ':/' in saved_text.replace('res://','').replace('user://','').replace('https://','').replace('http://',''),'Published hair contains an absolute local path')
		panel.save_version()
		assert(FileAccess.get_sha256(panel.destination.text)==saved_sha)
		panel.source_path.text = panel.destination.text
		var locator = previous.config.spec.duplicate(true)
		if config.get('relocate_private_copies',false):
			for key in ['path','mesh_path']:
				assert(locator[key].begins_with(config.output.get_base_dir()),'Relocation test must use own private copies')
				assert(DirAccess.rename_absolute(locator[key],locator[key]+'.away')==OK)
		panel.load_source()
		assert(panel.scene!=null,panel.message.text)
		hair = panel.scene.get_node('IndependentHair')
		assert(interop.skeleton(panel.scene).get_bone_count()==original_count)
		assert(hair.guide_skeleton.get_meta('ainative_auxiliary_skeleton')==true)
		assert(hair.config.lod==2 and hair.config.cards and hair.config.hat)
		if config.get('relocate_private_copies',false):
			for key in ['path','mesh_path']: assert(DirAccess.rename_absolute(locator[key]+'.away',locator[key])==OK)
			output.portable_reopen_without_sources = true
		var valid_scene = panel.scene
		var valid_revision = valid_scene.get_meta('scalp_binding').revision
		panel.controls.face_width.value = -.3
		assert(panel.scene==valid_scene and panel.scene.get_meta('scalp_binding').revision==valid_revision,'Missing locator changed saved face')
		output.missing_locator_preserves_scene = true
		var corrupt_scene = interop.load_scene(panel.destination.text).scene
		var bad_data = corrupt_scene.get_node('IndependentHair').get_meta('hair_data').duplicate(true)
		bad_data.lod = 9
		corrupt_scene.get_node('IndependentHair').set_meta('hair_data',bad_data)
		preload('res://addons/ainative/rigging.gd').owners(corrupt_scene,corrupt_scene)
		var packed = PackedScene.new()
		assert(packed.pack(corrupt_scene)==OK)
		var bad_scene_path = config.output+'-bad-metadata.tscn'
		assert(ResourceSaver.save(packed,bad_scene_path)==OK)
		corrupt_scene.free()
		panel.source_path.text = bad_scene_path
		panel.load_source()
		assert(panel.scene==valid_scene,'Invalid saved metadata replaced the last valid character')
		output.bad_metadata_preserves_scene = true
		output.saved_sha256 = saved_sha
		output.failure_preserves_scene = true
		await process_frame
		var scroll = host.get_node('WorkbenchScroll')
		scroll.scroll_vertical = int(panel.position.y)
		await process_frame
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png(config.output+'-workbench.png')
	var file = FileAccess.open(config.output+'.json',FileAccess.WRITE)
	file.store_string(JSON.stringify(output,'\t'))
	quit()
