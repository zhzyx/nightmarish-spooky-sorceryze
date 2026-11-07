@tool
extends Node3D
const I = preload('res://addons/ainative/interop.gd')
var config = {}
var body: Skeleton3D
var guide_skeleton: Skeleton3D
var surface: MeshInstance3D
var head = -1
var offsets = []
var velocities = []
var previous = Vector3.ZERO
var initialized = false
var reset_count = 0
var collision_count = 0
var last_step_us = 0
var hat_mesh: MeshInstance3D
var scalp_cap: MeshInstance3D

func _ready():
	config = get_meta('hair_data',{})
	var error = load(get_script().resource_path.get_base_dir().path_join('hair.gd')).runtime_error(get_parent(),config,get_meta('authored_scalp_cap',{}))
	if error:
		set_meta('hair_error',error)
		set_process(false)
		push_error(error)
		return
	for child in get_children():
		remove_child(child)
		child.free()
	process_priority = 100
	body = I.skeleton(get_parent())
	head = body.find_bone(config.head_bone)
	guide_skeleton = Skeleton3D.new()
	guide_skeleton.name = 'HairGuideBones'
	guide_skeleton.set_meta('ainative_auxiliary_skeleton',true)
	guide_skeleton.set_meta('ainative_auxiliary_role','hair-guides-v1')
	add_child(guide_skeleton)
	for c in config.columns:
		guide_skeleton.add_bone('hair_root_'+str(c))
		guide_skeleton.add_bone('hair_tip_'+str(c))
		guide_skeleton.set_bone_parent(c*2+1,c*2)
		guide_skeleton.set_bone_rest(c*2,Transform3D(Basis.IDENTITY,point(c,0)))
		guide_skeleton.set_bone_rest(c*2+1,Transform3D(Basis.IDENTITY,point(c,config.rows-1)-point(c,0)))
		guide_skeleton.set_bone_pose_position(c*2,point(c,0))
		guide_skeleton.set_bone_pose_position(c*2+1,point(c,config.rows-1)-point(c,0))
		offsets.append(Vector3.ZERO)
		velocities.append(Vector3.ZERO)
	surface = MeshInstance3D.new()
	surface.name = 'HairSurface'
	add_child(surface)
	surface.skeleton = surface.get_path_to(guide_skeleton)
	var skin = Skin.new()
	for i in guide_skeleton.get_bone_count(): skin.add_bind(i,guide_skeleton.get_bone_global_rest(i).affine_inverse())
	surface.skin = skin
	hat_mesh = MeshInstance3D.new()
	hat_mesh.name = 'AuthoredHat'
	var cap = SphereMesh.new()
	cap.radius = .115
	cap.height = .23
	hat_mesh.mesh = cap
	hat_mesh.position = point(config.columns/2,0)+Vector3(0,.015,.035)
	var material = StandardMaterial3D.new()
	material.albedo_color = Color(.13,.2,.32)
	hat_mesh.material_override = material
	add_child(hat_mesh)
	var cap_data = get_meta('authored_scalp_cap')
	scalp_cap = MeshInstance3D.new()
	scalp_cap.name = 'AuthoredScalpCap'
	var cap_arrays = []
	cap_arrays.resize(Mesh.ARRAY_MAX)
	var cap_points = PackedVector3Array()
	for p in cap_data.vertices: cap_points.append(Vector3(p[0],p[1],p[2]))
	cap_arrays[Mesh.ARRAY_VERTEX] = cap_points
	cap_arrays[Mesh.ARRAY_INDEX] = PackedInt32Array(cap_data.indices)
	var cap_surface = ArrayMesh.new()
	cap_surface.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES,cap_arrays)
	var cap_tool = SurfaceTool.new()
	cap_tool.create_from(cap_surface,0)
	cap_tool.generate_normals()
	scalp_cap.mesh = cap_tool.commit()
	var cap_material = StandardMaterial3D.new()
	cap_material.albedo_color = Color(.12,.045,.015)
	cap_material.cull_mode = BaseMaterial3D.CULL_DISABLED
	scalp_cap.material_override = cap_material
	add_child(scalp_cap)
	# The demonstration hat follows the authored scalp cap, rather than a
	# sphere that can cover the face. The rear root mask is independent.
	hat_mesh.mesh = scalp_cap.mesh
	hat_mesh.position = Vector3(0,.004,0)
	rebuild()

func point(c: int,r: int) -> Vector3:
	var p = config.vertices[c*config.rows+r]
	return Vector3(p[0],p[1],p[2])

func configure(lod: int,cards: bool,hat: bool):
	if lod<0 or lod>2: return
	config.lod = lod
	config.cards = cards
	config.hat = hat
	set_meta('hair_data',config)
	rebuild()

