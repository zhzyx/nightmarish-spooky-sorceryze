extends SceneTree
const P = preload('res://addons/ainative/cloth_panel.gd')
const I = preload('res://addons/ainative/interop.gd')
func _initialize(): run.call_deferred()
func run():
	var config = JSON.parse_string(FileAccess.get_file_as_string(OS.get_cmdline_user_args()[0]))
	var built = P.assemble(config)
	if built.has('error'): printerr(built); quit(1); return
	root.add_child(built.scene); built.runner.playing = false
	var sk = I.skeleton(built.scene); var cloth = built.cloth; var runner = built.runner
	var hip_y = sk.get_bone_global_rest(int(cloth.profile.mapping.hips)).origin.y
	var knee_y = sk.get_bone_global_rest(int(cloth.profile.mapping.shin_l)).origin.y
	var surfaces = []; var triangles = 0
	for mi in built.scene.find_children('*','MeshInstance3D',true,false):
		if mi.name=='Garment' or mi.skin==null: continue
		for si in mi.mesh.get_surface_count():
			var a = mi.mesh.surface_get_arrays(si)
			var indices = a[Mesh.ARRAY_INDEX]; var verts = a[Mesh.ARRAY_VERTEX]
			var selected = PackedInt32Array(); var used = {}
			for t in range(0,indices.size(),3):
				var center = (verts[indices[t]]+verts[indices[t+1]]+verts[indices[t+2]])/3
				var in_band = center.y>knee_y-.12 and center.y<hip_y-.10 if cloth.binding.kind=='skirt' else center.y>1.2
				if in_band:
					for k in 3: selected.append(indices[t+k]); used[indices[t+k]] = true
			triangles += selected.size()/3
			surfaces.append({'arrays':a,'indices':selected,'used':used.keys(),'skin':mi.skin})
	var player = runner.get_node(runner.player_path)
	var frames = ceili(player.get_animation(runner.animation_name).length*60)
	var worst = 0; var crossing_frames = []; var total_edges = 0
	for frame in frames:
		runner.sample(frame/60.0)
		var bvh = cloth.visual.mesh.generate_triangle_mesh()
		var crossings = 0
		for surface in surfaces:
			var a = surface.arrays; var skin = surface.skin; var transforms = []
			for bind in skin.get_bind_count(): transforms.append(sk.get_bone_global_pose(skin.get_bind_bone(bind))*skin.get_bind_pose(bind))
			var posed = {}
			for vertex in surface.used:
				var value = Vector3.ZERO
				for k in 4:
					var weight = a[Mesh.ARRAY_WEIGHTS][vertex*4+k]
					if weight>0: value += (transforms[a[Mesh.ARRAY_BONES][vertex*4+k]]*a[Mesh.ARRAY_VERTEX][vertex])*weight
				posed[vertex] = cloth.global_transform.affine_inverse()*sk.global_transform*value
			for t in range(0,surface.indices.size(),3):
				for k in 3:
					var start = posed[surface.indices[t+k]]; var end = posed[surface.indices[t+(k+1)%3]]
					total_edges += 1
					if start.distance_squared_to(end)>.000000001 and not bvh.intersect_segment(start,end).is_empty(): crossings += 1
		worst = maxi(worst,crossings)
		if crossings>0: crossing_frames.append({'frame':frame,'crossing_edges':crossings})
	var report = {'method':'all edges of actual skinned body triangles in declared rest band against actual rendered cloth triangle BVH, every 60Hz frame','triangles_per_frame':triangles,'frames':frames,'tested_edges':total_edges,'worst_crossing_edges':worst,'crossing_frames':crossing_frames,'scope':'thigh/knee band knee_y-0.12 to hip_y-0.10' if cloth.binding.kind=='skirt' else 'upper-body rest centroid y>1.2m; includes shoulder/back, not whole-body certification'}
	FileAccess.open(config.output+'-body-intersections.json',FileAccess.WRITE).store_string(JSON.stringify(report,'\t'))
	print(JSON.stringify(report)); quit(0 if worst==0 else 1)
