@tool
extends VBoxContainer
const Customization = preload('res://addons/ainative/customization.gd')
const Interop = preload('res://addons/ainative/interop.gd')
var scene: Node3D
var source_sha = ''
var source_path: LineEdit
var destination: LineEdit
var binding_path: LineEdit
var message: Label
var controls = {}
var preview_callback: Callable
var last_result = {}
var immutable_base: Node3D
var wardrobe_path: LineEdit
var fit_revision = ''
var viewport: SubViewport
var stage: Node3D
var camera: Camera3D
var body_motion_path: LineEdit
var body_player: AnimationPlayer
var face_stream_path: LineEdit
var face_frame: SpinBox
var expression_frames = []
var host_node
var base_source_path: LineEdit

func initialize(host):
	host_node = host
	var rows = get_children()
	var layout = HBoxContainer.new()
	add_child(layout)
	var fields = VBoxContainer.new()
	fields.custom_minimum_size.x = 420
	layout.add_child(fields)
	for row in rows: row.reparent(fields)
	var container = SubViewportContainer.new()
	container.custom_minimum_size = Vector2(600,780)
	container.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	container.stretch = true
	layout.add_child(container)
	viewport = SubViewport.new()
	viewport.size = Vector2i(700,780)
	viewport.own_world_3d = true
	viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	container.add_child(viewport)
	stage = Node3D.new()
	viewport.add_child(stage)
	var environment = WorldEnvironment.new()
	environment.environment = Environment.new()
	environment.environment.background_mode = Environment.BG_COLOR
	environment.environment.background_color = Color(.12,.15,.2)
	environment.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.environment.ambient_light_color = Color.WHITE
	environment.environment.ambient_light_energy = .6
	stage.add_child(environment)
	var light = DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-30,-25,0)
	light.light_energy = 1.6
	stage.add_child(light)
	camera = Camera3D.new()
	camera.fov = 45
	stage.add_child(camera)
	preview_callback = func(candidate):
		host.preview_token = ''
		stage.add_child(candidate)
		camera.position = Vector3(0,1.48,.85)
		camera.look_at(Vector3(0,1.46,0))

func _process(_delta):
	if is_instance_valid(body_player): frame_character()

func frame_character():
	if not is_instance_valid(scene) or not is_instance_valid(camera): return
	var binding = scene.get_meta('face_binding',{})
	var sk = Interop.skeleton(scene)
	if sk==null or not binding.get('body_mapping') is Dictionary: return
	var index = sk.find_bone(binding.body_mapping.head)
	if index<0: return
	sk.force_update_all_bone_transforms()
	var pose = sk.get_bone_global_pose(index)
	var center = sk.global_transform*pose.origin+Vector3(0,.08,0)
	var direction = (pose.basis*sk.get_bone_global_rest(index).basis.inverse()*Vector3(0,0,1)).normalized()
	camera.global_position = center+direction*.85+Vector3(0,.03,0)
	camera.look_at(center)

