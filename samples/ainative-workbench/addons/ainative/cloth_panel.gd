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
	if not binding is Dictionary or binding.get('schema')!=1 or binding.get('kind') not in ['cape','skirt']: return 'Invalid cloth binding schema/kind'
	for key in ['vertices','indices','proxy','edges','mapping','weights','offsets','pins']:
		if not binding.get(key) is Array or binding[key].is_empty(): return 'Missing binding array: '+key
	var n = binding.proxy.size(); var r = binding.vertices.size()
	if binding.pins.size()!=n or binding.mapping.size()!=r or binding.weights.size()!=r or binding.offsets.size()!=r or binding.indices.size()%3!=0: return 'Inconsistent binding sizes'
	for key in ['vertices','proxy','offsets']:
		for point in binding[key]:
			if not point is Array or point.size()!=3: return 'Binding point must have 3 coordinates'
			for coordinate in point:
				if not (coordinate is int or coordinate is float) or not is_finite(coordinate): return 'Nonfinite binding point'
	for index in binding.indices:
		if not (index is int or index is float) or int(index)!=index or index<0 or index>=r: return 'Invalid render index'
	for edge in binding.edges:
		if not edge is Array or edge.size()!=2: return 'Invalid solver edge'
		for index in edge:
			if not (index is int or index is float) or int(index)!=index or index<0 or index>=n: return 'Invalid solver index'
	for i in r:
		if not binding.mapping[i] is Array or not binding.weights[i] is Array or binding.mapping[i].size()!=4 or binding.weights[i].size()!=4: return 'Four mapping weights required'
		var total = 0.0
		for k in 4:
			var index = binding.mapping[i][k]; var weight = binding.weights[i][k]
			if not (index is int or index is float) or int(index)!=index or index<0 or index>=n: return 'Invalid mapped particle'
			if not (weight is int or weight is float) or not is_finite(weight) or weight<0 or weight>1: return 'Invalid render binding weight'
			total += weight
		if absf(total-1)>.00001: return 'Render weights must sum to one'
	for pin in binding.pins:
		if not (pin is int or pin is float) or not is_finite(pin) or pin<0 or pin>1: return 'Invalid authored pin weight'
	return ''
func initialize(workbench):
	host = workbench; name = 'ClothPanel'
	var title = Label.new(); title.text = 'Cloth • separate simulation / render binding • world-space XPBD'; add_child(title)
	configuration = host.line(self,'Cloth scene + immutable binding configuration JSON')
	host.button(self,'Assemble / reopen cloth',build)
	settings_edit = TextEdit.new(); settings_edit.custom_minimum_size.y = 65; settings_edit.text = '{"mass":0.15,"compliance":0.000001,"pin_weight":1.0,"lod":0}'; add_child(settings_edit)
	var help = Label.new(); help.text = 'mass 0.01–10; compliance 0–0.01; pin_weight 0.5–1; pin_overrides: {"top vertex index":0–1}'; add_child(help)
	host.button(self,'Apply cloth parameters / reset',apply_settings)
	quality = OptionButton.new()
	for item in ['Full simulation: 120Hz / 5 iterations','Reduced simulation: 60Hz / 2 iterations','Rigid fallback: simulation disabled']: quality.add_item(item)
	add_child(quality)
	quality.item_selected.connect(func(index):
		if not is_instance_valid(cloth): return
		var value = cloth.settings.duplicate(true); value.lod = index; settings_edit.text = JSON.stringify(value); apply_settings())
	modes = OptionButton.new()
	for item in ['realtime','bake','replay']: modes.add_item(item)
	add_child(modes); modes.item_selected.connect(change_mode)
	host.button(self,'Play / pause cloth animation',func():
		if is_instance_valid(runner): runner.playing = not runner.playing)
	host.button(self,'Teleport +2m / reset',func():
		if is_instance_valid(built): built.position.x += 2)
	destination = host.line(self,'New cloth .tscn version destination')
	host.button(self,'Save cloth + cache as new version',save)
	message = Label.new(); message.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART; add_child(message)
	var preview = TextureRect.new(); preview.custom_minimum_size = Vector2(400,360); preview.expand_mode = TextureRect.EXPAND_IGNORE_SIZE; preview.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED; preview.texture = host.viewport.get_texture(); add_child(preview)
