@tool
extends VBoxContainer
const Session = preload('res://addons/ainative/character_session.gd')
var session: Node
var host
var source: LineEdit
var destination: LineEdit
var message: Label
var wardrobe: OptionButton
var hair_enabled: CheckBox
var cloth_enabled: CheckBox
var body: HSlider
var face: HSlider
var local_config: Dictionary = {}
var viewport: SubViewport
var animation_choice: OptionButton
var hair_lod: OptionButton
var hat: CheckBox
var quality: OptionButton
var export_target: OptionButton
var export_path: LineEdit
var jaw_width: HSlider
var nose_width: HSlider
var mouth: HSlider
var gaze: HSlider
var last_error = ''

func initialize(workbench):
	host = workbench
	name = 'CharacterWorkbench'
	var title = Label.new()
	title.text = '角色工作台 · 每个版本保存完整角色'
	add_child(title)
	source = host.line(self,'角色配置文件')
	var settings = ConfigFile.new()
	settings.load(host.state_dir.path_join('character.cfg'))
	source.text = settings.get_value('character','setup','')
	var chooser = FileDialog.new()
	chooser.file_mode = FileDialog.FILE_MODE_OPEN_FILE
	chooser.title = '选择角色配置'
	chooser.ok_button_text = '打开'
	chooser.cancel_button_text = '取消'
	chooser.access = FileDialog.ACCESS_FILESYSTEM
	chooser.filters = PackedStringArray(['*.json ; 角色配置'])
	add_child(chooser)
	chooser.file_selected.connect(func(path): source.text = path; load_character())
	host.button(self,'浏览角色',func(): chooser.popup_centered_ratio(.7))
	host.button(self,'载入角色',load_character)
	var row = HBoxContainer.new()
	add_child(row)
	var controls = VBoxContainer.new()
	controls.custom_minimum_size.x = 280
	row.add_child(controls)
	body = slider(controls,'体型宽度',.8,1.2,1.0)
	face = slider(controls,'脸部宽度',-.5,.5,0.0)
	jaw_width = slider(controls,'下颌宽度',-.5,.5,0.0)
	nose_width = slider(controls,'鼻部宽度',-.5,.5,0.0)
	host.button(controls,'应用体型和脸型',apply_shape)
	mouth = slider(controls,'张嘴程度',0,1,0)
	gaze = slider(controls,'视线左右偏移',-1,1,0)
	host.button(controls,'应用口型和视线',apply_expression)
	wardrobe = OptionButton.new()
	wardrobe.add_item('基础角色')
	controls.add_child(wardrobe)
	host.button(controls,'更换服装',change_clothes)
	hair_enabled = CheckBox.new()
	hair_enabled.text = '独立发型'
	controls.add_child(hair_enabled)
	hair_enabled.toggled.connect(func(_v): change_components())
	cloth_enabled = CheckBox.new()
	cloth_enabled.text = '布料动态'
	controls.add_child(cloth_enabled)
	cloth_enabled.toggled.connect(func(_v): change_components())
	host.button(controls,'播放 / 暂停动画',func(): session.playing = not session.playing)
	host.button(controls,'从头播放动画',func(): session.seek(0.0))
	animation_choice = OptionButton.new()
	animation_choice.add_item('当前动画')
	controls.add_child(animation_choice)
	host.button(controls,'切换动画',change_animation)
	hair_lod = OptionButton.new()
	for label in ['头发细节：完整','头发细节：中等','头发细节：低']: hair_lod.add_item(label)
	controls.add_child(hair_lod)
	hair_lod.item_selected.connect(func(_i): hair_options())
	hat = CheckBox.new()
	hat.text = '佩戴帽子'
	controls.add_child(hat)
	hat.toggled.connect(func(_v): hair_options())
	quality = OptionButton.new()
	for label in ['布料：完整模拟','布料：简化模拟','布料：刚性预览']: quality.add_item(label)
	controls.add_child(quality)
	quality.item_selected.connect(func(_i): cloth_quality())
	host.button(controls,'烘焙布料以流畅回放',func(): report(await session.bake_cloth(),'布料已烘焙，正在使用缓存回放。'))
	var container = SubViewportContainer.new()
	container.custom_minimum_size = Vector2(620,600)
	container.stretch = true
	row.add_child(container)
	viewport = SubViewport.new()
	viewport.size = Vector2i(620,600)
	viewport.own_world_3d = true
	container.add_child(viewport)
	var stage = Node3D.new()
	viewport.add_child(stage)
	var camera = Camera3D.new()
	stage.add_child(camera)
	camera.position = Vector3(0,1.2,3.2)
	camera.look_at(Vector3(0,1.0,0))
	var light = DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-30,-25,0)
	stage.add_child(light)
	var environment = WorldEnvironment.new()
	environment.environment = Environment.new()
	environment.environment.background_mode = Environment.BG_COLOR
	environment.environment.background_color = Color(.12,.15,.2)
	environment.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.environment.ambient_light_color = Color.WHITE
	environment.environment.ambient_light_energy = .7
	stage.add_child(environment)
	session = Session.new()
	session.stage = stage
	add_child(session)
	destination = host.line(self,'角色新版本路径（.tscn）')
	host.button(self,'保存角色版本',save)
	host.button(self,'重新打开角色版本',reopen)
	var scope = Label.new()
	scope.text = '兼容副本包含：身体、保留的蒙皮服装与腰带、静态脸型和已烘焙的身体动画。\n布料模拟表面、独立头发、头皮盖、面部动画和独立道具请使用完整角色版本。'
	scope.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(scope)
	export_target = OptionButton.new()
	for label in ['UE4','Manny','Mixamo']: export_target.add_item(label)
	add_child(export_target)
	export_path = host.line(self,'兼容副本新路径（.glb）')
	host.button(self,'导出已保存角色的兼容副本',export_character)
	message = Label.new()
	message.text = '请选择角色配置文件并载入角色。源资源保持不变。'
	message.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(message)
	var diagnostic = AcceptDialog.new()
	diagnostic.title = '角色操作详情'
	diagnostic.ok_button_text = '确定'
	add_child(diagnostic)
	host.button(self,'操作详情',func(): diagnostic.dialog_text = last_error if not last_error.is_empty() else '暂无失败记录。'; diagnostic.popup_centered(Vector2i(640,240)))

