extends SceneTree
const Interop = preload('res://addons/ainative/interop.gd')
var failures = []

func _initialize(): run.call_deferred()

func check(ok: bool, message: String):
	if not ok: failures.append(message)

func run():
	var args = OS.get_cmdline_user_args()
	if args.size()!=1: print('Usage: -- config.json'); quit(2); return
	var config = JSON.parse_string(FileAccess.get_file_as_string(args[0]).trim_prefix('\ufeff'))
	if not config is Dictionary: quit(2); return
	var report = {'schema_version':1,'cases':[],'failures':failures}
	for case in config.cases:
		var s = Interop.load_scene(case.source_path)
		var t = Interop.load_scene(case.target_path)
		if s.has('error') or t.has('error'): failures.append(str(s.get('error',t.get('error','')))); continue
		root.add_child(s.scene)
		root.add_child(t.scene)
		var sp = Interop.extract(s.scene,case.source_family,case.source_provenance,case.get('source_corrections',{}))
		var tp = Interop.extract(t.scene,case.target_family,case.target_provenance,case.get('target_corrections',{}))
		if sp.has('error') or tp.has('error'): failures.append(str(sp.get('error',tp.get('error','')))); s.scene.free(); t.scene.free(); continue
		check(FileAccess.get_sha256(case.source_path)==sp.profile.source.sha256,'source SHA256')
		check(FileAccess.get_sha256(case.target_path)==tp.profile.source.sha256,'target SHA256')
		var source_motion_reference = measure(s.scene)
		var target_motion_identity = {}
		if case.has('target_motion_path'):
			var motion_scene = Interop.load_scene(case.target_motion_path)
			if motion_scene.has('error'): failures.append(motion_scene.error)
			else:
				root.add_child(motion_scene.scene)
				var provenance = case.get('target_motion_provenance',{}).duplicate(true)
				check(provenance.get('sha256') == FileAccess.get_sha256(case.target_motion_path),'separate animation source SHA256')
				var motion_profile = Interop.extract(motion_scene.scene,case.target_family,provenance)
				if motion_profile.has('error'): failures.append(motion_profile.error)
				else:
					target_motion_identity = {'source':provenance,'skeleton_revision':motion_profile.profile.revision}
					var motion_result = Interop.attach_animations(t.scene,motion_scene.scene,motion_profile.profile,tp.profile)
					check(not motion_result.has('error'),'separate actual animation onto full target skeleton')
				motion_scene.scene.free()
		var bound = Interop.bind(s.scene,sp.profile,tp.profile)
		if bound.has('error'): failures.append(bound.error); s.scene.free(); t.scene.free(); continue
		root.add_child(bound.scene)
		var animations = Interop.attach_animations(bound.scene,s.scene,sp.profile,tp.profile,case.get('contacts',{}))
		check(not animations.has('error'),'animation conversion')
		var output = case.output_prefix
		check(Interop.stage_scene(bound.scene,output+'.tscn')=='','stage scene')
		check(Interop.stage_glb(bound.scene,output+'.glb')=='','stage GLB')
		var profile_file = FileAccess.open(output+'.profile.json',FileAccess.WRITE)
		profile_file.store_string(JSON.stringify(tp.profile,'  ',true,true))
		profile_file.close()
		var readback = Interop.load_scene(output+'.glb')
		check(not readback.has('error'),'GLB readback')
		var roundtrip_bones = 0
		var roundtrip = {}
		if readback.has('scene'):
			root.add_child(readback.scene)
			var round_sk = Interop.skeleton(readback.scene)
			if round_sk!=null: roundtrip_bones = round_sk.get_bone_count()
			check(roundtrip_bones==tp.profile.bones.size(),'GLB full skeleton retained')
			roundtrip = verify_roundtrip(bound.scene,readback.scene,tp.profile)
			readback.scene.free()
		var metrics = measure(bound.scene,case.get('contacts',{}))
		var motion_comparison = compare_motion(source_motion_reference,metrics,Interop.proportion(sp.profile,tp.profile))
		check(not metrics.is_empty(),'nonempty source animations')
		var moved = false
		for value in metrics.values():
			if value is Dictionary and value.get('max_bone_displacement_m',0)>.001: moved = true
		check(moved,'source animation actually moves target')
		# Animation return is separately checked; target meshes are not replaced with source meshes.
		var reverse = Interop.attach_animations(s.scene,bound.scene,tp.profile,sp.profile,case.get('contacts',{}))
		check(not reverse.has('error'),'reverse animation conversion')
		var reverse_metrics = measure(s.scene,case.get('contacts',{}))
		# Also transfer original external animation, not only generated roundtrip clips.
		var external = Interop.attach_animations(s.scene,t.scene,tp.profile,sp.profile,case.get('target_contacts',{}))
		check(not external.has('error'),'external target animation conversion')
		var external_metrics = measure(s.scene,case.get('target_contacts',{}))
		report.cases.append({'id':case.id,'source_revision':sp.profile.revision,'target_revision':tp.profile.revision,'target_bones':tp.profile.bones.size(),'roundtrip_bones':roundtrip_bones,'roundtrip':roundtrip,'binding':bound.diagnostics,'animations':animations,'source_motion_reference':source_motion_reference,'motion_comparison':motion_comparison,'forward_metrics':metrics,'reverse_metrics':reverse_metrics,'external_target_to_source_metrics':external_metrics,'target_tool_status':'pending_external_readback'})
		report.cases[-1]['target_motion_identity'] = target_motion_identity
		bound.scene.free()
		s.scene.free()
		t.scene.free()
	print(JSON.stringify(report))
	if config.has('report_path'):
		var file = FileAccess.open(config.report_path,FileAccess.WRITE)
		file.store_string(JSON.stringify(report,'  ',true,true))
		file.close()
	quit(0 if failures.is_empty() else 1)

