@tool
extends RefCounted
# Procedural 17-bone locomotion templates. No third-party motion clips are used.
const NAMES = ['hips','spine','chest','neck','head','upper_arm_l','forearm_l','hand_l','upper_arm_r','forearm_r','hand_r','thigh_l','shin_l','foot_l','thigh_r','shin_r','foot_r','root']
const PARENTS = [17,0,1,2,3,2,5,6,2,8,9,0,11,12,0,14,15,-1]
const FPS = 60
const CLIPS = ['walk_in_place','run_in_place','jump']

static func rest_positions(height: float) -> Array:
	var h = height
	return [Vector3(0,.51,0)*h,Vector3(0,.61,0)*h,Vector3(0,.73,0)*h,Vector3(0,.83,0)*h,Vector3(0,.91,0)*h,Vector3(.13,.76,0)*h,Vector3(.29,.76,0)*h,Vector3(.44,.76,0)*h,Vector3(-.13,.76,0)*h,Vector3(-.29,.76,0)*h,Vector3(-.44,.76,0)*h,Vector3(.085,.49,0)*h,Vector3(.085,.27,0)*h,Vector3(.085,.055,.04)*h,Vector3(-.085,.49,0)*h,Vector3(-.085,.27,0)*h,Vector3(-.085,.055,.04)*h,Vector3.ZERO]

static func make_skeleton(height: float = 1.8) -> Skeleton3D:
	var sk = Skeleton3D.new()
	sk.name = 'Skeleton3D'
	var positions = rest_positions(height)
	for bone_name in NAMES: sk.add_bone(bone_name)
	for i in NAMES.size():
		sk.set_bone_parent(i,PARENTS[i])
		var relative = positions[i]-positions[PARENTS[i]] if PARENTS[i]>=0 else positions[i]
		sk.set_bone_rest(i,Transform3D(Basis.IDENTITY,relative))
	sk.reset_bone_poses()
	return sk

static func make_scene(height: float = 1.8) -> Node3D:
	var scene = Node3D.new()
	scene.name = 'AINativeLocomotionTemplates'
	var sk = make_skeleton(height)
	scene.add_child(sk)
	var player = AnimationPlayer.new()
	player.name = 'AnimationPlayer'
	scene.add_child(player)
	var library = AnimationLibrary.new()
	for clip in CLIPS: library.add_animation(clip,build_animation(sk,clip))
	player.add_animation_library('',library)
	scene.set_meta('ainative_locomotion',{
		'schema_version':1,
		'generator':'analytic-foot-trajectory-two-bone-ik-v1',
		'ai_inference':false,
		'third_party_motion_assets':[],
		'height_m':height,
		'up':'+Y',
		'forward':'+Z',
		'root_motion':false,
		'fps':FPS,
		'clips':CLIPS
	})
	own(scene,scene)
	return scene

static func own(node: Node, owner_node: Node):
	if node!=owner_node: node.owner = owner_node
	for child in node.get_children(): own(child,owner_node)

static func duration_for(clip: String) -> float:
	match clip:
		'walk_in_place': return 1.1
		'run_in_place': return .7
		'jump': return 1.4
	return 0.0

static func build_animation(sk: Skeleton3D, clip: String) -> Animation:
	var animation = Animation.new()
	animation.resource_name = clip
	animation.length = duration_for(clip)
	animation.loop_mode = Animation.LOOP_NONE if clip=='jump' else Animation.LOOP_LINEAR
	var rotation_tracks = {}
	for bone_name in NAMES:
		var track = animation.add_track(Animation.TYPE_ROTATION_3D)
		animation.track_set_path(track,NodePath('Skeleton3D:'+bone_name))
		animation.track_set_interpolation_type(track,Animation.INTERPOLATION_LINEAR)
		rotation_tracks[bone_name] = track
	var hip_track = animation.add_track(Animation.TYPE_POSITION_3D)
	animation.track_set_path(hip_track,NodePath('Skeleton3D:hips'))
	animation.track_set_interpolation_type(hip_track,Animation.INTERPOLATION_LINEAR)
	var samples = int(round(animation.length*FPS))
	var hip_rest = sk.get_bone_rest(0).origin
	for sample_index in range(samples+1):
		var time = minf(float(sample_index)/FPS,animation.length)
		var phase = time/animation.length
		if sample_index==samples: phase = 0.0 if clip!='jump' else 1.0
		var pose = sample_pose(sk,clip,phase)
		for bone_name in NAMES:
			var rotation = pose.rotations.get(bone_name,Quaternion.IDENTITY) as Quaternion
			animation.rotation_track_insert_key(rotation_tracks[bone_name],time,rotation)
		animation.position_track_insert_key(hip_track,time,hip_rest+pose.hip_shift)
	animation.set_meta('generator','analytic-foot-trajectory-two-bone-ik-v1')
	animation.set_meta('in_place',clip!='jump')
	animation.set_meta('sample_rate',FPS)
	return animation

