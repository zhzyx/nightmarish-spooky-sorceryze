extends SceneTree
const P = preload('res://addons/ainative/cloth_panel.gd')
const I = preload('res://addons/ainative/interop.gd')
var failures = []
func check(value, label):
	if not value: failures.append(label); printerr('FAIL '+label)
func _initialize(): run.call_deferred()
func run():
	var args = OS.get_cmdline_user_args()
	var config = JSON.parse_string(FileAccess.get_file_as_string(args[0]))
	var built = P.assemble(config)
	if built.has('error'): printerr(built); quit(1); return
	root.add_child(built.scene); built.runner.playing = false
	var cloth = built.cloth; var runner = built.runner
	var error = cloth.initialize()
	if error: printerr(error); quit(1); return
	var player = runner.get_node(runner.player_path)
	var duration = player.get_animation(runner.animation_name).length
	var frames = ceili(duration*60)
	var report = {'animation':runner.animation_name,'duration':duration,'frames':frames,'source_sha256':cloth.binding.source_sha256,'binding_revision':cloth.binding.binding_revision,'modes':[],'failures':failures}
	var render_references = []
	var max_residual = 0.0
	var max_free_residual = 0.0
	var dynamic_motion = 0.0
	cloth.mode = 'bake'
	for frame in frames:
		runner.sample(frame/60.0)
		check(not cloth.result.has('error'),'bake final-pose consumption '+str(frame))
		render_references.append(cloth.rendered.duplicate())
		for i in cloth.points.size():
			check(cloth.points[i].is_finite(),'finite simulated point')
			if cloth.binding.pins[i]<1: dynamic_motion = maxf(dynamic_motion,cloth.points[i].distance_to(cloth.pin_targets[i]))
		# Every render triangle centroid and edge midpoint against animated proxies.
		var indices = cloth.binding.indices
		for t in range(0,indices.size(),3):
			var a = cloth.global_transform*cloth.rendered[int(indices[t])]
			var b = cloth.global_transform*cloth.rendered[int(indices[t+1])]
			var c = cloth.global_transform*cloth.rendered[int(indices[t+2])]
			var prescribed_boundary = false
			for corner in 3:
				var vertex = int(indices[t+corner]); var fixed = 0.0
				for k in 4: fixed += cloth.pin_weights[int(cloth.data.mapping[vertex][k])]*float(cloth.data.weights[vertex][k])*float(cloth.settings.pin_weight)
				if fixed>0: prescribed_boundary = true
			for point in [(a+b+c)/3,(a+b)/2,(b+c)/2,(c+a)/2]:
				var residual = point.distance_to(cloth.project(point,0)); max_residual = maxf(max_residual,residual)
				if not prescribed_boundary: max_free_residual = maxf(max_free_residual,residual)
	check(dynamic_motion>.01,'free particles move independently of rigid pin frame')
	report.dynamic_displacement_m = dynamic_motion; report.render_proxy_max_penetration_m = max_residual
	report.free_render_proxy_max_penetration_m = max_free_residual
	report.boundary_contact_policy = 'Triangles influenced by pinned boundary use continuous free-weight contact correction and actual-body validation; entirely free triangles use full capsule correction'
	check(max_free_residual<.003,'free render triangle proxy clearance below 3mm')
	var bake_count = cloth.cache.frames.size()
	check(bake_count==frames,'one deterministic cache sample per 60Hz frame')
	cloth.mode = 'replay'
	var replay_error = 0.0
	for frame in frames:
		runner.sample(frame/60.0)
		for i in cloth.rendered.size(): replay_error = maxf(replay_error,cloth.rendered[i].distance_to(render_references[frame][i]))
	check(replay_error<.00001,'cache reproduces render mapping exactly')
	report.replay_max_error_m = replay_error
	cloth.mode = 'realtime'; var reset_before = cloth.resets
	built.scene.position.x += 2; runner.sample(.5)
	check(cloth.resets>reset_before,'teleport reset')
	built.scene.position.x -= 2; runner.sample(.6)
	reset_before = cloth.resets; runner.sample(200)
	check(cloth.resets>reset_before,'large time jump reset')
	for lod in [1,2]:
		cloth.settings.lod = lod; check(cloth.initialize().is_empty(),'LOD initialization')
		for frame in frames: runner.sample(frame/60.0)
		report.modes.append(cloth.result.duplicate())
		check(not cloth.result.has('error'),'LOD playback '+str(lod))
	cloth.settings.lod = 0; cloth.initialize()
	var saved_cache = cloth.cache.duplicate(true)
	built.scene.set_meta('character_dna',{'revision':'changed-body','body':{'hips':1.1}})
	runner.sample(.5); check(cloth.result.has('error'),'DNA rejects current binding/cache')
	check(not cloth.initialize().is_empty(),'DNA cannot bypass refit by reinitialize')
	built.scene.remove_meta('character_dna'); cloth.initialize()
	check(cloth.cache==saved_cache,'invalid state retains previous valid cache')
	var sk = I.skeleton(built.scene); sk.scale = Vector3(1,2,1)
	runner.sample(.5); check(cloth.result.has('error'),'nonuniform scale rejected'); sk.scale = Vector3.ONE
	cloth.initialize(); cloth.mode = 'replay'
	preload('res://addons/ainative/rigging.gd').owners(built.scene,built.scene); cloth.visual.owner = null
	var path = config.output+'-saved.tscn'
	check(not FileAccess.file_exists(path),'save destination new')
	if not FileAccess.file_exists(path):
		var packed = PackedScene.new(); check(packed.pack(built.scene)==OK,'pack cloth/cache'); check(ResourceSaver.save(packed,path)==OK,'save cloth/cache')
		var reopened = I.load_scene(path); check(not reopened.has('error'),'reopen cloth/cache')
		if not reopened.has('error'):
			root.add_child(reopened.scene); var rr = reopened.scene.get_node('LayeringPlayer'); rr.playing = false; rr.sample(0)
			var rc = reopened.scene.get_node('ClothSolver'); check(not rc.result.has('error'),'reopened compatible replay'); check(rc.cache.frames.size()==frames,'cache persisted'); reopened.scene.free()
	var original_binding = JSON.parse_string(FileAccess.get_file_as_string(config.binding))
	report.source_preserved = FileAccess.get_sha256(original_binding.source)==cloth.binding.source_sha256
	check(report.source_preserved,'immutable AI source preserved')
	FileAccess.open(config.output+'-acceptance.json',FileAccess.WRITE).store_string(JSON.stringify(report,'\t'))
	print(JSON.stringify(report)); quit(0 if failures.is_empty() else 1)
