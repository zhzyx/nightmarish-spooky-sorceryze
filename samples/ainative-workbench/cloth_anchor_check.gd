extends SceneTree
const P = preload('res://addons/ainative/cloth_panel.gd')
const I = preload('res://addons/ainative/interop.gd')
func _initialize(): run.call_deferred()
func body_faces(scene, sk):
	var faces = []
	for mi in scene.find_children('*','MeshInstance3D',true,false):
		if mi.skin==null or mi.name=='Garment': continue
		var transforms = []
		for bind in mi.skin.get_bind_count(): transforms.append(sk.get_bone_global_pose(mi.skin.get_bind_bone(bind))*mi.skin.get_bind_pose(bind))
		for si in mi.mesh.get_surface_count():
			var a = mi.mesh.surface_get_arrays(si); var vertices = a[Mesh.ARRAY_VERTEX]; var indices = a[Mesh.ARRAY_INDEX]
			var posed = []
			for i in vertices.size():
				var value = Vector3.ZERO
				for k in 4:
					var weight = a[Mesh.ARRAY_WEIGHTS][i*4+k]
					if weight>0: value += transforms[a[Mesh.ARRAY_BONES][i*4+k]]*vertices[i]*weight
				posed.append(sk.global_transform*value)
			for t in range(0,indices.size(),3):
				var center = (vertices[indices[t]]+vertices[indices[t+1]]+vertices[indices[t+2]])/3
				if center.y<1.2: continue
				for k in 3:
					var v = posed[indices[t+k]]; faces.append([v.x,v.y,v.z])
	return faces
func run():
	var config = JSON.parse_string(FileAccess.get_file_as_string(OS.get_cmdline_user_args()[0]))
	var built = P.assemble(config)
	if built.has('error'): printerr(built); quit(1); return
	root.add_child(built.scene); built.runner.playing = false
	var sk = I.skeleton(built.scene); var cloth = built.cloth
	sk.reset_bone_poses(); var rest_faces = body_faces(built.scene,sk)
	built.runner.sample(119.0/60)
	var pins = []; var targets = []; var pin_error = 0.0; var rest_pins = []
	for i in cloth.rest.size():
		if cloth.pin_weights[i]>0:
			var point = cloth.points[i]; pins.append([point.x,point.y,point.z])
			var target = cloth.pin_targets[i]; targets.append([target.x,target.y,target.z])
			var rest = cloth.rest[i]; rest_pins.append([rest.x,rest.y,rest.z])
			pin_error = maxf(pin_error,point.distance_to(target))
	var top = []; var max_y = -INF
	for v in cloth.binding.vertices: max_y = maxf(max_y,v[1])
	for i in cloth.binding.vertices.size():
		if absf(cloth.binding.vertices[i][1]-max_y)<.00001:
			var point = cloth.global_transform*cloth.rendered[i]; top.append([point.x,point.y,point.z])
	var report = {'pose_time':119.0/60,'pin_target_max_error_m':pin_error,'pins':pins,'targets':targets,'rest_pins':rest_pins,'render_top':top,'body_faces':body_faces(built.scene,sk),'rest_body_faces':rest_faces,'profile_revision':cloth.profile.revision,'source_scene_sha256':FileAccess.get_sha256(config.scene)}
	FileAccess.open(config.output+'-anchor-geometry.json',FileAccess.WRITE).store_string(JSON.stringify(report))
	print(JSON.stringify({'pins':pins.size(),'render_top':top.size(),'pin_target_max_error_m':pin_error,'output':config.output+'-anchor-geometry.json'})); quit()
