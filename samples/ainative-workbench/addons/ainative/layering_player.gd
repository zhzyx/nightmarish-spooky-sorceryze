@tool
extends Node
const Layering = preload('res://addons/ainative/layering.gd')
const Interop = preload('res://addons/ainative/interop.gd')
@export var config: Dictionary = {}
@export var skeleton_path: NodePath
@export var player_path: NodePath
@export var weapon_path: NodePath
@export var animation_name: String = 'generated'
@export var clips: Dictionary = {}
@export var playing: bool = true
var time_seconds: float = 0
var result: Dictionary = {}
signal pose_evaluated(pose: Dictionary)
func _ready():
	process_priority = 100
	var player = get_node_or_null(player_path)
	if player: player.active = false
func _process(delta):
	if playing: sample(time_seconds+delta)
func sample(time: float):
	if not is_finite(time): result = {'error':'时间戳必须为有限数值'}; return
	var sk = get_node_or_null(skeleton_path) as Skeleton3D
	var player = get_node_or_null(player_path) as AnimationPlayer
	if sk==null or player==null or not player.has_animation(animation_name): result = {'error':'缺少骨架或源动画'}; return
	var error = Layering.validate(sk,config)
	if error: result = {'error':error}; return
	for layer in config.get('layers',[]):
		if not layer.has('clip'): continue
		if not clips.has(layer.clip) or not clips[layer.clip] is Animation: result = {'error':'图层动画片段不存在'}; return
		var candidate = clips[layer.clip] as Animation
		for track in candidate.get_track_count():
			var path = candidate.track_get_path(track)
			if path.get_subname_count()!=1 or not str(path.get_subname(0)) in layer.mask or sk.find_bone(str(path.get_subname(0)))<0 or candidate.track_get_type(track) not in [Animation.TYPE_ROTATION_3D,Animation.TYPE_POSITION_3D,Animation.TYPE_SCALE_3D]: result = {'error':'图层轨道无效'}; return
	var previous_pose = Layering.capture(sk)
	var previous_time = time_seconds
	time_seconds = fposmod(time,player.get_animation(animation_name).length)
	sk.reset_bone_poses()
	player.active = true
	player.play(animation_name)
	player.seek(time_seconds,true)
	player.active = false
	var sampled = config.duplicate(true)
	for layer in sampled.get('layers',[]):
		if not layer.has('clip'): continue
		if not clips.has(layer.clip): result = {'error':'图层动画片段不存在'}; return
		var clip = clips[layer.clip] as Animation
		layer.pose = layer.get('pose',{}).duplicate(true)
		for track in clip.get_track_count():
			var path = clip.track_get_path(track)
			if path.get_subname_count()!=1: result = {'error':'图层轨道必须指向骨骼'}; return
			var bone = str(path.get_subname(0))
			if not bone in layer.mask: result = {'error':'动画片段的写入超出遮罩范围'}; return
			var i = sk.find_bone(bone)
			if i<0: result = {'error':'动画片段包含未知骨骼'}; return
			var transform = Interop.decode(layer.pose[bone]) if layer.pose.has(bone) else sk.get_bone_pose(i)
			var t = fposmod(time_seconds,clip.length)
			match clip.track_get_type(track):
				Animation.TYPE_ROTATION_3D: transform.basis = Basis(clip.rotation_track_interpolate(track,t))
				Animation.TYPE_POSITION_3D: transform.origin = clip.position_track_interpolate(track,t)
				Animation.TYPE_SCALE_3D: transform.basis = transform.basis.orthonormalized().scaled(clip.scale_track_interpolate(track,t))
				_: result = {'error':'不支持此图层轨道'}; return
			layer.pose[bone] = Interop.encode(transform)
	result = Layering.evaluate(sk,Layering.capture(sk),sampled,time_seconds)
	if result.has('error'):
		for i in previous_pose.size(): sk.set_bone_pose(i,previous_pose[i])
		time_seconds = previous_time
		return
	var weapon = get_node_or_null(weapon_path)
	if weapon: weapon.global_transform = sk.global_transform*result.weapon_transform
	# Preserve unwrapped caller time so downstream cloth can detect large seeks.
	result['input_timestamp_seconds'] = time
	pose_evaluated.emit(result)
