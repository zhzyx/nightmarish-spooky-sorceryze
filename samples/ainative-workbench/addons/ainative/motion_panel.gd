@tool
extends VBoxContainer
const Motion = preload('res://addons/ainative/motion.gd')
const Interop = preload('res://addons/ainative/interop.gd')
var host: Control
var runtime: LineEdit
var prompt: LineEdit
var context: LineEdit
var video: LineEdit
var result_path: LineEdit
var destination: LineEdit
var target: LineEdit
var target_avatar: LineEdit
var target_family: OptionButton
var timeline: HSlider
var fps: SpinBox
var contacts: LineEdit
var edits: TextEdit
var message: Label
var in_place: CheckBox
var looping: CheckBox
var smoothing: SpinBox
var built: Dictionary = {}
var thread: Thread
var response: Dictionary = {}
var last_publish_code = -1

func initialize(workbench: Control):
	host = workbench
	var title = Label.new()
	title.text = '动作生成 · 本地 MDM / MediaPipe'
	add_child(title)
	var motion_preview = TextureRect.new()
	motion_preview.custom_minimum_size = Vector2(480,280)
	motion_preview.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	motion_preview.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	motion_preview.texture = host.viewport.get_texture()
	add_child(motion_preview)
	runtime = host.line(self,'独立动作运行环境目录','')
	prompt = host.line(self,'动作描述（MDM 通常使用英文动作描述）','')
	context = host.line(self,'上下文（仅支持 MDM 提示词 / 视频元信息，暂不支持图片）','')
	video = host.line(self,'本地视频路径','')
	result_path = host.line(self,'动作新版本路径（JSON）','')
	var row = HBoxContainer.new()
	add_child(row)
	host.button(row,'从文字生成动作',func(): generate(false))
	host.button(row,'从视频估计动作',func(): generate(true))
	host.button(row,'载入 / 预览动作',preview)
	in_place = CheckBox.new()
	in_place.text = '原地运动'
	row.add_child(in_place)
	looping = CheckBox.new()
	looping.text = '循环播放（请检查首尾衔接）'
	row.add_child(looping)
	smoothing = SpinBox.new()
	smoothing.max_value = .95
	smoothing.step = .05
	smoothing.tooltip_text = '时间平滑程度；0 表示保留原始观测值'
	row.add_child(smoothing)
	edits = TextEdit.new()
	edits.custom_minimum_size.y = 65
	edits.text = '[]'
	edits.tooltip_text = '关键点修正：[{"stream":"body","frame":0,"point":0,"position":[0,1,0]}]。保存的数据流仍保留原始测量值。'
	add_child(edits)
	target = host.line(self,'可选：已验证的目标骨架配置（.profile.json，用于 #147 重定向）','')
	target_avatar = host.line(self,'可选：已实际绑定的目标角色（.tscn / .glb）','')
	target_family = OptionButton.new()
	for family in Interop.FAMILIES:
		target_family.add_item({'anatomical':'解剖模板','ue4':'UE4','ue5_manny':'UE5 Manny','ue5_quinn':'UE5 Quinn','mixamo':'Mixamo'}[family])
		target_family.set_item_metadata(target_family.item_count-1,family)
	add_child(target_family)
	host.button(self,'重定向到目标骨架',retarget)
	fps = SpinBox.new()
	fps.min_value = 1
	fps.max_value = 240
	fps.value = 30
	fps.tooltip_text = '重定向采样率'
	add_child(fps)
	contacts = host.line(self,'脚部接地区间 JSON（#147）','[]')
	timeline = HSlider.new()
	timeline.step = .001
	timeline.value_changed.connect(func(value):
		if built.has('scene'):
			var player = built.scene.get_node('AnimationPlayer')
			player.play('generated')
			player.seek(value,true)
			player.pause())
	add_child(timeline)
	host.button(self,'播放动作',func():
		if built.has('scene'): built.scene.get_node('AnimationPlayer').play('generated'))
	destination = host.line(self,'动画新版本路径（.tscn）','')
	host.button(self,'保存动画新版本',save)
	message = Label.new()
	message.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(message)

