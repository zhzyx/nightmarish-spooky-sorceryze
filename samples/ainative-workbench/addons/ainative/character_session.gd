@tool
extends Node
# One transactional owner for the integrated character. Local recipe paths are
# deliberately kept outside the portable scene, in the user's private recipe.
const I = preload('res://addons/ainative/interop.gd')
const C = preload('res://addons/ainative/customization.gd')
const H = preload('res://addons/ainative/hair.gd')
const L = preload('res://addons/ainative/layering.gd')
const Cloth = preload('res://addons/ainative/cloth_panel.gd')
var live: Node3D
var recipe: Dictionary = {}
var generation = 0
var clock_seconds = 0.0
var playing = false
var stage: Node3D
var frame_usec = 0
var expression_frames: Array = []
var evaluation_count = 0
var baking = false
var bake_epoch = 0
var last_expression_frame_index = -1
signal changed

func rebuild(value: Dictionary, expected: int = -1) -> String:
	if expected!=-1 and expected!=generation: return 'Character changed; retry the operation.'
	for key in ['body','face','garment','hair','cloth','layers','cloth_settings']:
		if value.has(key) and not value[key] is Dictionary: return 'Invalid character option: '+key
	if value.has('face_layers') and not value.face_layers is Array: return 'Invalid expression layers.'
	for key in ['binding','motion','expression','layer_template']:
		if value.has(key) and not value[key] is String: return 'Invalid source locator: '+key
	if not value.get('garment',{}).is_empty():
		if not value.garment.get('path') is String or not value.garment.get('spec') is Dictionary: return 'Choose a verified clothing source.'
	if value.has('hair_display'):
		var display = value.hair_display
		if not display is Dictionary or display.get('lod') not in [0,1,2] or not display.get('cards') is bool or not display.get('hat') is bool: return 'Invalid hair display option.'
	if not value.get('base') is String or not value.get('source_sha256') is String: return 'Select a verified character.'
	if FileAccess.get_sha256(value.base)!=value.source_sha256: return 'Character source changed; previous character retained.'
	var loaded = I.load_scene(value.base)
	if loaded.has('error'): return loaded.error
	var candidate = loaded.scene
	if candidate.has_node('BodyMotion') or candidate.has_node('LayeringPlayer') or candidate.has_node('Garment'):
		candidate.free()
		return 'Choose an immutable base character, not a fitted or animated version.'
	if not candidate.has_meta('face_binding'):
		var binding = read_object(value.get('binding',''))
		if binding.get('asset_sha256')!=value.source_sha256: candidate.free(); return 'Face source does not match.'
		candidate.set_meta('face_binding',binding)
	var binding = candidate.get_meta('face_binding',{})
	var dna = C.dna(binding.get('source_sha256',''),value.get('body',{}),value.get('face',{}),binding.get('mapping_version',''))
	var applied = C.apply_face(candidate,dna,value.get('face_layers',[]))
	if applied.has('error'): candidate.free(); return applied.error
	var profile = I.extract(candidate,'anatomical',{'sha256':value.source_sha256,'version':'integrated-v1','authority':binding.get('source_url','')},binding.get('body_mapping',{}))
	if profile.has('error'): candidate.free(); return profile.error
	if value.get('garment',{})!={}:
		var item = value.garment
		var fitted = C.refit(candidate,profile.profile,dna,item.path,item.spec)
		candidate.free()
		if fitted.has('error'): return fitted.error
		candidate = fitted.scene
		applied = C.apply_face(candidate,dna,value.get('face_layers',[]))
		if applied.has('error'): candidate.free(); return applied.error
	if value.get('motion','')!='':
		var error = attach_motion(candidate,value.motion,profile.profile,value.get('layers',{}))
		if error: candidate.free(); return error
	if value.get('layer_template','')!='':
		var template = I.load_scene(value.layer_template)
		if template.has('error'): candidate.free(); return template.error
		var original = template.scene.get_node_or_null('LayeringPlayer')
		var runner = candidate.get_node_or_null('LayeringPlayer')
		if original==null or runner==null: template.scene.free(); candidate.free(); return 'Layer template requires a body animation.'
		runner.config = original.config.duplicate(true)
		runner.config.skeleton_revision = L.signature(I.skeleton(candidate))
		runner.clips = original.clips.duplicate(true)
		var weapon = template.scene.get_node_or_null(original.weapon_path)
		# weapon_path is relative to the controller, not the scene root.
		weapon = original.get_node_or_null(original.weapon_path)
		if weapon:
			var copied = weapon.duplicate()
			candidate.add_child(copied)
			runner.weapon_path = runner.get_path_to(copied)
		template.scene.free()
		var error = L.validate(I.skeleton(candidate),runner.config)
		if error: candidate.free(); return error
	var next_frames: Array = []
	if value.get('expression','')!='':
		var document = read_object(value.expression)
		next_frames = document.get('streams',{}).get('face',{}).get('frames',[])
		if next_frames.is_empty(): candidate.free(); return 'No detected face frames.'
		var error = validate_expression(next_frames)
		if error: candidate.free(); return error
	if value.get('hair',{})!={}:
		var bound = H.bind(candidate,value.hair)
		if bound.has('error'): candidate.free(); return bound.error
	if value.get('cloth',{})!={}:
		var config = value.cloth.duplicate(true)
		config.scene = value.base
		var assembled = Cloth.assemble(config,candidate)
		if assembled.has('error'): return assembled.error
		candidate = assembled.scene
	stage.add_child(candidate)
	if candidate.has_node('IndependentHair'):
		var display = value.get('hair_display',{'lod':0,'cards':true,'hat':false})
		candidate.get_node('IndependentHair').configure(display.lod,display.cards,display.hat)
	if candidate.has_node('ClothSolver') and value.has('cloth_settings'):
		candidate.get_node('ClothSolver').settings = value.cloth_settings.duplicate(true)
	var error = activate(candidate)
	if error: candidate.free(); return error
	if expected!=-1 and expected!=generation: candidate.free(); return 'A newer character is active.'
	var previous = live
	live = candidate
	recipe = value.duplicate(true)
	expression_frames = next_frames
	live.set_meta('session_expression_frames',next_frames)
	generation += 1
	cancel_bake()
	live.set_meta('character_session',{'schema':1,'source_sha256':value.source_sha256,'generation':generation,'clock_seconds':clock_seconds})
	if is_instance_valid(previous): previous.free()
	evaluate(0.0)
	changed.emit()
	return ''

