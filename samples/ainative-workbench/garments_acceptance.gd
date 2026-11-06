extends SceneTree
const Garments = preload('res://addons/ainative/garments.gd')
const Interop = preload('res://addons/ainative/interop.gd')
var failures = []
func _initialize(): run.call_deferred()
func check(value: bool, label: String):
	print(('PASS ' if value else 'FAIL ')+label)
	if not value: failures.append(label)
func run():
	var args = OS.get_cmdline_user_args()
	if args.size()!=1: printerr('Expected private config JSON'); quit(2); return
	var config = JSON.parse_string(FileAccess.get_file_as_string(args[0]).trim_prefix('\ufeff'))
	if not config is Dictionary or FileAccess.file_exists(config.receipt): quit(2); return
	var external_json = JSON.stringify({'asset':{'version':'2.0'},'buffers':[{'uri':'mutable.bin','byteLength':4}]}).to_utf8_buffer()
	while external_json.size()%4: external_json.append(32)
	var external_glb = PackedByteArray()
	external_glb.resize(20)
	external_glb.encode_u32(0,0x46546c67)
	external_glb.encode_u32(4,2)
	external_glb.encode_u32(8,20+external_json.size())
	external_glb.encode_u32(12,external_json.size())
	external_glb.encode_u32(16,0x4e4f534a)
	external_glb.append_array(external_json)
	var external_path = config.output_dir.path_join('external-dependency-negative.glb')
	if FileAccess.file_exists(external_path): quit(2); return
	var external_file = FileAccess.open(external_path,FileAccess.WRITE)
	external_file.store_buffer(external_glb)
	external_file.close()
	check(Garments.source_bytes(external_path,FileAccess.get_sha256(external_path)).has('error'),'reject external GLB dependency with matching container hash')
	var report = {'scope':'binding, provenance and replay contracts only; not visual/business acceptance','visual_status':config.get('visual_status','requires_review'),'cases':[],'failures':failures}
	for target in config.targets:
		var loaded = Interop.load_scene(target.path)
		if loaded.has('error'): failures.append(loaded.error); continue
		root.add_child(loaded.scene)
		var extracted = Interop.extract(loaded.scene,target.family,{'sha256':FileAccess.get_sha256(target.path),'version':target.version,'authority':target.authority})
		if extracted.has('error'): failures.append(extracted.error); loaded.scene.free(); continue
		var profile = extracted.profile
		var aligned_normals = 0
		var opposite_normals = 0
		for mi in loaded.scene.find_children('*','MeshInstance3D',true,false):
			for si in mi.mesh.get_surface_count():
				var original_arrays = mi.mesh.surface_get_arrays(si)
				var original_normals = original_arrays[Mesh.ARRAY_NORMAL]
				var recomputed = Garments.normal_arrays(original_arrays)[Mesh.ARRAY_NORMAL]
				for vi in recomputed.size():
					if recomputed[vi].dot(original_normals[vi])>0: aligned_normals+=1
					elif recomputed[vi].dot(original_normals[vi])<0: opposite_normals+=1
		check(aligned_normals>opposite_normals*10,'derived normals preserve actual imported outward orientation')
		var tampered = loaded.scene.duplicate()
		var tampered_sk = Interop.skeleton(tampered)
		tampered_sk.set_bone_parent(int(profile.mapping.head),int(profile.mapping.hips))
		var first_source = config.garments[0]
		var tampered_result = Garments.fit(first_source.path,first_source.spec,tampered,profile,{})
		check(tampered_result.has('error'),'reject parent-only hierarchy tampering')
		if tampered_result.has('scene'): tampered_result.scene.free()
		tampered.free()
		for source in config.garments:
			var before = FileAccess.get_sha256(source.path)
			var base_vertices = PackedVector3Array()
			for shape_index in 2:
				var shape = {} if shape_index==0 else {'chest':1.15,'waist':.9,'hips':1.1,'depth':1.15}
				var built = Garments.fit(source.path,source.spec,loaded.scene,profile,shape)
				check(not built.has('error'),'fit '+target.family+'/'+source.spec.kind+'/'+str(shape_index))
				if built.has('error'): printerr(built.error); continue
				root.add_child(built.scene)
				var garment = built.scene.get_node('Garment')
				var partitions = built.manifest.partitions
				check(partitions.rigid.size()+partitions.skinned.size()+partitions.cloth.size()==built.manifest.vertices,'complete vertex partition')
				check(built.manifest.avatar_profile_revision==profile.revision,'immutable Profile fit provenance')
				if source.spec.kind=='skirt':
					check(not partitions.cloth.is_empty() and built.manifest.auxiliary_bone>=profile.bones.size(),'cloth region and accessory bone')
					check(built.manifest.cloth_solver.begins_with('none'),'no solver claim')
				if source.spec.kind=='armor': check(partitions.rigid.size()==built.manifest.vertices,'rigid armor partition')
				for si in garment.mesh.get_surface_count():
					var a = garment.mesh.surface_get_arrays(si)
					var valid_weights = true
					for vi in a[Mesh.ARRAY_VERTEX].size():
						var total = 0.0
						for j in 4: total += a[Mesh.ARRAY_WEIGHTS][vi*4+j]
						# ArrayMesh packs four weights as UNORM16; each loses at most 1/65535.
						if absf(total-1)>4.0/65535.0+.000001: valid_weights = false
					check(valid_weights,'normalized binding weights')
				var vertices = garment.mesh.surface_get_arrays(0)[Mesh.ARRAY_VERTEX]
				var shape_delta = 0.0
				if shape_index==0: base_vertices = vertices
				else:
					for i in vertices.size(): shape_delta = maxf(shape_delta,vertices[i].distance_to(base_vertices[i]))
					check(shape_delta>.001,'actual chest/waist/hips/depth vertex difference')
				var sk = Interop.skeleton(built.scene)
				var rest_positions = posed_vertices(garment,sk)
				var bone = int(profile.mapping.hips) if source.spec.kind=='skirt' else int(profile.mapping.get('chest',profile.mapping.hips))
				sk.set_bone_pose_rotation(bone,sk.get_bone_rest(bone).basis.get_rotation_quaternion()*Quaternion(Vector3.UP,.4))
				var posed = posed_vertices(garment,sk)
				var movement = 0.0
				for i in posed.size(): movement = maxf(movement,posed[i].distance_to(rest_positions[i]))
				check(movement>.001,'actual skinned garment deformation')
				var output = config.output_dir.path_join(target.family+'-'+source.spec.kind+'-'+str(shape_index)+'.tscn')
				check(Garments.stage(built.scene,output)=='','stage independent assembly')
				var reopened = Interop.load_scene(output)
				check(not reopened.has('error'),'reopen independent assembly')
				if reopened.has('scene'):
					root.add_child(reopened.scene)
					var reopen_garment = reopened.scene.get_node('Garment')
					check(binding_matches(garment,reopen_garment),'reopened complete mesh weights and Skin binds retained')
					var reopened_manifest = reopened.scene.get_meta('garment',{})
					check(reopened_manifest.get('revision')==built.manifest.revision and Interop.revision(reopened_manifest)==built.manifest.revision,'reopened canonical immutable manifest and revision')
					var extension = built.manifest.skeleton_extension
					check(Interop.skeleton(reopened.scene).get_bone_count()==profile.bones.size()+extension.bones.size(),'reopened exact base plus extension bone count')
					var reopen_sk = Interop.skeleton(reopened.scene)
					var bones_match = true
					var definitions = profile.bones+extension.bones
					for i in definitions.size():
						if reopen_sk.get_bone_name(i)!=definitions[i].name or reopen_sk.get_bone_parent(i)!=int(definitions[i].parent) or not reopen_sk.get_bone_rest(i).is_equal_approx(Interop.decode(definitions[i].local_rest)): bones_match = false
					check(bones_match,'reopened base and accessory bone definitions retained')
					reopen_sk.reset_bone_poses()
					var reopened_rest = posed_vertices(reopen_garment,reopen_sk)
					reopen_sk.set_bone_pose_rotation(bone,reopen_sk.get_bone_rest(bone).basis.get_rotation_quaternion()*Quaternion(Vector3.UP,.4))
					var reopened_posed = posed_vertices(reopen_garment,reopen_sk)
					var replay_error = 0.0
					for vi in reopened_posed.size(): replay_error = maxf(replay_error,maxf(reopened_posed[vi].distance_to(posed[vi]),reopened_rest[vi].distance_to(rest_positions[vi])))
					check(replay_error<.00001,'reopened same action skin deformation matches')
					check(extension.combined_revision==Interop.revision({'base_profile_revision':profile.revision,'bones':extension.bones}),'combined skeleton revision reproducible')
					var repeat = Garments.fit(source.path,source.spec,reopened.scene,profile,shape)
					check(repeat.has('error'),'refuse accumulating garments or accessory bones on derived avatar')
					if repeat.has('scene'): repeat.scene.free()
					reopened.scene.free()
				var output_hash = FileAccess.get_sha256(output)
				check(Garments.stage(built.scene,output)!='' and FileAccess.get_sha256(output)==output_hash,'no overwrite')
				check(FileAccess.get_sha256(source.path)==before,'generated source bytes preserved')
				report.cases.append({'family':target.family,'kind':source.spec.kind,'shape':shape,'shape_vertex_delta_m':shape_delta,'animation_vertex_delta_m':movement,'output':output,'sha256':output_hash,'manifest':built.manifest})
				built.scene.free()
			var invalid = Garments.fit(source.path,source.spec,loaded.scene,profile,{'chest':1.5})
			check(invalid.has('error'),'out of envelope explicit failure')
			if invalid.has('scene'): invalid.scene.free()
		loaded.scene.free()
	var file = FileAccess.open(config.receipt,FileAccess.WRITE)
	file.store_string(JSON.stringify(report,'  ',true,true))
	file.close()
	quit(0 if failures.is_empty() else 1)

