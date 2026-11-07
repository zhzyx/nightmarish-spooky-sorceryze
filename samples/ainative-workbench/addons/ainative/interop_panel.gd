@tool
extends VBoxContainer
const Interop = preload('res://addons/ainative/interop.gd')
var host: Control
var source_path: LineEdit
var reference_path: LineEdit
var source_family: OptionButton
var target_family: OptionButton
var authority: LineEdit
var version: LineEdit
var corrections: TextEdit
var contacts: TextEdit
var destination: LineEdit
var message: Label
var motions: OptionButton
var built: Node3D
var profile: Dictionary = {}
var input_hashes: Dictionary = {}

func initialize(workbench: Control):
	host = workbench
	var title = Label.new()
	title.text = '骨架互通 · 版本化参考资源'
	add_child(title)
	source_path = host.line(self,'源绑定角色（.tscn / .glb / .fbx）','')
	host.button(self,'选择源角色',func(): browse(source_path))
	reference_path = host.line(self,'目标参考资源或已保存的 .profile.json','')
	host.button(self,'选择目标参考资源 / 骨架配置',func(): browse(reference_path))
	var row = HBoxContainer.new()
	add_child(row)
	source_family = OptionButton.new()
	target_family = OptionButton.new()
	for family in Interop.FAMILIES:
		var label = {'anatomical':'解剖模板','ue4':'UE4','ue5_manny':'UE5 Manny','ue5_quinn':'UE5 Quinn','mixamo':'Mixamo'}[family]
		source_family.add_item(label)
		source_family.set_item_metadata(source_family.item_count-1,family)
		target_family.add_item(label)
		target_family.set_item_metadata(target_family.item_count-1,family)
	row.add_child(source_family)
	row.add_child(target_family)
	target_family.select(1)
	authority = host.line(self,'参考来源标识（URI，不填本地路径）','')
	version = host.line(self,'参考来源版本','')
	corrections = TextEdit.new()
	corrections.custom_minimum_size.y = 60
	corrections.text = '{}'
	corrections.tooltip_text = '修正目标语义到实际骨骼名的映射，例如 {"hips":"mixamorig:Hips"}'
	add_child(corrections)
	contacts = TextEdit.new()
	contacts.custom_minimum_size.y = 55
	contacts.text = '{}'
	contacts.tooltip_text = '按动画指定脚部着地区间：{"squat":[{"side":"l","start":0,"end":2},{"side":"r","start":0,"end":2}]}'
	add_child(contacts)
	var actions = HBoxContainer.new()
	add_child(actions)
	host.button(actions,'提取并预览目标骨架',preview_target)
	host.button(actions,'适配网格、绑定并重定向',build)
	motions = OptionButton.new()
	actions.add_child(motions)
	host.button(actions,'播放',play)
	host.button(actions,'恢复静止姿势',rest)
	destination = host.line(self,'新版本路径（.json 骨架配置 / .tscn 角色 / .glb 导出）','')
	host.button(self,'保存新版本 / 导出',save)
	message = Label.new()
	message.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(message)

func target_profile() -> Dictionary:
	if reference_path.text.get_extension().to_lower()=='json':
		var p = JSON.parse_string(FileAccess.get_file_as_string(reference_path.text))
		if not p is Dictionary: return {'error':'骨架配置 JSON 无效'}
		var error = Interop.validate(p)
		return {'profile':p} if error=='' else {'error':error}
	var loaded = Interop.load_scene(reference_path.text)
	if loaded.has('error'): return loaded
	var edits = JSON.parse_string(corrections.text)
	if not edits is Dictionary: loaded.scene.free(); return {'error':'映射修正 JSON 无效'}
	var result = Interop.extract(loaded.scene,str(target_family.get_item_metadata(target_family.selected)),{'sha256':FileAccess.get_sha256(reference_path.text),'version':version.text,'authority':authority.text},edits)
	loaded.scene.free()
	return result

func preview_target():
	var result = target_profile()
	if result.has('error'): message.text = result.error; return
	profile = result.profile
	input_hashes = {reference_path.text:FileAccess.get_sha256(reference_path.text)}
	message.text = '已完成语义映射 · '+str(profile.bones.size())+' 根实际骨骼 · 修订 '+profile.revision+'\n'+JSON.stringify(profile.mapping)
	var scene = Node3D.new()
	var sk = Interop.make_skeleton(profile)
	scene.add_child(sk)
	var lines = ImmediateMesh.new()
	lines.surface_begin(Mesh.PRIMITIVE_LINES)
	for i in profile.bones.size():
		var parent = int(profile.bones[i].parent)
		if parent<0: continue
		lines.surface_add_vertex(Interop.decode(profile.bones[i].global_rest).origin)
		lines.surface_add_vertex(Interop.decode(profile.bones[parent].global_rest).origin)
	lines.surface_end()
	var mesh = MeshInstance3D.new()
	mesh.mesh = lines
	var material = StandardMaterial3D.new()
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	material.albedo_color = Color(1,.65,.1)
	mesh.material_override = material
	scene.add_child(mesh)
	show_scene(scene)

