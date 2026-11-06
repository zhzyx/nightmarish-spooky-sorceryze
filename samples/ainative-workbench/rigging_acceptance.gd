extends SceneTree
const Rig = preload('res://addons/ainative/rigging.gd')
var failures = []

func check(ok: bool, description: String):
	if not ok: failures.append(description)

func _initialize():
	run.call_deferred()

func run():
	var args = OS.get_cmdline_user_args()
	if args.size()<2: push_error('Usage -- source.glb new.tscn [params.json]'); quit(2); return
	var p = Rig.defaults(args[0])
	p.confirmed_humanoid = true
	if args.size()>2:
		var parsed = JSON.parse_string(FileAccess.get_file_as_string(args[2]).trim_prefix('\ufeff'))
		if not parsed is Dictionary: print('Invalid params JSON'); quit(2); return
		p = parsed
	var result = Rig.build(args[0],p)
	if result.has('error'): print(JSON.stringify(result)); quit(1); return
	root.add_child(result.scene)
	var error = Rig.stage(result.scene,args[1])
	if error: print(error); quit(1); return
	var reloaded = load(args[1]).instantiate()
	root.add_child(reloaded)
	await process_frame
	var sk = reloaded.get_node('Skeleton3D')
	var body = reloaded.get_node('Body')
	var max_rest_error = 0.0
	var count = 0
	for si in body.mesh.get_surface_count():
		var a = body.mesh.surface_get_arrays(si)
		for i in a[Mesh.ARRAY_VERTEX].size():
			var v = a[Mesh.ARRAY_VERTEX][i]
			var out = Vector3.ZERO
			var total = 0.0
			for j in 4:
				var bi = a[Mesh.ARRAY_BONES][i*4+j]
				var w = a[Mesh.ARRAY_WEIGHTS][i*4+j]
				check(bi>=0 and bi<sk.get_bone_count() and is_finite(w) and w>=0,'weight/index')
				total += w
				out += (sk.get_bone_global_rest(bi)*body.skin.get_bind_pose(bi)*v)*w
			check(absf(total-1)<1e-4,'weight sum')
			max_rest_error = maxf(max_rest_error,out.distance_to(v))
			count += 1
	check(max_rest_error<0.0002,'rest geometry')
	var player = reloaded.get_node('AnimationPlayer')
	var movement = {}
	var foot_drift = 0.0
	var sole_drift = 0.0
	for motion in ['raise_arms','squat','turn']:
		player.play(motion)
		player.advance(1.0)
		check(player.current_animation==motion,'animation playback')
		sk.force_update_all_bone_transforms()
		var maximum = 0.0
		for si in body.mesh.get_surface_count():
			var a = body.mesh.surface_get_arrays(si)
			for i in a[Mesh.ARRAY_VERTEX].size():
				var v = a[Mesh.ARRAY_VERTEX][i]
				var deformed = Vector3.ZERO
				for j in 4:
					var bi = a[Mesh.ARRAY_BONES][i*4+j]
					deformed += (sk.get_bone_global_pose(bi)*body.skin.get_bind_pose(bi)*v)*a[Mesh.ARRAY_WEIGHTS][i*4+j]
				check(deformed.is_finite(),'finite deformation')
				maximum = maxf(maximum,deformed.distance_to(v))
		movement[motion] = maximum
		check(maximum>.02,'nonempty motion '+motion)
		if motion=='squat':
			for sample in 41:
				player.seek(sample*.05,true)
				sk.force_update_all_bone_transforms()
				for name in ['foot_l','foot_r']:
					var index = sk.find_bone(name)
					foot_drift = maxf(foot_drift,sk.get_bone_global_pose(index).origin.distance_to(sk.get_bone_global_rest(index).origin))
				for si in body.mesh.get_surface_count():
					var a = body.mesh.surface_get_arrays(si)
					for vi in a[Mesh.ARRAY_VERTEX].size():
						var v = a[Mesh.ARRAY_VERTEX][vi]
						if v.y>p.height_m*.025: continue
						var deformed = Vector3.ZERO
						for j in 4:
							var bi = a[Mesh.ARRAY_BONES][vi*4+j]
							deformed += (sk.get_bone_global_pose(bi)*body.skin.get_bind_pose(bi)*v)*a[Mesh.ARRAY_WEIGHTS][vi*4+j]
						sole_drift = maxf(sole_drift,deformed.distance_to(v))
	check(foot_drift<.003,'squat ankle contact')
	check(sole_drift<.003,'squat actual sole contact')
	var bad = p.duplicate(true)
	bad.source_sha256 = 'changed'
	check(Rig.build(args[0],bad).has('error'),'source hash rejection')
	bad = p.duplicate(true)
	bad.height_m = -1
	check(Rig.build(args[0],bad).has('error'),'negative height rejection')
	bad = p.duplicate(true)
	bad.weights = {'0':{'999':1.0}}
	bad.weights_geometry = Rig.geometry_key(bad)
	check(Rig.build(args[0],bad).has('error'),'invalid bone rejection')
	bad = p.duplicate(true)
	bad.route = 'free'
	bad.joints = {}
	var pending = Rig.build(args[0],bad)
	check(not pending.get('accepted',true),'unknown free mesh remains pending')
	if pending.has('scene'): pending.scene.free()
	print(JSON.stringify({'vertices':count,'bones':sk.get_bone_count(),'rest_error':max_rest_error,'diagnostics':result.diagnostics,'published':args[1],'failures':failures,'movement_m':movement,'squat_ankle_drift_m':foot_drift,'squat_sole_drift_m':sole_drift}))
	quit(0 if failures.is_empty() else 1)
