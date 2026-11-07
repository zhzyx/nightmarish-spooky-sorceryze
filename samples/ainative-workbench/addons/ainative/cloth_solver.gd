@tool
extends Node3D
# Independently implemented XPBD distance constraints (Macklin et al., 2016).
# World-space particles, meter rest data; consumes final_body_pose, never writes bones.
const I = preload('res://addons/ainative/interop.gd')
const G = preload('res://addons/ainative/garments.gd')
@export var binding: Dictionary = {}
@export var profile: Dictionary = {}
@export var settings: Dictionary = {'mass':0.15,'compliance':0.000001,'pin_weight':1.0,'lod':0}
@export var skeleton_path: NodePath
@export var layering_path: NodePath
@export var mode: String = 'realtime'
@export var cache: Dictionary = {}
@export var identity: Dictionary = {}
var points = PackedVector3Array()
var previous = PackedVector3Array()
var rest = PackedVector3Array()
var pin_targets = PackedVector3Array()
var lengths = PackedFloat32Array()
var invmass = PackedFloat32Array()
var lambdas = PackedFloat32Array()
var capsules: Array = []
var visual: MeshInstance3D
var last_time: float = -1
var last_input_time: float = -1
var last_origin = Vector3.ZERO
var resets: int = 0
var result: Dictionary = {}
var samples: Array = []
var rendered = PackedVector3Array()
var expected_key: String
var frame: int = 0
var skeleton_revision: String
var pin_weights = PackedFloat32Array()
var animation_mutated = false
var data: Dictionary = {}
var initialized: bool = false
var animation_content_revision: String
var observed_animations: Dictionary = {}
var runtime_profile: Dictionary = {}
static func animation_value(value):
	if value is Vector3: return [value.x,value.y,value.z]
	if value is Quaternion: return [value.x,value.y,value.z,value.w]
	return value
func animation_resources() -> Dictionary:
	var runner = get_node_or_null(layering_path)
	if runner==null: return {}
	var player = runner.get_node_or_null(runner.player_path)
	if player==null or not player.has_animation(runner.animation_name): return {}
	var resources = {'base':player.get_animation(runner.animation_name)}
	for name in runner.clips: resources['clip:'+str(name)] = runner.clips[name]
	return resources
func animation_fingerprint(resources: Dictionary) -> String:
	var content = {}
	for name in resources:
		var animation = resources[name] as Animation
		if animation==null: return ''
		var tracks = []
		for track in animation.get_track_count():
			var keys = []
			for key in animation.track_get_key_count(track): keys.append([animation.track_get_key_time(track,key),animation_value(animation.track_get_key_value(track,key)),animation.track_get_key_transition(track,key)])
			tracks.append([animation.track_get_type(track),str(animation.track_get_path(track)),animation.track_is_enabled(track),animation.track_get_interpolation_type(track),animation.track_get_interpolation_loop_wrap(track),keys])
		content[name] = [animation.length,animation.loop_mode,tracks]
	return I.revision(content)
static func binding_digest(value: Dictionary) -> String:
	var content = value.duplicate(true)
	content.erase('binding_revision'); content.erase('source')
	return I.revision(content)
func _ready():
	process_priority = 200
	var runner = get_node_or_null(layering_path)
	if runner and not runner.pose_evaluated.is_connected(consume): runner.pose_evaluated.connect(consume)
	initialize()