func _ready():
	var title = Label.new()
	title.text = '角色定制 / 已映射的面部资源'
	add_child(title)
	source_path = LineEdit.new()
	source_path.placeholder_text = '已映射的 Rain GLB / 已保存场景路径'
	add_child(source_path)
	binding_path = LineEdit.new()
	binding_path.placeholder_text = '面部绑定 FaceBinding JSON（资源专用语义映射）'
	add_child(binding_path)
	base_source_path = LineEdit.new()
	base_source_path.placeholder_text = '重新打开时使用的原始模型路径（仅保存在本地设置中）'
	add_child(base_source_path)
	button('载入原始资源',load_source)
	for key in ['chest','waist','hips','depth']+Customization.FACE_KEYS+['jawOpen','mouthSmile','mouthFrown','browDown','eyeBlink','lookLeft','lookRight','lookUp','lookDown']:
		var row = HBoxContainer.new()
		add_child(row)
		var label = Label.new()
		label.text = {
			'chest':'胸部宽度','waist':'腰部宽度','hips':'臀部宽度','depth':'身体厚度',
			'face_width':'脸部宽度','jaw_width':'下颌宽度','nose_width':'鼻部宽度',
			'jawOpen':'张嘴','mouthSmile':'微笑','mouthFrown':'嘴角下垂','browDown':'压眉',
			'eyeBlink':'眨眼','lookLeft':'向左看','lookRight':'向右看','lookUp':'向上看','lookDown':'向下看',
		}.get(key,key)
		label.custom_minimum_size.x = 125
		row.add_child(label)
		var slider = HSlider.new()
		slider.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		slider.step = .01
		slider.min_value = .8 if key in ['chest','waist','hips','depth'] else (-.5 if key in Customization.FACE_KEYS else 0)
		slider.max_value = 1.2 if key in ['chest','waist','hips','depth'] else (.5 if key in Customization.FACE_KEYS else 1)
		slider.value = 1 if key in ['chest','waist','hips','depth'] else 0
		row.add_child(slider)
		controls[key] = slider
		slider.value_changed.connect(func(_v): apply())
	destination = LineEdit.new()
	destination.placeholder_text = '新版本保存路径（.tscn，保留已有版本）'
	add_child(destination)
	button('保存版本',save_version)
	wardrobe_path = LineEdit.new()
	wardrobe_path.placeholder_text = '独立服装配置 JSON'
	add_child(wardrobe_path)
	button('从原始模型重新拟合独立服装',refit_garment)
	body_motion_path = LineEdit.new()
	body_motion_path.placeholder_text = '已生成的身体动画场景（含 motion_target_profile）'
	add_child(body_motion_path)
	button('载入并播放身体动画',load_body_motion)
	button('暂停身体动画',func():
		if is_instance_valid(body_player): body_player.pause())
	face_stream_path = LineEdit.new()
	face_stream_path.placeholder_text = 'MediaPipe 面部数据流 JSON'
	add_child(face_stream_path)
	button('载入捕捉的表情',load_expression)
	face_frame = SpinBox.new()
	face_frame.prefix = '表情帧 '
	face_frame.step = 1
	add_child(face_frame)
	face_frame.value_changed.connect(func(_v): apply())
	message = Label.new()
	message.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	message.text = '可手动调整口型和视线。语音 AI 功能尚未实现。'
	add_child(message)

func button(text: String, callback: Callable):
	var b = Button.new()
	b.text = text
	b.pressed.connect(callback)
	add_child(b)

func load_source():
	var result = Interop.load_scene(source_path.text)
	if result.has('error'):
		message.text = result.error
		return
	var candidate = result.scene
	var candidate_sha = FileAccess.get_sha256(source_path.text)
	if not candidate.has_meta('face_binding'):
		var binding = JSON.parse_string(FileAccess.get_file_as_string(binding_path.text))
		if not binding is Dictionary or binding.get('asset_sha256')!=candidate_sha:
			message.text = '映射资源校验值不匹配，或缺少面部绑定 FaceBinding'
			candidate.free()
			return
		candidate.set_meta('face_binding',binding)
		candidate_sha = binding.source_sha256
	var candidate_binding = candidate.get_meta('face_binding',{})
	if not candidate_binding is Dictionary:
		message.text = 'FaceBinding 必须为 JSON 对象，当前资源已保留'
		candidate.free()
		return
	var candidate_dna = candidate.get_meta('character_dna',Customization.dna(candidate_binding.get('source_sha256',''),{}, {},candidate_binding.get('mapping_version','')))
	if not candidate_dna is Dictionary or not candidate.get_meta('face_layers',[]) is Array:
		message.text = '已保存的角色参数或分层配置无效，当前资源已保留'
		candidate.free()
		return
	var preflight = Customization.apply_face(candidate,candidate_dna,candidate.get_meta('face_layers',[]))
	if preflight.has('error'):
		message.text = preflight.error
		candidate.free()
		return
	# The panel exposes every slider, including zero-valued channels. Validate
	# their capabilities before replacing the current scene, not on first edit.
	var available = []
	for mi in candidate.find_children('*','MeshInstance3D',true,false):
		for i in mi.get_blend_shape_count(): available.append(str(mi.mesh.get_blend_shape_name(i)))
	for key in controls:
		if not candidate_binding.morphs.has(key) or not candidate_binding.morphs[key] in available:
			message.text = '不支持该语义形变：'+key+'；当前资源已保留'
			candidate.free()
			return
	var base_path = source_path.text if FileAccess.get_sha256(source_path.text)==candidate_binding.get('asset_sha256') else base_source_path.text
	var base_candidate
	if base_path!=source_path.text:
		var base_result = Interop.load_scene(base_path)
		if base_result.has('error') or FileAccess.get_sha256(base_path)!=candidate.get_meta('face_binding').asset_sha256:
			message.text = '原始模型不存在或已变化，无法重新打开并重新拟合'
			if base_result.has('scene'): base_result.scene.free()
			candidate.free()
			return
		base_candidate = base_result.scene
		base_candidate.set_meta('face_binding',candidate.get_meta('face_binding'))
	else: base_candidate = candidate.duplicate()
	if is_instance_valid(scene): scene.queue_free()
	if is_instance_valid(immutable_base): immutable_base.free()
	scene = candidate
	source_sha = candidate_binding.source_sha256
	immutable_base = base_candidate
	base_source_path.text = base_path
	body_player = scene.get_node_or_null('BodyMotion')
	expression_frames = []
	face_frame.set_value_no_signal(0)
	for key in controls: controls[key].set_value_no_signal(1.0 if key in ['chest','waist','hips','depth'] else 0.0)
	var snapshot_layers = scene.get_meta('face_layers',[]).duplicate(true)
	if scene.has_meta('character_dna'):
		var dna = scene.get_meta('character_dna')
		source_sha = dna.source_sha256
		for group in ['body','face']:
			for key in dna[group]: controls[key].set_value_no_signal(dna[group][key])
		for layer in scene.get_meta('face_layers',[]):
			for key in layer.channels:
				if controls.has(key): controls[key].set_value_no_signal(layer.channels[key])
	if preview_callback.is_valid(): preview_callback.call(scene)
	if is_instance_valid(body_player) and scene.has_meta('body_playback'):
		var playback = scene.get_meta('body_playback')
		body_player.play(playback.name)
		body_player.seek(playback.time,true)
		if not playback.playing: body_player.pause()
	apply()
	# A different capture previously loaded in this panel must not replace the
	# saved expression or its channel ownership while reopening an old version.
	if not candidate_dna.body.is_empty() or not candidate_dna.face.is_empty():
		last_result = Customization.apply_face(scene,candidate_dna,snapshot_layers)
		message.text = '已恢复保存的体型、脸型和表情。'
	frame_character()