static func assemble(config: Dictionary) -> Dictionary:
	for key in ['scene','binding','family']:
		if not config.get(key) is String: return {'error':'Missing '+key}
	var loaded = I.load_scene(config.scene)
	if loaded.has('error'): return loaded
	var scene = loaded.scene
	var old = scene.get_node_or_null('ClothSolver')
	if old:
		var problem = binding_error(old.binding)
		if problem: scene.free(); return {'error':problem}
		if Solver.binding_digest(old.binding)!=old.binding.get('binding_revision'): scene.free(); return {'error':'Saved binding content changed'}
		return {'scene':scene,'cloth':old,'runner':scene.get_node_or_null('LayeringPlayer')}
	var binding = JSON.parse_string(FileAccess.get_file_as_string(config.binding))
	var binding_problem = binding_error(binding)
	if binding_problem: scene.free(); return {'error':binding_problem}
	if FileAccess.get_sha256(binding.get('source',''))!=binding.get('source_sha256'): scene.free(); return {'error':'Missing or changed immutable cloth source'}
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
	if binding.kind=='skirt' and garment==null: scene.free(); return {'error':'Skirt assembly requires the reviewed source garment and waist partition'}
	if garment and binding.kind=='skirt':
		var manifest = scene.get_meta('garment',{})
		if not manifest.has('partitions') or not manifest.partitions.has('cloth'): scene.free(); return {'error':'Skirt requires reviewed garment partitions'}
		if manifest.get('garment',{}).get('source_sha256')!=binding.source_sha256 or manifest.garment.get('kind')!='skirt': scene.free(); return {'error':'Cloth source must match retained waist source/version'}
		if I.revision(manifest)!=manifest.get('revision'): scene.free(); return {'error':'Reviewed garment manifest changed'}
		var vertex_count = 0
		for surface in garment.mesh.get_surface_count(): vertex_count += garment.mesh.surface_get_arrays(surface)[Mesh.ARRAY_VERTEX].size()
		if manifest.get('vertices')!=vertex_count or not manifest.partitions.cloth is Array: scene.free(); return {'error':'Garment partition vertex count changed'}
		for vertex in manifest.partitions.cloth:
			if not (vertex is int or vertex is float) or int(vertex)!=vertex or vertex<0 or vertex>=vertex_count: scene.free(); return {'error':'Invalid garment cloth partition index'}
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
		if players.is_empty(): scene.free(); return {'error':'Target needs actual animation'}
		var player = players[0]
		var names = player.get_animation_list()
		var selected = ''
		for candidate in names:
			if candidate!='RESET': selected = candidate; break
		if player.has_animation('squat'): selected = 'squat'
		if selected.is_empty(): scene.free(); return {'error':'No playable target animation'}
		runner = preload('res://addons/ainative/layering_player.gd').new(); runner.name = 'LayeringPlayer'; scene.add_child(runner)
		runner.config = {'skeleton_revision':L.signature(sk),'layers':[],'fingers':{}}
		runner.skeleton_path = runner.get_path_to(sk); runner.player_path = runner.get_path_to(player); runner.animation_name = selected
	var cloth = Solver.new(); cloth.name = 'ClothSolver'; cloth.binding = binding; cloth.profile = profile.profile
	cloth.identity = {'input_animation_scene_sha256':FileAccess.get_sha256(config.scene),'prepared_binding_revision':generator_revision,'target_family':config.family,'body_shape':scene.get_meta('garment',{}).get('body_shape',{}),'dna_at_bind':I.revision(scene.get_meta('character_dna',{}))}
	scene.add_child(cloth); cloth.skeleton_path = cloth.get_path_to(sk); cloth.layering_path = cloth.get_path_to(runner)
	return {'scene':scene,'cloth':cloth,'runner':runner}