func initialize() -> String:
	initialized = false
	if mode not in ['realtime','bake','replay']: return '未知的布料模式'
	if binding.get('schema')!=1 or binding.get('proxy',[]).is_empty(): return '缺少布料绑定'
	if binding_digest(binding)!=binding.get('binding_revision'): return '绑定内容哈希不匹配'
	if not cache.is_empty():
		if not cache.get('key') is String or cache.get('fps')!=60 or not cache.get('frames') is Array: return '缓存头格式无效'
		for values in cache.frames:
			if not values is Array or values.size()!=binding.proxy.size(): return '缓存中的粒子数量无效'
			for point in values:
				if not point is Array or point.size()!=3: return '缓存中的点数据格式无效'
				for coordinate in point:
					if not (coordinate is int or coordinate is float) or not is_finite(coordinate): return '缓存中的点包含非有限数值'
	# Freeze the evaluated binding. Editor mutations take effect only through validated initialize.
	data = binding.duplicate(true)
	if not profile.has('revision'): return '缺少目标骨架配置'
	var profile_problem = I.validate(profile)
	if profile_problem: return profile_problem
	runtime_profile = profile.duplicate(true)
	for key in ['mass','compliance','pin_weight']:
		if not settings.has(key) or not (settings[key] is int or settings[key] is float) or not is_finite(float(settings[key])): return '求解器参数必须为有限数值：'+key
	if settings.mass<.01 or settings.mass>10 or settings.compliance<0 or settings.compliance>.01 or settings.pin_weight<.5 or settings.pin_weight>1: return '求解器参数超出支持范围'
	if not (settings.get('lod') is int or settings.get('lod') is float) or settings.lod not in [0,1,2]: return 'LOD 必须为整数 0、1 或 2'
	pin_weights = PackedFloat32Array(binding.pins)
	if not settings.get('pin_overrides',{}) is Dictionary: return '固定点覆盖必须将顶部边界索引映射到 0–1 范围内的权重'
	for key in settings.get('pin_overrides',{}):
		if not str(key).is_valid_int(): return '固定点索引必须为整数'
		var index = int(key); var weight = settings.pin_overrides[key]
		if index<0 or index>=pin_weights.size() or binding.pins[index]<1 or not (weight is int or weight is float) or not is_finite(weight) or weight<0 or weight>1: return '只能编辑已声明的顶部边界固定点，权重必须为 0–1 范围内的有限数值'
		pin_weights[index] = weight
	var anchors = 0
	for weight in pin_weights:
		if weight>0: anchors += 1
	if anchors<2: return '顶部边界至少需要两个锚点'
	var sk = get_node_or_null(skeleton_path) as Skeleton3D
	if sk==null: return '缺少骨架'
	if identity.get('dna_at_bind')!=I.revision(get_parent().get_meta('character_dna',{})): return 'DNA 已改变；初始化或重新打开前必须重新适配绑定'
	if sk.get_bone_count()!=profile.bones.size(): return '骨架已改变；请重新适配绑定'
	for i in sk.get_bone_count():
		if sk.get_bone_name(i)!=profile.bones[i].name or sk.get_bone_parent(i)!=int(profile.bones[i].parent) or not sk.get_bone_rest(i).is_equal_approx(I.decode(profile.bones[i].local_rest)): return '骨架静止姿势已改变；请重新适配绑定'
	var scale = sk.global_basis.get_scale()
	if not scale.is_equal_approx(Vector3.ONE): return '布料要求世界缩放为 1；请将缩放烘焙到以米为单位的静止数据中'
	skeleton_revision = preload('res://addons/ainative/layering.gd').signature(sk)
	rest.clear()
	for p in binding.proxy: rest.append(Vector3(p[0],p[1],p[2]))
	points.resize(rest.size()); previous.resize(rest.size()); pin_targets.resize(rest.size()); invmass.resize(rest.size())
	lengths.clear()
	for edge in binding.edges: lengths.append(rest[int(edge[0])].distance_to(rest[int(edge[1])]))
	lambdas.resize(lengths.size())
	for i in rest.size(): invmass[i] = (1-pin_weights[i]*float(settings.pin_weight))/float(settings.mass)
	observed_animations = animation_resources()
	animation_content_revision = animation_fingerprint(observed_animations)
	if observed_animations.is_empty() or animation_content_revision.is_empty(): return '缺少动画内容'
	animation_mutated = false
	for animation in observed_animations.values():
		if not animation.changed.is_connected(invalidate_animation): animation.changed.connect(invalidate_animation)
	expected_key = cache_key()
	if mode=='replay' and cache.get('key')!=expected_key: return '已保存的回放缓存已过期；请重新构建并烘焙'
	var runner = get_node_or_null(layering_path)
	if runner:
		var player = runner.get_node(runner.player_path)
		for animation_name in player.get_animation_list():
			var animation = player.get_animation(animation_name)
			if not animation.changed.is_connected(invalidate_animation): animation.changed.connect(invalidate_animation)
	if visual==null:
		visual = MeshInstance3D.new(); visual.name = 'SimulatedClothRender'; add_child(visual)
	last_time = -1
	last_input_time = -1
	initialized = true
	return ''