static func sample_pose(sk: Skeleton3D, clip: String, phase: float) -> Dictionary:
	var pose = {'rotations':{},'hip_shift':Vector3.ZERO,'feet':{},'foot_pitch':{}}
	var height = sk.get_bone_global_rest(4).origin.y/.91
	if clip=='jump': return jump_pose(sk,phase,height)
	var walk = clip=='walk_in_place'
	var stride = height*(.20 if walk else .34)
	var duty = .62 if walk else .38
	var lift = height*(.06 if walk else .11)
	var drop = height*(.035 if walk else .07)
	var bob = height*(.008 if walk else .015)
	var arm = .48 if walk else .78
	var elbow = .28 if walk else .72
	var lean = .035 if walk else .12
	var omega = TAU*phase
	pose.hip_shift = Vector3(0,-drop+bob*(1.0-cos(2.0*omega))*.5,0)
	for side in ['l','r']:
		var offset = 0.0 if side=='l' else .5
		var leg_phase = fposmod(phase+offset,1.0)
		var target = gait_foot(sk,side,leg_phase,stride,duty,lift)
		var pitch = gait_pitch(leg_phase,duty,.08 if walk else .14)
		pose.feet[side] = target
		pose.foot_pitch[side] = pitch
		apply_leg(sk,pose,side,target,pitch)
	var arm_l = arm*cos(omega)
	var arm_r = -arm_l
	pose.rotations.upper_arm_l = arm_rotation(-1.22,arm_l)
	pose.rotations.upper_arm_r = arm_rotation(1.22,arm_r)
	pose.rotations.forearm_l = Quaternion(Basis(Vector3.RIGHT,-elbow))
	pose.rotations.forearm_r = Quaternion(Basis(Vector3.RIGHT,-elbow))
	pose.rotations.spine = Quaternion(Basis(Vector3.RIGHT,lean))
	pose.rotations.chest = Quaternion.from_euler(Vector3(lean*.3,.07*sin(omega) if walk else .11*sin(omega),0))
	pose.rotations.head = Quaternion.from_euler(Vector3(-lean*.45,-.035*sin(omega),0))
	return pose

static func gait_foot(sk: Skeleton3D, side: String, phase: float, stride: float, duty: float, lift: float) -> Vector3:
	var rest = sk.get_bone_global_rest(sk.find_bone('foot_'+side)).origin
	if phase<duty:
		rest.z += stride*(.5-phase/duty)
		return rest
	var u = (phase-duty)/(1.0-duty)
	rest.z += stride*(-.5+smoothstep(0.0,1.0,u))
	rest.y += lift*sin(PI*u)
	return rest

static func gait_pitch(phase: float, duty: float, amount: float) -> float:
	if phase<duty: return 0.0
	return amount*sin(PI*(phase-duty)/(1.0-duty))

