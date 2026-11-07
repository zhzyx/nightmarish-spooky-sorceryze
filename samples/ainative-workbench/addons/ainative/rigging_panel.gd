@tool
extends VBoxContainer
const Rig = preload('res://addons/ainative/rigging.gd')
var host: Control
var source = ''
var params: Dictionary = {}
var route: OptionButton
var height: SpinBox
var crop: SpinBox
var clean: CheckBox
var confirm: CheckBox
var corrections: TextEdit
var message: Label
var target: LineEdit
var built: Node3D
var overlay: MeshInstance3D
var source_field: LineEdit

func initialize(workbench: Control):
	host = workbench
	var title = Label.new()
	title.text = 'Character • anatomical template fitting (not general AI rigging)'
	add_child(title)
	if host.get_meta('ainative_builtin',false):
		var import_row = HBoxContainer.new()
		add_child(import_row)
		source_field = host.line(import_row,'Local .glb / embedded .gltf Mesh')
		var chooser = FileDialog.new()
		chooser.file_mode = FileDialog.FILE_MODE_OPEN_FILE
		chooser.access = FileDialog.ACCESS_FILESYSTEM
		chooser.filters = PackedStringArray(['*.glb,*.gltf ; Mesh'])
		add_child(chooser)
		chooser.file_selected.connect(set_source)
		host.button(import_row,'Browse Mesh',func(): chooser.popup_centered_ratio(.7))
		host.button(import_row,'Use Mesh',func(): set_source(source_field.text))
	var row = HBoxContainer.new()
	add_child(row)
	route = OptionButton.new()
	route.add_item('Standard humanoid • T pose')
	route.add_item('Free mesh • mark all joints')
	row.add_child(route)
	height = number(row,'Height (m)',1.8,.2,4,.01)
	crop = number(row,'Remove below source Y',-10000,-10000,10000,.001)
	clean = CheckBox.new()
	clean.text = 'Remove duplicate/degenerate faces'
	add_child(clean)
	confirm = CheckBox.new()
	confirm.text = 'I checked: Y-up, selected reference pose, distinct arms/legs; free/marked has complete joint landmarks'
	add_child(confirm)
	corrections = TextEdit.new()
	corrections.custom_minimum_size.y = 85
	corrections.placeholder_text = 'Joint positions in normalized metres and vertex weight overrides'
	corrections.text = '{"joints":{},"weights":{},"yaw_degrees":0}'
	add_child(corrections)
	var actions = HBoxContainer.new()
	add_child(actions)
	host.button(actions,'Fit / preview cleanup',fit)
	for motion in ['raise_arms','squat','turn']:
		host.button(actions,motion,func(): play(motion))
	host.button(actions,'Rest',rest)
	host.button(actions,'Load fitted joint markers',load_markers)
	target = host.line(self,'New character .tscn / saved version to reopen',ProjectSettings.globalize_path('user://character-v1.tscn'))
	var save_row = HBoxContainer.new()
	add_child(save_row)
	host.button(save_row,'Save new character version',save_version)
	host.button(save_row,'Reopen version + corrections',reopen)
	message = Label.new()
	message.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(message)

func number(parent: Node, label: String, value: float, low: float, high: float, step: float) -> SpinBox:
	var text = Label.new()
	text.text = label
	parent.add_child(text)
	var field = SpinBox.new()
	field.min_value = low
	field.max_value = high
	field.step = step
	field.value = value
	parent.add_child(field)
	return field

func set_source(path: String):
	source = path
	if source_field: source_field.text = path
	params = Rig.defaults(path)
	built = null
	confirm.button_pressed = false
	message.text = 'Source ready. Cleanup is previewed before saving; source bytes are never changed.'

func fit():
	if source.is_empty(): message.text = 'Preview a generated mesh first.'; return
	var edits = JSON.parse_string(corrections.text)
	if not edits is Dictionary: message.text = 'Invalid correction JSON'; return
	var candidate = params.duplicate(true)
	candidate.route = 'standard' if route.selected==0 else 'free'
	candidate.height_m = height.value
	candidate.crop_below_y = crop.value
	candidate.clean_faces = clean.button_pressed
	candidate.confirmed_humanoid = confirm.button_pressed
	for key in ['joints','weights','yaw_degrees','reference_pose','weights_geometry']:
		if edits.has(key): candidate[key] = edits[key]
	var result = Rig.build(source,candidate)
	if result.has('error'): message.text = result.error; return
	params = candidate
	show_scene(result.scene)
	message.text = JSON.stringify(result.diagnostics)+'\n'+('Ready for ROM review.' if result.accepted else 'Needs landmark / T-pose review.')

