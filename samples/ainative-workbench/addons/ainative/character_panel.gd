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
	title.text = 'Character workbench · one character, one version'
	add_child(title)
	source = host.line(self,'Character setup file')
	var settings = ConfigFile.new()
	settings.load(host.state_dir.path_join('character.cfg'))
	source.text = settings.get_value('character','setup','')
	var chooser = FileDialog.new()
	chooser.file_mode = FileDialog.FILE_MODE_OPEN_FILE
	chooser.access = FileDialog.ACCESS_FILESYSTEM
	chooser.filters = PackedStringArray(['*.json ; Character setup'])
	add_child(chooser)
	chooser.file_selected.connect(func(path): source.text = path; load_character())
	host.button(self,'Browse characters',func(): chooser.popup_centered_ratio(.7))
	host.button(self,'Choose character',load_character)
	var row = HBoxContainer.new()
	add_child(row)
	var controls = VBoxContainer.new()
	controls.custom_minimum_size.x = 280
	row.add_child(controls)
	body = slider(controls,'Body width',.8,1.2,1.0)
	face = slider(controls,'Face width',-.5,.5,0.0)
	jaw_width = slider(controls,'Jaw width',-.5,.5,0.0)
	nose_width = slider(controls,'Nose width',-.5,.5,0.0)
	host.button(controls,'Apply body and face',apply_shape)
	mouth = slider(controls,'Mouth opening',0,1,0)
	gaze = slider(controls,'Look left / right',-1,1,0)
	host.button(controls,'Apply mouth and gaze',apply_expression)
	wardrobe = OptionButton.new()
	wardrobe.add_item('Base character')
	controls.add_child(wardrobe)
	host.button(controls,'Change clothes',change_clothes)
	hair_enabled = CheckBox.new()
	hair_enabled.text = 'Independent hairstyle'
	controls.add_child(hair_enabled)
	hair_enabled.toggled.connect(func(_v): change_components())
	cloth_enabled = CheckBox.new()
	cloth_enabled.text = 'Cloth movement'
	controls.add_child(cloth_enabled)
	cloth_enabled.toggled.connect(func(_v): change_components())
	host.button(controls,'Play / pause animation',func(): session.playing = not session.playing)
	host.button(controls,'Restart animation',func(): session.seek(0.0))
	animation_choice = OptionButton.new()
	animation_choice.add_item('Current animation')
	controls.add_child(animation_choice)
	host.button(controls,'Change animation',change_animation)
	hair_lod = OptionButton.new()
	for label in ['Hair detail: full','Hair detail: medium','Hair detail: low']: hair_lod.add_item(label)
	controls.add_child(hair_lod)
	hair_lod.item_selected.connect(func(_i): hair_options())
	hat = CheckBox.new()
	hat.text = 'Wear hat'
	controls.add_child(hat)
	hat.toggled.connect(func(_v): hair_options())
	quality = OptionButton.new()
	for label in ['Cloth: full simulation','Cloth: reduced simulation','Cloth: rigid preview']: quality.add_item(label)
	controls.add_child(quality)
	quality.item_selected.connect(func(_i): cloth_quality())
	host.button(controls,'Bake cloth for smooth playback',func(): report(await session.bake_cloth(),'Cloth baked; replay active.'))
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
	destination = host.line(self,'New character version (.tscn)')
	host.button(self,'Save character version',save)
	host.button(self,'Reopen character version',reopen)
	var scope = Label.new()
	scope.text = 'Compatibility copy: body, retained skinned clothing/waistband, static face shape and baked body motion.\nSimulated cloth surfaces, independent hair geometry, scalp cap, face animation and separate props are excluded; use the full character version for these.'
	scope.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(scope)
	export_target = OptionButton.new()
	for label in ['UE4','Manny','Mixamo']: export_target.add_item(label)
	add_child(export_target)
	export_path = host.line(self,'New compatibility copy (.glb)')
	host.button(self,'Export saved character copy',export_character)
	message = Label.new()
	message.text = 'Browse to your character setup, then choose the character. Source assets stay unchanged.'
	message.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(message)
	var diagnostic = AcceptDialog.new()
	diagnostic.title = 'Character operation details'
	add_child(diagnostic)
	host.button(self,'Operation details',func(): diagnostic.dialog_text = last_error if not last_error.is_empty() else 'No failed operation.'; diagnostic.popup_centered(Vector2i(640,240)))

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
	message.text = success if error.is_empty() else 'Operation could not finish; current character retained. See operation details.'
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
		wardrobe.add_item('Base character')
		for item in value.get('wardrobe',[]): wardrobe.add_item(item.spec.id)
		animation_choice.clear()
		for item in value.get('animations',[]): animation_choice.add_item(item.label)
		hair_enabled.set_pressed_no_signal(false)
		cloth_enabled.set_pressed_no_signal(false)
		sync_controls_from_session()
	report(error,'Character ready. Change shape, clothing and animation here.')