func rebuild():
	var arrays = []
	arrays.resize(Mesh.ARRAY_MAX)
	var vertices = PackedVector3Array()
	var bones = PackedInt32Array()
	var weights = PackedFloat32Array()
	var indices = PackedInt32Array()
	var colors = PackedColorArray()
	var step = [1,2,4][config.lod]
	for c in config.columns:
		for r in config.rows:
			vertices.append(point(c,r))
			var t = float(r)/(config.rows-1)
			bones.append_array(PackedInt32Array([c*2,c*2+1,0,0]))
			weights.append_array(PackedFloat32Array([1-t,t,0,0]))
			colors.append(Color(.12,.045,.015).lightened(.13*float(c%3)))
	for c in range(0,config.columns-1,step):
		var next = mini(c+step,config.columns-1)
		for r in range(0,config.rows-1,step):
			# Crown-only hat mask: preserve the visible lower rear hair.
			if config.hat and r<config.rows/8: continue
			var end = mini(r+step,config.rows-1)
			var a = c*config.rows+r
			var b = next*config.rows+r
			var d = c*config.rows+end
			var e = next*config.rows+end
			if config.cards:
				# Independent planar ribbon quads retain complete silhouette at
				# coarse LOD. They approximate source curvature without holes.
				var first = vertices.size()
				for pair in [[c,r],[next,r],[c,end],[next,end]]:
					var p = point(pair[0],pair[1])
					p.z = (point(c,pair[1]).z+point(next,pair[1]).z)*.5
					vertices.append(p)
					var t = float(pair[1])/(config.rows-1)
					bones.append_array(PackedInt32Array([pair[0]*2,pair[0]*2+1,0,0]))
					weights.append_array(PackedFloat32Array([1-t,t,0,0]))
					colors.append(Color(.12,.045,.015).lightened(.06*float((c/step)%3)))
				indices.append_array(PackedInt32Array([first,first+1,first+2,first+1,first+3,first+2]))
			else: indices.append_array(PackedInt32Array([a,b,d,b,e,d]))
	arrays[Mesh.ARRAY_VERTEX] = vertices
	arrays[Mesh.ARRAY_BONES] = bones
	arrays[Mesh.ARRAY_WEIGHTS] = weights
	arrays[Mesh.ARRAY_INDEX] = indices
	arrays[Mesh.ARRAY_COLOR] = colors
	var mesh = ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES,arrays)
	var surface_tool = SurfaceTool.new()
	surface_tool.create_from(mesh,0)
	surface_tool.generate_normals()
	mesh = surface_tool.commit()
	var material = StandardMaterial3D.new()
	material.vertex_color_use_as_albedo = true
	material.cull_mode = BaseMaterial3D.CULL_DISABLED
	material.roughness = .8
	mesh.surface_set_material(0,material)
	surface.mesh = mesh
	hat_mesh.visible = config.hat
	scalp_cap.visible = not config.hat
	set_meta('triangle_count',indices.size()/3)

func _process(delta):
	if not is_instance_valid(body) or head<0: return
	if config.scalp_revision!=get_parent().get_meta('scalp_binding',{}).get('revision'):
		set_meta('hair_error','头皮已改变；请重新绑定头发。')
		set_process(false)
		return
	var start = Time.get_ticks_usec()
	body.force_update_all_bone_transforms()
	global_transform = body.global_transform*body.get_bone_global_pose(head)
	var displacement = global_position-previous
	var reset = not initialized or displacement.length()>.4 or delta>.15
	if reset:
		reset_count += 1
		for c in config.columns:
			offsets[c] = Vector3.ZERO
			velocities[c] = Vector3.ZERO
	previous = global_position
	initialized = true
	var dt = clampf(delta,0,.033333)
	var colliders = []
	var mapping = get_parent().get_meta('face_binding',{}).get('body_mapping',{})
	for key in ['head','neck','upper_arm_l','upper_arm_r']:
		var index = body.find_bone(mapping.get(key,''))
		if index>=0: colliders.append([to_local(body.global_transform*body.get_bone_global_pose(index).origin),.10 if key=='head' else .075])
	for c in config.columns:
		if not reset: velocities[c] -= global_basis.inverse()*displacement*3.0
		velocities[c] += (-offsets[c]*38.0-velocities[c]*9.0)*dt
		offsets[c] += velocities[c]*dt
		offsets[c] = offsets[c].limit_length(.065)
		var rest = point(c,config.rows-1)
		var tip = rest+offsets[c]
		for sphere in colliders:
			var away = tip-sphere[0]
			if away.length()<sphere[1]:
				tip = sphere[0]+(away.normalized() if away.length()>.00001 else Vector3.BACK)*sphere[1]
				collision_count += 1
			offsets[c] = (tip-rest).limit_length(.15)
		guide_skeleton.set_bone_pose_position(c*2+1,guide_skeleton.get_bone_rest(c*2+1).origin+offsets[c])
	last_step_us = Time.get_ticks_usec()-start