static func jump_pose(sk: Skeleton3D, phase: float, height: float) -> Dictionary:
	var pose = {'rotations':{},'hip_shift':Vector3.ZERO,'feet':{},'foot_pitch':{}}
	var keys = [
		[0.0,0.0,0.0,0.0,.25,.03,0.0],
		[.12,0.0,0.0,0.0,.25,.03,0.0],
		[.30,-.13,0.0,.55,.35,.18,0.0],
		[.38,-.09,0.0,-.65,.25,.10,0.0],
		[.45,.05,.07,-1.65,.12,.02,.08],
		[.60,.25,.31,-1.25,.30,.06,.18],
		[.70,.18,.22,-.45,.30,.08,.10],
		[.82,0.0,0.0,.25,.35,.15,0.0],
		[.90,-.12,0.0,.45,.40,.20,0.0],
		[1.0,0.0,0.0,0.0,.25,.03,0.0]
	]
	var index = 0
	while index<keys.size()-2 and phase>float(keys[index+1][0]): index += 1
	var a = keys[index]
	var b = keys[index+1]
	var u = smoothstep(0.0,1.0,inverse_lerp(float(a[0]),float(b[0]),clampf(phase,0.0,1.0)))
	var hip = lerpf(float(a[1]),float(b[1]),u)*height
	var foot = lerpf(float(a[2]),float(b[2]),u)*height
	var arm = lerpf(float(a[3]),float(b[3]),u)
	var elbow = lerpf(float(a[4]),float(b[4]),u)
	var lean = lerpf(float(a[5]),float(b[5]),u)
	var pitch = lerpf(float(a[6]),float(b[6]),u)
	pose.hip_shift = Vector3(0,hip,0)
	for side in ['l','r']:
		var target = sk.get_bone_global_rest(sk.find_bone('foot_'+side)).origin
		target.y += foot
		pose.feet[side] = target
		pose.foot_pitch[side] = pitch
		apply_leg(sk,pose,side,target,pitch)
	pose.rotations.upper_arm_l = arm_rotation(-1.22,arm)
	pose.rotations.upper_arm_r = arm_rotation(1.22,arm)
	pose.rotations.forearm_l = Quaternion(Basis(Vector3.RIGHT,-elbow))
	pose.rotations.forearm_r = Quaternion(Basis(Vector3.RIGHT,-elbow))
	pose.rotations.spine = Quaternion(Basis(Vector3.RIGHT,lean))
	pose.rotations.chest = Quaternion(Basis(Vector3.RIGHT,lean*.3))
	pose.rotations.head = Quaternion(Basis(Vector3.RIGHT,-lean*.45))
	return pose

static func arm_rotation(down: float, swing: float) -> Quaternion:
	return Quaternion(Basis(Vector3.BACK,down)*Basis(Vector3.RIGHT,swing))

static func apply_leg(sk: Skeleton3D, pose: Dictionary, side: String, target: Vector3, foot_pitch: float):
	var thigh = sk.find_bone('thigh_'+side)
	var shin = sk.find_bone('shin_'+side)
	var foot = sk.find_bone('foot_'+side)
	var start = sk.get_bone_rest(0).origin+pose.hip_shift+sk.get_bone_rest(thigh).origin
	var upper = sk.get_bone_rest(shin).origin
	var lower = sk.get_bone_rest(foot).origin
	var relative = target-start
	var l1 = Vector2(upper.y,upper.z).length()
	var l2 = Vector2(lower.y,lower.z).length()
	var distance = clampf(Vector2(relative.y,relative.z).length(),absf(l1-l2)+.000001,l1+l2-.000001)
	var alpha = atan2(-relative.z,-relative.y)
	var rest1 = atan2(-upper.z,-upper.y)
	var rest2 = atan2(-lower.z,-lower.y)
	var theta = acos(clampf((l1*l1+distance*distance-l2*l2)/maxf(2.0*l1*distance,1e-9),-1.0,1.0))
	var bend = acos(clampf((distance*distance-l1*l1-l2*l2)/maxf(2.0*l1*l2,1e-9),-1.0,1.0))
	var thigh_angle = alpha-theta-rest1
	var shin_angle = bend+rest1-rest2
	pose.rotations['thigh_'+side] = Quaternion(Basis(Vector3.RIGHT,thigh_angle))
	pose.rotations['shin_'+side] = Quaternion(Basis(Vector3.RIGHT,shin_angle))
	pose.rotations['foot_'+side] = Quaternion(Basis(Vector3.RIGHT,foot_pitch-thigh_angle-shin_angle))