func measure(scene: Node3D, contacts: Dictionary = {}) -> Dictionary:
	var sk = Interop.skeleton(scene)
	var player = scene.get_node_or_null('AnimationPlayer')
	if player == null:
		var players = scene.find_children('*','AnimationPlayer',true,false)
		if players.is_empty(): return {}
		player = players[0]
	var values = {}
	for name in player.get_animation_list():
		if name=='RESET': continue
		var animation = player.get_animation(name)
		var maximum = 0.0
		var root_displacement = 0.0
		var horizontal_root_displacement = 0.0
		var first_root = Vector3.ZERO
		var feet = {}
		var foot_drift = 0.0
		var contact_foot_error = 0.0
		var sole_drift = 0.0
		var reference_vertices = {}
		var finger_rotation = 0.0
		var finger_bones = 0
		var finger_weighted_vertices = 0
		var finger_samples = []
		var first_finger_poses = {}
		var finger_skin_motion = 0.0
		for mi in scene.find_children('*','MeshInstance3D',true,false):
			if mi.skin==null: continue
			for si in mi.mesh.get_surface_count():
				var arrays = mi.mesh.surface_get_arrays(si)
				var stride = arrays[Mesh.ARRAY_WEIGHTS].size()/arrays[Mesh.ARRAY_VERTEX].size()
				for vi in arrays[Mesh.ARRAY_VERTEX].size():
					var weighted = false
					var influences = []
					for k in int(stride):
						var offset = vi*int(stride)+k
						if arrays[Mesh.ARRAY_WEIGHTS][offset]<=.001: continue
						var bind_id = arrays[Mesh.ARRAY_BONES][offset]
						var bi = mi.skin.get_bind_bone(bind_id)
						if mi.skin.get_bind_name(bind_id)!='': bi = sk.find_bone(mi.skin.get_bind_name(bind_id))
						influences.append([bi,mi.skin.get_bind_pose(bind_id),arrays[Mesh.ARRAY_WEIGHTS][offset]])
						if is_finger(str(sk.get_bone_name(bi))): weighted = true
					if weighted:
						finger_weighted_vertices += 1
						finger_samples.append([arrays[Mesh.ARRAY_VERTEX][vi],influences])
		var times = []
		for i in range(31): times.append(animation.length*i/30.0)
		for contact in contacts.get(name,[]):
			times.append(float(contact.start))
			times.append(float(contact.end))
		times.sort()
		for sample in times.size():
			var time = times[sample]
			player.play(name)
			player.seek(time,true)
			sk.force_update_all_bone_transforms()
			for bi in sk.get_bone_count():
				var pose = sk.get_bone_global_pose(bi)
				check(pose.origin.is_finite(),'finite animation pose')
				maximum = maxf(maximum,pose.origin.distance_to(sk.get_bone_global_rest(bi).origin))
				if is_finger(str(sk.get_bone_name(bi))):
					if sample==0:
						finger_bones += 1
						first_finger_poses[bi] = sk.get_bone_pose(bi)
					var first_rotation = first_finger_poses[bi].basis.orthonormalized().get_rotation_quaternion()
					finger_rotation = maxf(finger_rotation,first_rotation.angle_to(sk.get_bone_pose_rotation(bi)))
				if sk.get_bone_parent(bi)<0:
					if sample==0: first_root = pose.origin
					root_displacement = maxf(root_displacement,pose.origin.distance_to(first_root))
					var delta = pose.origin-first_root
					horizontal_root_displacement = maxf(horizontal_root_displacement,Vector2(delta.x,delta.z).length())
				if 'foot' in str(sk.get_bone_name(bi)).to_lower():
					if sample==0: feet[bi] = pose.origin
					foot_drift = maxf(foot_drift,pose.origin.distance_to(feet[bi]))
			var frozen = {}
			for item in finger_samples:
				var delta = Vector3.ZERO
				for influence in item[1]:
					var bi = influence[0]
					var point = influence[1]*item[0]
					delta += (sk.get_bone_global_pose(bi)*point-frozen_finger_global(sk,bi,first_finger_poses,frozen)*point)*influence[2]
				finger_skin_motion = maxf(finger_skin_motion,delta.length())
			var active = []
			for ci in contacts.get(name,[]).size():
				var contact = contacts[name][ci]
				if time<contact.start or time>contact.end: continue
				active.append(ci)
				for bi in sk.get_bone_count():
					if not contact_bone(str(sk.get_bone_name(bi)),contact.side): continue
					var goal = sk.get_bone_global_rest(bi).origin
					if contact.has('position_m'): goal = Vector3(contact.position_m[0],contact.position_m[1],contact.position_m[2])
					contact_foot_error = maxf(contact_foot_error,sk.get_bone_global_pose(bi).origin.distance_to(goal))
			if not active.is_empty():
				for mi in scene.find_children('*','MeshInstance3D',true,false):
					if mi.skin==null: continue
					for si in mi.mesh.get_surface_count():
						var arrays = mi.mesh.surface_get_arrays(si)
						var count = arrays[Mesh.ARRAY_WEIGHTS].size()/arrays[Mesh.ARRAY_VERTEX].size()
						for vi in arrays[Mesh.ARRAY_VERTEX].size():
							var vertex = arrays[Mesh.ARRAY_VERTEX][vi]
							if vertex.y>.05: continue
							var deformed = Vector3.ZERO
							var side_weights = {'l':0.0,'r':0.0}
							for k in int(count):
								var offset = vi*int(count)+k
								var bind_id = arrays[Mesh.ARRAY_BONES][offset]
								var bi = mi.skin.get_bind_bone(bind_id)
								if mi.skin.get_bind_name(bind_id)!='': bi = sk.find_bone(mi.skin.get_bind_name(bind_id))
								deformed += (sk.get_bone_global_pose(bi)*mi.skin.get_bind_pose(bind_id)*vertex)*arrays[Mesh.ARRAY_WEIGHTS][offset]
								for side in ['l','r']:
									if contact_bone(str(sk.get_bone_name(bi)),side): side_weights[side] += arrays[Mesh.ARRAY_WEIGHTS][offset]
							for ci in active:
								if side_weights[contacts[name][ci].side]<.5: continue
								var key = str(mi.get_instance_id())+':'+str(si)+':'+str(vi)+':'+str(ci)
								if not reference_vertices.has(key): reference_vertices[key] = deformed
								sole_drift = maxf(sole_drift,deformed.distance_to(reference_vertices[key]))
		if contacts.has(name):
			check(contact_foot_error<.003,'planted ankle <3mm '+name)
			check(not reference_vertices.is_empty(),'planted sole samples '+name)
			check(sole_drift<.005,'planted sole <5mm '+name)
		values[name] = {'max_bone_displacement_m':maximum,'root_displacement_m':root_displacement,'foot_motion_from_first_frame_m':foot_drift,'sole_drift_m':sole_drift,'sole_samples':reference_vertices.size(),'finger_bones':finger_bones,'weighted_finger_vertices':finger_weighted_vertices,'max_local_finger_motion_rad':finger_rotation,'max_finger_skin_motion_m':finger_skin_motion,'finger_status':'weighted articulated fingers measured' if finger_weighted_vertices>0 and finger_rotation>.01 and finger_skin_motion>.0001 else 'no demonstrated weighted finger articulation','contact_status':'checked ankle 3mm / sole 5mm' if contacts.has(name) else 'motion measured; planted intervals not supplied'}
		values[name]['planted_ankle_error_m'] = contact_foot_error
		values[name]['horizontal_root_displacement_m'] = horizontal_root_displacement
	player.stop()
	sk.reset_bone_poses()
	return values