func browse(field: LineEdit):
	var dialog = FileDialog.new()
	dialog.access = FileDialog.ACCESS_FILESYSTEM
	dialog.file_mode = FileDialog.FILE_MODE_OPEN_FILE
	dialog.title = '选择骨架或角色资源'
	dialog.ok_button_text = '打开'
	dialog.cancel_button_text = '取消'
	dialog.filters = PackedStringArray(['*.tscn, *.glb, *.gltf, *.fbx, *.json ; 骨架 / 角色'])
	add_child(dialog)
	dialog.file_selected.connect(func(path): field.text = path; dialog.queue_free())
	dialog.canceled.connect(dialog.queue_free)
	dialog.popup_centered_ratio(.7)

func show_scene(scene: Node3D):
	host.preview_token = ''
	host.confirmation = {}
	host.preview_resource = null
	if is_instance_valid(host.preview_scene): host.preview_scene.queue_free()
	built = scene
	host.preview_scene = scene
	host.preview_root.add_child(scene)
	host.mesh_container.show()
	host.frame_mesh()

func build():
	var loaded = Interop.load_scene(source_path.text)
	if loaded.has('error'): message.text = loaded.error; return
	var source = Interop.extract(loaded.scene,str(source_family.get_item_metadata(source_family.selected)),{'sha256':FileAccess.get_sha256(source_path.text),'version':FileAccess.get_sha256(source_path.text),'authority':'artifact:source-avatar'})
	var target = target_profile()
	if source.has('error') or target.has('error'): message.text = str(source.get('error',target.get('error',''))); loaded.scene.free(); return
	profile = target.profile
	host.preview_root.add_child(loaded.scene)
	var result = Interop.bind(loaded.scene,source.profile,profile)
	if result.has('error'): message.text = result.error; loaded.scene.free(); return
	var planted = JSON.parse_string(contacts.text)
	if not planted is Dictionary: message.text = '脚部着地区间 JSON 无效'; loaded.scene.free(); result.scene.free(); return
	var animations = Interop.attach_animations(result.scene,loaded.scene,source.profile,profile,planted)
	var metadata = result.scene.get_meta('interop')
	metadata['contacts'] = planted
	metadata['animation_source_sha256'] = FileAccess.get_sha256(source_path.text)
	metadata['avatar_revision'] = Interop.revision({'binding':metadata.avatar_revision,'contacts':planted,'animation_source':metadata.animation_source_sha256})
	loaded.scene.free()
	if animations.has('error'): message.text = animations.error; result.scene.free(); return
	input_hashes = {source_path.text:FileAccess.get_sha256(source_path.text),reference_path.text:FileAccess.get_sha256(reference_path.text)}
	show_scene(result.scene)
	motions.clear()
	for motion in built.get_node('AnimationPlayer').get_animation_list():
		motions.add_item({'raise_arms':'抬臂','squat':'下蹲','turn':'转身'}.get(motion,motion))
		motions.set_item_metadata(motions.item_count-1,motion)
	message.text = JSON.stringify(result.diagnostics)+'\n'+JSON.stringify(animations)+'\n导出前请检查姿势、双手和双脚。仍需在目标工具中单独验证。'

func play():
	if is_instance_valid(built) and built.has_node('AnimationPlayer') and motions.item_count>0: built.get_node('AnimationPlayer').play(str(motions.get_item_metadata(motions.selected)))

func rest():
	if not is_instance_valid(built): return
	if built.has_node('AnimationPlayer'): built.get_node('AnimationPlayer').stop()
	var sk = Interop.skeleton(built)
	if sk: sk.reset_bone_poses()

func save():
	for path in input_hashes:
		if FileAccess.get_sha256(path)!=input_hashes[path]: message.text = '输入已变化，请重新生成一个修订版本。'; return
	var suffix = destination.text.get_extension().to_lower()
	var staged = host.state_dir.path_join('interop-'+str(Time.get_ticks_usec())+'.'+suffix)
	var error = ''
	if suffix=='json' and not profile.is_empty():
		var file = FileAccess.open(staged,FileAccess.WRITE)
		if file==null: message.text = '无法暂存骨架配置'; return
		file.store_string(JSON.stringify(profile,'  ',true,true))
		file.close()
	elif is_instance_valid(built) and built.has_meta('interop'):
		rest()
		error = Interop.stage_scene(built,staged) if suffix=='tscn' else Interop.stage_glb(built,staged) if suffix=='glb' else '请选择 .json、.tscn 或 .glb 路径'
	else: error = '请先提取骨架配置或生成角色'
	if error: message.text = error; return
	var output = []
	var code = OS.execute(host.python_edit.text,[host.host_edit.text.get_base_dir().path_join('interop_publish.py'),staged,ProjectSettings.globalize_path(destination.text)],output,true)
	message.text = host.diagnostic_error('保存失败',output) if code!=0 else '已保存不可覆盖的新版本。目标工具的验证记录补齐前，绑定状态保持为 target_bound。'
