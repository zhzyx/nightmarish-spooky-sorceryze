@tool
extends RefCounted
const Interop = preload('res://addons/ainative/interop.gd')
const NAMES = ['hips','thigh_l','thigh_r','spine','shin_l','shin_r','chest','foot_l','foot_r','upper_chest','toe_l','toe_r','neck','clavicle_l','clavicle_r','head','upper_arm_l','upper_arm_r','forearm_l','forearm_r','hand_l','hand_r']
const PARENTS = [-1,0,0,0,1,2,3,4,5,6,7,8,9,9,9,12,13,14,16,17,18,19]

static func v(a: Array) -> Vector3:
	return Vector3(a[0],a[1],a[2])

static func own(node: Node, root: Node):
	for child in node.get_children():
		child.owner = root
		own(child,root)

static func stage(scene: Node3D, path: String) -> String:
	var snapshot = scene.duplicate()
	own(snapshot,snapshot)
	for player in snapshot.find_children('*','AnimationPlayer',true,false): player.stop()
	var sk = Interop.skeleton(snapshot)
	if sk!=null: sk.reset_bone_poses()
	var error = Interop.stage_scene(snapshot,path)
	snapshot.free()
	return error

static func positions(frame: Dictionary, profile: String) -> Array:
	var raw = frame.get('positions',[])
	if profile=='humanml3d-22-v1': return raw.duplicate(true)
	if profile!='mediapipe-pose33-v1' or raw.size()!=33: return []
	var p = []
	for item in raw: p.append(Vector3(item[0],-item[1],-item[2]))
	var hips = (p[23]+p[24])*.5
	var shoulders = (p[11]+p[12])*.5
	var result = [hips,p[23],p[24],hips.lerp(shoulders,.33),p[25],p[26],hips.lerp(shoulders,.67),p[27],p[28],shoulders,p[31],p[32],shoulders.lerp(p[0],.5),shoulders.lerp(p[11],.5),shoulders.lerp(p[12],.5),p[0],p[11],p[12],p[13],p[14],p[15],p[16]]
	var out = []
	for point in result: out.append([point.x,point.y,point.z])
	return out