func cache_key() -> String:
	var runner = get_node_or_null(layering_path)
	return I.revision({'source':binding.get('source_sha256'),'binding':binding.get('binding_revision'),'profile':profile.get('revision'),'dna':get_parent().get_meta('character_dna',{}),'identity':identity,'solver':settings,'layers':runner.config if runner else {},'animation':runner.animation_name if runner else '', 'animation_content':animation_content_revision,'algorithm':'xpbd-world-v3-weighted-render-contact'})
func invalidate_animation(): animation_mutated = true
func reset_particles():
	for i in rest.size(): points[i] = pin_targets[i]; previous[i] = points[i]
	resets += 1
func project(p: Vector3, margin: float = .015) -> Vector3:
	for c in capsules:
		var ab: Vector3 = c[1]-c[0]
		var q: Vector3 = c[0]+ab*clampf((p-c[0]).dot(ab)/maxf(ab.length_squared(),.000001),0,1)
		var d = p-q
		var radius: float = c[2]+margin
		if d.length_squared()<radius*radius:
			p = q+(d.normalized() if d.length_squared()>.0000001 else Vector3.BACK)*radius
	return p
func consume(pose: Dictionary):
	var start = Time.get_ticks_usec()
	if not initialized: result = {'error':'布料初始化失败；已保留原几何并停用求解'}; return
	if animation_resources()!=observed_animations: result = {'error':'动画资源已替换；请重新构建并烘焙'}; return
	if pose.get('schema')!='ainative.final_body_pose.v1': result = {'error':'需要 final_body_pose 最终身体姿势'}; return
	if points.is_empty():
		var error = initialize()
		if error: result = {'error':error}; return
	if animation_mutated or cache_key()!=expected_key or get_parent().get_meta('garment_fit_stale',false): result = {'error':'身体、骨架配置、求解器或动画已改变；绑定和缓存已失效，请重新适配'}; return
	if pose.get('skeleton_revision')!=skeleton_revision: result = {'error':'骨架已改变；绑定和缓存已失效'}; return
	var sk = get_node(skeleton_path) as Skeleton3D
	if not sk.global_basis.get_scale().is_equal_approx(Vector3.ONE): result = {'error':'不支持世界缩放不为 1 或非均匀缩放'}; return
	var global_poses = pose.global_bone_poses
	var anchor = int(runtime_profile.mapping.hips if data.kind=='skirt' else runtime_profile.mapping.get('chest',runtime_profile.mapping.hips))
	var transform = sk.global_transform*I.decode(global_poses[anchor])*I.decode(runtime_profile.bones[anchor].global_rest).affine_inverse()
	for i in rest.size(): pin_targets[i] = transform*rest[i]
	capsules.clear()
	for item in [['hips','chest',.18],['chest','neck',.17],['thigh_l','shin_l',.115],['thigh_r','shin_r',.115],['shin_l','foot_l',.085],['shin_r','foot_r',.085]]:
		if runtime_profile.mapping.has(item[0]) and runtime_profile.mapping.has(item[1]):
			capsules.append([sk.global_transform*I.decode(global_poses[int(runtime_profile.mapping[item[0]])]).origin,sk.global_transform*I.decode(global_poses[int(runtime_profile.mapping[item[1]])]).origin,item[2]])
	var time: float = pose.timestamp_seconds
	var dt = time-last_time
	var input_time: float = pose.get('input_timestamp_seconds',time)
	var input_delta = input_time-last_input_time
	if last_time<0 or dt<=0 or dt>.1 or input_delta<=0 or input_delta>.1 or sk.global_position.distance_to(last_origin)>.5: reset_particles(); dt = 1.0/60
	last_input_time = input_time
	last_origin = sk.global_position; last_time = time
	if mode=='replay':
		var runner = get_node(layering_path)
		var player = runner.get_node(runner.player_path)
		var full_frames = ceili(player.get_animation(runner.animation_name).length*60)
		if cache.get('key')!=expected_key or cache.get('frames',[]).size()!=full_frames: result = {'error':'没有兼容且完整的烘焙缓存'}; return
		var index = clampi(roundi(time*60),0,cache.frames.size()-1)
		var values = cache.frames[index]
		for i in points.size(): points[i] = sk.global_transform*Vector3(values[i][0],values[i][1],values[i][2])
	elif int(settings.lod)==2:
		# Explicit low-quality rigid pinned fallback, not advertised as full cloth.
		reset_particles()
	else:
		var substeps = maxi(1,ceili(dt/(1.0/(120 if int(settings.lod)==0 else 60))))
		var h = dt/substeps
		var alpha = float(settings.compliance)/(h*h)
		for sub in substeps:
			for i in points.size():
				if invmass[i]==0: points[i] = pin_targets[i]; previous[i] = points[i]; continue
				var old = points[i]
				points[i] += (points[i]-previous[i])*pow(.98,h*60)+Vector3(0,-9.81,0)*h*h
				previous[i] = old
			lambdas.fill(0)
			for iteration in (5 if int(settings.lod)==0 else 2):
				for e in data.edges.size():
					var edge = data.edges[e]
					var a = int(edge[0]); var b = int(edge[1])
					var d = points[b]-points[a]; var length = d.length()
					var denom = invmass[a]+invmass[b]+alpha
					if length<.000001 or denom<=0: continue
					var dl = (-(length-lengths[e])-alpha*lambdas[e])/denom
					lambdas[e] += dl
					points[a] -= invmass[a]*dl*d/length
					points[b] += invmass[b]*dl*d/length
				for i in points.size():
					if invmass[i]>0: points[i] = project(points[i],.025)
					else: points[i] = pin_targets[i]
					if pin_weights[i]>0 and invmass[i]>0: points[i] = points[i].lerp(pin_targets[i],pin_weights[i]*float(settings.pin_weight))
	var solved = Time.get_ticks_usec()
	rendered.resize(data.vertices.size())
	var local = global_transform.affine_inverse()
	for i in rendered.size():
		var p = Vector3.ZERO
		var fixed_weight = 0.0
		for k in 4:
			var particle = int(data.mapping[i][k]); var weight = float(data.weights[i][k])
			p += points[particle]*weight
			fixed_weight += pin_weights[particle]*float(settings.pin_weight)*weight
		var o = data.offsets[i]
		p += transform.basis*Vector3(o[0],o[1],o[2])
		# Prescribed boundary points stay on their anchors. Blend contact by free
		# weight, so partial pins approach the fixed boundary continuously.
		rendered[i] = local*p.lerp(project(p,.02),1.0-clampf(fixed_weight,0,1))
	var a = []; a.resize(Mesh.ARRAY_MAX)
	a[Mesh.ARRAY_VERTEX] = rendered; a[Mesh.ARRAY_INDEX] = PackedInt32Array(data.indices)
	var mesh = ArrayMesh.new(); mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES,G.normal_arrays(a))
	var material = StandardMaterial3D.new(); material.albedo_color = Color(.38,.08,.11) if data.kind=='skirt' else Color(.07,.2,.32); material.cull_mode = BaseMaterial3D.CULL_DISABLED; material.roughness = .85
	mesh.surface_set_material(0,material); visual.mesh = mesh
	var ended = Time.get_ticks_usec()
	result = {'solver_us':solved-start,'render_upload_us':ended-solved,'total_us':ended-start,'resets':resets,'mode':mode,'quality':'刚性回退（已停用模拟）' if int(settings.lod)==2 else 'XPBD','particles':points.size(),'render_vertices':rendered.size()}
	samples.append(result.duplicate()); frame += 1
	if samples.size()>4096: samples.pop_front()
	if mode=='bake':
		if cache.get('key')!=expected_key: cache = {'key':expected_key,'fps':60,'frames':[]}
		var values = []
		for p in points:
			var local_point = sk.global_transform.affine_inverse()*p
			values.append([local_point.x,local_point.y,local_point.z])
		cache.frames.append(values)
