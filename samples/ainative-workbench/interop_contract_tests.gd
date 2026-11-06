extends SceneTree
const I = preload('res://addons/ainative/interop.gd')
const Rig = preload('res://addons/ainative/rigging.gd')
var failures = []

func check(value: bool, label: String):
	if not value: failures.append(label)

func _initialize(): run.call_deferred()

func run():
	var scene = Node3D.new()
	root.add_child(scene)
	var sk = Skeleton3D.new()
	sk.name = 'Skeleton3D'
	scene.add_child(sk)
	for name in Rig.NAMES: sk.add_bone(name)
	for i in Rig.NAMES.size():
		sk.set_bone_parent(i,Rig.PARENTS[i])
		sk.set_bone_rest(i,Transform3D(Basis.IDENTITY,Vector3(0,.1,0)))
	sk.reset_bone_poses()
	var result = I.extract(scene,'anatomical',{'sha256':'a'.repeat(64),'version':'test-only','authority':'fixture:synthetic-contract'})
	check(result.has('profile'),'extract fixture')
	if not result.has('profile'): print(JSON.stringify(result)); quit(1); return
	var p = result.profile
	check(I.validate(p)=='','valid profile')
	check(I.validate(JSON.parse_string(JSON.stringify(p,'',true,true)))=='','profile JSON roundtrip revision')
	check(I.revision({'value':1})!=I.revision({'value':{'number':'1'}}),'revision type collision rejected')
	var floating = {'values':Array(PackedFloat32Array([1.13686837721616e-13,-0.000048637829,1.23456789,-.002196347]))}
	var expected_revision = I.revision(floating)
	for i in 10:
		floating = JSON.parse_string(JSON.stringify(floating,'',true,true))
		check(I.revision(floating)==expected_revision,'engine float bits survive JSON reopening')
	var invalid_coordinates = p.duplicate(true)
	invalid_coordinates.coordinates.units = 'centimetres'
	invalid_coordinates.revision = I.revision(invalid_coordinates)
	check(I.validate(invalid_coordinates)!='','unsupported coordinate convention rejected')
	var invalid_mapping = p.duplicate(true)
	invalid_mapping.mapping.foot_l = invalid_mapping.mapping.foot_r
	invalid_mapping.revision = I.revision(invalid_mapping)
	check(I.validate(invalid_mapping)!='','overlapping bilateral semantics rejected')
	scene.scale = Vector3(2,2,2)
	check(I.extract(scene,'anatomical',p.source).has('error'),'unbaked ancestor scale rejected')
	scene.scale = Vector3.ONE
	check(I.semantic('mixamorig:LeftHandIndex1','mixamo')=='index_1_l','namespace finger semantics')
	check(I.semantic('upperarm_twist_01_l','ue5_manny')=='','twist explicit auxiliary')
	check(I.semantic('spine_04','ue5_manny')=='chest','Manny versioned spine')
	check(I.semantic('spine_02','ue4')=='chest','UE4 independent spine')
	var changed = p.duplicate(true)
	changed.bones[0].local_rest[9] += .01
	check(I.validate(changed)!='','stale revision rejected')
	changed = p.duplicate(true)
	changed.bones[0].parent = 0
	changed.revision = I.revision(changed)
	check(I.validate(changed)!='','cyclic skeleton rejected')
	var animation = Animation.new()
	animation.length = 1
	var track = animation.add_track(Animation.TYPE_POSITION_3D)
	animation.track_set_path(track,NodePath('Skeleton3D:root'))
	animation.position_track_insert_key(track,0,Vector3(0,.1,0))
	animation.position_track_insert_key(track,1,Vector3(1,.1,0))
	var retargeted = I.retarget(animation,p,p,10)
	check(I.retarget(animation,p,p,NAN).has('error'),'nonfinite FPS rejected')
	check(I.retarget(animation,p,p,30,[1]).has('error'),'invalid contact shape rejected')
	check(I.retarget(animation,p,p,30,[{'side':'l','start':0,'end':1,'position_m':[0]}]).has('error'),'short contact vector rejected')
	check(retargeted.has('animation'),'self retarget')
	if retargeted.has('animation'):
		var converted = retargeted.animation
		var root_track = converted.find_track(NodePath('Skeleton3D:root'),Animation.TYPE_POSITION_3D)
		check(converted.position_track_interpolate(root_track,1).distance_to(Vector3(1,.1,0))<.00001,'root motion conserved')
		var reverse = I.retarget(converted,p,p,10)
		check(reverse.animation.position_track_interpolate(root_track,1).distance_to(Vector3(1,.1,0))<.00001,'reverse root motion conserved')
	var mesh = ArrayMesh.new()
	var arrays = []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = PackedVector3Array([Vector3.ZERO,Vector3.RIGHT,Vector3.UP])
	arrays[Mesh.ARRAY_BONES] = PackedInt32Array([0,0,0,0,0,0,0,0,0,0,0,0])
	arrays[Mesh.ARRAY_WEIGHTS] = PackedFloat32Array([1,0,0,0,1,0,0,0,1,0,0,0])
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES,arrays)
	var body = MeshInstance3D.new()
	body.mesh = mesh
	body.skin = Skin.new()
	body.skin.add_bind(0,sk.get_bone_global_rest(0).affine_inverse()*Transform3D(Basis.IDENTITY,Vector3(.3,0,0)))
	scene.add_child(body)
	body.skeleton = body.get_path_to(sk)
	var rebound = I.bind(scene,p,p)
	check(rebound.has('scene'),'noncanonical source Skin binding accepted')
	if rebound.has('scene'):
		var out_mesh = rebound.scene.find_children('*','MeshInstance3D',true,false)[0]
		var points = out_mesh.mesh.surface_get_arrays(0)[Mesh.ARRAY_VERTEX]
		check(points[0].distance_to(Vector3(.3,0,0))<.00001,'actual source inverse bind rest deformation preserved')
		rebound.scene.free()
	var baked_transform = Transform3D(Basis(Vector3.FORWARD,.4).scaled(Vector3.ONE*2),Vector3(0,.5,0))
	scene.transform = baked_transform
	check(I.normalize_imported(scene)=='','uniform imported ancestor transform baked')
	var normalized = I.extract(scene,'anatomical',p.source)
	check(normalized.has('profile'),'normalized source profile')
	if normalized.has('profile'):
		var baked = I.bind(scene,normalized.profile,normalized.profile)
		check(baked.has('scene'),'normalized source bind')
		if baked.has('scene'):
			var vertices = baked.scene.find_children('*','MeshInstance3D',true,false)[0].mesh.surface_get_arrays(0)[Mesh.ARRAY_VERTEX]
			check(vertices[0].distance_to(baked_transform*Vector3(.3,0,0))<.00001,'baked source preserves actual transformed rest')
			baked.scene.free()
	scene.free()
	print(JSON.stringify({'synthetic_contract_tests_only':true,'failures':failures}))
	quit(0 if failures.is_empty() else 1)