static func build(doc: Dictionary, source_hash: String, in_place: bool = false, loop: bool = false, smoothing: float = 0.0) -> Dictionary:
	if doc.get('schema')!='ainative.motion.v1': return {'error':'Invalid motion contract'}
	var frames = doc.get('streams',{}).get('body',{}).get('frames',[])
	if frames.size()<2: return {'error':'At least two body frames required'}
	var profile_id = str(doc.get('source_profile',{}).get('id',''))
	var rest = []
	for frame in frames:
		rest = positions(frame,profile_id)
		if rest.size()==22: break
	if rest.size()!=22: return {'error':'No complete body observation'}
	# Derive measured segment lengths, then establish a declared anatomical
	# T-rest. Treating frame zero as rest would erase the initial action pose.
	var measured = rest.duplicate(true)
	for i in range(1,22):
		var length = v(measured[i]).distance_to(v(measured[PARENTS[i]]))
		var direction = Vector3.UP
		if i in [1,13,16,18,20]: direction = Vector3.RIGHT
		elif i in [2,14,17,19,21]: direction = Vector3.LEFT
		elif i in [4,5,7,8]: direction = Vector3.DOWN
		elif i in [10,11]: direction = Vector3(0,0,1)
		var point = v(rest[PARENTS[i]])+direction*maxf(length,.001)
		rest[i] = [point.x,point.y,point.z]
	var scene = Node3D.new()
	scene.name = 'Motion'
	var sk = Skeleton3D.new()
	sk.name = 'Skeleton3D'
	scene.add_child(sk)
	for name in NAMES: sk.add_bone(name)
	for i in 22:
		sk.set_bone_parent(i,PARENTS[i])
		var origin = v(rest[i])
		if PARENTS[i]>=0: origin -= v(rest[PARENTS[i]])
		sk.set_bone_rest(i,Transform3D(Basis.IDENTITY,origin))
	sk.reset_bone_poses()
	var extracted = Interop.extract(scene,'anatomical',{'sha256':source_hash,'version':source_hash,'authority':'motion:'+profile_id})
	if extracted.has('error'): scene.free(); return extracted
	var animation = Animation.new()
	animation.length = float(frames[-1].timestamp_ms-frames[0].timestamp_ms)/1000.0
	animation.loop_mode = Animation.LOOP_LINEAR if loop else Animation.LOOP_NONE
	var tracks = []
	for i in 22:
		var position = animation.add_track(Animation.TYPE_POSITION_3D)
		var rotation = animation.add_track(Animation.TYPE_ROTATION_3D)
		animation.track_set_path(position,NodePath('Skeleton3D:'+NAMES[i]))
		animation.track_set_path(rotation,NodePath('Skeleton3D:'+NAMES[i]))
		tracks.append([position,rotation])
	var previous = []
	var missing = 0
	var first = []
	var last = []
	var missing_intervals = []
	var gap_start = -1.0
	var processed_first = Vector3.ZERO
	var processed_last = Vector3.ZERO
	var first_rotations = []
	var last_rotations = []
	var cleanup_max_displacement = 0.0
	for frame in frames:
		var points = positions(frame,profile_id)
		if points.size()!=22:
			missing += 1
			if gap_start<0: gap_start = float(frame.timestamp_ms)
			continue
		if gap_start>=0:
			missing_intervals.append({'start_ms':gap_start,'end_ms':frame.timestamp_ms,'policy':'interpolated; inspect before use'})
			gap_start = -1
		if first.is_empty(): first = points.duplicate(true)
		last = points.duplicate(true)
		if not previous.is_empty() and smoothing>0:
			for i in 22:
				var point = v(points[i]).lerp(v(previous[i]),clampf(smoothing,0,.95))
				cleanup_max_displacement = maxf(cleanup_max_displacement,point.distance_to(v(points[i])))
				points[i] = [point.x,point.y,point.z]
		previous = points.duplicate(true)
		var bases = []
		for i in 22:
			var child = PARENTS.find(i)
			var basis = Basis.IDENTITY
			if child>=0:
				var before = v(rest[child])-v(rest[i])
				var after = v(points[child])-v(points[i])
				if before.length()>.00001 and after.length()>.00001: basis = Basis(Quaternion(before.normalized(),after.normalized()))
			bases.append(basis)
		var time = float(frame.timestamp_ms-frames[0].timestamp_ms)/1000.0
		var rotations = []
		for i in 22:
			var parent = PARENTS[i]
			var rotation = bases[i] if parent<0 else bases[parent].inverse()*bases[i]
			var point = v(points[i])
			if parent>=0: point = bases[parent].inverse()*(point-v(points[parent]))
			elif in_place: point = Vector3(rest[0][0],point.y,rest[0][2])
			if i==0:
				if first_rotations.is_empty(): processed_first = point
				processed_last = point
			rotations.append(rotation.get_rotation_quaternion())
			animation.position_track_insert_key(tracks[i][0],time,point)
			animation.rotation_track_insert_key(tracks[i][1],time,rotation.get_rotation_quaternion())
		if first_rotations.is_empty(): first_rotations = rotations
		last_rotations = rotations
	if gap_start>=0: missing_intervals.append({'start_ms':gap_start,'end_ms':frames[-1].timestamp_ms,'policy':'held last observation; inspect before use'})
	var seam = 0.0
	for i in 22: seam = maxf(seam,first_rotations[i].angle_to(last_rotations[i]))
	var library = AnimationLibrary.new()
	library.add_animation('generated',animation)
	var player = AnimationPlayer.new()
	player.name = 'AnimationPlayer'
	scene.add_child(player)
	player.add_animation_library('',library)
	own(scene,scene)
	scene.set_meta('motion_source_profile',extracted.profile)
	scene.set_meta('motion_provenance',doc.provenance)
	scene.set_meta('motion_streams',doc.streams)
	scene.set_meta('motion_context',doc.get('context',[]))
	scene.set_meta('motion_context_bundle',doc.get('context_bundle',[]))
	scene.set_meta('motion_revision_chain',{'parent_revision':doc.get('parent_revision',''),'derived_source_sha256':source_hash})
	scene.set_meta('motion_rest_policy','anatomical T-rest with segment lengths from first complete observation; no axial twist estimate')
	scene.set_meta('motion_processing',{'smoothing':smoothing,'in_place':in_place,'loop':loop,'missing_body_frames':missing,'missing_intervals':missing_intervals,'raw_root_displacement_m':v(last[0]).distance_to(v(first[0])),'processed_root_displacement_m':processed_last.distance_to(processed_first),'loop_root_seam_m':processed_last.distance_to(processed_first),'loop_max_joint_seam_radians':seam,'twist_policy':'position-only swing; axial twist unobserved'})
	var processing = scene.get_meta('motion_processing')
	processing['processed_root_horizontal_displacement_m'] = Vector2(processed_last.x-processed_first.x,processed_last.z-processed_first.z).length()
	processing['smoothing_max_displacement_m'] = cleanup_max_displacement
	processing['root_policy'] = 'horizontal in-place; retain vertical pose' if in_place else doc.source_profile.get('root_motion','model_generated')
	return {'scene':scene,'profile':extracted.profile,'animation':animation}