static func read_object(path: String) -> Dictionary:
	if not FileAccess.file_exists(path): return {}
	var value = JSON.parse_string(FileAccess.get_file_as_string(path).trim_prefix('\ufeff'))
	return value if value is Dictionary else {}

func attach_motion(candidate: Node3D, path: String, profile: Dictionary, layers: Dictionary) -> String:
	var loaded = I.load_scene(path)
	if loaded.has('error'): return loaded.error
	var source = loaded.scene
	var from_profile = source.get_meta('motion_target_profile',{})
	var error = I.validate(from_profile)
	if error: source.free(); return error
	var library = AnimationLibrary.new()
	var sk = I.skeleton(candidate)
	for original in source.find_children('*','AnimationPlayer',true,false):
		for clip_name in original.get_animation_list():
			if clip_name=='RESET': continue
			var converted = I.retarget(original.get_animation(clip_name),from_profile,profile)
			if converted.has('error'): source.free(); return converted.error
			for track in converted.animation.get_track_count():
				converted.animation.track_set_path(track,NodePath(str(candidate.get_path_to(sk))+':'+str(converted.animation.track_get_path(track).get_subname(0))))
			library.add_animation(clip_name.replace('/','_'),converted.animation)
	source.free()
	if library.get_animation_list().is_empty(): return 'No playable animation in this source.'
	var player = AnimationPlayer.new()
	player.name = 'BodyMotion'
	player.add_animation_library('',library)
	candidate.add_child(player)
	var runner = preload('res://addons/ainative/layering_player.gd').new()
	runner.name = 'LayeringPlayer'
	candidate.add_child(runner)
	runner.skeleton_path = runner.get_path_to(sk)
	runner.player_path = runner.get_path_to(player)
	runner.animation_name = library.get_animation_list()[0]
	runner.config = layers.duplicate(true) if not layers.is_empty() else {'layers':[],'fingers':{}}
	runner.config.skeleton_revision = L.signature(sk)
	candidate.set_meta('body_motion_source',{'sha256':FileAccess.get_sha256(path),'profile_revision':from_profile.revision})
	return L.validate(sk,runner.config)