func generate(is_video: bool):
	if thread!=null: message.text = '推理正在运行，请稍候'; return
	if runtime.text.is_empty() or result_path.text.is_empty(): message.text = '请填写运行环境目录和新结果路径'; return
	var python = host.python_edit.text
	var script = host.host_edit.text.get_base_dir().path_join('motion_provider.py')
	var args = [script,'--config',runtime.text.path_join('config.json'),'--mode','video_to_motion' if is_video else 'text_to_motion','--output',result_path.text,'--context',context.text,'--prompt',prompt.text]
	if is_video: args.append_array(['--video',video.text])
	thread = Thread.new()
	thread.start(func():
		var output = []
		var code = OS.execute(python,args,output,true)
		return {'code':code,'output':output})
	message.text = '本地模型正在推理…'

func _process(_delta):
	if thread!=null and not thread.is_alive():
		response = thread.wait_to_finish()
		thread = null
		message.text = '动作推理已完成，正在载入预览。' if response.code==0 else host.diagnostic_error('动作推理失败',response.output)
		if response.code==0: preview()
	if built.has('scene') and is_instance_valid(built.scene) and built.scene==host.preview_scene: frame_pose()

func frame_pose():
	var sk = Interop.skeleton(built.scene)
	if sk==null or not sk.is_inside_tree(): return
	sk.force_update_all_bone_transforms()
	var bounds = AABB(sk.global_transform*sk.get_bone_global_pose(0).origin,Vector3.ZERO)
	for i in sk.get_bone_count(): bounds = bounds.expand(sk.global_transform*sk.get_bone_global_pose(i).origin)
	var center = bounds.get_center()
	var radius = maxf(bounds.size.length()*.6,.25)
	var camera = host.preview_root.get_child(0) as Camera3D
	camera.position = center+Vector3(.5,.25,1).normalized()*radius/sin(deg_to_rad(camera.fov*.5))*1.2
	camera.near = radius/1000
	camera.far = radius*30
	camera.look_at(center)

func preview():
	var corrected = host.state_dir.path_join('motion-corrected-'+str(Time.get_ticks_usec())+'.json')
	var output = []
	var code = OS.execute(host.python_edit.text,[host.host_edit.text.get_base_dir().path_join('motion.py'),'--source',result_path.text,'--edits',edits.text,'--output',corrected],output,true)
	if code!=0: message.text = host.diagnostic_error('动作预览失败',output); return
	var doc = JSON.parse_string(FileAccess.get_file_as_string(corrected))
	built = Motion.build(doc,FileAccess.get_sha256(corrected),in_place.button_pressed,looping.button_pressed,smoothing.value)
	if built.has('error'): message.text = built.error; return
	show_scene(built.scene)
	var diagnostics = {}
	for name in doc.streams:
		var missing_times = []
		var low_times = []
		for frame in doc.streams[name].frames:
			if frame.missing: missing_times.append(frame.timestamp_ms)
			if frame.get('confidence') is Array and frame.confidence.any(func(value): return value<.5): low_times.append(frame.timestamp_ms)
		diagnostics[name] = {'missing_ms':missing_times,'low_confidence_ms':low_times}
	message.text = '源骨架配置 '+built.profile.revision+'\n'+JSON.stringify(built.scene.get_meta('motion_processing'))+'\n'+JSON.stringify(diagnostics)+'\n手部与面部数据已单独保留。使用前请检查身体数据缺失区间。'
