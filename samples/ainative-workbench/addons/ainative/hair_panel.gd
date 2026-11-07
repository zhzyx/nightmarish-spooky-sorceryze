@tool
extends 'res://addons/ainative/customization_panel.gd'
const Hair = preload('res://addons/ainative/hair.gd')
var hair_source: LineEdit
var hair_lod: OptionButton
var hair_cards: CheckBox
var hair_hat: CheckBox
var current_hair_spec = {}

func load_source():
	var loaded = Interop.load_scene(source_path.text)
	if loaded.has('error'):
		message.text = loaded.error
		return
	var candidate = loaded.scene
	var saved = candidate.get_node_or_null('IndependentHair')
	var snapshot = {}
	if saved!=null:
		snapshot = saved.get_meta('hair_data',{}).duplicate(true)
		var error = Hair.runtime_error(candidate,snapshot,saved.get_meta('authored_scalp_cap',{}))
		if error:
			message.text = '已保存的头发源资源或头皮已变化，当前角色已保留。'
			candidate.free()
			return
	candidate.free()
	var previous_spec = current_hair_spec
	current_hair_spec = {}
	var previous_scene = scene
	super.load_source()
	if scene==previous_scene:
		current_hair_spec = previous_spec
		return
	if not snapshot.is_empty():
		current_hair_spec = snapshot.spec
		hair_lod.select(snapshot.lod)
		hair_cards.set_pressed_no_signal(snapshot.cards)
		hair_hat.set_pressed_no_signal(snapshot.hat)
		update_representation()

func _ready():
	super._ready()
	name = 'HairPanel'
	var title = Label.new()
	title.text = '独立头发 / 头皮绑定 / 人工制作的发片与网格'
	add_child(title)
	move_child(title,0)
	hair_source = LineEdit.new()
	hair_source.placeholder_text = '已验证的头发资源清单 JSON'
	add_child(hair_source)
	move_child(hair_source,1)
	button('将独立头发绑定到当前头皮',bind_hair)
	move_child(get_child(-1),2)
	hair_lod = OptionButton.new()
	for label in ['完整细节（LOD 0）','中等细节（LOD 1）','低细节（LOD 2）']: hair_lod.add_item(label)
	add_child(hair_lod)
	move_child(hair_lod,3)
	hair_lod.item_selected.connect(func(_i): update_representation())
	hair_cards = CheckBox.new()
	hair_cards.text = '使用人工制作的导向发片（关闭后显示网格）'
	add_child(hair_cards)
	move_child(hair_cards,4)
	hair_cards.toggled.connect(func(_v): update_representation())
	hair_hat = CheckBox.new()
	hair_hat.text = '佩戴帽子并遮挡帽顶区域'
	add_child(hair_hat)
	move_child(hair_hat,5)
	hair_hat.toggled.connect(func(_v): update_representation())

func bind_hair():
	if not is_instance_valid(scene):
		message.text = '请先载入已完成骨骼映射的角色。'
		return
	var spec = JSON.parse_string(FileAccess.get_file_as_string(hair_source.text))
	if not spec is Dictionary:
		message.text = '请选择有效的头发资源，当前角色已保留。'
		return
	var result = Hair.bind(scene,spec)
	last_result = result
	if result.has('error'):
		message.text = result.error
		return
	current_hair_spec = spec.duplicate(true)
	update_representation()
	message.text = '独立后发已绑定，发根表面和导向线已更新。'

func apply():
	var static_change = false
	if is_instance_valid(scene):
		var dna = scene.get_meta('character_dna',{})
		for key in Customization.FACE_KEYS:
			if controls[key].value!=dna.get('face',{}).get(key,0.0): static_change = true
		for key in ['chest','waist','hips','depth']:
			if controls[key].value!=dna.get('body',{}).get(key,1.0): static_change = true
	if static_change and not current_hair_spec.is_empty():
		if not current_hair_spec.has('path'):
			message.text = '请选择原始头发资源以重新绑定当前脸型，当前角色已保留。'
			return
		var error = Hair.validate_source(current_hair_spec)
		if error:
			message.text = error
			return
	super.apply()
	if last_result.has('error'): return
	if is_instance_valid(scene) and not current_hair_spec.is_empty():
		var current = scene.get_node_or_null('IndependentHair')
		if current!=null and current.get_meta('hair_data').scalp_revision==scene.get_meta('scalp_binding').revision: return
		var spec = current_hair_spec.duplicate(true)
		spec.erase('binding_revision')
		var result = Hair.bind(scene,spec)
		if result.has('error'):
			message.text = result.error
			return
		update_representation()
		message.text = '脸型已更新，头发已重新绑定到调整后的头皮。'

func update_representation():
	if not is_instance_valid(scene): return
	var hair = scene.get_node_or_null('IndependentHair')
	if hair!=null and hair.is_node_ready(): hair.configure(hair_lod.selected,hair_cards.button_pressed,hair_hat.button_pressed)

func save_version():
	if not is_instance_valid(scene): return
	if destination.text.get_extension()!='tscn' or FileAccess.file_exists(destination.text):
		message.text = '请选择新的版本文件名。'
		return
	var staged = host_node.state_dir.path_join('hair-'+str(Time.get_ticks_usec())+'.tscn')
	var error = Hair.stage(scene,staged)
	if error:
		message.text = error
		return
	var output = []
	var code = OS.execute(host_node.python_edit.text,[host_node.host_edit.text.get_base_dir().path_join('interop_publish.py'),staged,ProjectSettings.globalize_path(destination.text)],output,true)
	message.text = '独立头发版本已保存。' if code==0 else host_node.diagnostic_error('保存未完成，当前角色已保留',output)
