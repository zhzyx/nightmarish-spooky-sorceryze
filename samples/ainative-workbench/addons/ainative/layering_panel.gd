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
	config_path = host.line(self,'Layering configuration JSON')
	host.button(self,'Load layering scene',load_configuration)
	modes = OptionButton.new()
	for name in ['Run + aim / two hand IK','Single hand sword','Original animation','Full body override']: modes.add_item(name)
	add_child(modes)
	modes.item_selected.connect(set_mode)
	garment = OptionButton.new()
	garment.add_item('Base avatar')
	add_child(garment)
	host.button(self,'Swap garment from original base',swap)
	host.button(self,'Play / pause',func():
		if is_instance_valid(runner): runner.playing = not runner.playing)
	settings = TextEdit.new()
	settings.custom_minimum_size.y = 100
	add_child(settings)
	host.button(self,'Apply masks / priorities / sockets / fingers JSON',apply_settings)
	destination = host.line(self,'New .tscn destination')
	host.button(self,'Save new version',save)
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
	if not FileAccess.file_exists(config_path.text): message.text = 'Configuration missing; previous scene retained'; return
	var value = JSON.parse_string(FileAccess.get_file_as_string(config_path.text).trim_prefix('\ufeff'))
	if not value is Dictionary or not value.has('scene') or not FileAccess.file_exists(value.scene): message.text = 'Invalid configuration; previous scene retained'; return
	var loaded = I.load_scene(value.scene)
	if loaded.has('error'): message.text = loaded.error; return
	var control = loaded.scene.get_node_or_null('LayeringPlayer')
	if control==null or L.validate(I.skeleton(loaded.scene),control.config): loaded.scene.free(); message.text = 'Invalid layering scene'; return
	config = value
	source_sha = FileAccess.get_sha256(config.scene)
	install(loaded.scene)
	garment.clear()
	garment.add_item('Base avatar')
	if config.has('wardrobe'):
		var wardrobe = JSON.parse_string(FileAccess.get_file_as_string(config.wardrobe))
		for item in wardrobe.garments: garment.add_item(item.spec.id)
	message.text = 'Loaded. Locomotion MDM; aiming, sword, fingers and weapon are authored fixtures.'
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
	if not candidate is Dictionary: message.text = 'Expected configuration object; previous pose retained'; return
	var error = L.validate(I.skeleton(built),candidate)
	if error: message.text = error; return
	var previous = runner.config
	runner.config = candidate
	runner.sample(runner.time_seconds)
	if runner.result.has('error'): runner.config = previous; message.text = runner.result.error; return
	base_config = candidate.duplicate(true)
	message.text = 'Configuration applied to current skeleton revision'
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
	message.text = 'Swapped '+item.spec.id+' from original base; '+str(sk.get_bone_count())+' bones.'
func save():
	if not is_instance_valid(built): return
	if destination.text.get_extension()!='tscn' or FileAccess.file_exists(destination.text): message.text = 'Choose a new .tscn path; existing versions are retained'; return
	M.own(built,built)
	var packed = PackedScene.new()
	packed.pack(built)
	var staged = ProjectSettings.globalize_path('user://layering-'+str(Time.get_ticks_usec())+'.tscn')
	var err = ResourceSaver.save(packed,staged)
	if err!=OK: message.text = 'Save failed; source retained'; return
	var output = []
	var code = OS.execute(host.python_edit.text,[ProjectSettings.globalize_path('res://../../tools/ainative/interop_publish.py'),staged,ProjectSettings.globalize_path(destination.text)],output,true)
	message.text = 'Saved '+destination.text if code==0 else 'Save failed; source retained: '+str(output)