func show_scene(scene: Node3D):
	host.preview_token = ""
	host.confirmation = {}
	host.preview_resource = null
	if is_instance_valid(host.preview_scene): host.preview_scene.queue_free()
	built = scene
	host.preview_scene = scene
	host.preview_root.add_child(scene)
	host.mesh_container.show()
	host.frame_mesh()

func play(motion: String):
	if is_instance_valid(built): built.get_node('AnimationPlayer').play(motion)

func rest():
	if not is_instance_valid(built): return
	built.get_node('AnimationPlayer').stop()
	built.get_node('Skeleton3D').reset_bone_poses()

func save_version():
	if not is_instance_valid(built): message.text = 'Fit and inspect first.'; return
	if FileAccess.get_sha256(source)!=params.source_sha256: message.text = 'Source changed'; return
	var staged = host.state_dir.path_join('rig-'+str(Time.get_ticks_usec())+'.tscn')
	var error = Rig.stage(built,staged)
	if error: message.text = error; return
	var output = []
	var code = OS.execute(host.python_edit.text,[host.host_edit.text.get_base_dir().path_join('rigging_publish.py'),staged,ProjectSettings.globalize_path(target.text)],output,true)
	if code!=0: error = str(output)
	var config = ConfigFile.new()
	config.set_value('sources',params.source_sha256,source)
	config.save(host.state_dir.path_join('rigging-sources.cfg'))
	message.text = error if error else 'Saved immutable character version with source hash, corrections, Skin and ROM.'

func reopen():
	if not FileAccess.file_exists(target.text): message.text = 'Version not found'; return
	var packed = ResourceLoader.load(target.text,'PackedScene',ResourceLoader.CACHE_MODE_IGNORE)
	if not packed is PackedScene: message.text = 'Invalid scene'; return
	var scene = packed.instantiate()
	var metadata = scene.get_meta('rigging',{})
	if metadata.is_empty(): scene.free(); message.text = 'No rigging provenance'; return
	var config = ConfigFile.new()
	config.load(host.state_dir.path_join('rigging-sources.cfg'))
	var local_source = config.get_value('sources',metadata.source_sha256,source)
	if FileAccess.get_sha256(local_source)!=metadata.source_sha256: scene.free(); message.text = 'Source changed; corrections cannot be rebound.'; return
	source = local_source
	if source_field: source_field.text = local_source
	params = metadata.parameters
	route.select(0 if params.route=='standard' else 1)
	height.value = params.height_m
	crop.value = params.crop_below_y
	clean.button_pressed = params.clean_faces
	confirm.button_pressed = params.confirmed_humanoid
	corrections.text = JSON.stringify({'joints':params.joints,'weights':params.weights,'yaw_degrees':params.yaw_degrees,'reference_pose':params.reference_pose,'weights_geometry':params.get('weights_geometry','')},'  ')
	show_scene(scene)
	message.text = 'Reopened exact saved source + corrections. Changes require a new version filename.'

func load_markers():
	if not is_instance_valid(built): return
	var stored = built.get_meta('rigging').parameters
	var sk = built.get_node('Skeleton3D')
	var joints = {}
	for i in sk.get_bone_count():
		var v = sk.get_bone_global_rest(i).origin
		joints[sk.get_bone_name(i)] = [v.x,v.y,v.z]
	corrections.text = JSON.stringify({'joints':joints,'weights':stored.weights,'yaw_degrees':stored.yaw_degrees,'reference_pose':'marked','weights_geometry':stored.get('weights_geometry','') if not stored.weights.is_empty() else Rig.geometry_key(stored)},'  ')
	message.text = 'Edit marker coordinates in metres, then Fit. Weight IDs use compacted surface order; changing cleanup changes IDs.'

func _process(_delta):
	if not is_instance_valid(built):
		if is_instance_valid(overlay): overlay.hide()
		return
	if not is_instance_valid(overlay):
		overlay = MeshInstance3D.new()
		overlay.name = 'JointPreviewOnly'
		host.preview_root.add_child(overlay)
		var material = StandardMaterial3D.new()
		material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		material.no_depth_test = true
		material.albedo_color = Color(1,.65,.1)
		overlay.material_override = material
	overlay.show()
	var lines = ImmediateMesh.new()
	lines.surface_begin(Mesh.PRIMITIVE_LINES)
	var sk = built.get_node('Skeleton3D')
	for i in sk.get_bone_count():
		var parent = sk.get_bone_parent(i)
		if parent<0: continue
		lines.surface_add_vertex(sk.get_bone_global_pose(i).origin)
		lines.surface_add_vertex(sk.get_bone_global_pose(parent).origin)
	lines.surface_end()
	overlay.mesh = lines