func activate(candidate: Node3D) -> String:
	var runner = candidate.get_node_or_null('LayeringPlayer')
	if runner:
		runner.set_process(false)
		runner.playing = false
		runner.sample(clock_seconds)
		if runner.result.has('error'): return runner.result.error
	var cloth = candidate.get_node_or_null('ClothSolver')
	if cloth:
		if runner.pose_evaluated.is_connected(cloth.consume): runner.pose_evaluated.disconnect(cloth.consume)
		var error = cloth.initialize()
		if error: return error
		cloth.consume(runner.result)
		if cloth.result.has('error'): return cloth.result.error
	var hair = candidate.get_node_or_null('IndependentHair')
	if hair:
		hair.set_process(false)
		var error = H.runtime_error(candidate,hair.get_meta('hair_data',{}),hair.get_meta('authored_scalp_cap',{}))
		if error: return error
	return ''

func cancel_bake():
	bake_epoch += 1

func seek(time: float):
	if not is_finite(time): return
	cancel_bake()
	clock_seconds = time
	evaluate(0.0)

func finish_bake(work: Node):
	if is_instance_valid(work.live): work.live.free()
	work.free()
	baking = false

func bake_cloth() -> String:
	if baking: return 'A cloth bake is already running.'
	if not is_instance_valid(live): return 'Choose a character first.'
	var cloth = live.get_node_or_null('ClothSolver')
	var runner = live.get_node_or_null('LayeringPlayer')
	if cloth==null or runner==null: return 'Enable cloth on an animated character first.'
	baking = true
	bake_epoch += 1
	var ticket = bake_epoch
	var expected = generation
	# The valid live cache, clock and playback stay untouched until commit.
	var work = get_script().new()
	work.stage = stage
	work.recipe = recipe.duplicate(true)
	work.expression_frames = expression_frames.duplicate(true)
	add_child(work)
	work.live = live.duplicate(14)
	work.live.visible = false
	stage.add_child(work.live)
	var error = work.activate(work.live)
	if error: finish_bake(work); return error
	var work_cloth = work.live.get_node('ClothSolver')
	var player = runner.get_node(runner.player_path)
	var count = ceili(player.get_animation(runner.animation_name).length*60)
	work_cloth.mode = 'bake'
	work_cloth.cache = {}
	work_cloth.last_time = -1
	for frame in count:
		if generation!=expected or ticket!=bake_epoch or not is_instance_valid(cloth):
			finish_bake(work)
			return 'Character changed; old bake discarded.'
		work.clock_seconds = frame/60.0
		work.evaluate(1.0/60.0)
		if work_cloth.result.has('error'):
			var problem = work_cloth.result.error
			finish_bake(work)
			return problem
		await get_tree().process_frame
	if generation!=expected or ticket!=bake_epoch or not is_instance_valid(cloth) or cloth.expected_key!=work_cloth.expected_key:
		finish_bake(work)
		return 'Character changed; old bake discarded.'
	cloth.cache = work_cloth.cache.duplicate(true)
	cloth.mode = 'replay'
	finish_bake(work)
	evaluate(0.0)
	return ''

