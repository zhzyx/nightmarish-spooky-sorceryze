extends SceneTree
# Measures declared body bands against the rendered cloth on the actual shared
# character. This is a sampled intersection check, not a watertight-body proof.
const Session = preload('res://addons/ainative/character_session.gd')
const I = preload('res://addons/ainative/interop.gd')
const Export = preload('res://addons/ainative/character_export.gd')
var session: Node
var output: String
var report: Dictionary = {}

func _initialize(): run.call_deferred()

func finish(error: String = ''):
	if error: report['error'] = error
	var file = FileAccess.open(output,FileAccess.WRITE)
	if file != null: file.store_string(JSON.stringify(report,'  ',true,true)); file.close()
	print(JSON.stringify({'success':error == '' and report.get('worst_crossing_edges',1) == 0,'frames':report.get('frames',0),'worst_crossing_edges':report.get('worst_crossing_edges',-1),'error':error}))
	if is_instance_valid(session): session.free()
	quit(0 if error == '' and report.get('worst_crossing_edges',1) == 0 else 1)

func run():
	var args = OS.get_cmdline_user_args()
	if args.size() != 1: printerr('Expected one private acceptance config'); quit(2); return
	var config = JSON.parse_string(FileAccess.get_file_as_string(args[0]))
	if not config is Dictionary: printerr('Invalid acceptance config'); quit(2); return
	output = config.get('output','')
	if output == '' or FileAccess.file_exists(output): printerr('Choose a new evidence output'); quit(2); return
	var path = str(config.get('scene',''))
	var sha = FileAccess.get_sha256(path)
	if sha == '' or sha != config.get('sha256'): finish('Frozen scene hash mismatch'); return
	var stage = Node3D.new()
	root.add_child(stage)
	session = Session.new()
	session.stage = stage
	root.add_child(session)
	var error = session.reopen(path,{})
	if error: finish(error); return
	session.playing = false
	var character = session.live
	var sk = I.skeleton(character)
	var cloth = character.get_node_or_null('ClothSolver')
	var runner = character.get_node_or_null('LayeringPlayer')
	if sk == null or cloth == null or runner == null: finish('Expected complete animated cloth character'); return
	var mode = str(config.get('mode','replay'))
	if mode not in ['realtime','replay']: finish('Choose realtime or replay'); return
	if mode == 'replay' and cloth.cache.get('key','') != cloth.expected_key: finish('Matching cloth cache required'); return
	cloth.mode = mode
	cloth.last_time = -1
	var hip_y = I.decode(cloth.profile.bones[int(cloth.profile.mapping.hips)].global_rest).origin.y
	var knee_y = I.decode(cloth.profile.bones[int(cloth.profile.mapping.shin_l)].global_rest).origin.y
	var surfaces = []
	var triangle_count = 0
	for part in character.find_children('*','MeshInstance3D',true,false):
		if part.name == 'Garment' or part.skin == null or part.get_node_or_null(part.skeleton) != sk or not Export.visible_part(part,character): continue
		if not I.node_transform(part).is_equal_approx(Transform3D.IDENTITY): finish('Body transform needs explicit normalization'); return
		var frozen = Export.frozen_mesh(part)
		if frozen.has('error'): finish(frozen.error); return
		for surface in frozen.mesh.get_surface_count():
			var arrays = frozen.mesh.surface_get_arrays(surface)
			var vertices = arrays[Mesh.ARRAY_VERTEX]
			var indices = arrays[Mesh.ARRAY_INDEX]
			if indices == null or indices.is_empty():
				indices = PackedInt32Array()
				for vertex in vertices.size(): indices.append(vertex)
			var selected = PackedInt32Array()
			var used = {}
			for triangle in range(0,indices.size(),3):
				var center = (vertices[indices[triangle]]+vertices[indices[triangle+1]]+vertices[indices[triangle+2]])/3.0
				if center.y <= knee_y-.12 or center.y >= hip_y-.10: continue
				for corner in 3: selected.append(indices[triangle+corner]); used[indices[triangle+corner]] = true
			if selected.is_empty(): continue
			var influences = int(arrays[Mesh.ARRAY_WEIGHTS].size()/vertices.size())
			if influences not in [4,8]: finish('Unsupported body Skin influence count'); return
			triangle_count += selected.size()/3
			surfaces.append({'arrays':arrays,'indices':selected,'used':used.keys(),'skin':part.skin,'influences':influences,'part':str(part.name)})
	if triangle_count == 0: finish('No actual body triangles in declared band'); return
	var player = runner.get_node(runner.player_path)
	var duration = player.get_animation(runner.animation_name).length
	var frames = ceili(duration*60)
	var crossings = []
	var worst = 0
	var total_edges = 0
	var character_id = character.get_instance_id()
	for frame in frames:
		session.clock_seconds = frame/60.0
		session.evaluate(0.0 if frame == 0 else 1.0/60.0)
		if runner.result.has('error') or cloth.result.has('error'): finish('Integrated animation/cloth evaluation failed'); return
		if session.live.get_instance_id() != character_id: finish('Character instance changed during measurement'); return
		var bvh = cloth.visual.mesh.generate_triangle_mesh()
		var count = 0
		for surface in surfaces:
			var arrays = surface.arrays
			var skin = surface.skin
			var transforms = []
			for bind in skin.get_bind_count():
				var bone = skin.get_bind_bone(bind)
				if skin.get_bind_name(bind) != '': bone = sk.find_bone(skin.get_bind_name(bind))
				if bone < 0 or bone >= sk.get_bone_count(): finish('Body Skin binding changed'); return
				transforms.append(sk.get_bone_global_pose(bone)*skin.get_bind_pose(bind))
			var posed = {}
			for vertex in surface.used:
				var value = Vector3.ZERO
				for influence in surface.influences:
					var offset = vertex*surface.influences+influence
					var weight = arrays[Mesh.ARRAY_WEIGHTS][offset]
					if weight > 0: value += (transforms[arrays[Mesh.ARRAY_BONES][offset]]*arrays[Mesh.ARRAY_VERTEX][vertex])*weight
				posed[vertex] = cloth.visual.global_transform.affine_inverse()*sk.global_transform*value
			for triangle in range(0,surface.indices.size(),3):
				for edge in 3:
					var start = posed[surface.indices[triangle+edge]]
					var end = posed[surface.indices[triangle+(edge+1)%3]]
					total_edges += 1
					if start.distance_squared_to(end) > .000000001 and not bvh.intersect_segment(start,end).is_empty(): count += 1
		worst = maxi(worst,count)
		if count > 0: crossings.append({'frame':frame,'crossing_edges':count})
	report = {'schema_version':1,'source_scene_sha256':sha,'character_instance_unchanged':true,'mode':mode,'duration_seconds':duration,'frames':frames,'sample_hz':60,'triangles_per_frame':triangle_count,'tested_edges':total_edges,'worst_crossing_edges':worst,'crossing_frames':crossings,'rest_band_m':[knee_y-.12,hip_y-.10],'method':'Actual primary-body Skin triangles with current static morphs; all triangle edges intersected against actual rendered cloth BVH at every 60Hz sample. Independent auxiliary skeletons excluded.','limits':'Declared thigh/knee rest-centroid band only; finite sampled frames, not continuous collision or whole-volume certification.'}
	if FileAccess.get_sha256(path) != sha: finish('Source changed during acceptance'); return
	finish()
