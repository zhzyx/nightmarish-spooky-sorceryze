extends SceneTree
const C = preload('res://addons/ainative/customization.gd')
const I = preload('res://addons/ainative/interop.gd')
func _initialize(): run.call_deferred()
func run():
	var args = OS.get_cmdline_user_args()
	assert(args.size()==2)
	var config = JSON.parse_string(FileAccess.get_file_as_string(args[0]))
	assert(not FileAccess.file_exists(args[1]))
	var loaded = I.load_scene(config.asset)
	assert(not loaded.has('error'))
	var scene = loaded.scene
	root.add_child(scene)
	var binding = JSON.parse_string(FileAccess.get_file_as_string(config.binding))
	scene.set_meta('face_binding',binding)
	var receipts = []
	for sign_value in [-1,1]:
		var dna = C.dna(binding.source_sha256,{'chest':1+sign_value*.2,'waist':1+sign_value*.2,'hips':1+sign_value*.2,'depth':1+sign_value*.2},{'face_width':sign_value*.5,'jaw_width':sign_value*.5,'nose_width':sign_value*.5},binding.mapping_version)
		var result = C.apply_face(scene,dna,[{'id':'boundary-manual','channels':{'jawOpen':1,'mouthSmile':1,'lookLeft':1,'eyeBlink':1}}])
		assert(not result.has('error'),str(result))
		var rest = scene.get_meta('scalp_binding').revision
		var pose = scene.get_meta('scalp_binding').pose_revision
		var vertices = 0
		var max_delta = 0.0
		for mi in scene.find_children('*','MeshInstance3D',true,false):
			var baked = mi.bake_mesh_from_current_blend_shape_mix()
			for surface in baked.get_surface_count():
				var actual = baked.surface_get_arrays(surface)[Mesh.ARRAY_VERTEX]
				var original = mi.mesh.surface_get_arrays(surface)[Mesh.ARRAY_VERTEX]
				assert(actual.size()==original.size())
				for i in actual.size():
					assert(actual[i].is_finite())
					max_delta = maxf(max_delta,actual[i].distance_to(original[i]))
					vertices += 1
		assert(vertices>10000 and max_delta>.01 and max_delta<.3,'Boundary geometry missing or exploded')
		result = C.apply_face(scene,dna,[])
		assert(not result.has('error'))
		assert(rest==scene.get_meta('scalp_binding').revision,'Expression invalidated rest binding')
		assert(pose!=scene.get_meta('scalp_binding').pose_revision,'Expression pose revision did not update')
		receipts.append({'sign':sign_value,'vertices':vertices,'max_morph_displacement_m':max_delta,'rest_binding_stable_under_expression':true})
	var file = FileAccess.open(args[1],FileAccess.WRITE)
	file.store_string(JSON.stringify({'asset_sha256':FileAccess.get_sha256(config.asset),'boundary_geometry':receipts},'\t'))
	file.close()
	print('Real Rain boundary geometry and split scalp revisions passed')
	quit()
