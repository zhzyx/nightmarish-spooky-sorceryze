@tool
extends VBoxContainer
const I = preload('res://addons/ainative/interop.gd')
const L = preload('res://addons/ainative/layering.gd')
const M = preload('res://addons/ainative/motion.gd')
const G = preload('res://addons/ainative/garments.gd')
var host: Control
var config_path: LineEdit
var destination: LineEdit
var modes: OptionButton
var garment: OptionButton
var message: Label
var config: Dictionary = {}
var built: Node3D
var runner: Node
var base_config: Dictionary
var source_sha: String
var settings: TextEdit
var local_preview: TextureRect
var weapon_mesh: Mesh
var weapon_visual_transform: Transform3D
func initialize(workbench):
	host = workbench
	config_path = host.line(self,'动画分层配置 JSON')
	host.button(self,'载入动画分层场景',load_configuration)
	modes = OptionButton.new()
	for name in ['跑动与瞄准 / 双手 IK','单手持剑','原始动画','全身覆盖']: modes.add_item(name)
	add_child(modes)
	modes.item_selected.connect(set_mode)
	garment = OptionButton.new()
	garment.add_item('基础角色')
	add_child(garment)
	host.button(self,'从原始角色重新换装',swap)
	host.button(self,'播放 / 暂停',func():
		if is_instance_valid(runner): runner.playing = not runner.playing)
	settings = TextEdit.new()
	settings.custom_minimum_size.y = 100
	add_child(settings)
	host.button(self,'应用遮罩、优先级、挂点和手指配置 JSON',apply_settings)
	destination = host.line(self,'新版本保存路径（.tscn）')
	host.button(self,'保存新版本',save)
	message = Label.new()
	message.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(message)
	local_preview = TextureRect.new()
	local_preview.custom_minimum_size = Vector2(400,380)
	local_preview.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	local_preview.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	local_preview.texture = host.viewport.get_texture()
	add_child(local_preview)
func load_configuration():
	if not FileAccess.file_exists(config_path.text): message.text = '配置文件不存在，原场景已保留'; return
	var value = JSON.parse_string(FileAccess.get_file_as_string(config_path.text).trim_prefix('\ufeff'))
	if not value is Dictionary or not value.has('scene') or not FileAccess.file_exists(value.scene): message.text = '配置无效，原场景已保留'; return
	var loaded = I.load_scene(value.scene)
	if loaded.has('error'): message.text = loaded.error; return
	var control = loaded.scene.get_node_or_null('LayeringPlayer')
	if control==null or L.validate(I.skeleton(loaded.scene),control.config): loaded.scene.free(); message.text = '动画分层场景无效'; return
	config = value
	source_sha = FileAccess.get_sha256(config.scene)
	install(loaded.scene)
	garment.clear()
	garment.add_item('基础角色')
	if config.has('wardrobe'):
		var wardrobe = JSON.parse_string(FileAccess.get_file_as_string(config.wardrobe))
		for item in wardrobe.garments: garment.add_item(item.spec.id)
	message.text = '已载入。移动动画来自 MDM；瞄准、持剑、手指和武器为人工制作的测试资源。'
func install(scene):
	host.preview_token = ''
	host.confirmation = {}
	host.preview_resource = null
	if is_instance_valid(host.preview_scene): host.preview_scene.queue_free()
	built = scene
	host.preview_scene = scene
	host.preview_root.add_child(scene)
	runner = scene.get_node('LayeringPlayer')
	base_config = runner.config.duplicate(true)
	var visual = scene.get_node('FunctionalWeaponFixture/GripBar')
	weapon_mesh = visual.mesh
	weapon_visual_transform = visual.transform
	host.mesh_container.show()
	host.frame_mesh()
	set_mode(modes.selected)