func build():
	bake_generation += 1
	if not FileAccess.file_exists(configuration.text): message.text = 'Configuration missing; previous instance retained'; return
	var config = JSON.parse_string(FileAccess.get_file_as_string(configuration.text).trim_prefix('\ufeff'))
	if not config is Dictionary: message.text = 'Invalid configuration; previous instance retained'; return
	var candidate = assemble(config)
	if candidate.has('error'): message.text = candidate.error; return
	# Validate inside tree before replacing last valid instance.
	host.preview_root.add_child(candidate.scene)
	var error = candidate.cloth.initialize()
	if error: candidate.scene.queue_free(); message.text = error; return
	if is_instance_valid(host.preview_scene): host.preview_scene.queue_free()
	host.preview_token = ''; host.confirmation = {}; host.preview_resource = null
	built = candidate.scene; cloth = candidate.cloth; runner = candidate.runner; host.preview_scene = built
	host.mesh_container.show(); host.frame_mesh(); message.text = 'Cloth assembled; LOD 0 full, 1 fewer steps, 2 rigid fallback.'
	settings_edit.text = JSON.stringify(cloth.settings); quality.select(int(cloth.settings.lod)); modes.select(['realtime','bake','replay'].find(cloth.mode))
func _process(_delta):
	if is_instance_valid(cloth) and cloth.result.has('error'): message.text = cloth.result.error
func apply_settings():
	bake_generation += 1
	if not is_instance_valid(cloth): return
	var value = JSON.parse_string(settings_edit.text)
	if not value is Dictionary: message.text = 'Parameters must be JSON object'; return
	var old = cloth.settings.duplicate(true); var old_mode = cloth.mode; cloth.settings = value; cloth.mode = 'realtime'
	var error = cloth.initialize()
	if error: cloth.settings = old; cloth.mode = old_mode; cloth.initialize(); message.text = error; return
	cloth.cache = {}; modes.select(0); message.text = 'Parameters applied; prior cache invalidated; realtime reset.'
func change_mode(index):
	bake_generation += 1
	if not is_instance_valid(cloth): return
	if index==2 and cloth.cache.get('key')!=cloth.expected_key: message.text = 'Bake matching configuration first'; return
	cloth.mode = modes.get_item_text(index)
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
			message.text = 'Baking '+str(frame+1)+' / '+str(frames)
			await get_tree().process_frame
		if generation!=bake_generation or not is_instance_valid(baking_cloth) or cloth!=baking_cloth: return
		cloth.mode = 'replay'; modes.select(2); runner.playing = true
	message.text = cloth.mode
func save():
	if not is_instance_valid(built): return
	if FileAccess.file_exists(destination.text) or destination.text.get_extension()!='tscn': message.text = 'Choose new .tscn; source and previous versions are immutable'; return
	preload('res://addons/ainative/rigging.gd').owners(built,built)
	# Dynamic render node is rebuilt from immutable binding on reopen.
	cloth.visual.owner = null
	var packed = PackedScene.new(); var error = packed.pack(built)
	var staged = host.state_dir.path_join('cloth-stage-'+str(Time.get_ticks_usec())+'.tscn')
	if error==OK: error = ResourceSaver.save(packed,staged)
	if error!=OK: message.text = 'Stage failed; active instance retained'; return
	var output = []
	var code = OS.execute(host.python_edit.text,[host.host_edit.text.get_base_dir().path_join('interop_publish.py'),staged,ProjectSettings.globalize_path(destination.text)],output,true)
	message.text = 'Published new cloth version atomically' if code==0 else str(output)