func show_scene(scene: Node3D):
	host.preview_token = ''
	host.confirmation = {}
	host.preview_resource = null
	if is_instance_valid(host.preview_scene): host.preview_scene.queue_free()
	host.preview_scene = scene
	host.preview_root.add_child(scene)
	host.mesh_container.show()
	# Animated joint spheres expose real estimated/generated playback.
	var sk = Interop.skeleton(scene)
	for i in (sk.get_bone_count() if scene.find_children('*','MeshInstance3D',true,false).is_empty() else 0):
		var attachment = BoneAttachment3D.new()
		attachment.bone_name = sk.get_bone_name(i)
		sk.add_child(attachment)
		var mesh = MeshInstance3D.new()
		var sphere = SphereMesh.new()
		sphere.radius = .025
		sphere.height = .05
		mesh.mesh = sphere
		attachment.add_child(mesh)
	host.frame_mesh()
	timeline.max_value = scene.get_node('AnimationPlayer').get_animation('generated').length
	scene.get_node('AnimationPlayer').play('generated')

func retarget():
	if not built.has('animation'): message.text = '请先预览源动作'; return
	var scene = Node3D.new()
	var profile
	if not target_avatar.text.is_empty():
		var loaded = Interop.load_scene(target_avatar.text)
		if loaded.has('error'): scene.free(); message.text = loaded.error; return
		scene.free()
		scene = loaded.scene
		var extracted = Interop.extract(scene,str(target_family.get_item_metadata(target_family.selected)),{'sha256':FileAccess.get_sha256(target_avatar.text),'version':FileAccess.get_sha256(target_avatar.text),'authority':'artifact:bound-target-avatar'})
		if extracted.has('error'): scene.free(); message.text = extracted.error; return
		profile = extracted.profile
		for old in scene.find_children('*','AnimationPlayer',true,false): old.get_parent().remove_child(old); old.free()
	else:
		profile = JSON.parse_string(FileAccess.get_file_as_string(target.text))
		if profile is Dictionary and Interop.validate(profile)=='': scene.add_child(Interop.make_skeleton(profile))
	if not profile is Dictionary: message.text = '目标骨架配置无效'; return
	var intervals = JSON.parse_string(contacts.text)
	if not intervals is Array: scene.free(); message.text = '接地区间必须为 JSON 数组'; return
	var result = Interop.retarget(built.animation,built.profile,profile,fps.value,intervals)
	if result.has('error'): message.text = result.error; return
	var player = AnimationPlayer.new()
	player.name = 'AnimationPlayer'
	scene.add_child(player)
	var library = AnimationLibrary.new()
	var skeleton_path = str(scene.get_path_to(Interop.skeleton(scene)))
	for track in result.animation.get_track_count():
		var path = result.animation.track_get_path(track)
		result.animation.track_set_path(track,NodePath(skeleton_path+':'+str(path.get_subname(0))))
	library.add_animation('generated',result.animation)
	player.add_animation_library('',library)
	for key in built.scene.get_meta_list(): scene.set_meta(key,built.scene.get_meta(key))
	scene.set_meta('motion_target_profile',profile)
	scene.set_meta('motion_retarget',result.diagnostics)
	scene.set_meta('motion_contacts',intervals)
	Motion.own(scene,scene)
	built.scene = scene
	show_scene(scene)
	message.text = '已通过 #147 完成重定向；目标修订 '+profile.revision+'\n'+JSON.stringify(result.diagnostics)

func save():
	last_publish_code = -1
	if not built.has('scene') or destination.text.get_extension()!='tscn': message.text = '请先预览动作并填写 .tscn 保存路径'; return
	var staged = host.state_dir.path_join('motion-staged.tscn')
	var error = Motion.stage(built.scene,staged)
	if error: message.text = error; return
	var output = []
	var code = OS.execute(host.python_edit.text,[host.host_edit.text.get_base_dir().path_join('interop_publish.py'),staged,destination.text],output,true)
	last_publish_code = code
	message.text = '动画新版本已保存' if code==0 else host.diagnostic_error('保存失败',output)

func _exit_tree():
	if thread!=null: thread.wait_to_finish()
