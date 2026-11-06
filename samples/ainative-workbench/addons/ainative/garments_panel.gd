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
	title.text = 'Independent garments • reviewed cage fit • cloth binding only (no solver)'
	add_child(title)
	config_path = host.line(self,'Garment acceptance / wardrobe configuration JSON')
	host.button(self,'Load wardrobe',load_wardrobe)
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
	host.button(row,'Fit / swap garment',build)
	host.button(row,'Play animation',play)
	destination = host.line(self,'New .tscn assembly destination')
	host.button(self,'Save new assembly version',save)
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
	if not value is Dictionary or not value.get('targets') is Array or not value.get('garments') is Array: return 'Invalid wardrobe configuration'
	for target in value.targets:
		if not target is Dictionary: return 'Target must be an object'
		for key in ['path','family','version','authority']:
			if not target.get(key) is String or target[key].is_empty(): return 'Target requires nonempty string: '+key
		if target.family not in ['anatomical','ue4','ue5_manny','mixamo']: return 'Unsupported target skeleton family'
		if not FileAccess.file_exists(target.path): return 'Target file missing'
	for garment in value.garments:
		if not garment is Dictionary or not garment.get('path') is String or not garment.get('spec') is Dictionary: return 'Garment requires path and spec'
		if garment.path.get_extension().to_lower()!='glb' or not FileAccess.file_exists(garment.path): return 'Garment GLB missing'
		var spec = garment.spec
		for key in ['id','version','kind','source_sha256']:
			if not spec.get(key) is String or spec[key].is_empty(): return 'Garment requires nonempty string: '+key
		if spec.kind not in ['top','armor','skirt']: return 'Unsupported garment kind'
		if spec.source_sha256.length()!=64 or not spec.source_sha256.is_valid_hex_number(false): return 'Invalid garment SHA256'
		if spec.has('occlude_torso') and not spec.occlude_torso is bool: return 'Occlusion must be boolean'
		if spec.has('yaw_degrees') and (not (spec.yaw_degrees is float or spec.yaw_degrees is int) or not is_finite(spec.yaw_degrees)): return 'Yaw must be finite'
		if spec.has('target_box'):
			if not spec.target_box is Array or spec.target_box.size()!=6: return 'Target box needs six numbers'
			for coordinate in spec.target_box:
				if not (coordinate is float or coordinate is int) or not is_finite(coordinate): return 'Target box must be finite'
	return ''
func load_wardrobe():
	var value = JSON.parse_string(FileAccess.get_file_as_string(config_path.text).trim_prefix('\ufeff'))
	var error = wardrobe_error(value)
	if error: message.text = error; return
	config = value
	targets.clear()
	garments.clear()
	for target in config.targets: targets.add_item(target.family)
	for garment in config.garments: garments.add_item(garment.spec.id+' / '+garment.spec.version)
	message.text = 'Loaded independent sources. Choose avatar, garment and body dimensions.'
func build():
	if targets.selected<0 or garments.selected<0: return
	var dimensions = JSON.parse_string(shape.text)
	if not dimensions is Dictionary: message.text = 'Body dimensions must be an object'; return
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
	message.text = 'Garment '+source.spec.id+' source '+source.spec.source_sha256+'\nDerived '+result.manifest.revision+' · '+str(result.manifest.vertices)+' vertices · cloth solver: none'
func play():
	if not is_instance_valid(built): return
	for player in built.find_children('*','AnimationPlayer',true,false):
		var names = player.get_animation_list()
		if not names.is_empty(): player.play('squat' if player.has_animation('squat') else names[0])
func save():
	if not is_instance_valid(built): return
	if destination.text.get_extension()!='tscn': message.text = 'Choose a new .tscn destination'; return
	if FileAccess.file_exists(destination.text): message.text = 'This version already exists. Choose a new destination.'; return
	var staged = host.state_dir.path_join('garment-'+str(Time.get_ticks_usec())+'.tscn')
	var error = Garments.stage(built,staged)
	if error: message.text = error; return
	var output = []
	var code = OS.execute(host.python_edit.text,[host.host_edit.text.get_base_dir().path_join('interop_publish.py'),staged,ProjectSettings.globalize_path(destination.text)],output,true)
	message.text = str(output) if code!=0 else 'Published independent assembly without overwriting any version: '+destination.text