func apply():
	if not is_instance_valid(scene): return
	var body = {}
	var face = {}
	var channels = {}
	for key in controls:
		if key in ['chest','waist','hips','depth']: body[key] = controls[key].value
		elif key in Customization.FACE_KEYS: face[key] = controls[key].value
		else: channels[key] = controls[key].value
	var dna = Customization.dna(source_sha,body,face,scene.get_meta('face_binding',{}).get('mapping_version',''))
	var layers = [{'id':'manual-ui','priority':10,'channels':channels}]
	if not expression_frames.is_empty():
		var expression = Customization.mediapipe_layer(expression_frames[int(face_frame.value)])
		if expression.has('error'):
			message.text = expression.error
			return
		var manual = {}
		for key in ['jawOpen','lookLeft','lookRight','lookUp','lookDown']: manual[key] = channels[key]
		layers = [expression,{'id':'manual-mouth-gaze','priority':10,'channels':manual}]
	last_result = Customization.apply_face(scene,dna,layers)
	if not last_result.has('error') and scene.has_meta('garment'):
		scene.set_meta('garment_fit_stale',scene.get_meta('garment_dna_revision','')!=dna.revision)
	message.text = last_result.error if last_result.has('error') else ('体型和脸型已更新。表情来自捕捉，口型和视线由手动控制。' if not expression_frames.is_empty() else '体型和脸型已更新。表情、口型和视线由手动控制。')
	if scene.get_meta('garment_fit_stale',false): message.text += ' 保存前请重新拟合服装。'

func save_version():
	if not is_instance_valid(scene): return
	if destination.text.get_extension()!='tscn' or FileAccess.file_exists(destination.text):
		message.text = '请填写新的 .tscn 版本路径，已有版本不能覆盖'
		return
	var staged = host_node.state_dir.path_join('customization-'+str(Time.get_ticks_usec())+'.tscn')
	var error = Customization.stage(scene,staged)
	if error:
		message.text = error
		return
	var output = []
	var code = OS.execute(host_node.python_edit.text,[host_node.host_edit.text.get_base_dir().path_join('interop_publish.py'),staged,ProjectSettings.globalize_path(destination.text)],output,true)
	message.text = '新版本已保存：'+destination.text if code==0 else host_node.diagnostic_error('保存失败，源资源已保留',output)