func _process(delta):
	if playing: clock_seconds += delta; evaluate(delta)

func evaluate(delta: float):
	if not is_instance_valid(live): return
	evaluation_count += 1
	var start = Time.get_ticks_usec()
	var runner = live.get_node_or_null('LayeringPlayer')
	if runner: runner.sample(clock_seconds)
	I.skeleton(live).force_update_all_bone_transforms()
	# Static DNA/scalp revisions were validated once at commit. Expression frames
	# only change mapped morph values, never refit geometry or rebind hair.
	if not expression_frames.is_empty():
		last_expression_frame_index = expression_index(clock_seconds)
		var expression = C.mediapipe_layer(expression_frames[last_expression_frame_index])
		var layers = recipe.get('face_layers',[]).duplicate(true)
		layers.append(expression)
		var mixed = C.arbitrate(layers)
		var binding = live.get_meta('face_binding')
		var dna = live.get_meta('character_dna')
		var scalp = live.get_meta('scalp_binding').duplicate(true)
		scalp.pose_revision = I.revision({'rest_revision':scalp.revision,'channels':mixed.channels})
		live.set_meta('scalp_binding',scalp)
		for mesh in live.find_children('*','MeshInstance3D',true,false):
			for i in mesh.get_blend_shape_count():
				var morph = str(mesh.mesh.get_blend_shape_name(i))
				for channel in C.CHANNELS:
					if binding.morphs.get(channel)==morph: mesh.set_blend_shape_value(i,mixed.channels.get(channel,0.0))
				for correction in binding.get('correctives',[]):
					if correction.morph==morph: mesh.set_blend_shape_value(i,dna.face.get(correction.parameter,0.0)*mixed.channels.get(correction.channel,0.0))
	var cloth = live.get_node_or_null('ClothSolver')
	if cloth and runner: cloth.consume(runner.result)
	var hair = live.get_node_or_null('IndependentHair')
	if hair: hair._process(delta)
	frame_usec = Time.get_ticks_usec()-start

static func validate_expression(frames: Array) -> String:
	var previous = -1.0
	for frame in frames:
		if not frame is Dictionary: return 'Invalid face frame.'
		var timestamp = frame.get('timestamp_ms')
		if not (timestamp is int or timestamp is float) or not is_finite(timestamp) or timestamp<0 or timestamp<=previous: return 'Face timestamps must be finite and strictly increasing.'
		if C.mediapipe_layer(frame).has('error'): return 'Missing or invalid face detection; source retained.'
		previous = timestamp
	return ''

func expression_index(time: float) -> int:
	# Decoded video PTS, sample-and-hold between observations. Before/after the
	# capture use its first/last valid frame; never invent a frame rate or loop.
	var low = 0
	var high = expression_frames.size()
	while low<high:
		var middle = (low+high)/2
		if expression_frames[middle].timestamp_ms<=time*1000.0: low = middle+1
		else: high = middle
	return maxi(0,low-1)