func set_mode(index):
	if not is_instance_valid(runner): return
	runner.config = base_config.duplicate(true)
	var visual = built.get_node('FunctionalWeaponFixture/GripBar')
	visual.mesh = weapon_mesh
	visual.transform = weapon_visual_transform
	if index==1:
		var blade = BoxMesh.new()
		blade.size = Vector3(.04,.015,.75)
		visual.mesh = blade
		visual.transform = Transform3D(Basis.IDENTITY,Vector3(0,0,.3))
		runner.config.equipment.mode = 'animation'
		var layer = runner.config.layers[0]
		layer.clip = 'sword'
		var clip = Animation.new()
		clip.length = 1.2
		clip.loop_mode = Animation.LOOP_LINEAR
		var track = clip.add_track(Animation.TYPE_ROTATION_3D)
		clip.track_set_path(track,NodePath('Skeleton3D:upperarm_r'))
		var q = I.decode(layer.pose.upperarm_r).basis.get_rotation_quaternion()
		for pair in [[0.0,-.7],[.35,1.1],[.65,-.4],[1.2,-.7]]: clip.rotation_track_insert_key(track,pair[0],q*Quaternion(Vector3.FORWARD,pair[1]))
		runner.clips.sword = clip
	elif index==2:
		runner.config.layers = []
		runner.config.fingers = {}
		runner.config.equipment.mode = 'animation'
	elif index==3:
		var names = []
		var sk = I.skeleton(built)
		for i in sk.get_bone_count(): names.append(sk.get_bone_name(i))
		runner.config.layers.append({'id':'full-body','priority':100,'weight':1,'full_body':true,'mask':names,'pose':{}})
	runner.sample(runner.time_seconds)
	settings.text = JSON.stringify(runner.config,'\t')
func apply_settings():
	if not is_instance_valid(runner): return
	var candidate = JSON.parse_string(settings.text)
	if not candidate is Dictionary: message.text = '配置必须为 JSON 对象，原姿势已保留'; return
	var error = L.validate(I.skeleton(built),candidate)
	if error: message.text = error; return
	var previous = runner.config
	runner.config = candidate
	runner.sample(runner.time_seconds)
	if runner.result.has('error'): runner.config = previous; message.text = runner.result.error; return
	base_config = candidate.duplicate(true)
	message.text = '配置已应用到当前骨架修订版本'
func swap():
	if config.is_empty(): return
	# Every swap starts from the same pristine native avatar, never a garment assembly.
	if garment.selected==0: load_configuration(); return
	var source = I.load_scene(config.base_avatar)
	if source.has('error'): message.text = source.error; return
	var profile = I.extract(source.scene,config.family,{'sha256':FileAccess.get_sha256(config.base_avatar),'version':'native','authority':'local-native'})
	var wardrobe = JSON.parse_string(FileAccess.get_file_as_string(config.wardrobe))
	var item = wardrobe.garments[garment.selected-1]
	var fitted = G.fit(item.path,item.spec,source.scene,profile.profile,{})
	source.scene.free()
	if fitted.has('error'): message.text = fitted.error; return
	var template = I.load_scene(config.scene).scene
	var sk = I.skeleton(fitted.scene)
	var animation_player = template.get_node('LayeringSource').duplicate()
	fitted.scene.add_child(animation_player)
	for name in animation_player.get_animation_list():
		var clip = animation_player.get_animation(name).duplicate()
		for track in clip.get_track_count(): clip.track_set_path(track,NodePath(str(fitted.scene.get_path_to(sk))+':'+str(clip.track_get_path(track).get_subname(0))))
		animation_player.get_animation_library('').remove_animation(name)
		animation_player.get_animation_library('').add_animation(name,clip)
	var control = template.get_node('LayeringPlayer').duplicate()
	fitted.scene.add_child(control)
	var weapon = template.get_node('FunctionalWeaponFixture').duplicate()
	fitted.scene.add_child(weapon)
	control.skeleton_path = control.get_path_to(sk)
	control.player_path = control.get_path_to(animation_player)
	control.weapon_path = control.get_path_to(weapon)
	control.config = base_config.duplicate(true)
	control.config.skeleton_revision = L.signature(sk)
	template.free()
	install(fitted.scene)
	message.text = '已从原始角色换装：'+item.spec.id+'；'+str(sk.get_bone_count())+' 根骨骼。'
func save():
	if not is_instance_valid(built): return
	if destination.text.get_extension()!='tscn' or FileAccess.file_exists(destination.text): message.text = '请选择新的 .tscn 路径，已有版本将保留'; return
	M.own(built,built)
	var packed = PackedScene.new()
	packed.pack(built)
	var staged = ProjectSettings.globalize_path('user://layering-'+str(Time.get_ticks_usec())+'.tscn')
	var err = ResourceSaver.save(packed,staged)
	if err!=OK: message.text = '保存失败，源资源已保留'; return
	var output = []
	var code = OS.execute(host.python_edit.text,[host.host_edit.text.get_base_dir().path_join('interop_publish.py'),staged,ProjectSettings.globalize_path(destination.text)],output,true)
	message.text = '已保存：'+destination.text if code==0 else host.diagnostic_error('保存失败，源资源已保留',output)