static func binding_matches(a: MeshInstance3D, b: MeshInstance3D) -> bool:
	if a.skeleton!=b.skeleton or a.skin==null or b.skin==null or a.skin.get_bind_count()!=b.skin.get_bind_count() or a.mesh.get_surface_count()!=b.mesh.get_surface_count(): return false
	for i in a.skin.get_bind_count():
		if a.skin.get_bind_bone(i)!=b.skin.get_bind_bone(i) or a.skin.get_bind_name(i)!=b.skin.get_bind_name(i) or not a.skin.get_bind_pose(i).is_equal_approx(b.skin.get_bind_pose(i)): return false
	for i in a.mesh.get_surface_count():
		var aa = a.mesh.surface_get_arrays(i)
		var ba = b.mesh.surface_get_arrays(i)
		for field in [Mesh.ARRAY_VERTEX,Mesh.ARRAY_INDEX,Mesh.ARRAY_BONES,Mesh.ARRAY_WEIGHTS]:
			if aa[field]!=ba[field]: return false
	return true

static func posed_vertices(mi: MeshInstance3D, sk: Skeleton3D) -> PackedVector3Array:
	var output = PackedVector3Array()
	for si in mi.mesh.get_surface_count():
		var a = mi.mesh.surface_get_arrays(si)
		for i in a[Mesh.ARRAY_VERTEX].size():
			var value = Vector3.ZERO
			for j in 4:
				var index = a[Mesh.ARRAY_BONES][i*4+j]
				value += (Interop.pose_global(sk,index)*mi.skin.get_bind_pose(index)*a[Mesh.ARRAY_VERTEX][i])*a[Mesh.ARRAY_WEIGHTS][i*4+j]
			output.append(value)
	return output