func save_version(path: String, python: String, publisher: String) -> String:
	if not is_instance_valid(live): return 'Choose a character first.'
	if recipe.get('read_only',false): return 'Original local sources are required to save edited versions.'
	if FileAccess.file_exists(path) or path.get_extension()!='tscn': return 'Choose a new version filename.'
	live.set_meta('character_session',{'schema':1,'source_sha256':recipe.source_sha256,'generation':generation,'clock_seconds':clock_seconds})
	live.set_meta('character_editing_state',portable_recipe(recipe))
	var temporary = ProjectSettings.globalize_path('user://character-'+str(Time.get_ticks_usec())+'.tscn')
	var cloth = live.get_node_or_null('ClothSolver')
	preload('res://addons/ainative/rigging.gd').owners(live,live)
	if cloth and is_instance_valid(cloth.visual): cloth.visual.owner = null
	var hair = live.get_node_or_null('IndependentHair')
	var hair_data = {}
	if hair:
		hair_data = hair.get_meta('hair_data')
		var error = H.runtime_error(live,hair_data,hair.get_meta('authored_scalp_cap'))
		if error: return error
		var portable = hair_data.duplicate(true)
		portable.spec.erase('path')
		portable.spec.erase('mesh_path')
		hair.set_meta('hair_data',portable)
		for child in hair.get_children(): clear_owners(child)
	var packed = PackedScene.new()
	var code_pack = packed.pack(live)
	if hair: hair.set_meta('hair_data',hair_data)
	if code_pack!=OK or ResourceSaver.save(packed,temporary)!=OK: return 'Could not encode character.'
	var output = []
	var code = OS.execute(python,[publisher,temporary,ProjectSettings.globalize_path(path)],output,true)
	if code==0:
		var local = FileAccess.open(recipe_path(FileAccess.get_sha256(path)),FileAccess.WRITE)
		if local==null: return 'Character saved; local editing recipe could not be recorded.'
		local.store_string(JSON.stringify(recipe))
		local.close()
	return '' if code==0 else 'Could not publish; current character retained.'

static func clear_owners(node: Node):
	node.owner = null
	for child in node.get_children(): clear_owners(child)

static func portable_recipe(value):
	if value is Dictionary:
		var output = {}
		for key in value:
			if key in ['base','binding','motion','expression','layer_template','path','mesh_path']:
				if value[key] is String and FileAccess.file_exists(value[key]): output[key+'_sha256'] = FileAccess.get_sha256(value[key])
			else: output[key] = portable_recipe(value[key])
		return output
	if value is Array:
		var output = []
		for item in value: output.append(portable_recipe(item))
		return output
	return value

func reopen(path: String, local_recipe: Dictionary) -> String:
	# The saved version's private editing recipe wins over the current UI state.
	# It is keyed by the actual published bytes and never embedded as local paths.
	local_recipe = read_object(recipe_path(FileAccess.get_sha256(path)))
	if not local_recipe.is_empty() and FileAccess.get_sha256(local_recipe.get('base',''))!=local_recipe.get('source_sha256'): return 'Original character source changed.'
	var loaded = I.load_scene(path)
	if loaded.has('error'): return loaded.error
	var candidate = loaded.scene
	var metadata = candidate.get_meta('character_session',{})
	if metadata.get('schema')!=1: candidate.free(); return 'Not a complete character version.'
	var saved_expression = candidate.get_meta('session_expression_frames',[])
	if not saved_expression is Array: candidate.free(); return 'Invalid saved expression stream.'
	var expression_error = validate_expression(saved_expression)
	if expression_error: candidate.free(); return expression_error
	if not local_recipe.is_empty() and metadata.get('source_sha256')!=local_recipe.get('source_sha256'): candidate.free(); return 'Version belongs to another character.'
	if local_recipe.is_empty():
		local_recipe = {'source_sha256':metadata.source_sha256,'face_layers':candidate.get_meta('face_layers',[]),'read_only':true}
	stage.add_child(candidate)
	var error = activate(candidate)
	if error: candidate.free(); return error
	var previous = live
	live = candidate
	recipe = local_recipe.duplicate(true)
	expression_frames = candidate.get_meta('session_expression_frames',[])
	clock_seconds = metadata.get('clock_seconds',0.0)
	generation += 1
	cancel_bake()
	if is_instance_valid(previous): previous.free()
	evaluate(0.0)
	changed.emit()
	return ''

static func recipe_path(sha: String) -> String:
	var directory = ProjectSettings.globalize_path('user://character-recipes')
	DirAccess.make_dir_recursive_absolute(directory)
	return directory.path_join(sha+'.json')

