@tool
extends VBoxContainer
const I = preload('res://addons/ainative/interop.gd')
const L = preload('res://addons/ainative/layering.gd')
const Solver = preload('res://addons/ainative/cloth_solver.gd')
const G = preload('res://addons/ainative/garments.gd')
var host: Control
var configuration: LineEdit
var destination: LineEdit
var settings_edit: TextEdit
var modes: OptionButton
var quality: OptionButton
var message: Label
var cloth: Node3D
var built: Node3D
var runner: Node
var bake_generation: int = 0
static func binding_error(binding) -> String:
	if not binding is Dictionary or binding.get('schema')!=1 or binding.get('kind') not in ['cape','skirt']: return '布料绑定格式或类型无效'
	for key in ['vertices','indices','proxy','edges','mapping','weights','offsets','pins']:
		if not binding.get(key) is Array or binding[key].is_empty(): return '缺少布料绑定数组：'+key
	var n = binding.proxy.size(); var r = binding.vertices.size()
	if binding.pins.size()!=n or binding.mapping.size()!=r or binding.weights.size()!=r or binding.offsets.size()!=r or binding.indices.size()%3!=0: return '布料绑定数据的数量不一致'
	for key in ['vertices','proxy','offsets']:
		for point in binding[key]:
			if not point is Array or point.size()!=3: return '布料绑定点必须包含三个坐标'
			for coordinate in point:
				if not (coordinate is int or coordinate is float) or not is_finite(coordinate): return '布料绑定点坐标必须为有限数值'
	for index in binding.indices:
		if not (index is int or index is float) or int(index)!=index or index<0 or index>=r: return '渲染顶点索引无效'
	for edge in binding.edges:
		if not edge is Array or edge.size()!=2: return '模拟边无效'
		for index in edge:
			if not (index is int or index is float) or int(index)!=index or index<0 or index>=n: return '模拟粒子索引无效'
	for i in r:
		if not binding.mapping[i] is Array or not binding.weights[i] is Array or binding.mapping[i].size()!=4 or binding.weights[i].size()!=4: return '每个渲染顶点需要四组映射权重'
		var total = 0.0
		for k in 4:
			var index = binding.mapping[i][k]; var weight = binding.weights[i][k]
			if not (index is int or index is float) or int(index)!=index or index<0 or index>=n: return '映射粒子无效'
			if not (weight is int or weight is float) or not is_finite(weight) or weight<0 or weight>1: return '渲染绑定权重无效'
			total += weight
		if absf(total-1)>.00001: return '渲染权重之和必须为 1'
	for pin in binding.pins:
		if not (pin is int or pin is float) or not is_finite(pin) or pin<0 or pin>1: return '固定点权重无效'
	return ''
func initialize(workbench):
	host = workbench; name = 'ClothPanel'
	var title = Label.new(); title.text = '布料 · 独立模拟与渲染绑定 · 世界空间 XPBD'; add_child(title)
	configuration = host.line(self,'布料场景及不可变绑定配置 JSON')
	host.button(self,'组装 / 重新打开布料',build)
	settings_edit = TextEdit.new(); settings_edit.custom_minimum_size.y = 65; settings_edit.text = '{"mass":0.15,"compliance":0.000001,"pin_weight":1.0,"lod":0}'; add_child(settings_edit)
	var help = Label.new(); help.text = '质量 mass：0.01–10；柔顺度 compliance：0–0.01；固定权重 pin_weight：0.5–1；单点覆盖 pin_overrides 示例：{"0":1}（顶点索引：权重）'; add_child(help)
	host.button(self,'应用布料参数并重置',apply_settings)
	quality = OptionButton.new()
	for item in ['完整模拟：120 Hz / 5 次迭代','简化模拟：60 Hz / 2 次迭代','刚性回退：关闭模拟']: quality.add_item(item)
	add_child(quality)
	quality.item_selected.connect(func(index):
		if not is_instance_valid(cloth): return
		var value = cloth.settings.duplicate(true); value.lod = index; settings_edit.text = JSON.stringify(value); apply_settings())
	modes = OptionButton.new()
	for item in ['realtime','bake','replay']:
		modes.add_item({'realtime':'实时模拟','bake':'烘焙缓存','replay':'缓存回放'}[item])
		modes.set_item_metadata(modes.item_count-1,item)
	add_child(modes); modes.item_selected.connect(change_mode)
	host.button(self,'播放 / 暂停布料动画',func():
		if is_instance_valid(runner): runner.playing = not runner.playing)
	host.button(self,'平移 2 米 / 重置模拟',func():
		if is_instance_valid(built): built.position.x += 2)
	destination = host.line(self,'布料新版本路径（.tscn）')
	host.button(self,'将布料和缓存保存为新版本',save)
	message = Label.new(); message.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART; add_child(message)
	var preview = TextureRect.new(); preview.custom_minimum_size = Vector2(400,360); preview.expand_mode = TextureRect.EXPAND_IGNORE_SIZE; preview.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED; preview.texture = host.viewport.get_texture(); add_child(preview)