func slider(parent: Node, label: String, minimum: float, maximum: float, initial: float) -> HSlider:
	var title = Label.new()
	title.text = label
	parent.add_child(title)
	var control = HSlider.new()
	control.min_value = minimum
	control.max_value = maximum
	control.step = .01
	control.value = initial
	parent.add_child(control)
	return control

func report(error: String, success: String):
	last_error = error
	message.text = success if error.is_empty() else '操作未完成，已保留当前角色。请查看操作详情。'
	if not error.is_empty():
		var path = host.state_dir.path_join('character-diagnostics.log')
		var output = FileAccess.open(path,FileAccess.READ_WRITE if FileAccess.file_exists(path) else FileAccess.WRITE)
		if output:
			output.seek_end()
			output.store_line(JSON.stringify({'time':Time.get_datetime_string_from_system(true),'generation':session.generation,'error':error}))
			output.close()

func load_character():
	var value = Session.read_object(source.text)
	var error = session.rebuild(value.get('character',{}))
	if error.is_empty():
		local_config = value
		var settings = ConfigFile.new()
		settings.set_value('character','setup',source.text)
		settings.save(host.state_dir.path_join('character.cfg'))
		wardrobe.clear()
		wardrobe.add_item('基础角色')
		for item in value.get('wardrobe',[]): wardrobe.add_item(item.spec.id)
		animation_choice.clear()
		for item in value.get('animations',[]): animation_choice.add_item(item.label)
		hair_enabled.set_pressed_no_signal(false)
		cloth_enabled.set_pressed_no_signal(false)
		sync_controls_from_session()
	report(error,'角色已就绪，可以调整体型、服装和动画。')

func apply_shape():
	var value = session.recipe.duplicate(true)
	value.body = {'chest':body.value,'waist':body.value,'hips':body.value,'depth':body.value}
	value.face = {'face_width':face.value,'jaw_width':jaw_width.value,'nose_width':nose_width.value}
	report(session.rebuild(value,session.generation),'体型和脸型已更新，服装及绑定已刷新。')

func change_clothes():
	var value = session.recipe.duplicate(true)
	value.garment = {} if wardrobe.selected==0 else local_config.wardrobe[wardrobe.selected-1]
	# A different clothing source needs its own reviewed cloth binding.
	value.cloth = {}
	var error = session.rebuild(value,session.generation)
	if error.is_empty(): cloth_enabled.set_pressed_no_signal(false)
	report(error,'服装已更换，动画、脸型和发型已保留。')

func change_components():
	var value = session.recipe.duplicate(true)
	value.hair = local_config.get('hair',{}) if hair_enabled.button_pressed else {}
	value.cloth = local_config.get('cloth',{}) if cloth_enabled.button_pressed else {}
	var error = ''
	if hair_enabled.button_pressed and value.hair.is_empty(): error = '角色配置中尚未选择发型。'
	elif cloth_enabled.button_pressed and value.cloth.is_empty(): error = '角色配置中尚未选择布料绑定。'
	else: error = session.rebuild(value,session.generation)
	if not error.is_empty() and is_instance_valid(session.live):
		hair_enabled.set_pressed_no_signal(session.live.has_node('IndependentHair'))
		cloth_enabled.set_pressed_no_signal(session.live.has_node('ClothSolver'))
	report(error,'角色组件已更新。')