func refit_garment():
	if not is_instance_valid(scene) or not is_instance_valid(immutable_base): return
	var config = JSON.parse_string(FileAccess.get_file_as_string(wardrobe_path.text))
	if not config is Dictionary or not config.get('garments') is Array or config.garments.is_empty():
		message.text = '请提供独立服装配置'
		return
	var binding = immutable_base.get_meta('face_binding',{})
	var extracted = Interop.extract(immutable_base,'anatomical',{'sha256':binding.asset_sha256,'version':binding.mapping_version,'authority':binding.source_url},binding.get('body_mapping',{}))
	if extracted.has('error'):
		message.text = extracted.error
		return
	var garment = config.garments[0]
	var spec = garment.spec.duplicate(true)
	# Reviewed Rain torso cage, supplied by the asset binding/wardrobe config.
	if config.has('target_box'): spec.target_box = config.target_box
	var result = Customization.refit(immutable_base,extracted.profile,scene.get_meta('character_dna'),garment.path,spec)
	if result.has('error'):
		message.text = result.error
		return
	var layers = scene.get_meta('face_layers',[])
	var next_player: AnimationPlayer
	var playback = {}
	if is_instance_valid(body_player):
		playback = {'name':body_player.assigned_animation,'time':body_player.current_animation_position if body_player.assigned_animation!='' else 0.0,'playing':body_player.is_playing()}
		if playback.name=='': playback.name = body_player.get_animation_list()[0]
		next_player = body_player.duplicate()
		result.scene.add_child(next_player)
		result.scene.set_meta('body_motion_source',scene.get_meta('body_motion_source'))
	scene.queue_free()
	scene = result.scene
	Customization.apply_face(scene,scene.get_meta('character_dna'),layers)
	fit_revision = scene.get_meta('garment_cache_key')
	body_player = next_player
	if preview_callback.is_valid(): preview_callback.call(scene)
	if is_instance_valid(body_player):
		body_player.play(playback.name)
		body_player.seek(playback.time,true)
		if not playback.playing: body_player.pause()
	message.text = '独立服装已按当前体型重新拟合。'

func _exit_tree():
	if is_instance_valid(immutable_base): immutable_base.free()

func load_body_motion():
	if not is_instance_valid(scene): return
	var loaded = Interop.load_scene(body_motion_path.text)
	if loaded.has('error'):
		message.text = loaded.error
		return
	var source = loaded.scene
	var profile = source.get_meta('motion_target_profile',{})
	var error = Interop.validate(profile)
	if error:
		message.text = error
		source.free()
		return
	var binding = scene.get_meta('face_binding')
	var extracted = Interop.extract(immutable_base,'anatomical',{'sha256':binding.asset_sha256,'version':binding.mapping_version,'authority':binding.source_url},binding.body_mapping)
	if extracted.has('error'):
		message.text = extracted.error
		source.free()
		return
	var library = AnimationLibrary.new()
	var sk = Interop.skeleton(scene)
	for original in source.find_children('*','AnimationPlayer',true,false):
		for name in original.get_animation_list():
			if name=='RESET': continue
			var converted = Interop.retarget(original.get_animation(name),profile,extracted.profile)
			if converted.has('error'):
				message.text = converted.error
				source.free()
				return
			for i in converted.animation.get_track_count():
				var bone = converted.animation.track_get_path(i).get_subname(0)
				converted.animation.track_set_path(i,NodePath(str(scene.get_path_to(sk))+':'+str(bone)))
			library.add_animation(name.replace('/','_'),converted.animation)
	source.free()
	if library.get_animation_list().is_empty():
		message.text = '身体动画源中没有可用动画'
		return
	if is_instance_valid(body_player):
		body_player.get_parent().remove_child(body_player)
		body_player.free()
	body_player = AnimationPlayer.new()
	body_player.name = 'BodyMotion'
	scene.add_child(body_player)
	body_player.add_animation_library('',library)
	body_player.play(library.get_animation_list()[0])
	scene.set_meta('body_motion_source',{'sha256':FileAccess.get_sha256(body_motion_path.text),'profile_revision':profile.revision})
	message.text = '正在播放生成的身体动画，面部通道独立保留。'

func load_expression():
	var document = JSON.parse_string(FileAccess.get_file_as_string(face_stream_path.text))
	if not document is Dictionary or not document.get('streams') is Dictionary or not document.streams.get('face') is Dictionary or not document.streams.face.get('frames') is Array or document.streams.face.frames.is_empty():
		message.text = '面部数据流中没有检测到有效帧'
		return
	for frame in document.streams.face.frames:
		if not frame is Dictionary or Customization.mediapipe_layer(frame).has('error'):
			message.text = '面部数据流包含缺失或无效的检测结果，原有效资源已保留'
			return
	expression_frames = document.streams.face.frames
	face_frame.max_value = expression_frames.size()-1
	face_frame.value = 0
	apply()