static func assemble(config: Dictionary, current: Node3D = null) -> Dictionary:
	for key in ['scene','binding','family']:
		if not config.get(key) is String: return {'error':'缺少配置字段：'+key}
	var loaded = I.load_scene(config.scene) if current==null else {'scene':current}
	if loaded.has('error'): return loaded
	var scene = loaded.scene
	var old = scene.get_node_or_null('ClothSolver')
	if old:
		var problem = binding_error(old.binding)
		if problem: scene.free(); return {'error':problem}
		if Solver.binding_digest(old.binding)!=old.binding.get('binding_revision'): scene.free(); return {'error':'已保存的布料绑定内容已变化'}
		return {'scene':scene,'cloth':old,'runner':scene.get_node_or_null('LayeringPlayer')}
	var binding = JSON.parse_string(FileAccess.get_file_as_string(config.binding))
	var binding_problem = binding_error(binding)
	if binding_problem: scene.free(); return {'error':binding_problem}
	if FileAccess.get_sha256(binding.get('source',''))!=binding.get('source_sha256'): scene.free(); return {'error':'原始布料资源不存在或已变化'}
	# Absolute local source path belongs only to the private preparation/configuration.
	# Saved scenes retain the source SHA and self-contained derived data.
	var generator_revision = binding.binding_revision
	binding.erase('source')
	var profile = I.extract(scene,config.family,{'sha256':FileAccess.get_sha256(config.scene),'version':'cloth-target-v1','authority':'local-authorized'})
	if profile.has('error'): scene.free(); return profile
	var shape = scene.get_meta('character_dna',{}).get('body',scene.get_meta('garment',{}).get('body_shape',{}))
	if not shape.is_empty():
		var shape_error = G.shape_error(shape)
		if shape_error: scene.free(); return {'error':shape_error}
		var globals = I.globals(profile.profile)
		var hip = globals[int(profile.profile.mapping.hips)].origin.y
		var chest = globals[int(profile.profile.mapping.get('chest',profile.profile.mapping.hips))].origin.y
		for key in ['proxy','vertices']:
			for i in binding[key].size():
				var p = binding[key][i]; var v = G.shaped(Vector3(p[0],p[1],p[2]),shape,hip,chest)
				binding[key][i] = [v.x,v.y,v.z]
		for i in binding.vertices.size():
			var blended = Vector3.ZERO
			for k in 4:
				var p = binding.proxy[int(binding.mapping[i][k])]; blended += Vector3(p[0],p[1],p[2])*float(binding.weights[i][k])
			var v = binding.vertices[i]; var offset = Vector3(v[0],v[1],v[2])-blended
			binding.offsets[i] = [offset.x,offset.y,offset.z]
		binding['body_shape'] = shape
	binding.binding_revision = Solver.binding_digest(binding)
	var garment = scene.get_node_or_null('Garment')
	if binding.kind=='skirt' and garment==null: scene.free(); return {'error':'裙装组装需要已审核的原始服装和腰部分区'}
	if garment and binding.kind=='skirt':
		var manifest = scene.get_meta('garment',{})
		if not manifest.has('partitions') or not manifest.partitions.has('cloth'): scene.free(); return {'error':'裙装需要已审核的服装分区'}
		if manifest.get('garment',{}).get('source_sha256')!=binding.source_sha256 or manifest.garment.get('kind')!='skirt': scene.free(); return {'error':'布料源资源必须与保留的腰部资源及版本一致'}
		if I.revision(manifest)!=manifest.get('revision'): scene.free(); return {'error':'已审核的服装清单已变化'}
		var boundary = manifest.garment.get('cloth_start_y',I.decode(profile.profile.bones[int(profile.profile.mapping.hips)].global_rest).origin.y)
		if not (binding.get('cloth_top') is int or binding.get('cloth_top') is float) or not is_equal_approx(float(binding.cloth_top),float(boundary)):
			scene.free(); return {'error':'布料顶部必须与人工划定的腰部分区一致，请一并重新拟合'}
		var vertex_count = 0
		for surface in garment.mesh.get_surface_count(): vertex_count += garment.mesh.surface_get_arrays(surface)[Mesh.ARRAY_VERTEX].size()
		if manifest.get('vertices')!=vertex_count or not manifest.partitions.cloth is Array: scene.free(); return {'error':'服装分区顶点数量已变化'}
		for vertex in manifest.partitions.cloth:
			if not (vertex is int or vertex is float) or int(vertex)!=vertex or vertex<0 or vertex>=vertex_count: scene.free(); return {'error':'服装布料分区索引无效'}
		var cloth_flags = PackedByteArray(); cloth_flags.resize(int(manifest.vertices))
		for vertex in manifest.partitions.cloth: cloth_flags[int(vertex)] = 1
		var retained = ArrayMesh.new(); var offset = 0
		for surface in garment.mesh.get_surface_count():
			var arrays = garment.mesh.surface_get_arrays(surface)
			var indices = arrays[Mesh.ARRAY_INDEX]; var kept = PackedInt32Array()
			for triangle in range(0,indices.size(),3):
				if cloth_flags[offset+indices[triangle]]==0 or cloth_flags[offset+indices[triangle+1]]==0 or cloth_flags[offset+indices[triangle+2]]==0:
					kept.append_array(PackedInt32Array([indices[triangle],indices[triangle+1],indices[triangle+2]]))
			offset += arrays[Mesh.ARRAY_VERTEX].size()
			if kept.is_empty(): continue
			arrays[Mesh.ARRAY_INDEX] = kept; retained.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES,arrays)
			retained.surface_set_material(retained.get_surface_count()-1,garment.mesh.surface_get_material(surface))
		garment.mesh = retained
		garment.set_meta('cloth_partition_preservation',{'method':'Original non-cloth triangles and skin preserved; cloth partition replaced','manifest_revision':manifest.revision,'source_sha256':binding.source_sha256,'input_scene_sha256':FileAccess.get_sha256(config.scene),'retained_triangles':retained.get_faces().size()/3})
	var runner = scene.get_node_or_null('LayeringPlayer')
	var sk = I.skeleton(scene)
	if runner==null:
		var players = scene.find_children('*','AnimationPlayer',true,false)
		if players.is_empty(): scene.free(); return {'error':'目标角色需要包含实际动画'}
		var player = players[0]
		var names = player.get_animation_list()
		var selected = ''
		for candidate in names:
			if candidate!='RESET': selected = candidate; break
		if player.has_animation('squat'): selected = 'squat'
		if selected.is_empty(): scene.free(); return {'error':'目标角色没有可播放的动画'}
		runner = preload('res://addons/ainative/layering_player.gd').new(); runner.name = 'LayeringPlayer'; scene.add_child(runner)
		runner.config = {'skeleton_revision':L.signature(sk),'layers':[],'fingers':{}}
		runner.skeleton_path = runner.get_path_to(sk); runner.player_path = runner.get_path_to(player); runner.animation_name = selected
	var cloth = Solver.new(); cloth.name = 'ClothSolver'; cloth.binding = binding; cloth.profile = profile.profile
	cloth.identity = {'input_animation_scene_sha256':FileAccess.get_sha256(config.scene),'prepared_binding_revision':generator_revision,'target_family':config.family,'body_shape':scene.get_meta('garment',{}).get('body_shape',{}),'dna_at_bind':I.revision(scene.get_meta('character_dna',{}))}
	scene.add_child(cloth); cloth.skeleton_path = cloth.get_path_to(sk); cloth.layering_path = cloth.get_path_to(runner)
	return {'scene':scene,'cloth':cloth,'runner':runner}