func apply_shape():
	var value = session.recipe.duplicate(true)
	value.body = {'chest':body.value,'waist':body.value,'hips':body.value,'depth':body.value}
	value.face = {'face_width':face.value,'jaw_width':jaw_width.value,'nose_width':nose_width.value}
	report(session.rebuild(value,session.generation),'Shape updated; clothing and bindings refreshed.')

func change_clothes():
	var value = session.recipe.duplicate(true)
	value.garment = {} if wardrobe.selected==0 else local_config.wardrobe[wardrobe.selected-1]
	# A different clothing source needs its own reviewed cloth binding.
	value.cloth = {}
	var error = session.rebuild(value,session.generation)
	if error.is_empty(): cloth_enabled.set_pressed_no_signal(false)
	report(error,'Clothing changed; animation, face and hairstyle retained.')

func change_components():
	var value = session.recipe.duplicate(true)
	value.hair = local_config.get('hair',{}) if hair_enabled.button_pressed else {}
	value.cloth = local_config.get('cloth',{}) if cloth_enabled.button_pressed else {}
	var error = ''
	if hair_enabled.button_pressed and value.hair.is_empty(): error = 'No hairstyle selected in the character setup.'
	elif cloth_enabled.button_pressed and value.cloth.is_empty(): error = 'No cloth binding selected in the character setup.'
	else: error = session.rebuild(value,session.generation)
	if not error.is_empty() and is_instance_valid(session.live):
		hair_enabled.set_pressed_no_signal(session.live.has_node('IndependentHair'))
		cloth_enabled.set_pressed_no_signal(session.live.has_node('ClothSolver'))
	report(error,'Character components updated.')

func save():
	var error = session.save_version(destination.text,host.python_edit.text,host.host_edit.text.get_base_dir().path_join('interop_publish.py'))
	report(error,'Character saved as a new version.')

func reopen():
	report(session.reopen(destination.text,session.recipe),'Character version reopened.')
	if session.recipe.get('read_only',false): message.text = 'Character reopened for playback. Original local sources are needed for editing.'
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
		wardrobe.add_item('Base character')
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
	report(session.rebuild(value,session.generation),'Animation changed; character components retained.')

func apply_expression():
	if not is_instance_valid(session.live): return
	var layers = [{'id':'manual-mouth-gaze','priority':10,'channels':{'jawOpen':mouth.value,'lookLeft':maxf(-gaze.value,0),'lookRight':maxf(gaze.value,0)}}]
	var result = Session.C.apply_face(session.live,session.live.get_meta('character_dna'),layers)
	if result.has('error'): report(result.error,''); return
	session.recipe.face_layers = layers
	session.evaluate(0.0)
	report('','Mouth and gaze updated; hairstyle binding retained.')

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
	report(cloth.initialize(),'Cloth quality updated; prior bake invalidated.')
	session.recipe.cloth_settings = cloth.settings.duplicate(true)

func export_character():
	var profiles = local_config.get('target_profiles',[])
	if profiles.size()!=3: report('Choose the three verified target profiles in the local recipe.',''); return
	var target = Session.read_object(profiles[export_target.selected])
	var error = session.export_version(destination.text,target,export_path.text,host.python_edit.text,host.host_edit.text.get_base_dir().path_join('interop_publish.py'))
	report(error,'Compatibility copy saved. See its report for included and excluded channels.')