func compare_motion(source: Dictionary, target: Dictionary, ratio: float) -> Dictionary:
	var result = {}
	for name in source:
		if not target.has(name): continue
		var expected = source[name].horizontal_root_displacement_m*ratio
		var error = absf(target[name].horizontal_root_displacement_m-expected)
		check(error<.002,'horizontal root displacement ratio <2mm '+name)
		var finger_error = absf(source[name].max_local_finger_motion_rad-target[name].max_local_finger_motion_rad)
		if source[name].finger_status=='weighted articulated fingers measured' and target[name].weighted_finger_vertices>0:
			check(target[name].finger_status=='weighted articulated fingers measured','actual weighted finger motion transferred '+name)
			check(finger_error<.01,'finger motion amplitude <0.01rad '+name)
		result[name] = {'expected_horizontal_root_m':expected,'root_displacement_error_m':error,'finger_motion_amplitude_error_rad':finger_error}
	return result

func is_finger(name: String) -> bool:
	for part in ['thumb','index','middle','ring','pinky']:
		if part in name.to_lower(): return true
	return false

func frozen_finger_global(sk: Skeleton3D, index: int, first: Dictionary, cache: Dictionary) -> Transform3D:
	if cache.has(index): return cache[index]
	var local = first.get(index,sk.get_bone_pose(index))
	var parent = sk.get_bone_parent(index)
	cache[index] = frozen_finger_global(sk,parent,first,cache)*local if parent>=0 else local
	return cache[index]