func build():
	bake_generation += 1
	if not FileAccess.file_exists(configuration.text): message.text = '配置文件不存在，原实例已保留'; return
	var config = JSON.parse_string(FileAccess.get_file_as_string(configuration.text).trim_prefix('\ufeff'))
	if not config is Dictionary: message.text = '配置无效，原实例已保留'; return
	var candidate = assemble(config)
	if candidate.has('error'): message.text = candidate.error; return
	# Validate inside tree before replacing last valid instance.
	host.preview_root.add_child(candidate.scene)
	var error = candidate.cloth.initialize()
	if error: candidate.scene.queue_free(); message.text = error; return
	if is_instance_valid(host.preview_scene): host.preview_scene.queue_free()
	host.preview_token = ''; host.confirmation = {}; host.preview_resource = null
	built = candidate.scene; cloth = candidate.cloth; runner = candidate.runner; host.preview_scene = built
	host.mesh_container.show(); host.frame_mesh(); message.text = '布料已组装。LOD 0 为完整模拟，LOD 1 减少计算步数，LOD 2 为刚性回退。'
	settings_edit.text = JSON.stringify(cloth.settings); quality.select(int(cloth.settings.lod)); modes.select(['realtime','bake','replay'].find(cloth.mode))
func _process(_delta):
	if is_instance_valid(cloth) and cloth.result.has('error'): message.text = cloth.result.error