func save():
	var error = session.save_version(destination.text,host.python_edit.text,host.host_edit.text.get_base_dir().path_join('interop_publish.py'))
	report(error,'角色已保存为新版本。')

func reopen():
	report(session.reopen(destination.text,session.recipe),'角色版本已重新打开。')
	if session.recipe.get('read_only',false): message.text = '角色已重新打开，可直接回放；编辑时需要原始本地资源。'
	sync_controls_from_session()

func sync_controls_from_session():
	if is_instance_valid(session.live):
		var dna = session.live.get_meta('character_dna',{})
		body.set_value_no_signal(dna.get('body',{}).get('chest',1.0))
		face.set_value_no_signal(dna.get('face',{}).get('face_width',0.0))
		jaw_width.set_value_no_signal(dna.get('face',{}).get('jaw_width',0.0))
		nose_width.set_value_no_signal(dna.get('face',{}).get('nose_width',0.0))
		hair_enabled.set_pressed_no_signal(session.live.has_node('IndependentHair'))
		cloth_enabled.set_pressed_no_signal(session.live.has_node('ClothSolver'))
		var hair = session.live.get_node_or_null('IndependentHair')
		hair_lod.select(int(hair.config.lod) if hair else 0)
		hat.set_pressed_no_signal(hair.config.hat if hair else false)
		var cloth = session.live.get_node_or_null('ClothSolver')
		quality.select(int(cloth.settings.lod) if cloth else 0)
		wardrobe.clear()
		wardrobe.add_item('基础角色')
		var selected_garment = session.recipe.get('garment',{}).get('spec',{}).get('id','')
		for item in local_config.get('wardrobe',[]):
			wardrobe.add_item(item.spec.id)
			if item.spec.id==selected_garment: wardrobe.select(wardrobe.item_count-1)
		animation_choice.clear()
		for item in local_config.get('animations',[]):
			animation_choice.add_item(item.label)
			if item.path==session.recipe.get('motion',''): animation_choice.select(animation_choice.item_count-1)
		var mixed = Session.C.arbitrate(session.recipe.get('face_layers',[]))
		if not mixed.has('error'):
			mouth.set_value_no_signal(mixed.channels.get('jawOpen',0.0))
			gaze.set_value_no_signal(mixed.channels.get('lookRight',0.0)-mixed.channels.get('lookLeft',0.0))

func change_animation():
	if local_config.get('animations',[]).is_empty(): return
	var value = session.recipe.duplicate(true)
	value.motion = local_config.animations[animation_choice.selected].path
	report(session.rebuild(value,session.generation),'动画已切换，角色组件已保留。')

func apply_expression():
	if not is_instance_valid(session.live): return
	var layers = [{'id':'manual-mouth-gaze','priority':10,'channels':{'jawOpen':mouth.value,'lookLeft':maxf(-gaze.value,0),'lookRight':maxf(gaze.value,0)}}]
	var result = Session.C.apply_face(session.live,session.live.get_meta('character_dna'),layers)
	if result.has('error'): report(result.error,''); return
	session.recipe.face_layers = layers
	session.evaluate(0.0)
	report('','口型和视线已更新，发型绑定已保留。')

func hair_options():
	if not is_instance_valid(session.live): return
	var hair = session.live.get_node_or_null('IndependentHair')
	if hair:
		hair.configure(hair_lod.selected,true,hat.button_pressed)
		session.recipe.hair_display = {'lod':hair_lod.selected,'cards':true,'hat':hat.button_pressed}

func cloth_quality():
	if not is_instance_valid(session.live): return
	var cloth = session.live.get_node_or_null('ClothSolver')
	if not cloth: return
	session.cancel_bake()
	cloth.settings.lod = quality.selected
	cloth.mode = 'realtime'
	cloth.cache = {}
	report(cloth.initialize(),'布料质量已更新，之前的烘焙缓存已失效。')
	session.recipe.cloth_settings = cloth.settings.duplicate(true)

func export_character():
	var profiles = local_config.get('target_profiles',[])
	if profiles.size()!=3: report('请在本地角色配置中指定三个已验证的目标骨架配置。',''); return
	var target = Session.read_object(profiles[export_target.selected])
	var error = session.export_version(destination.text,target,export_path.text,host.python_edit.text,host.host_edit.text.get_base_dir().path_join('interop_publish.py'))
	report(error,'兼容副本已保存。所包含和省略的通道详见导出报告。')