func export_version(publication: String, target: Dictionary, destination: String, python: String, publisher: String) -> String:
	if not FileAccess.file_exists(publication): return 'Save a complete character version first.'
	if FileAccess.file_exists(destination) or FileAccess.file_exists(destination+'.report.json') or destination.get_extension()!='glb': return 'Choose a new .glb filename.'
	var sha = FileAccess.get_sha256(publication)
	var isolated = get_script().new()
	isolated.stage = stage
	add_child(isolated)
	var error = isolated.reopen(publication,{})
	if error: isolated.free(); return error
	var runner = isolated.live.get_node_or_null('LayeringPlayer')
	if runner==null: isolated.live.free(); isolated.free(); return 'Saved character needs body animation.'
	var player = runner.get_node(runner.player_path)
	var baked = isolated.bake_body(player.get_animation(runner.animation_name).length)
	if baked.has('error'): isolated.live.free(); isolated.free(); return baked.error
	if FileAccess.get_sha256(publication)!=sha: isolated.live.free(); isolated.free(); return 'Published source changed during sampling.'
	baked.animation.set_meta('character_publication_sha256',sha)
	var binding = isolated.live.get_meta('face_binding')
	var profile = I.extract(isolated.live,'anatomical',{'sha256':sha,'version':'published-character','authority':'local-authorized'},binding.body_mapping)
	if profile.has('error'): isolated.live.free(); isolated.free(); return profile.error
	var projected = preload('res://addons/ainative/character_export.gd').project(publication,sha,profile.profile,target,baked.animation)
	isolated.live.free()
	isolated.free()
	if projected.has('error'): return projected.error
	projected.report['sampling'] = {'fps':baked.fps,'length_seconds':baked.length,'evaluation':baked.evaluation,'source_publication_sha256':sha}
	var staged = ProjectSettings.globalize_path('user://character-export-'+str(Time.get_ticks_usec())+'.glb')
	error = I.stage_glb(projected.scene,staged)
	projected.scene.free()
	if error: return error
	var report_staged = staged+'.report.json'
	var report_file = FileAccess.open(report_staged,FileAccess.WRITE)
	if report_file==null: return 'Could not stage the compatibility report.'
	report_file.store_string(JSON.stringify(projected.report,'\t'))
	report_file.close()
	var output = []
	var pair_publisher = publisher.get_base_dir().path_join('character_publish.py')
	if OS.execute(python,[pair_publisher,staged,report_staged,ProjectSettings.globalize_path(destination)],output,true)!=0: return 'Could not publish compatibility copy and report.'
	return ''

func bake_body(length: float, fps: int = 30) -> Dictionary:
	if not is_instance_valid(live) or length<=0 or fps<1: return {'error':'Choose an animated character.'}
	var isolated = live.duplicate(14)
	stage.add_child(isolated)
	var error = activate(isolated)
	if error: isolated.free(); return {'error':error}
	var runner = isolated.get_node_or_null('LayeringPlayer')
	if runner==null: isolated.free(); return {'error':'Body animation is required.'}
	var skeleton = I.skeleton(isolated)
	var clip = Animation.new()
	clip.length = length
	for bone in skeleton.get_bone_count():
		for type in [Animation.TYPE_POSITION_3D,Animation.TYPE_ROTATION_3D,Animation.TYPE_SCALE_3D]:
			var track = clip.add_track(type)
			clip.track_set_path(track,NodePath('Skeleton3D:'+str(skeleton.get_bone_name(bone))))
	for frame in ceili(length*fps)+1:
		var time = minf(frame/float(fps),length)
		runner.sample(time)
		if runner.result.has('error'): isolated.free(); return runner.result
		for bone in skeleton.get_bone_count():
			var pose = skeleton.get_bone_pose(bone)
			clip.position_track_insert_key(bone*3,time,pose.origin)
			clip.rotation_track_insert_key(bone*3+1,time,pose.basis.get_rotation_quaternion())
			clip.scale_track_insert_key(bone*3+2,time,pose.basis.get_scale())
	isolated.free()
	return {'animation':clip,'fps':fps,'length':length,'evaluation':'body > layers > equipment IK > final bone poses'}