func contact_bone(name: String, side: String) -> bool:
	var n = name.to_lower()
	return 'foot' in n and not n.begins_with('ik_') and (n.ends_with('_'+side) or ('left' if side=='l' else 'right') in n)

func verify_roundtrip(original: Node3D, loaded: Node3D, profile: Dictionary) -> Dictionary:
	var sk = Interop.skeleton(loaded)
	if sk==null: return {'error':'No skeleton'}
	var max_rest = 0.0
	for b in profile.bones:
		var index = sk.find_bone(b.name)
		check(index>=0,'roundtrip bone name '+b.name)
		if index<0: continue
		var parent = sk.get_bone_parent(index)
		var expected_parent = profile.bones[int(b.parent)].name if int(b.parent)>=0 else ''
		check((str(sk.get_bone_name(parent)) if parent>=0 else '')==expected_parent,'roundtrip parent '+b.name)
		var expected = Interop.decode(b.global_rest)
		var actual = sk.get_bone_global_rest(index)
		max_rest = maxf(max_rest,actual.origin.distance_to(expected.origin))
		check(actual.basis.is_equal_approx(expected.basis),'roundtrip bone axis '+b.name)
	check(max_rest<.0001,'roundtrip rest translation <0.1mm')
	var vertices = 0
	var reconstruction = 0.0
	for mi in loaded.find_children('*','MeshInstance3D',true,false):
		if mi.skin==null: continue
		for si in mi.mesh.get_surface_count():
			var a = mi.mesh.surface_get_arrays(si)
			var stride = int(a[Mesh.ARRAY_WEIGHTS].size()/a[Mesh.ARRAY_VERTEX].size())
			for vi in a[Mesh.ARRAY_VERTEX].size():
				var v = a[Mesh.ARRAY_VERTEX][vi]
				var reconstructed = Vector3.ZERO
				var total = 0.0
				for k in stride:
					var offset = vi*stride+k
					var bind_id = a[Mesh.ARRAY_BONES][offset]
					var w = a[Mesh.ARRAY_WEIGHTS][offset]
					check(is_finite(w) and w>=0,'roundtrip finite weight')
					var bi = mi.skin.get_bind_bone(bind_id)
					if mi.skin.get_bind_name(bind_id)!='': bi = sk.find_bone(mi.skin.get_bind_name(bind_id))
					check(bi>=0 and bi<sk.get_bone_count(),'roundtrip bind bone')
					if bi<0: continue
					reconstructed += (sk.get_bone_global_rest(bi)*mi.skin.get_bind_pose(bind_id)*v)*w
					total += w
				check(absf(total-1)<.001,'roundtrip normalized weights')
				reconstruction = maxf(reconstruction,reconstructed.distance_to(v))
				vertices += 1
	check(vertices>0 and reconstruction<.001,'roundtrip weighted geometry <1mm')
	var original_players = original.find_children('*','AnimationPlayer',true,false)
	var loaded_players = loaded.find_children('*','AnimationPlayer',true,false)
	check(not loaded_players.is_empty(),'roundtrip AnimationPlayer')
	var clips = []
	var pose_error = 0.0
	var rotation_error = 0.0
	if not loaded_players.is_empty():
		var source_sk = Interop.skeleton(original)
		for p in original_players:
			for name in p.get_animation_list():
				check(loaded_players[0].has_animation(name),'roundtrip clip '+name)
				if loaded_players[0].has_animation(name):
					var clip = loaded_players[0].get_animation(name)
					check(absf(clip.length-p.get_animation(name).length)<.0001,'roundtrip animation duration')
					for fraction in [0.0,.25,.5,.75,1.0]:
						source_sk.reset_bone_poses()
						sk.reset_bone_poses()
						p.play(name)
						p.seek(p.get_animation(name).length*fraction,true)
						loaded_players[0].play(name)
						loaded_players[0].seek(clip.length*fraction,true)
						source_sk.force_update_all_bone_transforms()
						sk.force_update_all_bone_transforms()
						for i in source_sk.get_bone_count():
							var bi = sk.find_bone(source_sk.get_bone_name(i))
							if bi<0: continue
							var expected = source_sk.get_bone_global_pose(i)
							var actual = sk.get_bone_global_pose(bi)
							pose_error = maxf(pose_error,expected.origin.distance_to(actual.origin))
							rotation_error = maxf(rotation_error,expected.basis.orthonormalized().get_rotation_quaternion().angle_to(actual.basis.orthonormalized().get_rotation_quaternion()))
					clips.append(name)
			p.stop()
			source_sk.reset_bone_poses()
		loaded_players[0].stop()
		sk.reset_bone_poses()
	check(pose_error<.001 and rotation_error<.005,'roundtrip animation pose fidelity 1mm/0.005rad')
	return {'max_rest_translation_m':max_rest,'max_skin_rest_error_m':reconstruction,'vertices':vertices,'clips':clips,'max_animation_position_error_m':pose_error,'max_animation_rotation_error_rad':rotation_error}