func apply_settings():
	bake_generation += 1
	if not is_instance_valid(cloth): return
	var value = JSON.parse_string(settings_edit.text)
	if not value is Dictionary: message.text = '参数必须为 JSON 对象'; return
	var old = cloth.settings.duplicate(true); var old_mode = cloth.mode; cloth.settings = value; cloth.mode = 'realtime'
	var error = cloth.initialize()
	if error: cloth.settings = old; cloth.mode = old_mode; cloth.initialize(); message.text = error; return
	cloth.cache = {}; modes.select(0); message.text = '参数已应用，旧缓存已失效，实时模拟已重置。'
func change_mode(index):
	bake_generation += 1
	if not is_instance_valid(cloth): return
	if index==2 and cloth.cache.get('key')!=cloth.expected_key: message.text = '请先按当前配置烘焙布料'; return
	cloth.mode = str(modes.get_item_metadata(index))
	if index==1:
		var generation = bake_generation
		var baking_cloth = cloth; var baking_runner = runner
		cloth.cache = {}; runner.playing = false; cloth.last_time = -1
		var player = runner.get_node(runner.player_path) as AnimationPlayer
		var frames = ceili(player.get_animation(runner.animation_name).length*60)
		for frame in frames:
			if generation!=bake_generation or not is_instance_valid(baking_cloth) or cloth!=baking_cloth or runner!=baking_runner: return
			runner.sample(frame/60.0)
			if cloth.result.has('error'): message.text = cloth.result.error; return
			message.text = '正在烘焙 '+str(frame+1)+' / '+str(frames)
			await get_tree().process_frame
		if generation!=bake_generation or not is_instance_valid(baking_cloth) or cloth!=baking_cloth: return
		cloth.mode = 'replay'; modes.select(2); runner.playing = true
	message.text = {'realtime':'实时模拟已启用','bake':'正在烘焙缓存','replay':'缓存回放已启用'}[cloth.mode]
func save():
	if not is_instance_valid(built): return
	if FileAccess.file_exists(destination.text) or destination.text.get_extension()!='tscn': message.text = '请选择新的 .tscn 路径，源资源和已有版本将保留'; return
	preload('res://addons/ainative/rigging.gd').owners(built,built)
	# Dynamic render node is rebuilt from immutable binding on reopen.
	cloth.visual.owner = null
	var packed = PackedScene.new(); var error = packed.pack(built)
	var staged = host.state_dir.path_join('cloth-stage-'+str(Time.get_ticks_usec())+'.tscn')
	if error==OK: error = ResourceSaver.save(packed,staged)
	if error!=OK: message.text = '暂存失败，当前实例已保留'; return
	var output = []
	var code = OS.execute(host.python_edit.text,[host.host_edit.text.get_base_dir().path_join('interop_publish.py'),staged,ProjectSettings.globalize_path(destination.text)],output,true)
	message.text = '布料新版本已完整保存' if code==0 else host.diagnostic_error('保存失败',output)
