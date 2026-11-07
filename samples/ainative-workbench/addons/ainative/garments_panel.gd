@tool
extends VBoxContainer
const Garments = preload('res://addons/ainative/garments.gd')
const Interop = preload('res://addons/ainative/interop.gd')
var host: Control
var config_path: LineEdit
var targets: OptionButton
var garments: OptionButton
var shape: TextEdit
var destination: LineEdit
var message: Label
var config: Dictionary = {}
var built: Node3D
var local_preview: TextureRect
func initialize(workbench: Control):
	host = workbench
	var title = Label.new()
	title.text = '独立服装 · 已审核笼体拟合 · 仅布料绑定（不运行模拟）'
	add_child(title)
	config_path = host.line(self,'服装验收 / 衣柜配置 JSON')
	host.button(self,'载入衣柜',load_wardrobe)
	var row = HBoxContainer.new()
	add_child(row)
	targets = OptionButton.new()
	garments = OptionButton.new()
	row.add_child(targets)
	row.add_child(garments)
	shape = TextEdit.new()
	shape.custom_minimum_size.y = 50
	shape.text = '{"chest":1.0,"waist":1.0,"hips":1.0,"depth":1.0}'
	add_child(shape)
	host.button(row,'拟合 / 更换服装',build)
	host.button(row,'播放动画',play)
	destination = host.line(self,'组合角色新路径（.tscn）')
	host.button(self,'保存组合角色新版本',save)
	message = Label.new()
	message.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(message)
	local_preview = TextureRect.new()
	local_preview.custom_minimum_size = Vector2(360,280)
	local_preview.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	local_preview.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	local_preview.texture = host.viewport.get_texture()
	local_preview.hide()
	add_child(local_preview)
static func wardrobe_error(value) -> String:
	if not value is Dictionary or not value.get('targets') is Array or not value.get('garments') is Array: return '衣柜配置无效'
	for target in value.targets:
		if not target is Dictionary: return '目标配置必须为对象'
		for key in ['path','family','version','authority']:
			if not target.get(key) is String or target[key].is_empty(): return '目标配置需要非空字符串：'+key
		if target.family not in ['anatomical','ue4','ue5_manny','mixamo']: return '不支持该目标骨架类型'
		if not FileAccess.file_exists(target.path): return '目标文件不存在'
	for garment in value.garments:
		if not garment is Dictionary or not garment.get('path') is String or not garment.get('spec') is Dictionary: return '服装配置需要 path 和 spec 字段'
		if garment.path.get_extension().to_lower()!='glb' or not FileAccess.file_exists(garment.path): return '服装 GLB 文件不存在'
		var spec = garment.spec
		for key in ['id','version','kind','source_sha256']:
			if not spec.get(key) is String or spec[key].is_empty(): return '服装配置需要非空字符串：'+key
		if spec.kind not in ['top','armor','skirt']: return '不支持该服装类型'
		if spec.source_sha256.length()!=64 or not spec.source_sha256.is_valid_hex_number(false): return '服装 SHA256 校验值无效'
		if spec.has('occlude_torso') and not spec.occlude_torso is bool: return '遮挡开关必须为布尔值'
		if spec.has('yaw_degrees') and (not (spec.yaw_degrees is float or spec.yaw_degrees is int) or not is_finite(spec.yaw_degrees)): return '偏航角必须为有限数值'
		if spec.has('target_box'):
			if not spec.target_box is Array or spec.target_box.size()!=6: return '目标包围盒需要六个数值'
			for coordinate in spec.target_box:
				if not (coordinate is float or coordinate is int) or not is_finite(coordinate): return '目标包围盒坐标必须为有限数值'
	return ''
func load_wardrobe():
	var value = JSON.parse_string(FileAccess.get_file_as_string(config_path.text).trim_prefix('\ufeff'))
	var error = wardrobe_error(value)
	if error: message.text = error; return
	config = value
	targets.clear()
	garments.clear()
	for target in config.targets: targets.add_item({'anatomical':'解剖模板','ue4':'UE4','ue5_manny':'UE5 Manny','mixamo':'Mixamo'}[target.family])
	for garment in config.garments: garments.add_item(garment.spec.id+' / '+garment.spec.version)
	message.text = '独立资源已载入，请选择角色、服装和身体尺寸。'
func build():
	if targets.selected<0 or garments.selected<0: return
	var dimensions = JSON.parse_string(shape.text)
	if not dimensions is Dictionary: message.text = '身体尺寸必须为 JSON 对象'; return
	var target = config.targets[targets.selected]
	var source = config.garments[garments.selected]
	var loaded = Interop.load_scene(target.path)
	if loaded.has('error'): message.text = loaded.error; return
	var extracted = Interop.extract(loaded.scene,target.family,{'sha256':FileAccess.get_sha256(target.path),'version':target.version,'authority':target.authority})
	if extracted.has('error'): message.text = extracted.error; loaded.scene.free(); return
	var result = Garments.fit(source.path,source.spec,loaded.scene,extracted.profile,dimensions)
	loaded.scene.free()
	if result.has('error'): message.text = result.error; return
	host.preview_token = ''
	host.confirmation = {}
	host.preview_resource = null
	if is_instance_valid(host.preview_scene): host.preview_scene.queue_free()
	built = result.scene
	host.preview_scene = built
	host.preview_root.add_child(built)
	host.mesh_container.show()
	host.frame_mesh()
	local_preview.show()
	message.text = '服装 '+source.spec.id+' · 源文件校验值 '+source.spec.source_sha256+'\n派生版本 '+result.manifest.revision+' · '+str(result.manifest.vertices)+' 个顶点 · 未启用布料模拟'
func play():
	if not is_instance_valid(built): return
	for player in built.find_children('*','AnimationPlayer',true,false):
		var names = player.get_animation_list()
		if not names.is_empty(): player.play('squat' if player.has_animation('squat') else names[0])
func save():
	if not is_instance_valid(built): return
	if destination.text.get_extension()!='tscn': message.text = '请选择新的 .tscn 保存路径'; return
	if FileAccess.file_exists(destination.text): message.text = '该版本已存在，请选择新的保存路径。'; return
	var staged = host.state_dir.path_join('garment-'+str(Time.get_ticks_usec())+'.tscn')
	var error = Garments.stage(built,staged)
	if error: message.text = error; return
	var output = []
	var code = OS.execute(host.python_edit.text,[host.host_edit.text.get_base_dir().path_join('interop_publish.py'),staged,ProjectSettings.globalize_path(destination.text)],output,true)
	message.text = host.diagnostic_error('保存失败',output) if code!=0 else '独立组合角色已保存，已有版本保持不变：'+destination.text
